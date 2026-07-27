# CourseBank — design notes

CourseBank is the third member of the BankKit family (BookBank → DashBank →
CourseBank). It reuses the factory pattern end to end: request → headless
generation with craft skills → QA gate → publish to a public gallery. Decisions
locked 2026-07-27:

- **Plugin lives here** (`kit/coursebank`); **published artifacts will live in
  `sunprema/courses`** (the "academy" — GitHub Pages portal, the
  `sunprema/books` analog). Not created yet; see roadmap.
- **Courses are generated FROM a source corpus, not from web research alone.**
  A book starts from a topic; a course starts from a repo, a docs export, or a
  policy set, and the syllabus is derived from *that*, with `curriculum.json`
  claims citing corpus files at a pinned ref (`path@ref`). This is the
  staleness story: when the corpus moves, a diff names the lessons to
  regenerate. Web research supplements the corpus, it doesn't replace it.
- **Phone-first PWA, not the two-page spread.** Books are desktop reading
  artifacts; training happens on phones, planes, and factory floors. Lessons
  are single-column scrolling pages, and **every course is independently
  installable**: its own `manifest.webmanifest`, `sw.js`, and icons. The
  service worker precaches the *entire course* on first visit (courses are
  small and self-contained), so "visited once" = "works in airplane mode".
  `offline.json` is still generated per course for the future academy shelf
  (BookBank-style opt-in downloads of *other* courses).
- **Progress is offline-first.** Lesson completion, quiz scores, and
  resume-where-you-left-off live in `localStorage` per course
  (`assets/vendor/course-progress.js`, vendored from this plugin's
  `runtime/`). The runtime also queues xAPI-shaped statements locally; a sync
  endpoint and real xAPI/SCORM export are roadmap items, and nothing about
  the local format blocks them. The completion certificate unlocks from local
  state alone — no server round-trip to finish a course offline.
- **Instructors are the persona-equivalent** (`defaults/instructors/`):
  `the-mentor`, `the-socratic`, `the-operator`. Same `{name, tagline, voice}`
  shape and 3-tier cascade as BookBank personas.
- **CourseBank depends on the bookbank plugin** (installed from the same kit
  marketplace — the cloud routine installs both). It reuses BookBank's craft
  skills directly: `book-diagrams` (shared SVG grammar), `book-exercises`
  (the blur-reveal exercise kit — quiz markup is also what the progress
  runtime scores), `2d-concept-animations`, `svg-animations`,
  `typeset-cover`, and the image-slot pattern + `place_image.py`.
- **The publish gate is pedagogy, not art.** BookBank held books for cover
  art; DashBank holds dashboards for privacy; CourseBank holds courses until
  every lesson objective has a checkpoint question that tests it
  (`validate_course.py`, roadmap — the `validate_book.py` analog: schema
  check + objective↔checkpoint coverage + PWA completeness).

## Roadmap (agreed build order)

1. ✅ `write-course` skill + progress runtime + PWA templates + instructor
   defaults; prove one beautiful course locally (point it at a real
   open-source repo, generate its onboarding course, install on a phone,
   finish a module in airplane mode). **Proven 2026-07-27**: `zod-onboarding`
   (3 modules · 8 lessons · 3 checkpoints · cheatsheet · certificate),
   generated from colinhacks/zod @ 912f0f5, swiss theme, the-mentor voice —
   behavioral suite passed (progress, quiz scoring, resume, 80% certificate
   gate) and the airplane test passed (server killed; never-visited pages
   served from the SW precache).
2. `validate_course.py` + `build-academy.py` (the `build-library.py` analog:
   portal shelf, per-course offline downloads, installable academy) +
   `publish-academy` skill.
3. Create `sunprema/courses`: issue form (corpus URL, audience, instructor
   dropdown), `publish-on-merge.yml` pinned to a kit SHA, Pages.
4. `coursebank` cloud routine + `create-course-from-issue` +
   `dispatch-course-issue` skills (clone the bookbank routine skeleton —
   claim via `in-progress` label, branch `claude/course-<n>-<slug>`, draft
   PR, comment back).
5. Corpus-refresh flow: a `corpus-moved` issue names the new ref; a scoped
   revise pass regenerates only the lessons whose cited files changed.
6. xAPI statement export + progress sync endpoint (the LMS bridge), then the
   commercial layer (gated courses, orgs, completion reporting).
