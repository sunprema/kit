---
name: dispatch-book-issue
description: Fire your own cloud "bookbank" Routine for a book-request GitHub Issue and return immediately with the session URL — does not itself generate anything. Use when the user wants to "dispatch issue <n> to the cloud", "run the book routine for #<n>", or "generate this book in the cloud" without blocking their own terminal. Requires $BOOKBANK_ROUTINE_TRIGGER_ID (Routines are per-individual-account).
---

# dispatch-book-issue

A **thin dispatcher**, deliberately kept separate from `create-book-from-issue`
— firing the routine and running a full generation pass are different enough
jobs that combining them risks this skill accidentally trying to also
generate. This skill's entire job is one `RemoteTrigger` call.

## This needs your own Routine first

Claude Code Routines are **per-individual-account**: a trigger id belongs to
one person, and firing one requires the `RemoteTrigger` tool inside a Claude
Code session — there is no public curl-able webhook. So this skill does
nothing until *you* have created your own `bookbank` routine and exported its
trigger id:

```
export BOOKBANK_ROUTINE_TRIGGER_ID="trig_..."   # your own routine's id
```

`docs/routines.md` has the routine's prompt and setup. If it isn't set, **stop
and say so** — point the user at `docs/routines.md`, and note that
`create-book-from-issue` locally + `gh pr create` does the same job without
any cloud routine at all. Never guess or reuse someone else's trigger id.

## Arguments

- `/dispatch-book-issue <issue-number>` — e.g. `/dispatch-book-issue 42`.
- `/dispatch-book-issue` (no arg) — dispatch with no issue number; the
  routine's own prompt falls back to the oldest open `book-request` issue on
  your books repo that is **not** already labeled `in-progress` (i.e. it
  skips requests another run is already generating).

## Procedure

0. Read `$BOOKBANK_ROUTINE_TRIGGER_ID`. If it's empty, stop — see above.
1. Load the `RemoteTrigger` tool if it isn't already available
   (`ToolSearch select:RemoteTrigger`).
2. Fire exactly one call and report the result immediately — **do not poll
   or wait** for the routine to finish:
   ```
   RemoteTrigger({ action: "run", trigger_id: "<$BOOKBANK_ROUTINE_TRIGGER_ID>" })
   ```
   Pass the issue number as the run's freeform body if one was given, e.g.
   `{ action: "run", trigger_id: "...", body: { text: "<issue-number>" } }` —
   **unconfirmed whether the routine's stored prompt actually receives this**
   (resolve empirically the first time this is fired for real; if it turns
   out not to be wired through, the routine's own fallback — "no issue
   number given → oldest open `book-request` issue" — still makes a plain
   no-body `run` call useful on its own).
3. Report the returned session URL to the user so they can watch progress
   themselves. This skill's job ends here — it does not check back on the
   routine, and it does not open a PR itself (the routine's own prompt does
   that once generation finishes).
