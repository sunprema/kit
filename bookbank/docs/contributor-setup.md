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
