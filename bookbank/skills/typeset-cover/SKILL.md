---
name: typeset-cover
description: Design a book's cover as pure typography in its own theme and render it to cover.webp — no image model, no art round-trip. Use when a book needs a cover, when the gallery is showing a gradient fallback, when a "cover art needed" slot is still empty, or when the user wants to restyle an existing cover. Triggers include "typeset a cover", "make a cover for <book>", "this book needs a cover", "the shelf shows a gradient for <book>", "redo the cover".
---

# typeset-cover

Most BookBank themes are **type-led** — `swiss`, `binder`, `blueprint`,
`phosphor`, `codex`, `circuit`, `manga`, `poster` carry their identity in rules, numerals,
spacing and one disciplined accent, not in illustration. For those books the
best cover isn't a picture of the subject; it's the book's own design system,
set large. This skill composes that cover as HTML in the book's theme and
renders it to `cover.webp`.

The payoff is that the book **ships complete**. `build-library.py`'s
`cover_rel()` resolves a book's cover in this order:

```
cover.{webp,png}              <-- this skill writes here; wins over everything
assets/img/cover-art.{webp,png}
assets/img/cover.{webp,png}
(none)  -> deterministic gradient + the title in plain text
```

So a typeset cover takes precedence over any image slot, and the gallery
never falls back to a gradient. No image agent, no `image-request` issue, no
`art-approved` label, no waiting.

## When NOT to use this

Reach for the normal image-slot pipeline instead when the book genuinely wants
a *picture*: a biology book that needs a cell, a hardware book that wants a
photographed board, anything where the subject is visual. Typeset covers are
for books whose subject is an idea. If in doubt, ask which the user wants —
this skill and the art pipeline are alternatives, not a sequence.

## Arguments

- `/typeset-cover <book-id>` — compose and render a cover for that book.
- `/typeset-cover <book-id> --replace-slot` — additionally remove the book's
  unfilled cover **image slot** (see *Image slots*, below).
- `/typeset-cover <book-id> --width 2000` — render wider (default 1600).
- No argument: if exactly one book is in scope (the cwd is a book folder, or
  the conversation is clearly about one book), use it; otherwise list the
  books whose cover is currently a gradient and ask which.

## Procedure

1. **Resolve the root and book dir** using `write-book`'s cascade
   (`$BOOKBANK_ROOT` → cwd if it looks like a content-repo clone → `~/bookbank`),
   then `<root>/books/<book-id>/`.

2. **Read `book.json`** — `title`, `topic`, `summary`, `concepts` (for a count),
   `persona`, `theme`. **Resolve the theme** through the same 3-tier cascade
   `write-book` uses, and read its `tokens`, `fonts`, `background` and — most
   importantly — its `mood`.

3. **Read the book's own `index.html` cover hero**, if it exists. The book has
   already made typographic decisions (kicker wording, how the title breaks
   across lines, which word takes the accent). A cover that contradicts the
   book's first page looks like it belongs to a different book. Match it.

4. **Compose the cover HTML** in a scratch dir — **never inside the book
   folder**. `build-library.py` syncs the whole book directory to the public
   site, so a stray `cover-src.html` would be published. Use
   `${TMPDIR:-/tmp}/bookbank-cover-<book-id>/cover.html`. Start from
   `assets/cover-template.html` in this skill and follow *Design rules* below.

5. **Render:**
   ```
   ${CLAUDE_PLUGIN_ROOT}/skills/typeset-cover/scripts/render-cover.sh \
       "<scratch>/cover.html" "<book-dir>"
   ```
   It rasterizes at 2× and downsamples with LANCZOS (large flat type aliases
   badly at 1×), then encodes WebP q90 at exactly 16:10 — the shelf card's
   aspect, so nothing is cropped. Needs Chrome/Chromium and either Pillow or
   `cwebp`; it fails loudly with an install hint if either is missing.

6. **Look at what you made.** Read the rendered `cover.webp` back with the
   Read tool and judge it as a cover, not as code output. This is not
   optional — the whole skill is a visual one, and a composition bug (a title
   colliding with the foot rule, an accent that vanished into the background)
   is invisible in the source and obvious in the image. Fix and re-render.

7. **Check it survives being small** — see *Legibility at card size*.

8. **Image slots** — if the book has an unfilled cover slot (an `images[]`
   entry whose `id` contains `cover`, `concept: null`, and whose `file` is
   **not on disk**), the typeset cover now supersedes it. Two things follow:
   - The gallery already ignores the slot (root `cover.webp` wins), but
     `validate_book.py` still warns about it, and the book's own `index.html`
     still shows a dashed "Cover art needed" placeholder to readers.
   - With `--replace-slot`, remove that `images[]` entry **and** its
     `<figure class="img-slot">` from `index.html`, then re-check that the
     cover hero still composes well without it.

   **Never remove a slot whose file exists on disk** — that is art someone
   generated and placed. If the user wants the typeset cover to replace real
   art, make them say so explicitly.

9. **Report** the output path, dimensions, file size, and what design decisions
   you made — plus whether the slot was left in place or removed.

## Design rules

**The theme is the design; the book is the content.** Paste the theme's
`tokens` and `fonts` into `:root` verbatim and paint the stage from its
`background.css`. Never invent a color. A cover that uses a palette the book
doesn't use is worse than a gradient, because it looks like a mistake rather
than a default.

**Honor the theme's structural signatures.** The `mood` field of the newer
themes spells out what makes the look itself — reproduce those on the cover,
because they are the strongest identity you have:

| Theme | Cover motif that carries the identity |
|-------|----------------------------------------|
| `swiss` | Thick top rule, huge tight-tracked title flush left, one red word, vast whitespace, optional giant numeral |
| `binder` | Cream leaf with the spiral punch-holes down one edge, ruled hairlines, red-pen accent, a hand-labelled tab |
| `blueprint` | Cyan grid ground, title as a drafting annotation, dimension lines and a corner title-block |
| `phosphor` | Scanlines, mono type, a `$ ` prompt before the title, a blinking-cursor block (render it solid — a screenshot catches one frame) |
| `codex` | Centred classical title page, generous margins, rules above and below, a drop-cap or printer's ornament |
| `circuit` | Copper hairline frame with via dots at the corners, silkscreen reference designator, right-angled traces |
| `riso` | Misregistered second ink behind the title, halftone dot field, chunky bars |
| `aurora` | Aurora gradient wash, one frosted glass panel holding the title, gradient text fill |
| `arcade` | Neon horizon and perspective grid, condensed uppercase title with a single halo, `LEVEL 01` styling |
| `chalkboard` | Chalk hand for the title on slate, a hand-drawn underline, faint eraser smudge |
| `observatory` | Starfield, luminous serif title, one constellation line |

**Composition.** A cover is a hierarchy of three or four elements, not a
paragraph. Kicker, title, one clarifying line, one foot line — and the title
should dominate hard enough that at a glance you read it and nothing else.
Asymmetry beats centring for every theme except `codex`. Leave much more empty
space than feels comfortable; the most common failure is a cover that is
merely *full*.

**Say less than the book does.** The card already shows the title and summary
as text beneath the cover, so the cover doesn't need to explain anything. One
short clarifying line, at most. Never paste the `summary` in — it is written
for a different job.

**Size everything in `vw`/`vh`, never `px`.** The stage *is* the render
viewport, so vw-sized type makes the composition resolution-independent and
`--width` becomes a free parameter. A px-sized title silently changes
proportion when the render size changes.

**No network, ever.** System font stacks only (the same ones the themes
declare), no `@font-face`, no remote images, no CDN. The renderer runs from
`file://` and a missing resource fails silently into a wrong-looking cover.

### Legibility at card size

Shelf cards are `minmax(300px, 1fr)` — so a 1600px-wide cover is displayed at
roughly **320px**, a 5× reduction. That is the size the cover actually has to
work at:

- The title should be **≥ 5vw** (≈80px at 1600 → ~16px on the card).
- Nothing that matters should be below **1.2vw** (≈19px → ~4px on the card:
  a grey smudge). Fine print is decoration at card size — use it as texture,
  never to carry meaning.
- Hairlines thinner than **0.1vw** disappear entirely when downscaled. The
  theme's structural rules need weight to survive.
- **Test it:** after rendering, view the WebP at ~320px wide and confirm the
  title still reads and the composition still has a shape. If it turns to
  mush, the type is too small or the layout is too busy.

## Verification

Before reporting done:

- `cover.webp` exists at the book root, is 16:10, and is a sane size (a
  typeset cover is usually 20–120 KB; multi-MB means something went wrong).
- You have **looked at it** with the Read tool (step 6) and it reads as a
  cover at full size and at card size.
- `validate_book.py <book-dir>` still passes — if you used `--replace-slot`,
  confirm the removed `<figure>` left valid HTML and one fewer warning.
- The book's `index.html` still renders correctly from `file://` if you
  touched it.

## Report

Give the user: the path and dimensions, the design decisions you made (which
theme signatures you used, what you chose to leave out), whether the cover
slot was removed or left, and how to redo it — the composed HTML stays in the
scratch dir, so tweaking and re-rendering is one command.
