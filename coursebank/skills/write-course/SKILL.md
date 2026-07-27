---
name: write-course
description: Generate an interactive training course from a source corpus (a repo, docs site, or policy set) as a beautiful, installable, offline-first PWA — modules of single-column lessons with objectives, diagrams, exercises, checkpoint quizzes, tracked progress, and a completion certificate, in a chosen instructor's voice. Use when the user wants to "create a course", "build an onboarding course for <repo>", "turn these docs into a course", "make a training course on <topic>", or process the CourseBank build queue. Triggers include "coursebank", "write a course", "onboarding course", "training course", "course from this repo".
---

# write-course

CourseBank is the third member of the BankKit family. Where BookBank turns a
topic into a book, CourseBank turns a **source corpus** — a repo, a docs
export, a policy set — into a **course**: something the learner *does*, not
just reads. Every course is a **phone-first, installable PWA** that works
fully offline after one visit, tracks progress locally, and unlocks a
completion certificate. The value is **accurate, corpus-grounded teaching**
in a **beautiful, subject-fitting design** with **checkpoints that actually
test the objectives**.

CourseBank **assumes the bookbank plugin is installed** from the same kit
marketplace — it reuses BookBank's craft skills directly: `book-diagrams`
(the shared SVG grammar), `book-exercises` (the exercise/quiz kit the
progress runtime scores), `2d-concept-animations`, `svg-animations`,
`typeset-cover`, and the image-slot pattern.

## Arguments

- `/write-course` (no arg) — **process the queue.** Scan
  `<root>/courses/*/course.json`:
  - any course with `"status": "requested"` → ingest, design, and build it fully;
  - any course with `"status": "revising"` → revise it in place per
    `revisionNotes`; do not rebuild from scratch;
  - any lesson with `"status": "requested"` in a built course → generate just
    that lesson and wire it in.
  Report what you built. If the queue is empty, ask for a corpus or topic.
- `/write-course <corpus-or-topic>` — create a new course and build it. A URL
  or path is the corpus ("an onboarding course for github.com/org/repo"); a
  bare topic gets a web-research corpus like a BookBank book, recorded as
  `source.kind: "web"`. Honor an inline voice ("…in the Operator's voice") by
  matching an instructor (below).
- `/write-course expand "<lesson>" in <course>` — add and generate one lesson
  in an existing course.

## Where things live

- **Data root — first match wins:**
  1. `$COURSEBANK_ROOT`, if set.
  2. The current directory, if it looks like a content-repo clone — it has a
     `courses/` directory, a `catalog.json`, or a git remote whose URL
     contains `sunprema/courses` (or `$COURSEBANK_COURSES_REPO`, if set).
  3. `~/coursebank`, as a fallback.
- **Courses:** one folder per course under `<root>/courses/<course-id>/`:
  ```
  <root>/courses/zod-onboarding/
    course.json                    # the manifest (you read + update this)
    curriculum.json                # the distilled teaching artifact (below)
    index.html                     # course home: hero, syllabus, progress, resume, install
    lessons/01-01-schemas.html     # MM-NN-slug: module 01, lesson 01
    lessons/01-checkpoint.html     # module checkpoint (mostly quiz)
    cheatsheet.html                # dense printable quick reference
    certificate.html               # unlocks from local progress
    manifest.webmanifest           # this course's PWA identity
    sw.js                          # service worker (template from this skill, stamped)
    offline.json                   # generated precache list (gen_offline_manifest.py)
    icons/icon-192.png icons/icon-512.png
    assets/course.css course.js    # bespoke stylesheet + sw registration/install UI
    assets/exercises.css→(in course.css) exercises.js   # the bookbank exercise kit
    assets/vendor/course-progress.js  # the progress runtime (vendored)
    assets/img/*                   # local images (offline)
    cover.webp                     # gallery cover (typeset-cover or image slot)
  ```
- **Instructors & themes — 3-tier cascade, first match wins:**
  1. `<root>/instructors|themes/<id>.json` — per-clone override.
  2. `~/.claude/coursebank/instructors|themes/<id>.json` — per-user.
  3. `${CLAUDE_PLUGIN_ROOT}/defaults/instructors/<id>.json` — built-ins:
     `the-mentor`, `the-socratic`, `the-operator`.

  An **instructor** is `{ "name", "tagline", "voice" }` — the
  persona-equivalent; `course.json`'s `instructor` is the id, absent for a
  clear friendly teacher, or `"auto"` (resolve once at build time to the
  best fit for subject + audience, write the id back, never re-roll). A
  **theme** uses the same shape as BookBank themes (tokens + fonts +
  background + mood); CourseBank bundles none in v1 — absent means a
  neutral, legible house look, or copy a BookBank theme into
  `<root>/themes/`.

## course.json schema

```json
{
  "id": "zod-onboarding",
  "title": "Zod: From Schema to Safety",
  "topic": "the Zod validation library",
  "source": {
    "kind": "repo",
    "url": "https://github.com/colinhacks/zod",
    "ref": "b0e9b71",
    "include": ["README.md", "docs/**", "packages/zod/src/**"]
  },
  "audience": "TypeScript developers joining a team that uses Zod",
  "instructor": "the-mentor",
  "theme": "swiss",
  "status": "ready",
  "created": "2026-07-27",
  "summary": "Hands-on onboarding: schemas, parsing, refinement, and inference, from the library's own source.",
  "modules": [
    {
      "id": "foundations",
      "title": "Foundations",
      "lessons": [
        {
          "id": "schemas",
          "title": "Schemas as Types",
          "file": "lessons/01-01-schemas.html",
          "status": "ready",
          "source": "claude",
          "objective": "Declare a schema and infer its static type with z.infer."
        }
      ],
      "checkpoint": { "id": "ck-foundations", "file": "lessons/01-checkpoint.html", "status": "ready" }
    }
  ],
  "certificate": { "title": "Certificate of Completion — Zod Onboarding" },
  "images": [],
  "notes": "Team uses Zod 4 with tRPC; emphasize inference.",
  "revisionNotes": ""
}
```

Field rules (BookBank conventions carry over):

- `status` (course): `requested` → `ready` once every lesson + checkpoint is
  written and the PWA layer verifies. `revising` → `ready` once revisions are
  applied. `building` only if you stop midway.
- `source`: `kind` is `repo` | `docs` | `files` | `web`. For `repo`, **pin
  `ref` to the commit you ingested** — it's what makes claims citable and
  staleness diffable. `include` globs scope the ingest.
- **Every lesson has an `objective`** — one sentence, learner-can-now-do
  form. Objectives are the pedagogical contract: each one must be tested by
  a checkpoint question (see Checkpoints).
- `lessons[].source`: `user` or `claude`; **never drop or reorder user
  lessons.**
- `lessons[].file`: `lessons/MM-NN-slug.html`, module-major order.
  Checkpoints are `lessons/MM-checkpoint.html` with their own id.
- `instructor` / `theme` / `created`: durable request fields — preserve on
  rebuilds; resolve `"auto"` exactly once.
- `notes` (while `requested`) and `revisionNotes` (while `revising`) are the
  freeform briefs; clear each once applied.

## Teaching artifact — `curriculum.json` (required on every build)

The `research.json` analog: the durable, voice-free record the lessons are
rendered from. Same rules — **nothing appears in a lesson that isn't in the
artifact**; distill, don't dump (~100–300 KB max); voice-free by
construction; keyed by lesson id.

```json
{
  "schema": 1,
  "researched": "2026-07-27",
  "sources": [
    { "id": "src-readme", "kind": "corpus", "path": "README.md", "ref": "b0e9b71" },
    { "id": "src-zod-docs", "kind": "web", "url": "https://zod.dev/api", "title": "Zod API docs", "accessed": "2026-07-27" }
  ],
  "structure": {
    "rationale": "Why these modules and lessons, in this order — 2–4 sentences.",
    "audience": "TypeScript developers new to Zod."
  },
  "lessons": {
    "schemas": {
      "researched": "2026-07-27",
      "objective": "Declare a schema and infer its static type with z.infer.",
      "claims": [
        { "text": "z.infer<typeof schema> yields the schema's static TypeScript type.",
          "sources": ["src-readme"] }
      ],
      "snippets": [
        { "lang": "ts",
          "code": "const User = z.object({ name: z.string() });\ntype User = z.infer<typeof User>;",
          "note": "verified against zod@4.0", "sources": ["src-readme"] }
      ],
      "pitfalls": ["Calling .parse on unknown input throws; use .safeParse in handlers."],
      "quizBank": [
        {
          "q": "A handler receives untrusted JSON. Which call avoids a try/catch?",
          "options": [
            { "text": ".parse", "why": "parse throws ZodError on invalid input." },
            { "text": ".safeParse", "correct": true, "why": "Correct — safeParse returns a discriminated result." },
            { "text": "z.infer", "why": "infer is a type-level operator; it never runs." }
          ],
          "tests": "schemas"
        }
      ]
    }
  },
  "volatile": ["zod version and API names", "package layout"]
}
```

CourseBank-specific rules:

- **Corpus sources cite `path` + `ref`**, not just a URL — a claim traceable
  to a file at a commit is what makes the corpus-refresh flow (roadmap)
  possible. Web sources supplement; the corpus is primary when it exists.
- **`quizBank` lives here, not improvised in the page.** Each entry names the
  lesson objective it `tests`. Checkpoint pages draw from the module's
  lessons' quizBanks; this is how "every objective has a question that tests
  it" stays checkable.
- Every claim cites ≥1 source id; unverifiable claims stay out or carry
  `"sources": []` explicitly.

## Procedure (building a course)

1. **Read `course.json`.** Note topic, source, audience, instructor, seed
   lessons (`source: "user"` — required), and `notes`.
2. **Load the instructor** through the cascade and write in that `voice` —
   voice only. Resolve `"auto"` once (list all tiers, pick the genuine fit
   for subject + audience + notes, write the id back, say why in one line).
   **Load the theme** the same way — look only.
3. **Ingest the corpus.** For `kind: "repo"`: shallow-clone (or fetch the
   tree) at `source.ref` — if `ref` is unset, resolve the default branch's
   HEAD and **write the commit back to `source.ref`**. Read what `include`
   scopes: READMEs, docs, the load-bearing source files, examples, tests
   (tests are excellent teaching material — they show intended use). For
   `docs`/`files`: read the export. For `web`: research like a BookBank
   book. Supplement any corpus with targeted web research for context the
   corpus assumes (background concepts, ecosystem, current best practice).
4. **Design the syllabus.** 2–5 modules, each 2–5 lessons, ordered so each
   builds on the last; every lesson gets a one-sentence **objective** in
   learner-can-now-do form. Include every user seed lesson. A lesson teaches
   **one thing the learner does**, not one chapter of prose — if you can't
   write its objective, it's not a lesson yet. One checkpoint per module.
5. **Write `curriculum.json` before any prose** — sources, rationale, and a
   per-lesson entry of objective/claims/snippets/pitfalls/quizBank. Lessons
   are then written *from* the artifact; if writing reveals a gap, record
   first, then use.
6. **Build the shell:** `assets/course.css` (theme `:root` tokens + the
   layout below + **append `diagram-kit.css`** from the bookbank plugin's
   `book-diagrams` skill verbatim, and the exercise kit's `exercises.css`),
   `assets/course.js` (PWA wiring, below), the vendored
   `assets/vendor/course-progress.js` and `assets/exercises.js`, the PWA
   files (below), and `index.html` — hero (title, audience, summary,
   instructor byline, cover slot), the syllabus as module groups of
   `data-lesson-link` rows, a `.course-progress` bar, a `.course-resume`
   link, and a `.course-install` button.
7. **Write the lessons** from the artifact — layout and per-page contract
   below. Then each module's **checkpoint** and the **cheatsheet** (dense,
   printable) and **certificate.html**.
8. **Generate icons** — a lettermark on the theme's background (the
   typeset-cover aesthetic, shrunk): render `icons/icon-192.png` and
   `icons/icon-512.png` (512 must read as maskable — keep the mark inside
   the central 80%). Any local tooling works (the visual-QA Playwright
   install can screenshot an SVG; Pillow can compose one); no network fonts.
   Rendering with a raw headless Chromium works too — but pass
   `--force-device-scale-factor=1` or a retina host renders at 2× and the
   screenshot crops to the top-left quadrant, and use absolute centering in
   the icon page (flex centering has misrendered under headless screenshots).
9. **Stamp the PWA:** run
   `python3 "$CLAUDE_PLUGIN_ROOT/skills/write-course/scripts/gen_offline_manifest.py" <course-dir>`
   as the **last** build step — it writes `offline.json` and stamps `sw.js`'s
   cache name with a content hash. Re-run it after *any* later file change.
10. **Update `course.json`** — files + statuses `ready`, `summary`, resolved
    `source.ref`, image slots in `images[]`.
11. **Verify** (section below), then give the course a `cover.webp` — for a
    type-led theme use the bookbank `typeset-cover` skill; otherwise declare
    a cover-art image slot (id containing `cover`, `concept: null`) exactly
    like BookBank.

## Layout — phone-first, single column, installable

Courses do **not** use BookBank's two-page spread. Training happens on
phones; the layout is a **single scrolling column**, mobile-first:

- Readable measure: content column `max-width: 68ch`, centered, generous
  vertical rhythm; type scales up on desktop rather than reflowing into
  columns.
- **Sticky course bar** on every page: course title (links home), the
  module/lesson position, and a slim `.course-progress` bar. This is the
  PWA's persistent chrome.
- **Lesson page structure:** the objective as an unmissable callout at the
  top ("After this lesson you can: …"), the body (prose, code, diagrams,
  figures, at most one widget/animation where interaction genuinely earns
  it), **one exercise or quiz at the end** (the exercise kit's markup), then
  the `.lesson-done` button, then prev/next nav.
- **Nav contract (kept from BookBank):** visible prev/next/home links with
  `rel="prev"` / `rel="next"` / `rel="home"` on every page; chain
  `index.html → lesson 01-01 → … → MM-checkpoint → … → cheatsheet.html →
  certificate.html`. Costs nothing, keeps every Bank's pages
  machine-walkable.
- **Anchor contract (kept):** stable, page-unique `data-anchor` slugs on
  annotatable blocks; never churn existing ones on revision.
- **Checkpoint pages** are mostly quiz: 3–6 questions drawn from the
  module's `quizBank`, each `tests`-ing a distinct objective — together
  covering **every objective in the module**. Use the quiz markup only (the
  runtime scores first-answer); open with one line of framing in the
  instructor's voice.
- **Certificate page:** `body data-certificate`; locked state explains
  what's left (list the syllabus with done-marks); unlocked state
  (`body.cb-unlocked`) shows a typeset certificate — course title, learner
  name (`data-cert-name` input / `data-cert-name-out` echo), date
  (`data-cert-date`), instructor byline — print-styled (`@media print`
  hides chrome).
- Exercise blocks: reuse the bookbank kit verbatim (blur-reveal answers,
  `.quiz` / `.quiz-opt` with `data-correct` + `data-why`). Scroll pages
  relax the no-reflow constraint, but keep the kit's behavior anyway —
  consistency across Banks, and the runtime's scoring watches this markup.
- Theme tokens: same shape and discipline as BookBank — emit the theme's
  tokens/fonts in `:root {}`, reference variables everywhere, no hardcoded
  hex in the body of the stylesheet. Follow the mood; keep it legible.
- **Self-contained & offline:** all CSS/JS/assets local and relative; no
  CDNs, no network fonts. The course must render from `file://`.

### Progress runtime — wiring (contract in `runtime/README.md`)

Vendor and load on **every page**, after `exercises.js`:

```html
<script src="../assets/exercises.js"></script>
<script src="../assets/vendor/course-progress.js"></script>
```

Every page's `<body>` carries `data-course="<id>"` and `data-lessons="<the
full ordered id list from course.json — lessons and checkpoints>"`. Lesson
and checkpoint pages add `data-lesson="<id>" data-path="lessons/MM-NN-slug.html"`.
Style the runtime's classes in `course.css`: `.cb-hidden{display:none}`,
`.cb-done` treatments for syllabus rows and the button, and the
certificate's locked/unlocked states keyed off `body.cb-unlocked`. **The
`data-lessons` list must be identical on every page** — generate it once
from `course.json`, paste everywhere.

## The PWA layer

Three files at the course root make the course installable and
offline-complete; two are templates in this skill:

1. **`manifest.webmanifest`** — copy
   `${CLAUDE_PLUGIN_ROOT}/skills/write-course/assets/manifest.webmanifest`
   and fill the `__PLACEHOLDERS__`: title, a short name that fits under a
   home-screen icon (≤ 12 chars), summary, and the theme's `--bg` for both
   colors. Link it from every page's `<head>`
   (`<link rel="manifest" href="manifest.webmanifest">` — `../` from
   `lessons/`) along with `<meta name="theme-color">` and the standard
   viewport meta.
2. **`sw.js`** — copy `assets/sw.js` from this skill **verbatim**; never
   hand-edit the `CACHE_NAME` line (the generator stamps it). It precaches
   the whole course from `offline.json` on install — one visit online,
   fully usable in airplane mode after.
3. **`offline.json`** — generated; never write it by hand.

Registration + install UI live in `assets/course.js`:

```js
// Register the worker — HTTPS/localhost only; file:// has no SW, and that's
// fine: the course still works from file://, it just isn't installable there.
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  // From a lessons/ page this resolves one level up — always register the
  // course root's worker with the course root as scope:
  var root = location.pathname.replace(/(lessons\/)?[^/]*$/, '');
  navigator.serviceWorker.register(root + 'sw.js', { scope: root });
}
// Install button: hidden until the browser offers installability.
var deferred = null;
window.addEventListener('beforeinstallprompt', function (e) {
  e.preventDefault();
  deferred = e;
  document.querySelectorAll('.course-install').forEach(function (b) { b.classList.remove('cb-hidden'); });
});
document.addEventListener('click', function (e) {
  var b = e.target.closest && e.target.closest('.course-install');
  if (b && deferred) { deferred.prompt(); deferred = null; b.classList.add('cb-hidden'); }
});
```

The `.course-install` button starts with class `cb-hidden` in the markup (no
dead-looking UI on iOS Safari, which has no `beforeinstallprompt` — there,
installation is Share → Add to Home Screen, and the manifest still makes the
result standalone).

## Images & diagrams

BookBank's rules carry over wholesale: **inline SVG first** for anything
explanatory, using the shared `diagram-kit.css` grammar (already appended to
`course.css` in step 6 — patterns in the bookbank `book-diagrams` skill);
**image slots** for real/illustrative art you can't draw — same `images[]`
schema, same placeholder markup and `.img-slot` CSS, same `.webp`
declaration, filled with bookbank's `place_image.py`. Scroll pages don't
have the fixed-height overflow hazard, but keep the aspect-box + `max-height`
discipline anyway — an unconstrained image is still a bad phone experience.
One strong illustration per lesson at most.

## Expanding a lesson / revising a course

Both follow BookBank's paths, adjusted for courses:

- **Expand:** research the one lesson (corpus first), record its
  `curriculum.json` entry **including its objective and ≥1 quizBank
  question**, write `lessons/MM-NN-slug.html`, wire it into the syllabus on
  `index.html`, the prev/next chain, its module's checkpoint (the new
  objective needs a question), and — critically — **update the
  `data-lessons` list on every page**, then re-run `gen_offline_manifest.py`.
- **Revise:** read what's there first; treat `revisionNotes` as the brief;
  re-research only what the notes touch (corpus at the pinned ref, or bump
  `source.ref` deliberately and note which lessons the diff touches);
  keep untouched lessons, the theme, and every learner-visible id stable —
  **lesson ids are progress keys**: renaming one orphans every learner's
  recorded progress for it, so never rename on revision. Mirror changes
  into `curriculum.json`, clear `revisionNotes`, set `ready`, re-run the
  generator.

## Verification (before marking `ready`)

1. **From `file://`:** every page renders; nav chain walks end to end both
   directions; exercises reveal and quizzes answer; `.lesson-done` toggles;
   the syllabus shows done-marks and the progress bar moves; the resume
   link goes to the last lesson visited; the certificate unlocks only after
   every lesson is done and checkpoints pass (use
   `courseProgress.export()` in the console to inspect, `reset()` to
   clean up after testing).
2. **As a PWA:** serve the course root over HTTP
   (`python3 -m http.server -d <course-dir> 8137`), open it, confirm the
   worker installs and `offline.json`'s count caches (DevTools →
   Application). Then **DevTools → Network → Offline** and hard-reload:
   every page, image, and script must load. This is the airplane test —
   non-negotiable.
3. **Phone width:** 390px viewport — no horizontal scroll, readable type,
   tappable targets. The bookbank `book-visual-qa` skill's browser pass
   works on any page set; use it for the sweep. Caveat when driving raw
   headless Chromium instead: it enforces a ~500px minimum window width, so
   a `--window-size=390,…` screenshot is silently a crop of a 485px
   viewport — for a true phone check, load the page in a 390px-wide
   `<iframe>` (with `--allow-file-access-from-files`) and compare the inner
   document's `scrollWidth` to its `clientWidth`.
4. `data-lessons` identical on every page (grep it); every objective in
   `course.json` matched by a `tests` entry in some checkpoint's questions;
   `gen_offline_manifest.py` run **after** the last file change (run it
   again if in doubt — it's idempotent).

## Report

Say what you built: module/lesson count and the syllabus shape, which
instructor and why (if `auto`), the corpus ref ingested, quiz/checkpoint
coverage ("every objective tested: yes"), the offline verification result
(files precached, airplane reload passed), and what's left (unfilled image
slots, cover status).

## Privacy / locality note

Everything stays local: courses are files on disk; progress lives in the
learner's browser storage and never leaves the device (the `events` queue is
inert until a sync layer exists — roadmap). Corpus ingestion happens at
build time; the generated course has no network dependencies.
