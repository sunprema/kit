# Writing and publishing books

BookBank's authoring tools ship as a Claude Code plugin from this repo
(`sunprema/kit`). You never need the BookBank macOS app, and you never clone
the whole tooling repo into your book's working copy — you install the plugin
once, then work inside your own **content repo**, which is where books live
and what GitHub Pages serves.

Two ways to use this: **run your own library** (the normal case) or
**contribute a book to someone else's**. Step 2 is where they differ.

## 1. Install the plugin (once)

```
/plugin marketplace add sunprema/kit
/plugin install bookbank@kit
```

This gives you `/write-book`, `/publish-library`, `/create-book-from-issue`,
and `/dispatch-book-issue`, plus the `place_image.py` helper and the
structural validator, wherever you run Claude Code.

## 2a. Run your own library

Create a public repo to hold the books and serve the site — the name is up to
you (`books` is the convention):

```
gh repo create <owner>/books --public --clone
cd books
```

Enable Pages: **Settings → Pages → Source: Deploy from a branch → `main` /
`root`**. That's the whole setup — while you're working inside the clone, the
tooling derives your repo slug from its `origin` remote, so **there is nothing
to export**.

If you want to run from somewhere else (say a `~/bookbank` data root), name the
repo explicitly:

```
export BOOKBANK_BOOKS_REPO="<owner>/books"
```

Resolution order is `--repo` → `$BOOKBANK_BOOKS_REPO` → the clone's `origin`
remote. There is **no baked-in default**, so a fresh install can never publish
into some other account's library; if none of the three resolve, the tools stop
with a setup hint. Set `$BOOKBANK_SITE_URL` only if you serve from a custom
domain; otherwise it's derived as `https://<owner>.github.io/books`.

## 2b. Or contribute to an existing library

Clone the library you're contributing to and work inside it (the slug is derived
from the clone, same as above). No sparse/partial clone is required to get
started, though if you want to avoid pulling every other book's images while you
iterate on one new book:

```
git clone --filter=blob:none --sparse https://github.com/<owner>/books
cd books
git sparse-checkout set books/<your-book-id> assets
```

You'll open a PR rather than publishing directly — see step 5.

## 3. Write a book

From inside your `books/` clone, with the plugin installed:

```
/write-book <topic>
```

The skill detects you're standing in a content-repo clone (it looks for a
`books/` dir, a `catalog.json`, or a git remote matching
`$BOOKBANK_BOOKS_REPO`) and writes the new book under `./books/<id>/` — no
`$BOOKBANK_ROOT` needed. Set `$BOOKBANK_ROOT` explicitly only if you want to
point at a different root.

## 4. Drop in artwork

Any image slot the skill leaves (`images[]` in `book.json`) can be filled
without the app:

```
python3 <plugin>/library/place_image.py <book-dir> <slot-id> <path-to-image>
```

Find `<plugin>` with `echo $CLAUDE_PLUGIN_ROOT` from inside a skill session,
or just ask Claude to run it — the skills invoke it via
`${CLAUDE_PLUGIN_ROOT}/library/place_image.py`.

## 5. Publish (or open a PR)

If you're the repo owner:

```
/publish-library <book-id>
```

It regenerates the shelf and catalog, pushes, and waits for Pages to go live.
Commits are made as **you** — whatever `git config user.email` says; the skill
never substitutes an identity.

If you're a contributor without push access to the library, open a PR
instead — commit your book folder and `git push` to a fork, then
`gh pr create`. A maintainer runs `/publish-library` after merge.

## Personas & themes

- **Built-in** personas/themes ship in this plugin's `defaults/`.
- **Per-user** overrides go in `~/.claude/bookbank/personas|themes/<id>.json` —
  useful for a voice/look you use across every book you write.
- **Per-clone** overrides go in `<content-repo-clone>/personas|themes/<id>.json`
  — never published (the publisher only syncs `books/*`), so it's safe for a
  one-off local experiment.

First match wins, in that order (clone → user → plugin default).

### Built-in personas

`book.json`'s `persona` field takes one of these ids, or the special value
`auto` — write-book then picks the best-fitting voice for the topic at build
time and replaces `auto` with the chosen id (once per book; the whole book is
one narrator).

Each persona describes a **style of explanation**, and the narrator name a book
displays is descriptive (e.g. "The First-Principles Physicist"). Don't put a
real person's name in a persona you add: a published book credits its narrator
on the cover and in the catalog, and a real name there reads as authorship or
endorsement by someone who had no part in it. The `feynman` and `isaac-newton`
ids predate this rule and are kept only so existing `book.json` files keep
resolving.

| id | voice |
|----|-------|
| `clear-mentor` | Patient senior engineer, example-first |
| `feynman` | First-principles, playful, intuition-first |
| `isaac-newton` | Principled natural philosopher — derives everything from necessity |
| `the-crafter` | Precise incremental teacher — build it a piece at a time |
| `the-guitarist` | Practical guitar master — calm, no fluff |
| `the-incident-commander` | Learn from outages — every concept is a postmortem |
| `the-historian` | The why behind the weird — technology as history |
| `the-adversary` | Threat-model thinking — understand a system by how it breaks |
| `the-whiteboard-architect` | Boxes, arrows, and trade-offs — systems at scale |
| `the-performance-engineer` | Measure first — mechanical sympathy and real numbers |
| `the-pragmatic-cto` | Boring technology, real deadlines — engineering as economics |
| `the-shonen-sensei` | Training arcs and named techniques — mastery earned one rival at a time |

### Built-in themes

Each theme is tokens + a mood + an `art` direction. The `mood` drives the CSS
skin, and the newer themes also demand *structural signatures* (spiral spine,
scanlines, via-dot corners, panel borders, …) spelled out there — reproduce
them, they're what make the look. The `art` string is not CSS: `write-book`
opens every image-slot prompt with it verbatim, including the cover, so a
book's generated artwork stays in the same visual world as its skin. A theme
you add should carry all three.

| id | look |
|----|------|
| `binder` | Spiral-bound practice notebook — cream ruled leaves, red-pen accent |
| `blueprint` | Cyan-on-navy drafting grid — technical and precise |
| `chalkboard` | Slate board and chalk — math and first principles |
| `codex` | Warm aged paper — a classic printed book |
| `observatory` | Deep space, glowing ink — built for wonder |
| `phosphor` | Green-phosphor CRT — scanlines, glow, a blinking cursor |
| `swiss` | White field, black grotesque, one red accent — grid discipline |
| `riso` | Two-ink zine — federal blue + fluoro pink, lovingly misregistered |
| `circuit` | Solder-mask green + copper traces — silkscreen precision |
| `aurora` | Polar-night gradients and frosted glass — calm and premium |
| `arcade` | Synthwave cabinet — neon horizon, pixel progress, LEVEL 01 |
| `manga` | Sumi ink on newsprint — panel borders, screentone, one vermilion shout |
