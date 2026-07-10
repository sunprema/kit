# Cloud dispatch: the `bookbank` Routine

Book generation can run in the cloud instead of a contributor's own terminal,
via one API-triggered Claude Code Routine. This path is realistically
**owner-only** — Routines are per-individual-account, so a contributor
without access to the owner's routine always falls back to local dispatch
(`/create-book-from-issue <n>` + `gh pr create`).

## Setup (one-time, owner only)

- **Environment**: a dedicated `bookbank` environment.
  - **Repositories**: `sunprema/books` only. The tooling plugin is installed
    via the environment's cached **setup script**, not cloned as a second
    repo:
    ```
    claude plugin marketplace add sunprema/kit
    claude plugin install bookbank@kit
    ```
    (Confirm the exact subcommand syntax against your Claude Code version
    before relying on it — verified once at first real routine run.)
  - **Network access**: **Full**. The default "Trusted" allowlist covers
    package registries/cloud APIs/dev domains, not the broad web research
    `write-book` needs.
- **Trigger**: API only. No schedule, no GitHub-events trigger (GitHub
  triggers don't support Issues events anyway).
- **Prompt**:
  ```
  /create-book-from-issue {{text}}
  ```
  run against `sunprema/books`, root `.`. After the skill reports done, the
  prompt itself:
  1. commits the new/updated book folder,
  2. pushes a `claude/`-prefixed branch,
  3. runs `gh pr create --draft` with a `Closes #{{issue-number}}` body — if
     validation left error-severity findings, title it
     `"NEEDS FIXES — <title>"` so a failure is never silent,
  4. comments the PR (or branch compare) link back on the originating issue.

## Open question — resolve empirically

Whether `gh pr create` is callable **unattended** inside a routine's sandbox
isn't confirmed by the product docs (they describe PR creation as a
session-view action, i.e. something a human clicks). If it isn't:
**push the branch and print/comment the compare URL instead** —
`https://github.com/sunprema/books/compare/main...claude/<branch>?expand=1`.
Either way, a human always reviews before anything merges.

## Firing it

Owner-side, from a normal Claude Code session:

```
/dispatch-book-issue <issue-number>
```

This is the `dispatch-book-issue` skill — a thin wrapper that reads
`$BOOKBANK_ROUTINE_URL` / `$BOOKBANK_ROUTINE_TOKEN` and does one
`curl -sX POST "$BOOKBANK_ROUTINE_URL" -H "Authorization: Bearer $BOOKBANK_ROUTINE_TOKEN" -d '{"text": "<issue-number>"}'`,
printing the returned session URL immediately — it does not wait for the
routine to finish, and it does not itself do any generation.
