# Cloud dispatch: the `bookbank` Routine

Book generation can run in the cloud instead of your own terminal, via one
Claude Code Routine. Routines are **per-individual-account**: there is no
shared routine to join, so this doc is a **recipe for creating your own**, not
a pointer to an existing one. Firing a routine requires the `RemoteTrigger`
tool inside a Claude Code session with routine access (there is no public,
curl-able webhook). Without one, local dispatch does the same job:
`/create-book-from-issue <n>` + `gh pr create` yourself.

Once you've created yours, record its id **on your own machine** so
`/dispatch-book-issue` can fire it:

```
export BOOKBANK_ROUTINE_TRIGGER_ID="trig_..."   # from your routine's URL
```

- **Name**: `bookbank`
- **URL**: `https://claude.ai/code/routines/<your-trigger-id>`

## How the routine gets its config: it doesn't need any

**A routine has no env-var field and does not inherit your shell**, so nothing
you `export` locally reaches it. It doesn't have to: the routine's
`session_context.sources` already materializes your books repo, so the session
is *standing inside a clone of it*, and every tool that needs the repo slug
derives it from that clone's `origin` remote.

```
$ cd <books-clone> && python3 .../build-library.py --out . --root .
repo: <owner>/<books> (from the origin remote)
```

Resolution is `--repo` → `$BOOKBANK_BOOKS_REPO` → the clone's `origin`, and it
covers `build-library.py`, `publish-library`, `pull-book`, `create-book-from-issue`,
and the data-root cascade (which keys off `books/` and `catalog.json`). Shell
callers share one implementation, `library/resolve-repo.sh`.

This is strictly safer than a baked-in default: it can only ever resolve to the
repo the session actually has. Two properties keep it honest —

- **Derivation only fires from a directory that looks like a books repo** (it
  has `books/` or `catalog.json`). Standing in some unrelated project does not
  silently make that project "your library" — the tools stop with a hint
  instead. Run from the kit repo, for instance, and resolution is refused.
- **If nothing resolves, the tools stop** rather than guess.

**The one thing to keep right in the prompt:** the routine must `cd` into the
books clone before running any bookbank tooling. This matters most if you adopt
the sparse-clone change in *Known issues* below — with `sources` pointed at the
kit repo, the session's default cwd is the kit checkout, and derivation there is
(correctly) refused. Make the prompt clone the books repo and `cd` into it.

## `.claude/settings.json` in the books repo — how the plugin gets loaded

The routine's checkout is read for project settings at session start, which is
the *only* reliable way to get the plugin into the run (the prompt can't
install it, and the trigger's own `enabled_plugins` field is ignored — see
above). Commit this to the books repo:

```json
{
  "extraKnownMarketplaces": {
    "kit": { "source": { "source": "github", "repo": "<owner>/kit" } }
  },
  "enabledPlugins": { "bookbank@kit": true }
}
```

The same file is where to pin config explicitly if you ever need to — a fork,
or a data root outside the clone — by adding
`"env": { "BOOKBANK_BOOKS_REPO": "<owner>/<books>" }`. That's not needed in the
normal case, since the slug derives from the checkout's `origin`.

A books repo whose `.gitignore` ignores all of `.claude/` must narrow it to
`.claude/settings.local.json` first, or the file will never be committed.
Nothing secret goes there — it's a public repo.

## What it actually is (corrected from an earlier draft of this doc)

The first version of this doc assumed a product shape that turned out not to
match the real `RemoteTrigger` API. Corrections, in case this needs
recreating:

- **No separate "environment with repos + network access" resource.** A
  routine's `job_config.ccr.session_context.sources` lists the git repo(s)
  directly — there's no environment-level repo/network config to set up
  first. Only one environment exists to reference: `Default`
  (`env_01KNsYPAMmXyhRadKPa1mZtK`, kind `anthropic_cloud`).
- **No visible network-access-level control** (no "Trusted" vs "Full"
  allowlist field in this schema) — `write-book`'s WebSearch/WebFetch reach
  is whatever the `Default` environment allows. Untested at doc-writing time
  whether that's broad enough; resolve empirically on first real dispatch.
- **No pure "API-trigger-only" mode.** Every routine requires either
  `cron_expression` or a `run_once_at` timestamp. This routine is created
  with `enabled: false` and `run_once_at` set to 2031 (i.e. never) — the
  *only* way it ever actually runs is an explicit `RemoteTrigger` `run` call.
- **No setup-script hook**, and **installing the plugin from the prompt does
  not work.** Plugins are resolved when a session *starts*, so a
  `claude plugin marketplace add … && claude plugin install …` run from
  inside the prompt installs to disk but never registers the skills into the
  session already running. The symptom is the routine announcing "the
  BookBank plugin isn't in the marketplace" and then improvising a book by
  hand — worse than failing, because it skips the validator, the image-slot
  contract, and the house design. Declare the plugin in the **checked-out
  repo's `.claude/settings.json`** instead (see below), and have the prompt
  verify the skill is available and *stop* if it isn't.
- **`enabled_plugins` / `extra_marketplaces` on the trigger are not
  writable.** The schema has both fields, which look like the obvious place
  for the above. An update carrying `enabled_plugins: ["bookbank@kit"]`
  returns `HTTP 200`, bumps `updated_at`, and the field still reads back
  `[]`. It is not a shape problem: a list of plain strings for
  `extra_marketplaces` fails with `400 unexpected token`, so the payload is
  parsed and then discarded. `job_config` *is* writable, so
  `session_context` changes (below) do stick — always read the trigger back
  after an update rather than trusting the 200.
- **`session_context.allowed_tools` must include `Skill`.** It is an
  allowlist, and the original routine's list (`Bash, Read, Write, Edit,
  Glob, Grep, WebSearch, WebFetch, TodoWrite`) had no way to invoke a slash
  command at all — so step 1, `/create-book-from-issue <n>`, was unreachable
  even with the plugin correctly loaded. Add `Task` too if the run should be
  able to use `stage-book-build`'s per-page subagents.
- **Creating a routine requires GitHub to be connected** (a GitHub App
  installation on the target repo, done via `/web-setup` or
  `/install-github-app` in Claude Code) — this is a prerequisite for
  *creating* the routine, not just for firing it; the first create attempt
  here failed with `401 authentication_error` until that was done.

## The routine's prompt (paraphrased — see the trigger for the verbatim text)

1. Install the tooling plugin if not already present.
2. **`cd` into the books-repo checkout before anything else.** Every later step
   derives the repo slug from that clone's `origin` remote, so the working
   directory *is* the configuration — see *How the routine gets its config*
   above. No env vars to set.
3. Resolve which issue to process: the run's freeform text if given,
   otherwise the oldest open `book-request`-labeled issue on your books repo
   **without the `in-progress` label** (skipping requests another run is
   already generating; stop if none qualify).
4. Duplicate-work guard: if the resolved issue already carries
   `in-progress`, stop and report instead of generating a duplicate
   (unless the run's freeform text explicitly says to redo it). Otherwise
   add the `in-progress` label + a "🏗️ Work started" comment *before* any
   generation, so a concurrently-fired run picks a different issue.
5. Run `/create-book-from-issue <n>`.
6. Commit, push a `claude/book-<n>-<slug>` branch, and `gh pr create --draft`
   with a `Closes #<n>` body — titled `"NEEDS FIXES — <title>"` instead of
   the normal title if `validate_book.py` left any error-severity findings,
   so a failure is never silent. If `gh pr create` isn't callable unattended
   in this sandbox, push the branch and use its compare URL instead.
7. Open image-request issues for the book's unfilled art slots:
   `python3 .github/scripts/open_image_requests.py <book-id> --branch
   claude/book-<n>-<slug> --repo <owner>/<books-repo>` (the opener lives in the
   books repo, so the freshly-cut branch has it). One `image-request` issue
   per slot with no file yet, each marked with book/slot/branch so the
   `place-image` Action can later commit the maintainer's art onto *this* PR
   branch — the book publishes only when the PR merges, so readers never see
   the prompt placeholders (see `.github/AUTOMATION.md` in the books repo).
   Best-effort + idempotent: a clean no-op if the book has no slots, and a
   script error is noted on the issue but never fails the run.
8. Comment the PR (or compare URL) back on the originating issue. On a
   failure that produced no branch/PR, remove `in-progress` again so the
   request re-enters the queue; on success the label stays and the merged
   PR's `Closes #<n>` closes the issue.

## Open questions — status after the first real fire (2026-07-11, issue #2)

1. **Resolved: `gh pr create --draft` works unattended.** Fired against a
   real test issue (sunprema/books#2); the routine pushed
   `claude/book-2-http-caching-headers`, opened
   [PR #3](https://github.com/sunprema/books/pull/3) as a draft with a
   correct `Closes #2` body and the expected (non-"NEEDS FIXES") title, and
   commented the PR link back on the issue — all three steps of the prompt
   completed exactly as written. The branch-push/compare-URL fallback was
   never exercised (wasn't needed) but is still there for the future.
2. **Inconclusive.** Fired with `body: { text: "2" }`, and it correctly
   generated a book for issue #2 — but #2 was *also* the oldest (only) open
   `book-request` issue at that moment, so this run can't distinguish
   "the body actually reached the prompt" from "the fallback found the same
   issue anyway." Re-test with two open issues and a `body.text` pointing at
   the *non-oldest* one to resolve this for real.
3. **Resolved: the `Default` environment's network access is sufficient.**
   The generated PR cites real research against MDN's Cache-Control/ETag
   pages and RFC 9110/9111 — `write-book`'s WebSearch/WebFetch reach worked
   without any Trusted-allowlist restriction being visible.

Also observed: the routine followed the issue's "keep it short" note more
faithfully (3 concepts) than the equivalent local test earlier in this
project's build did (which produced 8 despite the same instruction) — not a
routine-specific finding, just model-run variance, noted here in case it
recurs.

## Known issues / to look at

1. **Every routine run full-clones the ~90MB books repo (2026-07-12).** The
   platform materializes whatever repo `job_config.ccr.session_context.sources`
   lists, and the docs offer no shallow/sparse option for that initial clone —
   yet generating a new book needs zero existing blobs from the library, so
   per-run transfer grows linearly with the library for no benefit.
   **Proposed fix (designed, not yet implemented):** point `sources` at
   `sunprema/kit` (tiny; the session installs the plugin from it anyway) and
   have the prompt bootstrap the content repo itself with
   `git clone --filter=blob:none --sparse https://github.com/<owner>/<books-repo>`
   — the same recipe `pull-book`'s `.pull` clone uses locally, making per-run
   transfer a few hundred KB regardless of library size.
   **If you adopt this, the prompt must `cd` into that bootstrapped clone**
   before any bookbank tooling runs. With `sources` pointing at the kit, the
   session's default cwd is the kit checkout, where repo derivation is
   deliberately refused (it has no `books/` or `catalog.json`) — so the run
   would stop with a setup hint rather than misfire, but it would still stop.
   **Blocking unknown:** whether the sandbox's git/`gh` token is minted
   per-listed-repo (a `kit`-sourced session couldn't push to `books`) or
   per-GitHub-App-installation (it just works). Resolve empirically: update
   the routine, test-fire on a real queued issue, and have the prompt report
   `du -sh` of both checkouts to replace the full-clone *assumption* with a
   measurement. If auth fails, the run dies at the bootstrap clone before
   generating anything; reverting `sources` is one API call.

## Firing it

Owner-side, from a normal Claude Code session with `RemoteTrigger` access:

```
/dispatch-book-issue <issue-number>
```

This is the `dispatch-book-issue` skill — it calls
`RemoteTrigger({ action: "run", trigger_id: "trig_01MfD61D3X8R4Ln6JtgDy3RQ" })`
(optionally with `body: { text: "<issue-number>" }`) and reports the returned
session URL immediately, without waiting for the routine to finish.
