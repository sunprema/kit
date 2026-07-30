# Publishing from CI: `publish-on-merge.yml`

If books reach your library by **merging a PR** (the cloud-routine path, or any
contributor PR) rather than by you running `/publish-library` locally, something
has to regenerate the front door after the merge. That's this workflow — it
lives in your **books repo** at `.github/workflows/publish-on-merge.yml`, not
in the kit.

## The one thing to get right

`build-library.py` does not only write the front door. It writes generated
output **into `books/**`** as well:

| path | what breaks if it isn't committed |
|------|-----------------------------------|
| `books/*/offline.json` | the shelf's `⤓ Offline` button 404s — download fails |
| `books/*/**.html` | book pages lose the `⌂ Library` chip and their share-preview `<meta>` tags |
| `books/*/assets/img/og-share.jpg` | shared links show no preview card |

So the commit step must `git add -A`. A workflow that adds only
`index.html catalog.json assets` produces a site that **looks** fine and is
quietly broken: `catalog.json` carries each book's `offline_bytes` (computed in
memory, so the button renders with a correct-looking "0.4 MB"), while the
`offline.json` that the button actually fetches was never pushed.

This is not hypothetical — it's how `what-is-oauth`,
`jwts-promises-and-betrayals`, `entire-io`, and `zig-memory-allocators` shipped
with dead Offline buttons (and no `⌂ Library` chip, and no share previews)
while the 55 books published via `/publish-library` — which does `git add -A` —
worked.

## Loop safety — do it with a guard, not a narrow `git add`

The reason to exclude `books/**` from the commit was to stop the publish commit
from re-triggering the `paths: books/**` filter. Solve that with an explicit
guard on the run instead, so correctness doesn't depend on committing less than
the generator wrote:

```yaml
jobs:
  publish:
    # The publish commit touches books/**, so it re-matches the paths filter.
    # Skip our own commits rather than under-committing to avoid the loop.
    if: github.event.head_commit.author.name != 'bookbank-bot'
```

The regen is idempotent anyway (OG/chip injection uses idempotency markers,
`offline.json` is content-hashed), so a second pass is a no-op — the guard just
saves a wasted run.

## The workflow

```yaml
name: Publish on book merge

on:
  push:
    branches: [main]
    paths:
      - 'books/**'

concurrency:
  group: publish
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  publish:
    if: github.event.head_commit.author.name != 'bookbank-bot'
    runs-on: ubuntu-latest
    env:
      GH_TOKEN: ${{ github.token }}
    steps:
      - name: Checkout main
        uses: actions/checkout@v4
        with:
          ref: main

      # build-library.py + defaults/personas from the pinned kit plugin.
      # Bump the SHA deliberately to adopt kit's shelf/generator fixes.
      - name: Fetch bookbank plugin (pinned)
        run: |
          git clone --filter=blob:none --sparse https://github.com/sunprema/kit /tmp/kit
          git -C /tmp/kit sparse-checkout set bookbank/library bookbank/defaults
          git -C /tmp/kit checkout <KIT_SHA>

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      # Regenerate IN PLACE from the book.json's on main. --root == --out == "."
      # → same-clone, no re-sync. CLAUDE_PLUGIN_ROOT is required or persona
      # names render blank. The macOS-only `sips` share-JPEG step is skipped
      # gracefully on Ubuntu (cosmetic).
      - name: Rebuild shelf, catalog, and per-book generated files
        env:
          CLAUDE_PLUGIN_ROOT: /tmp/kit/bookbank
        run: |
          python3 /tmp/kit/bookbank/library/build-library.py \
            --out . --root . --repo "${{ github.repository }}"

      # git add -A: the generator writes into books/** too (offline.json, the
      # library chip, share-preview tags). Adding only the front door ships a
      # shelf that advertises files which were never pushed.
      - name: Commit regenerated output
        run: |
          git config user.name  "bookbank-bot"
          git config user.email "bookbank-bot@users.noreply.github.com"
          git add -A
          if git diff --cached --quiet; then
            echo "::notice::Shelf already current — nothing to publish."
            exit 0
          fi
          git commit -m "Publish: rebuild shelf after ${{ github.sha }}"
          git push origin main

      # Fail the run if a book serves but its offline manifest doesn't — the
      # exact failure this workflow used to introduce.
      - name: Verify offline manifests are live
        run: |
          sleep 45   # Pages deploy
          base="https://${GITHUB_REPOSITORY%%/*}.github.io/${GITHUB_REPOSITORY#*/}"
          fail=0
          for d in books/*/; do
            id="$(basename "$d")"
            code=$(curl -s --retry 3 --retry-all-errors -o /dev/null \
                        -w '%{http_code}' "$base/books/$id/offline.json")
            [ "$code" = 200 ] || { echo "::error::offline.json $code for $id"; fail=1; }
          done
          exit $fail
```

Replace `<KIT_SHA>` with the kit commit you want to pin, and bump it
deliberately when you want generator fixes.

## Repairing books already published broken

Books merged before the `git add -A` fix are missing their generated files. One
same-clone regen commits all of them at once:

```sh
git clone https://github.com/<owner>/books && cd books
CLAUDE_PLUGIN_ROOT=<kit>/bookbank python3 <kit>/bookbank/library/build-library.py \
  --out . --root . --repo <owner>/books
git add -A && git commit -m "Backfill generated per-book files (offline.json, chip, OG)"
git push
```

`--root . --out .` means no book content is re-synced or overwritten — it only
regenerates what the generator owns. Verify with the loop from the workflow's
last step.

Expect that first repair commit to touch ~110 files, not just the broken books'.
Alongside the missing manifests, it carries a **one-time whitespace
normalization**: `inject_chip`'s fallback branch (used for pages with no
`</body>` tag, which is a legal omission) used to prepend a newline that its own
strip regex didn't remove, so every republish appended one more blank line to
every such page. Those pages grew a line per publish, showed up dirty in
`git status` on every run, and made a CI "nothing changed → skip the commit"
check unable to ever fire. The fix `rstrip`s before re-appending, so the
accumulated blank lines collapse once and stay collapsed.

After that commit, regeneration is verifiably idempotent — a second and third
run over the same tree produce byte-identical output, so the workflow's
`git diff --cached --quiet` short-circuit works and publishes stop churning
every book page.
