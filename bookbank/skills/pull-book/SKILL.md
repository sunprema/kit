---
name: pull-book
description: Pull one or more published BookBank books from the content repo (default sunprema/books) into the local data root, without cloning the whole ~90MB library. Use when the user wants to "pull a book locally", "get <book> into my BookBank app", "sync <book> from the site", or "download just this book". Triggers include "pull-book <id>", "get the http-caching-headers book locally", "sync this book to my app".
---

# pull-book

Publishing (`publish-library`) is one-way — books land on the public
`sunprema/books` repo, but nothing automatically syncs them back into your
own local data root (`$BOOKBANK_ROOT`, the folder BookBank.app reads). This
skill is the reverse direction: grab just the book(s) you actually want,
without a full clone of every other book's art.

## Arguments

- `/pull-book <book-id>` — pull one book.
- `/pull-book <book-id> <book-id> ...` — pull several in one pass.

## How it stays small

A full clone of `$BOOKBANK_BOOKS_REPO` pulls every book's images along with
it (~90MB and growing). Instead, keep a **stable sparse/partial clone** at
`<root>/.pull`, analogous to `publish-library`'s `<root>/.publish` — reused
across pulls so repeat calls are a cheap `git pull`, not a re-clone, and
`--filter=blob:none` means blobs (images) are only fetched for paths
actually listed in the sparse-checkout, never for books you didn't ask for:

```bash
REPO="${BOOKBANK_BOOKS_REPO:-sunprema/books}"
PULL="${BOOKBANK_ROOT:-$HOME/bookbank}/.pull"
if [ -d "$PULL/.git" ]; then
  git -C "$PULL" sparse-checkout add books/<id1> books/<id2> ...
  git -C "$PULL" pull -q origin main
else
  gh repo clone "$REPO" "$PULL" -- --filter=blob:none --sparse -q
  git -C "$PULL" sparse-checkout set books/<id1> books/<id2> ...
fi
```

(`sparse-checkout add`, not `set`, on an existing clone — `set` would
*replace* the sparse path list and drop books pulled in a previous call,
losing their local copy's link to the shared clone. `add` accumulates.)

## Procedure

1. Resolve root via the usual cascade (`$BOOKBANK_ROOT` → cwd if it looks
   like a content-repo clone → `~/bookbank`) and repo via
   `$BOOKBANK_BOOKS_REPO` (default `sunprema/books`).
2. Run the clone/pull-and-sparse-checkout sequence above for every requested
   book id.
3. For each book id, copy `<root>/.pull/books/<id>` to
   `<root>/books/<id>`, **overwriting** any existing local copy — this
   skill's whole point is "give me the current published version," so a
   stale local copy (e.g. one you'd started revising locally) is
   intentionally replaced. If that matters, warn before overwriting a local
   copy whose `book.json` has uncommitted-looking differences (e.g.
   `status: "revising"`) rather than silently clobbering it.
4. Report which book(s) landed and their local path. If BookBank.app is
   running, mention pressing **⌘R** (Refresh Library) to pick them up
   without relaunching.

## Notes

- This only pulls what's on `main` (published, `"ready"` books) — for a book
  still on an open PR branch, run the standalone script in this skill's
  directory instead: `pull-book-branch.sh [--force] <branch-name>`. It
  discovers which book(s) the branch touches, fetches just those into the
  same `.pull` sparse clone, copies them into `<root>/books/`, and leaves
  the clone back on `main`. `--force` overwrites a local copy whose
  `book.json` says `"revising"` (otherwise that book is skipped). No agent
  needed — it's plain bash.
- The reverse direction (you edited a pulled book locally and want the change
  back on the repo) is `push-book-pr.sh [--onto <branch>] [--dry-run]
  <book-id> [commit message...]`, in the same directory. It commits the local
  copy of `books/<id>` and raises a PR off `main` — or, with `--onto`, pushes
  onto an existing unmerged branch (e.g. `claude/book-...`) to update that
  branch's open PR instead of opening a duplicate. `--dry-run` shows the
  commit without pushing. Also plain bash (git + gh).
- `<root>/.pull` accumulates sparse paths over time and is safe to delete
  entirely if it grows unwieldy — the next pull just re-clones it.
