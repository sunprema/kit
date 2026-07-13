---
name: create-book-from-issue
description: Turn a BookBank "book request" GitHub Issue into a seeded book.json, then hand off to write-book's existing queue procedure to actually generate it. Use when the user wants to "create a book from issue <n>", "process book request #<n>", or when dispatching cloud generation for a filed book request. Triggers include "create-book-from-issue", "generate the book for issue 42".
---

# create-book-from-issue

A **thin wrapper**: it resolves a GitHub Issue into a seeded `book.json`, then
defers to the `write-book` skill's existing "process the queue" procedure to
actually research and write the book. It is not a second generation
pipeline — `write-book` stays the single source of truth for what makes a
book correct (structure, design, image slots, everything in its SKILL.md).

## Arguments

- `/create-book-from-issue <issue-number>` — e.g. `/create-book-from-issue 42`.
- `/create-book-from-issue <issue-url>` — a full GitHub issue URL; the repo is
  taken from the URL instead of step 1 below.

## Procedure

1. **Resolve repo + root**, same rules as `write-book`: `$BOOKBANK_BOOKS_REPO`
   (default `sunprema/books`) for the repo; the root cascade
   (`$BOOKBANK_ROOT` → cwd if it looks like a content-repo clone → `~/bookbank`)
   for where the book gets written. If given a full issue URL, take the repo
   from the URL instead of the env default.

2. **Fetch the issue:**
   ```
   gh issue view <n> --repo <repo> --json title,body,labels,comments,url
   ```

3. **Guard against duplicate work, then mark the issue as started.** If the
   fetched issue's labels already include **`in-progress`**, **stop here** —
   another run (a contributor's local session or the cloud routine) is
   already generating this book. Report that, and list what's actually free
   to work on (`gh issue list --repo <repo> --label book-request --state
   open`, minus the `in-progress` ones) — only proceed anyway if the user
   explicitly asked to redo/restart this specific issue. Otherwise, mark the
   issue **before any generation work**, so a concurrent run skips it:
   ```
   gh issue edit <n> --repo <repo> --add-label in-progress
   gh issue comment <n> --repo <repo> --body "🏗️ Work started — generating this book. A PR will be linked here when it's ready."
   ```
   (If the repo doesn't have the label yet: `gh label create in-progress
   --repo <repo> --color fbca04 --description "A BookBank book is already
   being generated for this issue — do not start duplicate work"`.)
   Lifecycle: on success **leave the label on** — the PR's `Closes #<n>`
   closes the issue when it merges. If generation fails with no
   branch/PR to show for it, **remove the label**
   (`gh issue edit <n> --repo <repo> --remove-label in-progress`) so the
   request goes back into the queue instead of looking stuck in progress.

4. **Parse the Issue Form body.** GitHub renders each form field as a
   markdown heading `### <Label>` followed by the answer (or `_No response_`
   if left blank). The label strings below **must match
   `book_details.yml` exactly** — this is a documented coupling between the
   two files; if you change one, change the other:

   | Label                  | book.json field                              |
   |-------------------------|----------------------------------------------|
   | `Topic`                 | `topic` (required — error out if `_No response_`) |
   | `Title`                 | `title`, if present                           |
   | `Persona`                | see step 6                                    |
   | `Theme`                  | see step 6                                    |
   | `Seed concepts`           | one `concepts[]` entry per non-blank line, `source: "user"`, `status: "requested"` |
   | `Notes`                   | `notes`                                       |
   | `Reference material`      | never copied into `book.json` — see step 7    |

5. **Slugify the title** (or the topic, if no title was given) into a
   book id: lowercase, spaces/punctuation → `-`, collapse repeats. If
   `<root>/books/<id>/` already exists, disambiguate by appending `-2`,
   `-3`, … (check each candidate) rather than colliding with an existing book.

6. **Resolve persona/theme against the 3-tier cascade** (`write-book`'s
   "Personas & themes" section) — if the free-text `Persona`/`Theme` answer
   case-insensitively matches an existing id at any tier, use that id.
   Otherwise, if the field is non-blank, pass the raw text through as part of
   `notes` (e.g. append `"Requested voice: <text>"` / `"Requested look:
   <text>"`) and let `write-book`'s existing "honor an inline voice" behavior
   handle it — do not invent a new persona/theme id yourself, and do not
   write an unresolved free-text string into the `persona`/`theme` fields
   (those fields are ids, not prose).

7. **Download any attachments to a scratch dir OUTSIDE the book folder** —
   e.g. `${TMPDIR:-/tmp}/bookbank-issue-<n>/` — never into
   `<book-dir>/assets/img/`. `Reference material` links/images are for
   research and art direction only; if they landed inside the book folder,
   `build-library.py`'s sync would publish them verbatim to the public site,
   including mood-board images the requester never meant to publish. Mention
   any reference material inline in `notes` (e.g. "reference links: …") so
   `write-book` sees it as context, without ever writing the files themselves
   under the book folder.

8. **Write `book.json`**:
   ```json
   {
     "id": "<slug>",
     "title": "<Title, or a working title from the topic>",
     "topic": "<Topic>",
     "status": "requested",
     "created": "<today, ISO yyyy-MM-dd>",
     "persona": "<resolved id, or omit>",
     "theme": "<resolved id, or omit>",
     "concepts": [
       { "id": "<slug>", "title": "<line>", "status": "requested", "source": "user" }
     ],
     "notes": "<Notes, plus any unresolved persona/theme text and reference-material links>",
     "sourceIssue": { "repo": "<owner/name>", "number": <n>, "url": "<issue url>" }
   }
   ```
   `sourceIssue` is new — it's what lets the dispatch prompt (local or cloud)
   write a `Closes #<n>` PR body later. Omit `concepts` entirely (empty
   array) if no seed concepts were given — `write-book` chooses concepts
   itself in that case.

9. **Defer to `write-book`'s Procedure.** Run its "process the queue" path
   (conceptually `/write-book` with no argument, scoped to this one book) —
   do not re-implement research/design/build logic here.

10. **Run `validate_book.py`** against the finished book dir. Report errors
   and warnings **distinctly** (they're different severities — see
   `validate_book.py`'s docstring). Do **not** flip the book to `"ready"`
   if any error-severity finding remains; a warning (e.g. a dangling image
   slot) does not block `"ready"`.

11. **Does not open a PR.** PR-opening is dispatch-mode-specific:
    - **Local dispatch** (a contributor running this skill themselves): tell
      them the book is built/validated and to review it, then run
      `gh pr create` themselves when satisfied.
    - **Cloud dispatch** (the `bookbank` Routine): the routine's own prompt
      handles committing, pushing, and opening the draft PR after this skill
      reports done — see `docs/routines.md`.

    Keeping PR-opening out of this skill keeps it identical for both paths.

## Report

Tell the user: the book id/path, whether it passed validation cleanly or has
outstanding warnings/errors, and what to do next (review + `gh pr create`,
or — for cloud dispatch — that the routine will handle the rest).
