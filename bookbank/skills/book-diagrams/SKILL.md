---
name: book-diagrams
description: Draw explanatory diagrams for a BookBank book as theme-tokened inline SVG, using one shared visual grammar across the whole library. Use when a concept needs a figure, when a page is a wall of prose, or when existing diagrams look inconsistent from chapter to chapter. Triggers include "add a diagram", "draw this", "visualize this concept", "this page needs a figure", "make a flow chart / timeline / sequence diagram" for a book.
---

# book-diagrams

A diagram is the highest-value thing you can add to a technical page, and the
easiest to do inconsistently. The JWT book got six good SVGs — but the class
vocabulary was invented while writing them, so the next book would have
invented a slightly different one, and the library would drift into a dozen
private dialects.

This skill fixes the grammar: **one class vocabulary, one coordinate space, one
set of proportions**, all driven by theme tokens so a diagram re-skins with the
book and never needs editing.

## When a diagram is the right answer

Inline SVG is the default for anything **explanatory** — flows, sequences,
timelines, state machines, comparisons, layered stacks. It is crisp at any
size, weighs nothing, needs no files, and inherits the theme.

Do not reach for it when:

- The content is **tabular** — more than ~4 states, ~6 messages, or ~5 rows of
  comparison reads better as a `<table>`. A cramped diagram is worse than an
  honest table.
- The visual needs to be **photographic or illustrative** — that is an image
  slot (see `write-book`) or a typeset cover.
- The thing is **interactive** — a parameter to drag, a process to watch
  converge. That is a canvas widget (see `2d-concept-animations` and
  `widgets/README.md`), not a diagram.

One strong diagram per concept page. Two is usually one too many.

## Procedure

1. **Install the vocabulary once per book.** Append
   `assets/diagram-kit.css` (in this skill) to the book's `assets/book.css`,
   if its classes aren't there already. It is pure token references — no
   hardcoded colors — so it works in every theme.

2. **Pick the pattern** from `references/patterns.md`: flow, before/after,
   timeline, sequence, layered stack, state machine, or comparison. Each is a
   tested, copy-pasteable snippet. Start from the closest one rather than from
   an empty `<svg>`.

3. **Adapt it to the content**, holding the conventions below.

4. **Render and look at it.** Every diagram, every time — see *Verification*.
   Geometry bugs are invisible in markup and glaring on screen; the shipped
   patterns themselves had a label collision and a set of missing labels that
   only a render exposed.

## The conventions

**One coordinate space per book: `viewBox="0 0 560 H"`.** Width stays 560
everywhere so stroke weights and label sizes are visually identical from page
to page; only the height varies (110–220). Past ~240 tall, a diagram crowds its
column — split it into two.

**Colors come only from the classes.** `.stroke`, `.stroke-soft`,
`.stroke-red`, `.fill-soft`, `.fill-ink`, `.fill-red`, and the text classes
`.big`, `.red`, `.dim`, `.mono`, `.on-ink`. Never write a hex value or a
`style=` attribute into a diagram: the moment you do, the book cannot be
re-skinned, which is the one thing themes exist for.

**The accent marks exactly one idea.** The attack, the failure, the layer this
chapter is about, the answer. A diagram with three red things has none.

**Never let color carry meaning alone.** Anything marked in accent also gets a
label — colorblind readers, greyscale print, and downscaled thumbnails all lose
hue. `.red` on a `<text>` plus the word "attack" beats red alone.

**Arrowheads are drawn paths, not markers.** Three points, 8 long by 4
half-height, sharing the arrow's stroke class. SVG markers need per-color
`<defs>` and silently break on re-skin.

**`<title>` first, always,** referenced by `aria-labelledby`. It is the
accessible name and the fallback when the SVG doesn't paint. The `<figcaption>`
is a different job — it says what the reader should *conclude*, not what the
picture contains.

**Integer coordinates.** Sub-pixel positions blur hairlines.

**Label baselines sit at box `y` + 21** for a 32px box — that optically centres
an 11px label. Full sizing table at the foot of `references/patterns.md`.

## Verification

Render before you believe it. The cheapest loop, from a book folder:

```bash
"$CHROME" --headless --disable-gpu --hide-scrollbars \
  --window-size=1200,900 --virtual-time-budget=3000 \
  --screenshot=/tmp/diagram-check.png "file://$PWD/concepts/NN-page.html"
```

then read the PNG. Check specifically for: labels colliding with boxes or with
each other (the most common bug by far), text overflowing its container, arrows
that stop short of or overshoot their target, and whether the thing still reads
at a glance.

Then run `/book-visual-qa` on the book — an over-tall SVG shoves the whole
spread, and that check catches it.

## Report

Say which pattern you used, what the accent marks, and confirm you rendered and
looked at it. If you chose a table over a diagram, say why — that is a design
decision worth surfacing, not a failure to draw.
