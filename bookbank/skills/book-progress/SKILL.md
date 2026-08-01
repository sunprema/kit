---
name: book-progress
description: Add quiet, automatic reading progress to a BookBank book — chapters mark themselves read as the reader reaches their last spread, the contents page grows subtle read-marks, and a small "resume reading" link deep-links back to the exact spread. No buttons, no chrome, nothing in the reading path. Use when a book should remember where the reader is, when the user asks for "resume where I left off", "track reading progress", "mark chapters as read", or "which chapters have I finished".
---

# book-progress

Courses ask the learner to *do* something, so CourseBank has a "mark lesson
complete" button. Books must not — a chapter is completed **by reading it**,
and any UI that interrupts that is a cost. This skill adds progress to a
BookBank book with **zero required interaction**:

- A chapter marks itself **read** when the reader reaches its last spread
  (desktop) or the end of the page (the mobile scroll layout). Landing on a
  too-short-to-scroll page counts after a short dwell.
- The contents page gets **quiet read-marks** (`bb-read` class on the TOC
  links — the book's CSS decides how softly to show them).
- A small **resume link** on the cover/contents deep-links to the exact
  spread the reader left, via the pager's existing `#s<N>` support.
- Everything is per-book `localStorage`; nothing leaves the device, nothing
  needs a network, and with JS off the book is byte-for-byte unchanged.

## Install (once per book)

1. Vendor the runtime — one call, and it knows both paths:
   ```bash
   "$CLAUDE_PLUGIN_ROOT/library/vendor.sh" "<book-dir>" book-progress.js
   ```
   `assets/book-progress.js` in **this skill is the master copy and is never
   written to** — not to adapt it to a book, not to fix a book's markup. It is
   read, copied, and left alone; a change to the runtime is a change to the
   plugin, made deliberately and shared by every book. (`vendor.sh` refuses any
   destination under the plugin root, which is the mistake it exists to stop.)
2. Load it **after `book.js`** on every page (index, concepts, cheatsheet):
   ```html
   <script src="../assets/book.js"></script>
   <script src="../assets/book-progress.js"></script>
   ```
3. Declare the book id on every page's `<body>` — explicit beats derivation:
   ```html
   <body data-book="rust-programming">
   ```
   (Without it, the runtime derives the id from the URL's book folder, which
   works for the standard layout — a legacy book gets progress from steps
   1–2 alone.)
4. On `index.html`, add the resume link somewhere quiet in the cover/TOC
   area — it must ship `hidden`, so nothing shows for a first-time reader:
   ```html
   <a class="book-resume" hidden>Resume reading →</a>
   ```
   Optionally add a progress whisper (empty until something is read):
   ```html
   <span class="book-progress-note"></span>
   ```
5. Style both in `book.css`, token-driven and **deliberately quiet** — this
   is annotation, not interface. The accent color is never used for
   progress; soft ink and the rule gray are the palette:
   ```css
   /* TOC read-marks: a soft check after the entry — or dim the row instead */
   .toc a.bb-read::after{ content:" ✓"; color:var(--ink-soft); font-size:.8em; }

   .book-resume{
     font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
     color:var(--ink-soft); text-decoration:none;
   }
   .book-resume:hover{ color:var(--accent); }
   .book-progress-note{ font-size:.72rem; color:var(--ink-soft); }
   ```
   Adapt **these CSS selectors** to the book's own TOC markup; keep the weight
   low. The adaptation happens in `book.css` only — never by editing the
   vendored runtime, whose own selectors (`.bb-read`, `.book-resume`,
   `.book-progress-note`) are the contract the CSS hooks onto.

## How the runtime learns the reader's position

In preference order — install-and-go on existing books, precise on new ones:

1. **`bookbank:spread` CustomEvent** with `detail: {i, total}` — new books'
   pagers dispatch it from `render()` (the write-book pager reference now
   includes the line). Reaching `i === total - 1` marks the chapter read.
2. **Watching `.book-pageno`** — the stock pager rewrites it as
   `"i+1 / total"` on every turn, so a MutationObserver gives the same
   signal on an **unmodified existing book**. A book that removed the page
   number and doesn't dispatch the event gets resume-tracking but no
   automatic read-marks on desktop (the mobile path still works).
3. **Scroll, below the pager's ~900px breakpoint** — there are no spreads;
   ≥85% scroll counts, and an unscrollable page counts after ~2.5s.

## Markup contract (all optional beyond the script tag)

| Markup | Behavior |
| --- | --- |
| `<body data-book="<id>">` | Names the storage bucket; else derived from the URL. |
| any `<a>` to a read chapter | Gets `.bb-read` (index and everywhere else). |
| `<a class="book-resume" hidden>` | `href` set to `concepts/NN-x.html#s<N>`; unhidden (+`.bb-show`) once there's history. |
| `<span class="book-progress-note">` | Filled with "3 of 9 chapters read" / "All 9 chapters read"; empty until then. |

API for the console and the app: `window.bookProgress` —
`isRead(basename)` · `markRead(basename, val?)` · `resumeHref()` ·
`export()` · `reset()`.

## Rules (the kit's standing ones, plus this skill's own)

- **Never bind arrow keys, never hijack scroll** — the pager owns them; the
  scroll listener is passive and read-only.
- **Nothing in the reading path.** No toasts, no badges on concept pages, no
  "chapter complete!" moments. Progress renders only where the reader
  already looks for orientation: the contents page.
- **Degrades to nothing.** No JS, no runtime file, private-mode storage —
  the book reads identically; the resume link ships `hidden`.
- **Chapters are keyed by file basename** — never renumber existing chapter
  files on a revision (write-book already forbids it; this is one more
  reason).

## Verification

1. Open a concept page from `file://`, turn to its last spread with → keys,
   then open `index.html`: that chapter's TOC entry shows the read-mark,
   the resume link is visible and points at `concepts/NN-x.html#s<N>`, and
   following it lands on the same spread.
2. Narrow below 900px, scroll a chapter to the bottom, and confirm it marks
   read via the scroll path.
3. Confirm the first-visit experience is untouched: clear state
   (`bookProgress.reset()` in the console), reload the index — no resume
   link, no note, no marks.
4. Confirm ← → still turn pages and `/book-visual-qa` passes — the runtime
   must not have added anything the QA eye can see on a concept page.

## Report

Say what was installed (runtime + which optional hooks), how read-detection
is wired for this book (event, pageno observer, or both), and confirm the
first-visit page is visually unchanged.
