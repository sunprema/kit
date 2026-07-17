# Research/Prose Split — `research.json`, the book's durable research artifact

**Goal:** separate what a build *learned* (facts, sources, structure decisions) from
what it *wrote* (the persona-voiced HTML prose), by persisting the research as a
distilled `research.json` beside `book.json`. Today the research dies with the
build session — every re-voice, revision, depth change, or freshness pass has to
re-fetch the web and hope it lands on the same facts. With the split, prose becomes
a cheap, repeatable *rendering* of a durable research artifact.

This is a change to the **kit** (`/Volumes/x/kit/bookbank`) — primarily the
`write-book` skill's procedure, with small additions to `stage-book-build` and
`validate_book.py`. The BookBank.app needs **no changes for Phase 1**; later
phases add app affordances that consume the artifact.

## What it unlocks

| Feature | Without the split | With `research.json` |
|---|---|---|
| **Re-voice** (same book, new persona) | full re-research + rewrite | rewrite prose only, no web |
| **Depth toggle** ("simpler / deeper" on one section) | re-research that topic mid-session | regenerate from the same claims |
| **Refresh / editions** | rebuild and eyeball what changed | re-research → diff against recorded claims → change-highlight |
| **Honest citations** | whatever survived in-context | every claim carries source ids; a sources page is generated, not recalled |
| **Staged-build consistency** | late pages rely on session memory | every page writes from the same recorded structure + facts |

## The artifact

One file per book, beside `book.json`:

```
<root>/books/rust-programming/
  book.json
  research.json        ← this doc
  index.html
  concepts/…
```

### Schema

```json
{
  "schema": 1,
  "researched": "2026-07-17",
  "sources": [
    {
      "id": "src-trpl-ch4",
      "url": "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html",
      "title": "The Rust Programming Language, ch. 4",
      "kind": "official-docs",
      "accessed": "2026-07-17"
    }
  ],
  "structure": {
    "rationale": "Why these concepts, in this order — 2–4 sentences.",
    "audience": "Working programmers new to Rust."
  },
  "concepts": {
    "ownership": {
      "researched": "2026-07-17",
      "claims": [
        {
          "text": "Assigning a String moves it; the original binding is invalidated at compile time.",
          "sources": ["src-trpl-ch4"]
        }
      ],
      "snippets": [
        {
          "lang": "rust",
          "code": "let s1 = String::from(\"hi\");\nlet s2 = s1; // s1 is moved",
          "note": "verified against Rust 1.79",
          "sources": ["src-trpl-ch4"]
        }
      ],
      "pitfalls": ["Beginners expect a copy; only Copy types copy on assignment."],
      "furtherReading": ["src-trpl-ch4"]
    }
  },
  "volatile": ["Rust version numbers", "stdlib API signatures"]
}
```

Field rules:

- **`sources[]`** — deduplicated across the book; every entry has a stable `id`
  that claims reference. `kind` is freeform but prefer
  `official-docs` / `reference` / `article` / `paper` / `repo`.
- **`concepts` is keyed by concept id** (the same ids as `book.json`'s
  `concepts[].id`), *not* by file path — ids survive renumbering, files don't.
- **`claims[]`** — the atomic unit. Each claim: one falsifiable statement in
  plain neutral prose (NOT persona voice — the artifact is voice-free by
  definition), with ≥1 source id. If you couldn't source it, either don't write
  it into the book or mark it `"sources": []` explicitly so a later verify pass
  can find it.
- **`snippets[]`** — code you verified or took from a primary source, with
  version notes. These are the ground truth the page's highlighted examples
  render from.
- **`volatile`** — book-level list of what will go stale first; a future
  refresh pass reads this to know where to look.
- **Per-concept `researched` date** — a revise pass that re-researches one
  concept bumps only that concept's date, so freshness is trackable per page.

### Distill, don't dump — the size rule

`research.json` records what was **extracted**, never what was fetched. No raw
HTML, no page dumps, no full quotes longer than a sentence or two. Target the
same order of magnitude as the book's prose (~100–300 KB); if it's heading past
that, the entries are transcripts, not research. (For scale: books today run
4–23 MB on disk, of which the HTML prose is only ~90–190 KB — the artifact is
noise against the images.)

### Voice-free by construction

The persona lives in the prose; `research.json` must read the same whether the
book is narrated by Feynman or a drill sergeant. This is the invariant that
makes re-voicing safe: if persona flavor leaks into claims, a re-voice pass
inherits the old voice through the back door.

## Lifecycle — who writes it, when

### One-shot build (`/write-book <topic>`, queue pass)

The existing Procedure gains one output between research and writing: after
step 3 (research) and step 4 (choose concepts), **write `research.json` first**
— sources, structure rationale, and per-concept entries — *then* write the
pages from it. The prose pass should need no new web fetches; if writing a page
reveals a gap, fetch, **record the new claim/source in `research.json`**, then
use it. The rule: *nothing appears in a page that isn't in the artifact.*

### Staged build (`stage-book-build` / the app's BuildOrchestrator)

No new step type. The artifact accretes across the existing steps:

- **Scaffold** additionally writes the skeleton: `sources` it consulted for
  structure, `structure.rationale`, and an empty-object entry per concept.
  (Scaffold already reads the topic and locks design/voice; recording *why this
  outline* costs nothing extra.)
- **Each concept step** researches its page as today, but records its distilled
  findings under `concepts.<id>` **before** writing the page's HTML. Because
  each step re-reads state from disk, a concept step also *reads* the artifact
  first — shared sources and neighboring concepts' claims give a fresh-context
  step the cross-page consistency that single-pass builds got from session
  memory. This is a merge into one file from sequential steps — no contention
  while staged builds stay sequential (they do today; a future parallel fan-out
  would shard per-concept files, out of scope here).
- **Revise** re-researches only what `revisionNotes`/comments touch and updates
  exactly those entries (claims changed, sources added, per-concept
  `researched` bumped). Untouched entries survive, same as untouched pages.

### Existing books (backfill)

No migration. A book without `research.json` is a **legacy book** and every
consumer must degrade gracefully (re-voice falls back to re-research; refresh
falls back to full rebuild). Any `revising` pass on a legacy book backfills
entries for the concepts it actually touches — the artifact grows lazily along
the paths that get exercised.

## Consumers

**Phase 2 — Re-voice** (the first payoff). Reuses the existing `revising`
machinery — no new status, no app schema change: the app (or a human editing
`book.json`) changes `persona`, sets `status: "revising"`, and writes
`revisionNotes: "re-voice only"`. The skill's revise path, seeing a persona
change + an intact `research.json`, rewrites prose from the artifact **without
web research** — structure, claims, snippets, image slots, and every
`data-anchor` stay fixed; only the words change. A later app affordance
("Re-narrate as…" in RegenerateBookView) is just a nicer way to write those
three fields.

**Phase 3 — Refresh / editions.** A refresh pass re-researches guided by
`volatile` + source URLs, diffs new findings against recorded claims, updates
only pages whose claims changed, and can render a changelog ("2nd edition")
from the claim diff — reusing draft mode's change-highlight machinery.

**Also grounded by the artifact, when built:** per-section depth regeneration,
a generated sources/further-reading page, and reader-side "ask the narrator"
answers that cite recorded claims instead of the model's memory.

## Publishing

**`research.json` ships with the book.** It's 100–300 KB against a ~90 MB
books repo — negligible — and publishing it makes the artifact durable across
clones: the cloud routine builds in a content-repo clone, `pull-book` fetches
single books, and contributors work from forks; if the artifact were
local-only it would silently vanish along every one of those paths, and the
file-is-the-interface rule breaks. `build-library.py` needs no change (it syncs
`books/*` wholesale); `pull-book` should include the file. It contains only
topic research — nothing personal — so publishing is safe by construction.

## Validation (`library/validate_book.py`)

- **Warning** — no `research.json` (legacy book; every consumer must tolerate).
- **Error** — file exists but is malformed JSON / wrong shape.
- **Warning** — a `ready` concept has no entry (or an empty one) in
  `concepts.<id>` while the file exists — a new build that skipped the contract.
- **Warning** — a claim with `"sources": []` (flagged for a verify pass, not
  fatal).

Same severity split every caller already uses (`create-book-from-issue` step 9,
`stage-book-build`'s post-plan validation).

## What changes where

| Where | Change |
|---|---|
| `skills/write-book/SKILL.md` | Procedure writes `research.json` before prose; schema + distill/voice-free rules; revise path updates touched entries; re-voice fast-path (persona changed + artifact present → no web) |
| `skills/stage-book-build/SKILL.md` | scaffold/concept step prompts gain the artifact clauses; step verification checks the concept's entry exists |
| `library/validate_book.py` | the four checks above |
| `skills/pull-book/SKILL.md` | no change needed — it sparse-checks-out and copies the whole `books/<id>/` directory, so `research.json` travels automatically |
| BookBank.app | **nothing in Phase 1**; Phase 2 adds a "Re-narrate as…" action that writes `persona` + `revising` + a note (the skill does the rest) |

## Phases

1. **Emit** — `write-book` + `stage-book-build` produce `research.json` on
   every new build/revision; `validate_book.py` checks it. Ship this alone;
   the artifact starts accumulating value immediately.
   **✅ Implemented 2026-07-17** (skill contracts + step prompts + the
   `research` validator rule; legacy books validate with a warning only).
2. **Re-voice** — the revise fast-path + the app's "Re-narrate as…" action.
3. **Refresh / editions** — volatile-guided re-research, claim diff, changelog
   page.

## Non-goals

- **Not a cache of fetched pages** — the distill rule is the design, not an
  optimization.
- **No parallel-write story** — sequential staged steps merge into one file;
  sharding waits for parallel fan-out to exist.
- **No mass backfill** of the existing library — lazy, along revision paths.
- **No claim-verification pass** in Phase 1 — the artifact makes one *possible*
  (every claim is addressable and sourced); building the verifier is its own
  project.
