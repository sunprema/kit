# Cloud dispatch: the `bookbank` Routine

Book generation can run in the cloud instead of a contributor's own terminal,
via one Claude Code Routine. This path is realistically **owner-only** —
firing a routine requires the `RemoteTrigger` tool, which is only available
inside a Claude Code session with routine access (there is no public,
curl-able webhook). A contributor without access falls back to local
dispatch: `/create-book-from-issue <n>` + `gh pr create` themselves.

- **Trigger id**: `trig_01MfD61D3X8R4Ln6JtgDy3RQ`
- **Name**: `bookbank`
- **URL**: https://claude.ai/code/routines/trig_01MfD61D3X8R4Ln6JtgDy3RQ

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
- **No setup-script hook.** The plugin install (`claude plugin marketplace
  add sunprema/kit && claude plugin install bookbank@kit`) is the first
  instruction *inside the routine's own prompt*, not a separate environment
  bootstrap step.
- **Creating a routine requires GitHub to be connected** (a GitHub App
  installation on the target repo, done via `/web-setup` or
  `/install-github-app` in Claude Code) — this is a prerequisite for
  *creating* the routine, not just for firing it; the first create attempt
  here failed with `401 authentication_error` until that was done.

## The routine's prompt (paraphrased — see the trigger for the verbatim text)

1. Install the tooling plugin if not already present.
2. Resolve which issue to process: the run's freeform text if given,
   otherwise the oldest open `book-request`-labeled issue on
   `sunprema/books` **without the `in-progress` label** (skipping requests
   another run is already generating; stop if none qualify).
3. Duplicate-work guard: if the resolved issue already carries
   `in-progress`, stop and report instead of generating a duplicate
   (unless the run's freeform text explicitly says to redo it). Otherwise
   add the `in-progress` label + a "🏗️ Work started" comment *before* any
   generation, so a concurrently-fired run picks a different issue.
4. Run `/create-book-from-issue <n>`.
5. Commit, push a `claude/book-<n>-<slug>` branch, and `gh pr create --draft`
   with a `Closes #<n>` body — titled `"NEEDS FIXES — <title>"` instead of
   the normal title if `validate_book.py` left any error-severity findings,
   so a failure is never silent. If `gh pr create` isn't callable unattended
   in this sandbox, push the branch and use its compare URL instead.
6. Comment the PR (or compare URL) back on the originating issue. On a
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

## Firing it

Owner-side, from a normal Claude Code session with `RemoteTrigger` access:

```
/dispatch-book-issue <issue-number>
```

This is the `dispatch-book-issue` skill — it calls
`RemoteTrigger({ action: "run", trigger_id: "trig_01MfD61D3X8R4Ln6JtgDy3RQ" })`
(optionally with `body: { text: "<issue-number>" }`) and reports the returned
session URL immediately, without waiting for the routine to finish.
