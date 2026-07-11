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
   `sunprema/books`.
3. Run `/create-book-from-issue <n>`.
4. Commit, push a `claude/book-<n>-<slug>` branch, and `gh pr create --draft`
   with a `Closes #<n>` body — titled `"NEEDS FIXES — <title>"` instead of
   the normal title if `validate_book.py` left any error-severity findings,
   so a failure is never silent. If `gh pr create` isn't callable unattended
   in this sandbox, push the branch and use its compare URL instead.
5. Comment the PR (or compare URL) back on the originating issue.

## Open questions — resolve on first real fire

1. Whether `gh pr create` works unattended inside this sandbox at all
   (branch-push + compare-URL fallback is written into the prompt either
   way).
2. Whether `RemoteTrigger`'s `run` action's optional `body` actually reaches
   the routine as usable context, or is ignored — the prompt's own
   oldest-open-issue fallback means a bare `run` call is useful either way,
   but per-call issue targeting depends on this working.
3. Whether the `Default` environment's network access is broad enough for
   `write-book`'s general web research, or only covers a trusted allowlist
   (package registries / cloud APIs / dev domains).

## Firing it

Owner-side, from a normal Claude Code session with `RemoteTrigger` access:

```
/dispatch-book-issue <issue-number>
```

This is the `dispatch-book-issue` skill — it calls
`RemoteTrigger({ action: "run", trigger_id: "trig_01MfD61D3X8R4Ln6JtgDy3RQ" })`
(optionally with `body: { text: "<issue-number>" }`) and reports the returned
session URL immediately, without waiting for the routine to finish.
