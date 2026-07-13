#!/usr/bin/env bash
# pull-book-branch.sh — pull the book(s) added/changed on a branch of the
# BookBank content repo into the local data root, without a coding agent
# and without cloning the whole library.
#
# Usage:
#   pull-book-branch.sh [--force] <branch-name>
#
#   <branch-name>  Any branch on $BOOKBANK_BOOKS_REPO (e.g. an unmerged
#                  "claude/book-..." PR branch, or "main").
#   --force        Overwrite a local copy even if its book.json says
#                  status "revising" (otherwise that book is skipped).
#
# Environment (same cascade as the pull-book skill):
#   BOOKBANK_ROOT        local data root       (default: ~/bookbank)
#   BOOKBANK_BOOKS_REPO  GitHub owner/repo     (default: sunprema/books)
#
# Uses the shared sparse/partial clone at <root>/.pull — blobs (images)
# are only ever fetched for books actually requested.

set -euo pipefail

FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; shift; fi
BRANCH="${1:-}"
if [ -z "$BRANCH" ]; then
  echo "usage: $(basename "$0") [--force] <branch-name>" >&2
  exit 2
fi

ROOT="${BOOKBANK_ROOT:-$HOME/bookbank}"
REPO="${BOOKBANK_BOOKS_REPO:-sunprema/books}"
PULL="$ROOT/.pull"

# 1. Ensure the stable sparse/partial clone exists.
if [ ! -d "$PULL/.git" ]; then
  echo "Creating sparse partial clone of $REPO at $PULL ..."
  if command -v gh >/dev/null 2>&1; then
    gh repo clone "$REPO" "$PULL" -- --filter=blob:none --sparse -q
  else
    git clone --filter=blob:none --sparse -q "https://github.com/$REPO.git" "$PULL"
  fi
fi

# 2. Refresh all remote-tracking refs (cheap: no blobs are fetched).
git -C "$PULL" fetch -q --prune origin
if ! git -C "$PULL" rev-parse -q --verify "refs/remotes/origin/$BRANCH" >/dev/null; then
  echo "error: branch '$BRANCH' not found on $REPO" >&2
  exit 1
fi

# 3. Work out which book(s) the branch touches.
if [ "$BRANCH" = "main" ]; then
  echo "error: '$BRANCH' is the default branch — use the pull-book skill with explicit book ids instead" >&2
  exit 2
fi
BOOK_IDS=$(git -C "$PULL" diff --name-only "origin/main...origin/$BRANCH" -- 'books/' \
  | cut -d/ -f2 | sort -u)
if [ -z "$BOOK_IDS" ]; then
  echo "error: branch '$BRANCH' touches no files under books/" >&2
  exit 1
fi
echo "Branch '$BRANCH' touches:" $BOOK_IDS

# 4. Sparse-add the book paths (add, not set — accumulate across pulls),
#    then materialize the branch's version of them.
for id in $BOOK_IDS; do
  git -C "$PULL" sparse-checkout add "books/$id"
done
git -C "$PULL" checkout -q --detach "origin/$BRANCH"
trap 'git -C "$PULL" checkout -q main' EXIT   # always leave the clone on main

# 5. Copy each book into the local library.
mkdir -p "$ROOT/books"
PULLED=""
for id in $BOOK_IDS; do
  src="$PULL/books/$id"
  dst="$ROOT/books/$id"
  if [ ! -d "$src" ]; then
    echo "skip: books/$id does not exist on '$BRANCH' (deleted by the branch?)"
    continue
  fi
  if [ -f "$dst/book.json" ] && [ "$FORCE" -ne 1 ] \
     && grep -q '"status"[[:space:]]*:[[:space:]]*"revising"' "$dst/book.json"; then
    echo "skip: $dst is being revised locally (status \"revising\") — rerun with --force to overwrite"
    continue
  fi
  rm -rf "$dst"
  cp -R "$src" "$dst"
  PULLED="$PULLED $id"
  echo "pulled: $dst"
done

if [ -z "$PULLED" ]; then
  echo "Nothing pulled."
  exit 1
fi
echo "Done. If BookBank.app is running, press ⌘R (Refresh Library) to pick these up."
