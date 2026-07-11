---
name: write-book
description: Research a topic on the web and write it up as a beautiful, multi-page HTML book for BookBank — a cover + table of contents, one page per important concept, and a cheatsheet, in a chosen narrator's voice with a bespoke visual design that fits the subject. Think like you are a programming books author and analyze what topics are relavant to the users topic. The html content should be in light theme. It could use page transition animations. It should use a two page concept like physical books using most available space. Use when the user wants to "create a book", "write a book about <topic>", "build a BookBank book", "explain <topic> as a book", "add/expand a concept" in an existing book, or process the BookBank build queue. Triggers include "create a Rust book in Feynman's voice", "write a book on <topic>", "build the bookbank queue".
---

# write-book

BookBank is the **generative** member of the BankKit family. The app does no LLM
work — it writes a request (`book.json`) and shows the HTML you generate. Your job
is to turn a topic + a narrator persona into a **rich, multi-page HTML book** that
the BookBank app reads in its embedded WebView (and the user can also open in a
browser). The value is **accurate, well-researched content** in a **beautiful,
topic-fitting design**.

## Arguments

- `/write-book` (no arg) — **process the queue.** Scan `<root>/books/*/book.json`
  and do the outstanding work:
  - any book with `"status": "requested"` → research and build it fully;
  - any book with `"status": "revising"` → **revise it in place** (the
    "Regenerate" path — see below); do not rebuild from scratch;
  - any concept with `"status": "requested"` in an already-built book → generate
    just that page and link it in (the "expand a concept" path).
    Report what you built. If the queue is empty, ask for a topic.
- `/write-book <topic>` — create a new book on `<topic>` and build it. Honor an
  inline voice ("…in Feynman's voice") by matching a persona (below).
- `/write-book expand "<concept>" in <book>` — add and generate one concept page
  in an existing book.

### Staged (orchestrated) builds — the app's decomposed path

For large course books the app's **BuildOrchestrator** drives the build as scoped
steps instead of one queue pass. Each step is a **separate `claude` run**, so honor
it as *exactly* that step and nothing more:

- **Scaffold** (prompt says "SCAFFOLD (not fully build) …") — create the shared
  **shell only**: `assets/` (the stylesheet + a theme skin matching
  `designDirection`, the two-page-spread pager `book.js`, and any interactive/widget
  engine the pages will share) and `index.html` (cover + table of contents linking
  each concept **in book.json order** to `concepts/NN-<concept id>.html`, `NN` =
  1-based, zero-padded). Lock the persona voice and visual design. Do **not** write
  any concept body and do **not** change any concept's status. This fixes the
  template every later page reuses, so the pages come out consistent.
- **One concept** (prompt says "build EXACTLY ONE concept page …") — build only the
  named concept at the given path, against the **existing** scaffolded assets (reuse
  the shared CSS / pager / widget engine; do not restyle the book or touch any other
  page). Honor its `brief`/`notes`/`unit`/`cos`/`kind`. Then set **only** that
  concept's `file` + `status:"ready"` and make sure `index.html` links it.
- **Revise** — the in-place revision path (below), scoped to one book.

Because each step re-reads `book.json` from disk, the staged build is **resumable**:
only ever fill concepts still `"requested"`, and never touch `"proposed"` ones —
those are a guided-mode plan awaiting the author's approval.

## Where things live

- **Data root — first match wins:**
  1. `$BOOKBANK_ROOT`, if set.
  2. The current directory, if it **looks like a content-repo clone** — it has
     a `books/` directory, a `catalog.json`, or a git remote whose URL
     contains `sunprema/books` (or `$BOOKBANK_BOOKS_REPO`, if set). This is
     what makes "clone the content repo, run the skill" just work with no
     flags or env vars.
  3. `~/bookbank`, as a legacy fallback (the pre-plugin flat layout).
- **Books:** one folder per book under `<root>/books/<book-id>/`:
  ```
  <root>/books/rust-programming/
    book.json                 # the manifest (you read + update this)
    index.html                # cover + table of contents (the landing page)
    concepts/01-ownership.html # one page per concept
    concepts/02-borrowing.html
    cheatsheet.html           # a one-page quick reference
    assets/book.css           # the book's bespoke stylesheet
    assets/book.js            # optional: small, self-contained interactivity
    assets/img/*              # images downloaded/created at build time (offline)
    cover.png                 # optional: a generated cover the gallery shows
  ```
- **Personas & themes — a 3-tier override cascade, first match wins:**
  1. `<root>/personas|themes/<id>.json` — per-clone local override. Never
     published: `build-library.py`'s sync only touches `<root>/books/*`, so
     this is safe for a one-off local experiment.
  2. `~/.claude/bookbank/personas|themes/<id>.json` — per-user override, for a
     voice/look you want available across every book you write, regardless of
     which content-repo clone you're standing in.
  3. `${CLAUDE_PLUGIN_ROOT}/defaults/personas|themes/<id>.json` — the plugin's
     built-in personas/themes.

  A **persona** is `{ "name", "tagline", "voice" }`; `book.json`'s `persona`
  is the persona **id** (filename without `.json`), or absent for the default
  voice. A **theme** is the book's **look & feel** (palette, fonts,
  background); `book.json`'s `theme` is the theme **id**, or absent for a
  neutral house look. A theme is **tokens + a mood** — see **Design** below.

## book.json schema

```json
{
  "id": "rust-programming",
  "title": "Rust: Fearless Systems Programming",
  "topic": "the Rust programming language",
  "persona": "feynman",
  "theme": "blueprint",
  "status": "ready",
  "created": "2026-06-28",
  "summary": "A first-principles tour of ownership, borrowing, and fearless concurrency.",
  "concepts": [
    {
      "id": "ownership",
      "title": "Ownership & Moves",
      "file": "concepts/01-ownership.html",
      "status": "ready",
      "source": "claude"
    }
  ],
  "revisionNotes": "Add a section on async/await; the clone example on the ownership page is wrong",
  "notes": "Requester wants a strong section comparing this to Python's GIL"
}
```

`revisionNotes` is only present while `status` is `"revising"` — it's the
freeform ask for that one regenerate pass (see **Revising an existing book**
below). Clear it once applied.

`notes` is an optional field valid while `status` is `"requested"` — extra
freeform brief context for the *initial* build pass (the same idea as
`revisionNotes`, but for a book that hasn't been built yet). Treat it as
additional brief alongside `topic`/seed `concepts[]` when you research and
choose concepts — e.g. `create-book-from-issue` writes an issue's free-text
"notes" answer here. Clear it once the book reaches `"ready"`.

Field rules:

- `status` (book): `requested` → `ready` once `index.html` exists and every
  concept is written. `revising` → `ready` once the requested revisions are
  applied. (Use `building` only if you stop midway.)
- `concepts[].status`: `requested` until its `file` is written, then `ready`.
- `concepts[].file`: path **relative to the book folder** (`concepts/NN-slug.html`).
- `concepts[].source`: `user` (the person asked for it) or `claude` (you chose it).
  **Never drop or reorder user concepts** — keep them, generate them.
- Keep `created` as ISO `yyyy-MM-dd`; set it once and leave it.
- Preserve `id`, `title`, `topic`, `persona`, `theme` exactly as the app wrote them.
- `theme`: the look-&-feel id under `<root>/themes/`, or absent = neutral house
  look. It's a durable request field like `persona` — never drop it on a rebuild.
- `notes`: optional, only meaningful while `status` is `"requested"` — see
  the schema note above. Remove it once the book is `"ready"`.

## Procedure (building a book)

1. **Read `book.json`.** Note the topic, the persona id, any seed concepts the
   user already listed (`source: "user"` — these are required), and any
   `notes` (extra freeform brief context — fold it into your research and
   concept choices like an inline ask).
2. **Load the persona** by resolving its id through the 3-tier cascade above
   and write in that `voice`. The persona governs **voice only** — tone,
   analogies, how concepts are explained. If `persona` is absent, use a
   clear, friendly technical author. **Load the theme** the same way — it
   governs **look only** (palette, fonts, background). If `theme` is absent,
   use a neutral house look.
3. **Research the web.** Use WebSearch + WebFetch to get the topic _right_: current
   facts, idioms, version-accurate syntax, authoritative sources (official docs,
   reference material). Don't invent APIs or numbers. Prefer primary sources.
4. **Choose the important concepts.** Decide the ~6–12 concepts that genuinely
   matter for the topic and order them so each builds on the last. **Include every
   `source: "user"` concept**, plus the ones you judge essential. (For a focused
   "expand" request, generate only the requested concept.)
5. **Apply the theme** (see Design, below). The book's _structure_ is consistent
   across the library; its _skin_ comes from the selected **theme** — write the
   theme's `tokens`/`fonts` into `book.css`'s `:root {}` and paint the page from
   its `background`, then add only topic-specific flourishes _within_ that palette.
   Don't invent a palette from scratch: the theme is the skin, the topic is the
   flourish. (If `theme` is absent, use a neutral, legible house look.)
6. **Write the pages:**
   - `assets/book.css` — the full stylesheet (self-contained, no external CDNs).
   - `concepts/NN-slug.html` — one page per concept (`NN` = 01, 02, … in order).
   - `index.html` — the cover + table of contents linking each concept. Give the
     cover hero a **cover-art image slot** (`id` containing "cover", `concept:
     null`) so the library shows real artwork — see Images & diagrams.
   - `cheatsheet.html` — a dense, printable quick-reference (syntax tables,
     gotchas, the "30-second" summary).
   - Draw explanatory diagrams as **inline SVG**; for real/illustrative images you
     can't draw, leave an **image slot** placeholder (see Images & diagrams).
7. **Update `book.json`** — set each concept's `file` + `status: "ready"`, the
   book `status: "ready"`, a one-line `summary`, and any **image slots** in
   `images[]` (id + prompt + file).
8. Optionally render a `cover.png` (used by the gallery; otherwise it falls back to
   a gradient). Tell the user to press ⌘R / reopen the book to see the update.

## Expanding a concept (the "wherever I need" path)

The app queues a new concept by appending `{ "status": "requested", "source":
"user", … }` to `book.json`. To fulfil it: research that one concept, write its
`concepts/NN-slug.html` (next number in sequence), **add it to the table of
contents in `index.html`** and into the prev/next chain, then flip its status to
`ready`. Don't regenerate the whole book — just wire in the new page. If the new
page warrants an illustration, add its **image slot** to `images[]` and a
placeholder on the page like any other.

## Revising an existing book (the "Regenerate" path)

The app's "Regenerate" action doesn't delete anything — it edits `book.json`'s
request fields in place (possibly changing `topic`/`title`/`persona`), sets
`"status": "revising"`, and writes a `revisionNotes` string with what the user
wants changed (it may be empty — "just tighten what's there"). Your job is to
**improve the existing book, not rebuild it from zero**:

1. **Read what's already there first** — `index.html`, every `concepts/*.html`,
   `cheatsheet.html`, and `book.json`'s current `concepts`/`images`. This is the
   draft you're revising, not a blank page.
2. **Read `revisionNotes`** and treat it as the brief for this pass. If it
   names a concept ("the ownership chapter's clone example is wrong"), fix that
   page specifically. If it asks for more content ("add a section on X"),
   research X and add it — either as a new concept page (append to `concepts[]`
   with `source: "claude"`, wire it into the nav chain and table of contents
   like **Expanding a concept**) or as a new section on an existing page,
   whichever fits better.
3. **Re-research only what the notes touch, or anything you suspect is stale**
   (versions, APIs, facts) — don't re-run the entire research pass speculatively.
4. **Keep what's good.** Untouched concept pages, the design/skin, and
   `assets/book.css`/`book.js` should generally survive unchanged unless the
   notes (or a topic/persona change) call for a broader revision. Preserve every
   `images[]` entry that already has its `file` on disk (a user-dropped image) —
   never overwrite or drop a slot just because you're revising the page it's on;
   add new slots the same way a normal build would.
5. If `topic`, `title`, or `persona` changed, make sure the revised pages (and
   `index.html`'s hero/summary) reflect the new framing, not just the notes.
6. **Update `book.json`**: set `status: "ready"`, clear `revisionNotes` (the ask
   for this pass is done), and refresh `summary` if the book's scope changed.
7. Tell the user what you changed and what you left as-is.

### Applying draft-mode comments (`comments.json`)

A revising book may also carry a **`comments.json`** beside `book.json` —
element-addressed editorial comments the user attached to specific blocks in the
reader's **Draft mode**. They complement `revisionNotes` (which is book-wide):
treat each comment whose `status` is `"open"` as a precise instruction for one
block. Schema:

```json
{
  "comments": [{
    "id": "cm-0aea45c1",
    "page": "concepts/03-ownership.html",
    "anchor": {
      "quote": "In practice the borrow checker enforces ownership at compile time…",
      "prefix": "…text of the block just before it",
      "suffix": "text of the block just after it…"
    },
    "intent": "add-example",
    "body": "needs a concrete Vec<String> move example here",
    "status": "open",
    "reply": null
  }]
}
```

For each **open** comment:

1. Open its `page` (relative to the book folder) and find the block. If the
   comment's `anchor.dataAnchor` is set, match the element with that
   `data-anchor` (exact); otherwise find the block whose text matches
   `anchor.quote`, using `prefix`/`suffix` to disambiguate if the quote appears
   more than once. (`quote` may be truncated — match on a prefix of it.)
2. Apply the edit **in place**, steered by `intent` + `body`, and **keep the
   block's `data-anchor` unchanged** (see the Anchor contract) so the comment
   stays pinned even if you rewrite the block:
   - `expand` → add depth/detail · `simplify` → make it clearer/plainer ·
     `trim` → shorten · `fix` → correct the error the note names ·
     `add-example` → add a concrete worked example near the block ·
     `add-visual` → add an inline SVG diagram (or declare an image slot if it
     needs real artwork — see **Image slots**) · `cite` → add a source/reference ·
     `retone` → adjust the voice. Keep the rest of the page, its design, and the
     other blocks intact.
3. In `comments.json`, set that comment's `status` to `"resolved"` and write a
   one-line `reply` summarizing what you changed (e.g. `"Added a Vec<String>
   move example."`). Leave already-`resolved` comments untouched; preserve every
   other field and the file's structure. If an anchor no longer matches any block
   (the page changed a lot), honor its intent near the original location as best
   you can and say so in the `reply`.

This runs as part of the same `revising` pass — the app flips the book to
`revising` and hands you both `revisionNotes` (if any) and `comments.json`.

## Design — beautiful, topic-fitting, self-contained

The bar is "an exciting HTML book", not a plain doc. Within a **consistent house
structure**, give each book a **bespoke theme derived from its topic**:

- **House structure (consistent):** every page shares `assets/book.css`; a sticky
  top bar with the book title + links to Contents and Cheatsheet; each concept
  page has a heading, the body, and **prev / next / contents** navigation at the
  bottom. `index.html` is a cover hero + a numbered, linked table of contents.
- **Navigation contract (required) — mark the nav links so the app's page-turn
  keyboard shortcuts work.** The app binds **→ next page**, **← previous page**,
  and **↑ first page** for the reader (docked and full-screen "zen" mode), by
  following the page's nav anchors. So on every page give them the right `rel`:
  - next-page link → `rel="next"` (omit on the last page)
  - previous-page link → `rel="prev"` (omit on the first page)
  - the Contents/cover link → `rel="home"` (points to `index.html`)

  e.g. `<a class="nav-next" rel="next" href="03-borrowing.html">Next →</a>`,
  `<a class="nav-home" rel="home" href="../index.html">Contents</a>`. (Concept
  pages live in `concepts/`, so `home` is `../index.html`; on `index.html` itself
  it's `index.html`.) The first page is `index.html` — order the chain
  `index.html → concept 01 → … → cheatsheet.html`. Keep these links visible too,
  for mouse users and for plain-browser viewing.
- **Anchor contract (recommended) — give annotatable blocks a stable
  `data-anchor`.** The reader's Draft mode lets users comment on a specific block;
  a `data-anchor` lets a comment stay pinned to the exact node even after you
  rewrite that block's text (text-quote matching can't). On each **annotatable
  block** — headings, paragraphs, list items, `figure`s, callouts, code blocks —
  put a stable, page-unique slug: `<p data-anchor="ownership-p3">…`. Make it
  meaningful and **stable across revisions** (don't renumber existing blocks just
  because you inserted one). It's invisible and inert in a plain browser. When you
  **revise or apply comments, keep each block's existing `data-anchor`** — treat it
  like an id you must not churn; only add new ones for genuinely new blocks.

### Two-page spread (the open-book layout) — default for new books

Render each page as an **open physical book**: two pages side by side with a center
spine, filling the viewport, and a **page-flip** when turning. Long content paginates
into multiple spreads *within* the same file; turning past the last/first spread
moves to the next/previous file. This is the **default layout for new books.**

How it works (self-contained, works from `file://`):

- **Paginate with CSS multicolumn.** Put the page's readable content in a tall,
  fixed-height column box; the browser flows it into page-width columns. Two columns
  visible = one spread; you translate the box horizontally to turn spreads.
- **A pager (`assets/book.js`) exposes `window.bookbankPager`** with `next/prev/home`.
  The BookBank app binds **→ ← ↑** to it automatically; your own keydown is only for
  plain browsers and must **defer to the app** (early-return if `window.__bookbankNav`
  is set, which the app sets when it's hosting — otherwise both would fire).
- **Below ~900px, drop the spread and fall back to one normal, scrolling column** —
  two visible columns get unreadably narrow on a phone. The CSS media query in the
  skeleton below collapses `.book-viewport`/`.book-leaf` to natural document flow at
  that width, and the *same* breakpoint in `book.js` stops pagination so Next/Prev
  step file-to-file instead of spread-to-spread, like a normal multi-page site. This
  is **required for every book**, not optional — it's what makes a book actually
  readable on a phone.

Structure:

```html
<div class="book-viewport">           <!-- clips to the visible spread -->
  <article class="book-leaf">         <!-- content; multicolumn flows it into pages -->
    …all the page's content (headings, prose, code, figures, image slots)…
  </article>
  <div class="book-spine" aria-hidden="true"></div>   <!-- center gutter shadow -->
</div>
<nav class="book-nav">                <!-- visible controls + the rel contract -->
  <a rel="prev" href="01-ownership.html">‹ Prev</a>
  <a rel="home" href="../index.html">Contents</a>
  <span class="book-pageno"></span>
  <a rel="next" href="03-borrowing.html">Next ›</a>
</nav>
```

CSS skeleton (colors/fonts come from the theme tokens — `var(--bg)`, `var(--ink)`,
`var(--font-body)`, etc.; keep the mechanics):

```css
.book-viewport{ position:fixed; inset:0; overflow:hidden; }
.book-leaf{
  height:100vh; box-sizing:border-box; padding:6vh 0;
  column-fill:auto;                      /* fill each column fully, overflow rightward */
  transition: transform .5s cubic-bezier(.6,.02,.2,1);   /* the page-flip */
}
.book-leaf > *{ break-inside:avoid; }    /* don't split a block across the gutter */
.book-spine{ position:fixed; top:0; bottom:0; left:50%; width:2px; transform:translateX(-1px);
  box-shadow:0 0 22px 10px rgba(0,0,0,.10); pointer-events:none; }
.book-nav{ position:fixed; left:0; right:0; bottom:0; display:flex; gap:1.5rem;
  justify-content:center; align-items:center; padding:.6rem; }

/* Required mobile fallback — see "Below ~900px" above. The pager JS detects the
   same 900px breakpoint and stops setting columnWidth/columnGap/transform, so
   these rules aren't fighting inline styles. */
@media (max-width: 900px) {
  .book-viewport{ position:static; overflow:visible; }
  .book-leaf{ height:auto; padding:5vh 5vw; }
  .book-spine{ display:none; }
  .book-nav{ position:static; }
}
```

Pager reference (`assets/book.js`) — adapt, but keep the contract:

```js
(function(){
  var leaf = document.querySelector('.book-leaf');
  var vp   = document.querySelector('.book-viewport');
  if(!leaf || !vp) return;
  var i = 0, total = 1, spread = 1;
  // Same 900px breakpoint as the CSS. Below it there's no spread to paginate —
  // layout()/render() go inert and next()/prev() fall through to file navigation.
  function mobile(){ return !window.matchMedia('(min-width: 901px)').matches; }
  function contentRight(){
    // Rightmost content edge relative to the leaf's left edge. Measured from
    // child bounding rects, NOT leaf.scrollWidth — rects are engine-proof, and
    // both rects carry the current translateX equally so the difference is
    // invariant while flipped/animating.
    var base = leaf.getBoundingClientRect().left, right = 0, kids = leaf.children;
    for(var k = 0; k < kids.length; k++){
      var r = kids[k].getBoundingClientRect().right - base;
      if(r > right) right = r;
    }
    return right;
  }
  function layout(){
    if(mobile()){
      // Let the CSS breakpoint's natural flow take over — clear any inline
      // column/transform styles a wider layout() left behind (e.g. resize
      // across the breakpoint) and collapse to a single "page".
      leaf.style.columnGap = ''; leaf.style.columnWidth = ''; leaf.style.transform = '';
      total = 1; i = 0;
      var n0 = document.querySelector('.book-pageno');
      if(n0) n0.textContent = '';
      return;
    }
    var W = vp.clientWidth, gap = Math.round(W * 0.08), colW = (W - gap) / 2;
    leaf.style.columnGap = gap + 'px';
    leaf.style.columnWidth = colW + 'px';
    spread = 2 * (colW + gap);                              // distance per spread
    var cols = Math.max(1, Math.ceil((contentRight() - 1) / (colW + gap)));
    total = Math.max(1, Math.ceil(cols / 2));
    i = Math.min(i, total - 1);
    render();
  }
  function render(){
    if(mobile()) return;               // natural document flow — nothing to translate
    leaf.style.transform = 'translateX(' + (-i * spread) + 'px)';
    var n = document.querySelector('.book-pageno');
    if(n) n.textContent = (i + 1) + ' / ' + total;
  }
  function href(rel){ var a = document.querySelector('a[rel~="' + rel + '"]'); return a && a.getAttribute('href'); }
  window.bookbankPager = {
    next: function(){ if(i < total-1){ i++; render(); } else { var h=href('next'); if(h) location.href = h; } },
    prev: function(){ if(i > 0){ i--; render(); } else { var h=href('prev'); if(h) location.href = h + '#last'; } },
    home: function(){ var h=href('home'); if(h) location.href = h; }
  };
  window.addEventListener('resize', layout);
  window.addEventListener('load', function(){
    layout();
    var m = /^#s(\d+)$/.exec(location.hash);               // #s2 = deep-link to spread 2
    if(location.hash === '#last'){ i = total-1; render(); }
    else if(m){ i = Math.min(parseInt(m[1], 10) - 1, total - 1); render(); }
    setTimeout(layout, 250);                               // re-measure after fonts settle
  });
  // Images popping in or erroring (image-slot placeholders) reflow the columns.
  Array.prototype.forEach.call(document.images, function(im){
    im.addEventListener('load', layout);
    im.addEventListener('error', layout);
  });
  layout();
  // Plain-browser keyboard support; the BookBank app handles keys itself (it sets
  // window.__bookbankNav), so defer to it to avoid turning twice.
  document.addEventListener('keydown', function(e){
    if(window.__bookbankNav || e.metaKey || e.ctrlKey || e.altKey) return;
    if(e.key === 'ArrowRight'){ bookbankPager.next(); e.preventDefault(); }
    else if(e.key === 'ArrowLeft'){ bookbankPager.prev(); e.preventDefault(); }
    else if(e.key === 'ArrowUp'){ bookbankPager.home(); e.preventDefault(); }
  });
  // REQUIRED — route clicks on the visible Next/Prev links through the pager.
  // The raw links navigate FILES, so without this a mouse click on "Next ›"
  // skips the chapter's remaining spreads — the book reads as truncated, and
  // there's no scrollbar to reveal the loss (real bug, 2026-07-04). The pager
  // still follows the href once the last/first spread is reached.
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[rel~="next"],a[rel~="prev"]');
    if(!a) return;
    e.preventDefault();
    var rel = a.getAttribute('rel') || '';
    bookbankPager[rel.indexOf('next') >= 0 ? 'next' : 'prev']();
  });
})();
```

Notes: give the content generous inside margins so text never crowds the spine; size
the type so a typical concept is a few spreads, not twenty; keep figures/code blocks
from splitting (`break-inside:avoid`); and **`index.html`** can use the same open-book
frame for the cover (left page) + table of contents (right page). The skin (palette,
spine texture, flip easing, paper grain) comes from the **theme** (see Design) — the
mechanics above stay constant. Always verify it turns from `file://` before marking the book ready — and
verify **both** input paths: arrow keys AND mouse clicks on the visible Next/Prev
links must step through every spread of a chapter (spread 2, 3, …) before crossing
into the next file. A book where clicks skip straight to the next file hides its
mid-chapter content (including image-slot placeholders) with no scrollbar to betray
the loss. Also verify the **mobile fallback**: narrow the window below ~900px (or
use a phone-width preview) and confirm the spread collapses to one normally-scrolling
column with no clipped or overlapping content, and that Next/Prev now step file-to-file
(there are no spreads left to paginate).
- **Theme-driven skin (tokens + mood):** the **theme** supplies the skin, not your
  imagination. At the top of `book.css`, emit a `:root {}` that sets every one of
  the theme's `tokens` and `fonts` verbatim, and paint the page from `background`:
  ```css
  :root{
    /* …paste the theme's tokens: --bg, --bg-2, --ink, --ink-soft, --accent,
       --rule, --code-bg, and the code-highlight slots --kw --ty --fn --mac --str
       --num --cm --lif --at --en… */
    /* …and its fonts: --font-display, --font-body, --font-mono… */
  }
  body{
    color:var(--ink);
    background:var(--bg);                 /* base */
    background-image:<theme.background.css>;   /* the theme's gradient/texture layer */
    background-attachment:fixed;
    font-family:var(--font-body);
  }
  ```
  Then **reference the tokens everywhere** — headings use `var(--font-display)` and
  `var(--ink)`; rules/borders use `var(--rule)`; the accent uses `var(--accent)`;
  code blocks use `var(--code-bg)` with the highlight `<span>` classes mapped to the
  `--kw … --en` tokens (`.kw{color:var(--kw)} .ty{color:var(--ty)}` …). **Do not
  hardcode hex colors** in the body of the stylesheet — go through the variables so
  a re-skin (a new theme on the same book) is a clean swap. Follow the theme's
  `mood` for topic-specific motif and flourish, but stay inside this palette. Keep
  it legible: strong type scale, generous spacing, good contrast. If `theme` is
  absent, define a sensible neutral house `:root {}` yourself in the same shape.
- **Rich content blocks:** syntax-highlighted code (highlight inline with simple
  `<span>` classes + CSS — do **not** rely on a CDN), callouts (note / warning /
  key-idea), comparison tables, figures/diagrams (see **Images & diagrams**), and
  "cheatsheet" cards. Cite sources at the foot of a page where useful.
- **Self-contained & offline:** all CSS/JS/assets local and relative. No external
  `<link>`/`<script>` to CDNs, no web fonts that require network — the book must
  render from `file://` with no connection. Keep any `book.js` tiny (e.g.
  collapsibles, copy-code) and optional.
- **Accuracy first.** Beautiful but wrong is a failure. Ground code and claims in
  the research; show idiomatic, runnable examples.

## Images & diagrams

Images make a book sing — but the book must stay **offline and self-contained**:
never hotlink a remote URL in `<img>`. Pick the right tool for each visual:

- **Inline SVG — draw it yourself, preferred for anything explanatory.** Memory
  layouts, ownership/borrow graphs, state machines, flowcharts, request lifecycles,
  architecture. Crisp at any size, weighs nothing, no files, and you can **theme it
  to the book's palette**. If you can express it as SVG, do — don't make the user
  source a diagram you could draw.
- **Real/illustrative images you can't draw → declare an image slot** (next
  section). Photographs, stylized cover art, rich illustrations. You don't have the
  image, so you write a **prompt** for the user's external image agent (e.g. Nano
  Banana) and leave a placeholder they drop the result onto.
- **CSS/Unicode decoration** for badges, dividers, icon glyphs — no files needed.

Rules for every image: **relative paths, mind the depth** — concept pages live in
`concepts/`, so they reference `../assets/img/x.png`; `index.html` /
`cheatsheet.html` use `assets/img/x.png`. Always wrap in a `<figure>` with a
caption and `alt` text.

**Lock every image to a size — the page can't scroll.** Pages are fixed-height CSS
columns, so an image whose *actual* pixels are taller than you expect overflows its
column and shoves the rest of the spread into overlap (e.g. an over-tall cover pushes
its own content onto the facing page). Two defences, use **both**: (a) tell the image
generator the target size in the **prompt** so it comes out right, and (b) enforce it
in `book.css` regardless of what file is dropped — an `img` never renders taller than
its declared aspect box or a hard `max-height`. Never ship a bare
`figure img{max-width:100%;height:auto}` — that trusts the file's own dimensions.

### Image slots — prompt-and-drop (the user supplies the artwork)

Wherever a real/generated image would genuinely help, create an **image slot**:

1. **Record it in `book.json`** under `images[]`:
   ```json
   {
     "id": "ownership-move",
     "prompt": "A clean, modern editorial illustration: a String value as a labeled box moving along an arrow from variable s1 to s2, with s1 dimmed and crossed out to show it's been invalidated. Warm rust/oxide palette, flat vector style, generous whitespace, no text labels baked in. Target size ~1280×720px, 16:9 landscape; compose for a small on-page figure with the subject centred and safe margins — it is letterboxed into a 16:9 box, so keep nothing important near the edges.",
     "file": "assets/img/ownership-move.png",
     "alt": "Moving a String invalidates the original binding",
     "caption": "A move transfers ownership; the original binding can no longer be used.",
     "concept": "ownership",
     "aspect": "16:9"
   }
   ```
   Write a **standalone, vivid prompt** that another image model can run with no other
   context, and **always end it with a size expectation** — the target pixel dimensions
   + aspect (e.g. *"~1280×720px, 16:9 landscape"*) and a note that the art is letterboxed
   into that box so the subject should sit centred with safe margins. **Always set
   `aspect`** (`"16:9"`, `"3:2"`, `"1:1"`, `"4:3"`…) — it drives the CSS box, and the
   prompt's stated ratio must match it. Keep `file` = `assets/img/<id>.<ext>` (png/jpg) —
   the app saves the dropped image exactly there.
2. **Emit a placeholder** at that spot in the HTML. Use this exact structure so the
   app can wire it up (class names + `data-img-slot` / `data-img-file` matter; the
   `data-img-file` path is **relative to the book folder**, while the `<img src>` is
   relative to the page):
   Set `--img-aspect` on the figure to the slot's `aspect` (as a CSS ratio, `16 / 9`)
   and give the `<img>` matching `width`/`height` attributes — both reserve the box's
   shape before the file loads, so nothing reflows or overlaps when the art drops in:
   ```html
   <figure
     class="img-slot"
     data-img-slot="ownership-move"
     data-img-file="assets/img/ownership-move.png"
     style="--img-aspect:16 / 9"
   >
     <img
       class="img-real"
       src="../assets/img/ownership-move.png"
       alt="Moving a String invalidates the original binding"
       width="1280" height="720"
       onerror="this.closest('.img-slot').classList.add('img-missing')"
     />
     <div class="img-drop">
       <div class="img-drop-inner">
         <strong>Image needed</strong>
         <p class="img-prompt">
           A clean, modern editorial illustration: a String value … no text
           labels baked in.
         </p>
         <button type="button" class="img-copy">Copy prompt</button>
         <p class="img-hint">
           Generate this with your image agent, then drop the file here.
         </p>
       </div>
     </div>
     <figcaption>
       A move transfers ownership; the original binding can no longer be used.
     </figcaption>
   </figure>
   ```
   The `<img>` lives first and starts broken (the file doesn't exist yet); its
   `onerror` flags the slot, and the app's injected behavior CSS reveals the drop
   prompt. Once the user drops an image, the app writes it to `file`, reloads, the
   `<img>` resolves, and the placeholder hides — no rebuild needed. **Without
   the app** (the normal contributor path), fill a slot with
   `${CLAUDE_PLUGIN_ROOT}/library/place_image.py <book-dir> <slot-id> <source-file>`
   — it looks up the slot's declared `file`/`aspect`, converts the source to
   the right extension, writes it to the exact declared path, and warns
   (non-fatal) if the actual aspect is off from the declared one by more than
   ~10%. A dangling slot (declared but not yet on disk) is a `validate_book.py`
   **warning**, not an error — the book can still ship `"ready"` and the
   public shelf falls back to a gradient cover until the art lands.
3. **Style the slot** in `book.css` to fit the book (the app only injects the
   show/hide behavior + drag wiring + the "Copy prompt" action). Give `.img-drop`
   a tasteful dashed-card look, style `.img-prompt` as a readable quote, and the
   `.img-copy` button. (Opened in a plain browser the placeholder still shows the
   prompt — it just isn't droppable there.) **Size the real image off the declared
   aspect, never off the file** — this is what keeps an over-sized dropped image from
   overflowing the fixed-height column:
   ```css
   .img-slot .img-real{
     width:100%; aspect-ratio:var(--img-aspect, 16 / 9);
     height:auto; max-height:56vh;           /* hard cap so nothing blows out the page */
     object-fit:contain; object-position:center;   /* letterbox, never distort or crop-away */
     display:block; border:1px solid var(--edge); border-radius:10px;
   }
   /* any non-slot <figure img> too: */
   figure img{ max-width:100%; height:auto; max-height:56vh; object-fit:contain; display:block; }
   ```
   Tune `max-height` to the book, but keep a cap. Use `object-fit:cover` only for an
   image you *want* cropped to fill the box; `contain` (above) shows the whole art.

Keep slots **purposeful** — one strong illustration per concept at most; lean on
SVG for the explanatory diagrams.

## 3D figures (three.js) — offline-safe interactive visuals

For a genuinely **spatial or interactive** concept (a rotating molecule, a 3D
coordinate frame, a mesh you can orbit, a GPU/shader demo), an interactive
three.js canvas can earn its place. It is a **last resort, not a default** — if a
diagram can be inline SVG, make it SVG. At most **one 3D figure per concept page**.

Everything below exists because a book must render from `file://` with **no
network** (the app WebView, "Open in browser", and the plain-browser case all load
`file://`; only the GitHub Pages copy is served over HTTP).

### Loading three.js offline — vendor a self-bundled global

Do **not** use a CDN `<script>` (no network offline) and do **not** use
`<script type="module">` + an import map: module scripts are fetched under CORS and
`file://` is a null origin, so WKWebView/Safari **block relative module imports from
`file://`** — they'd work on GitHub Pages but break silently in the app. The old UMD
globals (`build/three.min.js`) were **removed in three.js r161**, so you can't just
drop one in either.

Instead, **bundle three.js + the exact addons the page needs into one classic IIFE**
that sets `window.THREE`, vendor it in the book, and load it with a plain
`<script>`. Classic scripts load fine from `file://`. Use the helper in this skill
(`scripts/build-three-bundle.sh`) — it installs three+esbuild once in a shared
cache, folds the addons onto `window.THREE`, is idempotent (re-run cheaply; skips
if the bundle exists, `FORCE=1` to rebuild), and writes to the right path:

```bash
# Default (three + OrbitControls):
"$CLAUDE_PLUGIN_ROOT/skills/write-book/scripts/build-three-bundle.sh" "<book-dir>"

# Extra addons — each as Name=import-spec:
"$CLAUDE_PLUGIN_ROOT/skills/write-book/scripts/build-three-bundle.sh" "<book-dir>" \
  OrbitControls=three/addons/controls/OrbitControls.js \
  GLTFLoader=three/addons/loaders/GLTFLoader.js
# Pin a version with THREE_VERSION=0.185.1, force a rebuild with FORCE=1.
```

It writes `<book>/assets/vendor/three.iife.js`. (Equivalent by hand if you can't
run the script: `npm i three esbuild`, an `entry.js` that
`import * as THREE from 'three'` + imports each addon + `Object.assign(THREE, …)` +
`window.THREE = THREE`, then `npx esbuild entry.js --bundle --minify --format=iife
--outfile=<book>/assets/vendor/three.iife.js`.)

Keep it **per-book** under `assets/vendor/` (books must stay self-contained and
portable when published) and reference it relatively — concept pages are one level
down, so `../assets/vendor/three.iife.js`. As always, `<meta charset="utf-8">` is
still the **first line** of every page (the mojibake gotcha applies here too).

```html
<script src="../assets/vendor/three.iife.js"></script>
<script src="../assets/three-figures.js"></script>   <!-- your scene code -->
```

### Fitting a canvas into the fixed-height spread

Pages are fixed-height CSS multicolumn spreads that **can't scroll**, so a canvas
taller than its column overflows and overlaps the rest of the spread — the same
failure mode as an over-tall image. Treat a 3D figure like an image slot:

- **Lock it to an aspect box with a hard cap; never let the renderer set the size:**
  ```css
  .three-figure{ break-inside:avoid; }
  .three-figure canvas{ width:100%; aspect-ratio:16/9; height:auto; max-height:56vh; display:block; }
  ```
- **Size the renderer to the figure, not the window:**
  `renderer.setSize(fig.clientWidth, fig.clientHeight, false)`, set `camera.aspect`
  from those, and clamp `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))`.
- **Re-measure on the pager's relayout** — the spread re-columns on `resize` and
  after fonts settle; listen to the same `resize` event `book.js` uses and re-fit.

### Runtime rules (all required)

- **Pause offscreen.** Gate the `requestAnimationFrame` loop behind an
  `IntersectionObserver` on the figure — a canvas on spread 5 must not burn GPU
  while spread 1 is showing. Stop the loop when it leaves the visible spread.
- **Honor `prefers-reduced-motion`** — render one static frame instead of animating.
- **Don't fight the pager.** The app binds **← → ↑** to page-turns and routes
  Next/Prev clicks through `window.bookbankPager`. Keep 3D interaction to
  **mouse-drag / wheel inside the canvas** (OrbitControls); avoid arrow-key camera
  controls (they'd turn the page) and stop pointer events on the canvas from
  bubbling to nav links.
- **No external assets.** Textures/HDRIs can't be hotlinked — generate procedurally
  or embed tiny textures as `data:` URIs inside the JS.
- **One GL context per page; dispose on teardown.** Browsers cap live WebGL
  contexts (~16), so one 3D figure per concept and release it when navigating away.

Verify the figure from `file://` before marking the book ready: it must render and
orbit with **no network**, stay inside its box across a spread reflow and the
~900px mobile fallback, and page-turn keys must still work with the canvas present.

**Always declare a cover-art slot** so the library shows real artwork instead of a
gradient. The gallery picks a book's cover from any image slot whose **`id`
contains `cover`** and whose **`concept` is `null`** (front-of-book, not tied to a
concept page) — so name it exactly `cover-art` (preferred) and set `"concept":
null`, `"file": "assets/img/cover-art.png"`. A themed id also works as long as it
contains "cover" (e.g. `gpu-zine-cover`), but **never** name a cover slot without
"cover" in the id or attach it to a concept, or the gallery won't recognize it.
Emit its placeholder in the `index.html` cover hero like any other slot. (A
pre-rendered root `cover.png` also works and takes precedence; otherwise the
gallery falls back to a gradient keyed off the book id.)

## Privacy / locality note

Everything stays **local**: books are files on disk under the data root; the app
reads them directly with no server. Research happens over the web during
generation; the generated book has no network dependencies.
