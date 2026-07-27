# course-progress.js — the CourseBank progress runtime

Offline-first lesson completion, quiz scoring, resume, and certificate gating
for a CourseBank course. One classic script, no dependencies, works from
`file://` and inside the installed PWA. State is per-course in
`localStorage['cb-progress:<courseId>']`; the runtime also queues xAPI-shaped
statements (`events[]`, capped at 200) for a future sync layer — nothing
requires a server.

## Install (once per course)

```bash
mkdir -p "<course-dir>/assets/vendor"
cp "$CLAUDE_PLUGIN_ROOT/runtime/course-progress.js" "<course-dir>/assets/vendor/"
```

Load it at the end of `<body>` on **every** page (index, lessons, checkpoints,
certificate), after the bookbank exercise kit if the page has quizzes:

```html
<script src="../assets/exercises.js"></script>
<script src="../assets/vendor/course-progress.js"></script>
```

## Markup contract

**Every page** declares the course on `<body>`:

```html
<body data-course="zod-onboarding" data-lessons="schemas,parsing,refine,ck-1">
```

- `data-course` — the course id; without it the runtime does nothing.
- `data-lessons` — the full ordered, comma-separated list of lesson +
  checkpoint ids from `course.json`. Required on any page that shows progress
  (index, certificate); recommended everywhere. It is the denominator — never
  compute progress from what's on one page.

**Lesson and checkpoint pages** add their own identity:

```html
<body data-course="zod-onboarding" data-lessons="…"
      data-lesson="schemas" data-path="lessons/01-01-schemas.html">
```

- `data-lesson` — this page's id. Its presence turns on visit tracking and
  quiz auto-scoring.
- `data-path` — course-root-relative path, used to build resume links.

**Widgets the runtime drives** (style them in `course.css`; the runtime only
toggles classes and fills text):

| Markup | Behavior |
| --- | --- |
| `<button class="lesson-done">` | Toggles this lesson's completion. Gets `.cb-done` + `aria-pressed`; label from `data-done-label` / `data-todo-label` (defaults "✓ Completed" / "Mark lesson complete"). |
| `<a data-lesson-link="<id>">` | Syllabus row; gets `.cb-done` when that lesson is done. |
| `<div class="course-progress"><i></i></div>` | The inner `<i>`'s width is set to the percent. |
| `<span class="course-progress-label">` | Text set to `NN%`. |
| `<a class="course-resume">` | `href` set to the last-visited lesson; `.cb-hidden` while there's no history. |
| `<body data-certificate>` | Certificate page: gets `.cb-unlocked` when eligible (below). |
| `[data-cert-date]` | Filled with today's date when unlocked. |
| `<input data-cert-name>` / `[data-cert-name-out]` | Learner's name, persisted and echoed onto the certificate. |

CSS the course must provide: `.cb-hidden { display: none }`, a `.cb-done`
treatment for syllabus rows and the button, and a locked/unlocked state for
the certificate keyed off `body.cb-unlocked`.

## Quiz auto-scoring

The runtime watches the bookbank exercise kit's `.quiz` / `.quiz-opt` markup
(capture-phase listener, so the kit's `stopPropagation` doesn't hide clicks).
Each quiz scores once — the first option picked — and when every quiz on a
lesson page has been answered, the tally is recorded as that lesson's score.
No extra markup needed beyond the kit's own.

## Certificate eligibility

All ids in `data-lessons` are done, **and** every lesson with a recorded quiz
score passed at ≥ 80% (`PASS` in the source). Checkpoints are just lessons
whose page is mostly quiz, so the same rule covers them.

## API (window.courseProgress)

`isDone(id)` · `markDone(id, done?)` · `quizResult(id, correct, total)` ·
`pct()` · `certificateEligible()` · `resumeHref()` · `export()` · `reset()`.

## Rules (same spirit as the book kit)

- Never bind arrow keys or hijack scroll.
- Degrade to nothing: with JS off the course is a plain readable site; no
  dead-looking UI (the resume link starts `.cb-hidden`, not broken).
- Multi-tab safe: `storage` events re-render.
- `localStorage` failures (private mode) are tolerated — the course still
  reads, progress just doesn't persist.
