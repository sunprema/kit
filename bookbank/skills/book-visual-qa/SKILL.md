---
name: book-visual-qa
description: Open every page of a BookBank book in a real browser and report layout bugs that file-level validation cannot see — orphaned headings, horizontal overflow, clipped or oversized images, empty columns. Use before publishing a book, after a revision, when a page "looks wrong" but validate_book.py passes, or when checking how a book reads on a phone. Triggers include "check the layout", "visual QA", "does this book look right", "screenshot every page", "is it broken on mobile".
---

# book-visual-qa

`validate_book.py` is **structural**: it reads files and checks contracts —
charset, nav `rel`s, self-containment, the pager's fold arithmetic. It is fast,
deterministic, and completely blind to **layout**. It will happily pass a book
whose heading is stranded alone at the foot of a column, whose image overflows
its box and shoves the facing page, or whose spread scrolls sideways on a phone.

That is not hypothetical. The JWT book passed `validate_book.py` clean while its
cover page had "Contents" orphaned at the foot of the left column with its list
on the right — found only because someone took a screenshot. This skill makes
that check systematic.

**The two are complements, not alternatives.** Run `validate_book.py` for
contracts, this for appearance. Neither subsumes the other.

## Arguments

- `/book-visual-qa <book-id>` — check every page at desktop and mobile.
- `/book-visual-qa <book-id> --out <dir>` — keep the screenshots somewhere you choose.
- No argument: use the book in context, or ask which.

## Procedure

1. **Resolve the book dir** using `write-book`'s root cascade.

2. **Run the checker:**
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/book-visual-qa/scripts/qa-book.py <book-dir>
   ```
   It opens `index.html`, every `concepts/*.html`, and `cheatsheet.html` in
   headless Chrome at both widths, measures the rendered geometry, and writes a
   screenshot per page per width. `--json` gives machine-readable output;
   `--no-screenshots` skips the images when you only want findings.

3. **Read the findings** (severities below). Errors are unambiguous bugs.
   Warnings are judgement calls — look at the screenshot before deciding.

4. **Look at the screenshots.** This is a required step, not a nicety. The
   checker measures what it knows how to measure; it cannot tell you the page is
   ugly, the type is too small, or the diagram is confusing. Read a few with the
   Read tool — always the cover, the cheatsheet, and any page the checker
   flagged.

5. **Fix, then re-run.** The re-run is the proof. Do not report a fix you
   have not seen the checker accept.

## What it checks

| Finding | Severity | What it means |
|---------|----------|---------------|
| `page-overflow` | error | The document scrolls horizontally. Wide content must scroll inside its own `overflow-x:auto` box — never the page. |
| `broken-image` | error | An `<img>` failed to load and is **not** an unfilled image-slot placeholder (those legitimately 404 until art is dropped). |
| `orphan-heading` | warning | A heading whose following block starts in the **next** column — stranded at a column foot, divorced from what it introduces. |
| `escapes-column` | warning | An element extending past the viewport with no scrollable ancestor: it is clipped with no way to reveal it. |
| `oversized-image` | warning | An image rendering taller than ~62% of the viewport, which shoves the rest of the spread. |
| `sparse-tail` | info | The last column is nearly empty. Often fine; sometimes a page that ends awkwardly. |

Exit status is 1 only for error-severity findings, mirroring
`validate_book.py`'s warning tier.

## Fixing an orphaned heading

Almost always one line, and it belongs in every book's `book.css`:

```css
/* A heading must never be the last thing in a column. */
h1,h2,h3,h4{ break-after:avoid; }
```

This cleared all three orphans in the JWT book in one edit. If a specific
heading still strands — usually because the block after it is tall and carries
`break-inside:avoid` — wrap the pair in a `<section>` and give **that**
`break-inside:avoid`, which moves them together:

```css
.toc-block{ break-inside:avoid; }   /* keeps "Contents" with its list */
```

## Two browser quirks the script handles for you

Both were discovered the hard way; do not re-derive them.

1. **`--dump-dom` honors `--window-size` width but not height.** Ask for 900 and
   the viewport is ~813 — about 87px goes to browser chrome. That silently
   shortens every column, which pushes blocks into the next column and
   **manufactures orphan findings for a layout no reader will ever see**. The
   script calibrates once per size and compensates. If you write your own probe,
   you must do the same or your measurements are fiction.

2. **Headless Chrome clamps viewport width to a 500px minimum.** A screenshot at
   `--window-size=420` produces a 420px-wide image of a 500px-wide layout, which
   *looks* like content is clipped when nothing is wrong. Measure before
   believing a narrow screenshot. 500px is still below the 900px breakpoint, so
   the single-column fallback is exercised either way.

## Verification

Before reporting done: the checker exits 0 (or its remaining warnings are ones
you have looked at and consciously accepted), and you have read at least the
cover and any flagged page as images.

## Report

Give the user: pages checked, findings by severity, what you fixed and the
re-run result, and where the screenshots are. If you accepted a warning rather
than fixing it, say which and why — an unexplained warning reads as an
oversight.
