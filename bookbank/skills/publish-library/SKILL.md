---
name: publish-library
description: Publish BookBank books to a public GitHub Pages library (default sunprema/books, live at sunprema.github.io/books/; configurable via $BOOKBANK_BOOKS_REPO / $BOOKBANK_SITE_URL). Syncs ready books, regenerates the cover-card shelf + catalog from each book.json, commits, pushes, and verifies the URLs are live. Use when the user wants to "publish the library", "publish my books", "push books to GitHub Pages", "put <book> online", "update the public book site", or "share a book publicly". Triggers include "publish-library", "publish the books", "add <book> to the public site".
---

# publish-library

Publishes BookBank books to a public GitHub Pages repo (default
**`sunprema/books`**, live at **https://sunprema.github.io/books/**). The books
are already self-contained static HTML — this skill's job is to sync the
chosen books into the repo, **regenerate** the front page + catalog from every
`book.json`, push, and confirm it's live. It parallels the global `promo`
skill but is book-specific and the shelf is generated, never hand-edited.

## Configuration

Both the target repo and the live URL are configurable — set these before
running if publishing to a fork or a different account:

```
export BOOKBANK_BOOKS_REPO="sunprema/books"          # owner/name, default shown
export BOOKBANK_SITE_URL="https://sunprema.github.io/books"  # default: derived
                                                                # from the repo
```

`build-library.py` reads both directly. The rest of this doc uses `$REPO` /
`$BASE` for these two values — resolve them once at the start of a run:
```
REPO="${BOOKBANK_BOOKS_REPO:-sunprema/books}"
BASE="${BOOKBANK_SITE_URL:-https://${REPO%%/*}.github.io/${REPO#*/}}"
```

- Repo: `https://github.com/$REPO` (public)
- Live base URL: `$BASE/`
- Each book: `$BASE/books/<book-id>/`

## The one thing that does the work

`${CLAUDE_PLUGIN_ROOT}/library/build-library.py`. It syncs books and generates
the whole front door — you do **not** hand-write `index.html`:

```
python3 "$CLAUDE_PLUGIN_ROOT/library/build-library.py" --out <clone-dir> [--root <bookbank-root>] [--only id1,id2]
```

- `--out`   a clone of the target repo (required).
- `--repo`  target repo as `owner/name` (default `$BOOKBANK_BOOKS_REPO` or `sunprema/books`).
- `--root`  BookBank data root — same cascade as `write-book`: `$BOOKBANK_ROOT`,
  else cwd if it looks like a content-repo clone, else `~/bookbank`.
- `--only`  comma-separated book ids to publish. **Omit to publish every book
  whose `status` is `ready`.** Publishing is **additive** — books already in the
  clone that you don't list are kept and still appear on the shelf.

It writes into `<out>`: `books/<id>/` (each book verbatim), `index.html` (the
responsive cover-card grid with search + voice filters), `catalog.json`,
`assets/library.css`, `assets/library.js`, `.nojekyll`, and `README.md` (once).
Books with real cover art (`cover.png` / `assets/img/cover-art.png` /
`assets/img/cover.png`) show it; the rest get a deterministic gradient cover.

## Arguments

- `/publish-library` (no arg) — **publish everything ready.** Sync all `ready`
  books and regenerate the shelf. This is the usual "refresh the whole site" run.
- `/publish-library <book-id>` (or several) — publish just those books
  (`--only`), additively. Use after building or expanding one book.

## Workflow

1. **Resolve config, then get a current clone.** If you're already standing
   inside a clone of `$REPO` (the common case — a contributor just wrote a
   book there via `/write-book`), **that clone *is* the root and *is* the
   thing to push** — don't clone a second copy of the repo into itself. Only
   maintain a separate `.publish` checkout when running from somewhere else
   (e.g. `~/bookbank`, the legacy flat layout) — reuse a stable checkout there
   so re-runs `git pull` instead of re-cloning ~90 MB:
   ```
   REPO="${BOOKBANK_BOOKS_REPO:-sunprema/books}"
   BASE="${BOOKBANK_SITE_URL:-https://${REPO%%/*}.github.io/${REPO#*/}}"
   if git rev-parse --show-toplevel >/dev/null 2>&1 && git remote -v | grep -q "$REPO"; then
     CLONE="$(git rev-parse --show-toplevel)"   # already the content repo
   else
     CLONE="${BOOKBANK_ROOT:-$HOME/bookbank}/.publish"
     [ -d "$CLONE/.git" ] && git -C "$CLONE" pull -q origin main \
       || gh repo clone "$REPO" "$CLONE"
   fi
   ```
   (`gh` must be authenticated as the repo owner — check `gh auth status`.)

2. **Generate.**
   ```
   python3 "$CLAUDE_PLUGIN_ROOT/library/build-library.py" --out "$CLONE" --repo "$REPO"            # all ready books
   python3 "$CLAUDE_PLUGIN_ROOT/library/build-library.py" --out "$CLONE" --repo "$REPO" --only <id>  # one/some books
   ```
   Read its stdout — it lists each book synced and whether it used real art or a
   gradient cover.

3. **Commit & push `main`.** Pages auto-deploys from `main` at root.
   ```
   cd "$CLONE" && git add -A
   git -c user.name="Sundar Nambuvel" -c user.email="sunprema.aws@gmail.com" \
     commit -m "Publish library — <what changed>

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   git push -q origin main
   ```
   (Skip the commit if `git status` is clean — nothing changed.)

4. **Verify it's live.** A deploy takes ~30–90s; a 404/stale catalog right after
   push is normal. Poll in the **background** (foreground `sleep` is blocked)
   until `catalog.json` reflects the expected count, then check each book URL.
   Use `curl --retry 3 --retry-all-errors` — a bare first request can return
   `000` (cold connection), which is **not** an HTTP failure; retry before
   reporting a problem.
   ```
   for i in $(seq 1 45); do
     n=$(curl -s "$BASE/catalog.json" | python3 -c "import sys,json;print(len(json.load(sys.stdin)['books']))" 2>/dev/null || echo 0)
     [ "$n" -ge <expected> ] && break; sleep 8
   done
   for id in <ids>; do
     c=$(curl -s --retry 3 --retry-all-errors -o /dev/null -w "%{http_code}" "$BASE/books/$id/")
     [ "$c" = 200 ] || echo "FAIL $c $id"
   done
   ```

5. **Report the live URLs** — the shelf `$BASE/` and the specific book(s)
   `$BASE/books/<id>/`.

## First-time / repo-missing setup

If `$REPO` does not exist, create it, then let step 2 generate the content and
step 3 push it:
```
gh repo create "$REPO" --public \
  --description "The BookBank Library — beautiful, web-researched books on GitHub Pages"
gh api -X POST "repos/$REPO/pages" -f "source[branch]=main" -f "source[path]=/"
```

## Notes & gotchas

- **Public repo.** Everything pushed is public, including each book's `book.json`
  (harmless title/summary/concept metadata). Don't publish a book the user wants
  kept private; confirm if unsure.
- **Only `ready` books ship.** The generator skips `requested`/`building` books
  even if named in `--only`.
- **The shelf is generated — never hand-edit** `index.html` / `catalog.json` in
  the repo. Change the look by editing the plugin's `library/build-library.py`
  (the `LIBRARY_CSS` / `render_index` parts) and re-running.
- **Keep `.nojekyll`** — without it Jekyll can drop `assets/`-style folders.
- **Book readers are desktop-first** (fixed-viewport two-page spread); the shelf
  is fully responsive. Fine to publish; just know phones get a tight reader.
- **Size:** the full library is ~90 MB (books carry their own art). Reusing the
  `.publish` clone and pulling keeps pushes incremental.
