#!/usr/bin/env bash
# Print the books repo as "owner/name", or exit 2 with a setup hint.
#
#   REPO="$("$CLAUDE_PLUGIN_ROOT/library/resolve-repo.sh")"        # cwd
#   REPO="$("$CLAUDE_PLUGIN_ROOT/library/resolve-repo.sh" "$DIR")" # a clone
#
# Resolution order — first match wins, matching build-library.py exactly:
#   1. $BOOKBANK_BOOKS_REPO
#   2. the `origin` remote of <dir> (default: cwd), if it's a github.com URL
#
# There is deliberately no third tier. A baked-in default would let a fresh
# install publish into somebody else's library; deriving from the clone you are
# standing in can only ever resolve to your own. This is what lets a cloud
# routine and a CI job run with no configuration at all — the session already
# has the books repo checked out.
set -euo pipefail

DIR="${1:-.}"

url=""
# Only derive from a directory that actually looks like a books content repo.
# <dir> is often just wherever the user happened to be standing, and without
# this an unrelated project's origin would resolve as "their books repo" and
# the caller would go on to clone or push against it. An explicit
# $BOOKBANK_BOOKS_REPO skips the check — naming it is the override.
if [ -d "$DIR" ] && { [ -d "$DIR/books" ] || [ -f "$DIR/catalog.json" ]; }; then
  # `git remote get-url` exits 128 outside a repo; under `set -o pipefail` that
  # would abort the caller with no message, so swallow it explicitly.
  url="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
fi

repo="${BOOKBANK_BOOKS_REPO:-$(
  printf '%s' "$url" \
    | sed -nE 's#^(git@github\.com:|(https?://|ssh://git@)github\.com/)([^/]+/.+)$#\3#p' \
    | sed -E 's#\.git$##; s#/$##'
)}"

if [ -z "$repo" ] || [ "${repo%%/*}" = "$repo" ]; then
  {
    echo "no books repo could be resolved."
    echo "  Run this from inside a clone of your books repo — one with a books/"
    echo "  dir or a catalog.json, so the slug can be taken from its origin"
    echo "  remote — or name it explicitly:"
    echo "    export BOOKBANK_BOOKS_REPO=<owner>/<name>"
  } >&2
  exit 2
fi

printf '%s\n' "$repo"
