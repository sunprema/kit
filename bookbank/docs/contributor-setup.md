# Contributing a book

BookBank's authoring tools ship as a Claude Code plugin from this repo
(`sunprema/kit`). You never need the BookBank macOS app, and you never clone
the whole tooling repo into your book's working copy — you install the plugin
once, then clone only the content repo (`sunprema/books`).

## 1. Install the plugin (once)

```
/plugin marketplace add sunprema/kit
/plugin install bookbank@kit
```

This gives you `/write-book`, `/publish-library`, `/create-book-from-issue`,
and `/dispatch-book-issue`, plus the `place_image.py` helper and the
structural validator, wherever you run Claude Code.

## 2. Clone the content repo

```
git clone https://github.com/sunprema/books
cd books
```

That's it — no sparse/partial clone is required to get started, though if you
want to avoid pulling every other book's images while you iterate on one new
book, a partial clone works too:

```
git clone --filter=blob:none --sparse https://github.com/sunprema/books
cd books
git sparse-checkout set books/<your-book-id> assets
```

## 3. Write a book

From inside your `books/` clone, with the plugin installed:

```
/write-book <topic>
```

The skill detects you're standing in a content-repo clone (it looks for a
`books/` dir, a `catalog.json`, or a `sunprema/books`-ish git remote) and
writes the new book under `./books/<id>/` — no `$BOOKBANK_ROOT` needed. Set
`$BOOKBANK_ROOT` explicitly only if you want to point at a different root.

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

If you're a contributor without push access to `sunprema/books`, open a PR
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

| id | voice |
|----|-------|
| `clear-mentor` | Patient senior engineer, example-first |
| `feynman` | First-principles, playful, intuition-first |
| `isaac-newton` | Principled natural philosopher — derives everything from necessity |
| `the-crafter` | Precise incremental teacher, "Crafting Interpreters" style |
| `the-guitarist` | Practical guitar master — calm, no fluff |
| `the-incident-commander` | Learn from outages — every concept is a postmortem |
| `the-historian` | The why behind the weird — technology as history |
| `the-adversary` | Threat-model thinking — understand a system by how it breaks |
| `the-whiteboard-architect` | Boxes, arrows, and trade-offs — systems at scale |
| `the-performance-engineer` | Measure first — mechanical sympathy and real numbers |
| `the-pragmatic-cto` | Boring technology, real deadlines — engineering as economics |

### Built-in themes

Each theme is tokens + a mood; the newer ones also demand *structural
signatures* (spiral spine, scanlines, via-dot corners, …) spelled out in the
theme's `mood` — reproduce them, they're what make the look.

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
