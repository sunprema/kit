#!/usr/bin/env bash
# push-book-pr.sh — the reverse of pull-book-branch.sh: take the local copy
# of a book from the BookBank data root, commit it to the content repo, and
# raise (or update) a pull request. Plain bash + git + gh, no agent needed.
#
# Usage:
#   push-book-pr.sh [--onto <branch>] [--dry-run] <book-id> [commit message...]
#
#   <book-id>       Directory name under <root>/books/ (e.g.
#                   from-disk-to-cpu-how-linux-runs-your-programs).
#   --onto <branch> Commit onto an existing remote branch instead of cutting
#                   a fresh one off main. Use this when the book lives on an
#                   unmerged PR branch (e.g. claude/book-...) — the push
#                   updates that branch's open PR rather than opening a new
#                   one against main that would duplicate the whole book.
#   --dry-run       Do everything except push/PR; prints the commit stat.
#   [message...]    Commit message (default: "Update <book-id>").
#
# Environment (same cascade as the pull-book skill):
#   BOOKBANK_ROOT        local data root       (default: ~/bookbank)
#   BOOKBANK_BOOKS_REPO  GitHub owner/repo     (default: sunprema/books)

set -euo pipefail

ONTO=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --onto)    ONTO="${2:?--onto needs a branch name}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -*)        echo "unknown option: $1" >&2; exit 2 ;;
    *)         break ;;
  esac
done
BOOK_ID="${1:-}"
if [ -z "$BOOK_ID" ]; then
  echo "usage: $(basename "$0") [--onto <branch>] [--dry-run] <book-id> [commit message...]" >&2
  exit 2
fi
shift
MSG="${*:-Update $BOOK_ID}"

ROOT="${BOOKBANK_ROOT:-$HOME/bookbank}"
REPO="${BOOKBANK_BOOKS_REPO:-sunprema/books}"
PULL="$ROOT/.pull"
SRC="$ROOT/books/$BOOK_ID"

if [ ! -d "$SRC" ]; then
  echo "error: no local book at $SRC" >&2
  exit 1
fi

# 1. Ensure the shared sparse/partial clone exists (same one pull uses).
if [ ! -d "$PULL/.git" ]; then
  echo "Creating sparse partial clone of $REPO at $PULL ..."
  if command -v gh >/dev/null 2>&1; then
    gh repo clone "$REPO" "$PULL" -- --filter=blob:none --sparse -q
  else
    git clone --filter=blob:none --sparse -q "https://github.com/$REPO.git" "$PULL"
  fi
fi
git -C "$PULL" fetch -q --prune origin

# 2. Pick the branch: an existing remote branch (--onto), or a fresh one.
if [ -n "$ONTO" ]; then
  if ! git -C "$PULL" rev-parse -q --verify "refs/remotes/origin/$ONTO" >/dev/null; then
    echo "error: --onto branch '$ONTO' not found on $REPO" >&2
    exit 1
  fi
  BRANCH="$ONTO"
  BASE="refs/remotes/origin/$ONTO"
else
  BRANCH="book/$BOOK_ID-update-$(date +%Y%m%d-%H%M%S)"
  BASE="refs/remotes/origin/main"
fi

# 3. Materialize the base branch's version of the book, then lay the local
#    copy over it so git sees exactly the user's edits (adds AND deletes).
git -C "$PULL" sparse-checkout add "books/$BOOK_ID"
git -C "$PULL" checkout -q -B "$BRANCH" "$BASE"
trap 'git -C "$PULL" checkout -q main && git -C "$PULL" branch -q -D "$BRANCH" 2>/dev/null || true' EXIT

rm -rf "$PULL/books/$BOOK_ID"
cp -R "$SRC" "$PULL/books/$BOOK_ID"
git -C "$PULL" add -A "books/$BOOK_ID"

if git -C "$PULL" diff --cached --quiet; then
  echo "No changes: local $BOOK_ID is identical to '$BRANCH' — nothing to commit."
  exit 0
fi

git -C "$PULL" commit -q -m "$MSG"
echo "Committed on '$BRANCH':"
git -C "$PULL" show --stat --oneline HEAD | sed 's/^/  /'

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run — nothing pushed. Rerun without --dry-run to push and raise the PR."
  exit 0
fi

# 4. Push, then create the PR (or just report the existing one when --onto
#    targets a branch that already has one open).
git -C "$PULL" push -q origin "HEAD:refs/heads/$BRANCH"
EXISTING=$(cd "$PULL" && gh pr list --head "$BRANCH" --state open --json url --jq '.[0].url' 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "Pushed. Existing PR updated: $EXISTING"
else
  TITLE=$(sed -n 's/.*"title"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SRC/book.json" | head -1)
  PR_URL=$(cd "$PULL" && gh pr create \
    --head "$BRANCH" \
    --title "$MSG" \
    --body "Updates the book \"${TITLE:-$BOOK_ID}\" (\`books/$BOOK_ID\`) from the local BookBank library.

🤖 Generated with [Claude Code](https://claude.com/claude-code)")
  echo "PR created: $PR_URL"
fi
