---
name: dispatch-book-issue
description: Fire the cloud "bookbank" Routine for a book-request GitHub Issue and return immediately with the session URL — does not itself generate anything. Use when the user wants to "dispatch issue <n> to the cloud", "run the book routine for #<n>", or "generate this book in the cloud" without blocking their own terminal. Owner-only (Routines are per-individual-account).
---

# dispatch-book-issue

A **thin dispatcher**, deliberately kept separate from `create-book-from-issue`
— firing an HTTP POST and running a full generation pass are different enough
jobs that combining them risks this skill accidentally trying to also
generate. This skill's entire job is one API call.

Realistically **owner-only**: Claude Code Routines are per-individual-account,
so a contributor without access to the owner's routine should use
`create-book-from-issue` locally + `gh pr create` instead. See
`docs/routines.md` for the routine's own setup.

## Arguments

- `/dispatch-book-issue <issue-number>` — e.g. `/dispatch-book-issue 42`.

## Procedure

1. Require `$BOOKBANK_ROUTINE_URL` and `$BOOKBANK_ROUTINE_TOKEN` to be set —
   if either is missing, stop and tell the user to set them (point at
   `docs/routines.md` for how the routine/trigger URL is obtained).
2. Fire exactly one request and print the result immediately — **do not
   poll or wait** for the routine to finish:
   ```
   curl -sX POST "$BOOKBANK_ROUTINE_URL" \
     -H "Authorization: Bearer $BOOKBANK_ROUTINE_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"text\": \"<issue-number>\"}"
   ```
3. Report the returned session URL (and issue number) to the user so they can
   watch progress themselves. This skill's job ends here — it does not check
   back on the routine, and it does not open a PR itself (the routine's own
   prompt does that once generation finishes).
