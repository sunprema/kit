---
name: book-apparatus
description: Add the scholarly furniture that makes a BookBank book feel like a book — a further-reading list, an index, and a glossary — mostly derived from data the book already carries. Use when a finished book should feel more complete, when readers need to look things up, or when research.json's sources are going unused. Triggers include "add an index", "add a glossary", "further reading", "add a bibliography", "make this feel like a real book".
---

# book-apparatus

A finished BookBank book is sitting on two things it never uses:

- **`research.json`** records every source, with per-claim, per-concept
  citations. That is a further-reading list already — including which chapter
  leans on which source, and which sources the book leans on most.
- **Concept pages mark key terms** with `<span class="term">`. That is an index
  already — the author hand-picked exactly the words worth indexing.

So the apparatus is mostly **derived, not written**. That matters beyond
convenience: a hand-written index drifts the moment a chapter is revised, while
a derived one is re-read out of the book every time.

## Arguments

- `/book-apparatus <book-id>` — add all three (whichever the book can support).
- `/book-apparatus <book-id> --only index|reading|glossary`

## Procedure

1. **Install the styles** — append `assets/apparatus.css` (this skill) to the
   book's `assets/book.css` if it isn't there.

2. **Generate the derived parts:**
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/book-apparatus/scripts/build-apparatus.py \
       <book-dir> --what both
   ```
   Prints HTML fragments to stdout (or `--out DIR` to write files). It has no
   opinion about where they live — that is step 3.

3. **Wire the fragments into the book.** Two placements, both valid:
   - **On the cheatsheet page**, after the existing cards. Best for a short
     book — no new page, no nav-chain surgery.
   - **As its own page**, `apparatus.html`, added to the end of the chain
     (`… → cheatsheet.html → apparatus.html`). Best when the index runs long.
     Give it the same house structure as every other page: topbar, viewport,
     leaf, spine, and nav with `rel="prev"`/`rel="home"`. Add it to
     `index.html`'s table of contents, and — if it is a numbered entry there —
     to `book.json`'s `concepts[]` so the two agree.

4. **Write the glossary by hand.** This one cannot be derived: a definition is
   authorship. See below.

5. **Verify** — see *Verification*.

## The three parts

### Further reading (derived)

Sources ranked by how many concepts cite them, each showing which chapters rely
on it. Sources with no citations are marked "Background — not cited directly",
which is honest and also a useful signal: a source nothing cites usually means
either the research went unused or a claim lost its citation.

If the script warns that claims cite unknown source ids, fix `research.json` —
that is a real bug in the research artifact, and `validate_book.py` flags it too.

### Index (derived)

Every `<span class="term">` in the book, alphabetised, linked to the pages where
it appears. Two consequences worth knowing:

- **The index is only as good as the term marking.** If a book marks three terms,
  the index has three entries. Before generating, read the pages and mark the
  terms that were introduced but never wrapped — that is the actual work here,
  and it improves the prose too (a marked term is a promise that this is where
  the idea is defined).
- **Links land on the page, not the spread.** A book page paginates into several
  spreads, and which spread a term falls on depends on the viewport, so it
  cannot be computed ahead of time. Page-level links are the honest equivalent
  of a print index's chapter reference. Do not fake a `#s2` deep link.

### Glossary (written)

Definitions are authorship — no script can write them. Rules:

- **One sentence, no forward references.** A glossary entry that needs another
  glossary entry to make sense has failed.
- **Define it as the book uses it**, not as a dictionary would. If the book
  spent a chapter arguing that "stateless" doesn't mean "no state anywhere",
  the glossary must say so.
- **Stay in the persona's voice.** A glossary in neutral encyclopedia-speak
  inside an `the-adversary` book reads like someone else wrote the back matter.
- Cross-reference with `<span class="g-see">See also …</span>`.

To surface a definition in running prose, add `data-def` to the term span:

```html
<span class="term" data-def="A token whose validity is checked from its own
contents, not by consulting a server.">self-contained</span>
```

The style gives it a dotted underline and a hover definition via `title`.
**Do not build an expanding popover** — a BookBank page is a fixed-height
spread that cannot scroll, so anything that grows on interaction re-flows the
columns under the reader. (Same constraint as `book-exercises`; the reasoning
is spelled out there.)

## Verification

- Re-run the script after any revision — a derived apparatus that is out of
  date is worse than none, because it looks authoritative.
- Open the new page from `file://` and click several index links; each must
  land on a real page.
- Run `validate_book.py` (a new page must satisfy the nav contract) and
  `/book-visual-qa` (a long index list can strand its heading or overflow).
- If you added a page, confirm `index.html`'s table of contents and
  `book.json` agree with the nav chain.

## Report

Say what was derived versus written, how many index entries and sources landed,
and — importantly — which terms you marked up to improve the index. If the
glossary is partial, say which terms you left out and why.
