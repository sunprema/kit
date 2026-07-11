---
name: stage-book-build
description: Build a large BookBank book as a sequence of separately-scoped `claude` runs — one to scaffold the shared shell, then one per concept page — instead of one long session for the whole book. Mirrors the BookBank.app's BuildOrchestrator/"Build in stages" path, but runnable headlessly (no app). Use for a syllabus-length or many-concept book, when a single-pass /write-book run risks running long or losing context late in the book, or when a caller (a human or the cloud routine) wants resumable, per-page progress. Triggers include "stage this book", "build in stages", "build this book page by page", "the queue has a big course book".
---

# stage-book-build

The single-pass `write-book` procedure ("process the queue") hands a whole
book to **one** `claude` session. That's fine for a small book, but a large
one (a syllabus-length course, a dozen+ concepts) means one long session with
context that degrades late in the book, a single point of failure (page 12
failing can jeopardize the whole run), and — empirically, from testing this
plugin — long single-pass headless sessions are the ones most likely to hit
an idle/stall cutoff.

This skill is a **headless-runnable equivalent of `BuildOrchestrator.swift`**
(the app's "Build in stages (per page)" path — see the app's
`docs/staged-builds.md` for the original design). It decomposes a build into
ordered steps and runs **one separate, freshly-scoped `claude` process per
step**. Because `book.json` is the only thing that carries state between
steps ("the file is the interface" — the app's own docs make this exact
point), any runner can drive it: the app, a human's terminal, or this skill.

## Arguments

- `/stage-book-build` (no arg) — compute the step list across **every** book
  in the queue that has work (see "Computing the step list" below), then run
  it top to bottom.
- `/stage-book-build <book-id>` — scope to one book.

## Computing the step list

Resolve root via the usual cascade. For each in-scope book, read `book.json`
and decide:

1. **`status: "revising"`** → exactly **one** step: `revise`. Nothing else
   for this book.
2. Otherwise:
   - If `index.html` doesn't exist yet under the book dir → one **`scaffold`**
     step, first.
   - Then, **for every concept in `concepts[]`, in array order** (not just
     the ones with work — the position matters for numbering), where that
     concept's `status` is `"requested"` → one **`concept`** step. Its file
     is `concepts/NN-<concept-id>.html`, where `NN` is the concept's
     **1-based position in the array**, zero-padded — the same numbering
     `write-book`'s Procedure already uses, computed from the concept's
     index, not a separate counter.

A book with no `index.html` and no `requested`/`revising` state contributes
no steps (nothing to do). Print the full computed plan before running
anything — book id, step count, and each step's title — so progress is
visible, mirroring the app's live checklist ("Step 4/19 · Linked Lists").

## Running each step

Each step is a **separate `claude -p` invocation** via Bash, run from the
resolved root, with the step's scoped prompt (exact templates below) as the
argument:

```bash
claude -p "<step prompt>" --allowedTools "Bash WebSearch WebFetch Write Edit Read Glob Grep TodoWrite"
```

Use `--allowedTools` (not `--dangerously-skip-permissions`) — narrower than
what the app's own runner uses (it skips permissions outright), but this
exact allowlist was validated end-to-end while building this plugin and
achieves the same unattended operation without a blanket bypass. Give each
call a generous timeout (the Bash tool's max, 600000ms) — if a step
genuinely needs longer than that, it's a Bash-tool constraint independent of
this skill.

**After every step, re-read `book.json` from disk and verify the step
actually did its job** (file-state truth, not the process's exit code alone):

- `scaffold` → `index.html` now exists, no concept's `status`/`file` changed.
- `concept` → that concept's `status` is now `"ready"` and its `file` exists.
- `revise` → book `status` is now `"ready"` and `revisionNotes` is cleared.

**On failure** (the process errors, times out, or the verification above
doesn't hold): **retry once** with the identical prompt — mirrors the app's
one-auto-retry-on-a-stall behavior. A retry is safe/idempotent here because a
failed step never wrote its expected `book.json` change, so nothing has
double-applied. If the retry **also** fails: **stop**, report which step
failed and which book/concept it was, note that every already-completed step
is saved (file-state truth means nothing already `"ready"` is lost), and that
running `/stage-book-build` again will **resume** — it recomputes the step
list from current disk state, so finished concepts are simply absent from
the new plan.

On success, move to the next step. Chain through the whole computed plan.

## Step prompts (verbatim contracts — do not paraphrase)

These mirror `Model.swift`'s `scaffoldPrompt`/`conceptPrompt`/`revisePrompt`
exactly, and satisfy the `write-book` skill's own "Staged (orchestrated)
builds" section — that section is written assuming a runner will send
exactly these scoped instructions.

**Scaffold** (`bookID` = the book's id):

```
Use the write-book skill to SCAFFOLD (not fully build) the BookBank book with id "<bookID>" at books/<bookID>/. Read its book.json — topic, persona, theme, and (if present) courseMeta, courseOutcomes, designDirection, voiceSample. Create ONLY the shared shell every page will reuse: (1) assets/ — the stylesheet(s) plus a theme skin matching designDirection, the two-page-spread pager (assets/book.js), and any interactive/widget engine the concepts will share; (2) index.html — the cover + table of contents linking every concept in book.json order to concepts/NN-<concept id>.html (NN = the concept's 1-based position, zero-padded), with a cover-art image slot. Lock the persona voice and the visual design. Do NOT write any concept page body and do NOT change any concept's status — leave every concept requested or proposed as it is. Then stop. Do not ask questions.
```

**One concept** (`bookID`, `conceptID`, `file` = `concepts/NN-<conceptID>.html`):

```
Use the write-book skill to build EXACTLY ONE concept page and nothing else. Book id "<bookID>", concept id "<conceptID>", at books/<bookID>/. Read book.json and this concept's brief, notes, unit, cos and kind. Build against the EXISTING assets/ and the design already scaffolded — reuse the shared stylesheet, pager and widget engine; do not restyle the book or touch any other page. Research the web for accurate content. Write the page to <file>, in the locked persona voice, honoring the brief and any author notes; if kind is "exam-prep" or "cheatsheet", follow that format. Then set ONLY this concept's file to "<file>" and status to "ready" in book.json (leave every other concept untouched) and make sure index.html links it. Then stop. Do not ask questions; if the topic is too vague, note it in the book's summary and still write the best page you can.
```

**Revise** (`bookID`):

```
Use the write-book skill to revise IN PLACE the BookBank book with id "<bookID>" at books/<bookID>/: read its existing pages, its revisionNotes, and any comments.json beside book.json — improve/add content and apply each open editorial comment to its anchored block, then mark that comment resolved, rather than rebuilding from scratch. Then set the book's status to "ready" and clear revisionNotes. Then stop. Do not ask questions.
```

A concept's `brief`/`notes`/`unit`/`cos`/`kind` fields are the same optional
per-concept fields `docs/staged-builds.md` documents for guided/course-book
plans — pass through whatever's on the concept; if absent, the concept step
falls back to the concept's `title` alone, same as a one-shot build would.

## After the whole plan finishes

Run `${CLAUDE_PLUGIN_ROOT}/library/validate_book.py <book-dir>` on each book
that was built or revised, and report errors vs. warnings distinctly (same
severity split as `create-book-from-issue`'s step 9). Don't consider a book
truly done if an error-severity finding remains — say so, even though every
concept shows `"ready"` in `book.json`.

## What this does NOT do (yet)

- **No parallel fan-out.** Steps run strictly sequentially, same as the
  app today (`docs/staged-builds.md` calls parallel fan-out "the next step"
  there too — not built in either place).
- **No idle-timeout, only a flat per-step timeout.** The app's runner kills a
  step after 5 minutes of *no output*; this skill can only give each Bash
  call a flat wall-clock cap (the Bash tool's own max). A step that's
  genuinely still working past that cap looks the same as a stalled one here.
- **Doesn't decide *when* to stage vs. one-shot.** `create-book-from-issue`
  still defers to `write-book`'s plain single-pass queue procedure by
  default; a caller (a human, or the cloud routine's prompt) can choose to
  invoke `/stage-book-build <id>` instead for a book that looks large
  (many seed concepts, a course/syllabus request) — that choice isn't
  automated here.
