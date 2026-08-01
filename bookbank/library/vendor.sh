#!/usr/bin/env bash
# Copy a plugin-shipped runtime asset into a book. One call, no paths to fill in.
#
#   "$CLAUDE_PLUGIN_ROOT/library/vendor.sh" <book-dir> <asset>...
#
#   "$CLAUDE_PLUGIN_ROOT/library/vendor.sh" "$BOOK" book-progress.js
#   "$CLAUDE_PLUGIN_ROOT/library/vendor.sh" "$BOOK" book-widgets.js book-three.js
#   "$CLAUDE_PLUGIN_ROOT/library/vendor.sh" "$BOOK" diagram-kit.css   # appends to book.css
#
# Why this exists rather than a `cp` in each SKILL.md: the copy has a plugin
# path on one side and a book path on the other, and the SKILL.md snippets
# wrote the book side as a literal `<book-dir>` placeholder. An agent following
# those steps holds both paths at once, and the failure mode observed on
# 2026-08-01 was a write aimed back at the plugin's own master copy — editing
# the installed plugin (or, with a `directory` marketplace, the kit checkout
# itself) instead of the book. That is unrecoverable-by-the-run damage: every
# later book inherits it.
#
# So the destinations live here, the caller names only the asset, and the
# script refuses outright to write anywhere under the plugin root.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"   # bookbank/ plugin root
ROOT="${CLAUDE_PLUGIN_ROOT:-$HERE}"
ROOT="$(cd "$ROOT" && pwd -P)"

usage() {
  {
    echo "usage: vendor.sh <book-dir> <asset>..."
    echo
    echo "assets:"
    echo "  book-progress.js   reading-progress runtime  -> <book>/assets/"
    echo "  book-widgets.js    2D canvas widget runtime  -> <book>/assets/vendor/"
    echo "  book-three.js      3D figure runtime         -> <book>/assets/vendor/"
    echo "  diagram-kit.css    shared diagram vocabulary -> appended to <book>/assets/book.css"
  } >&2
}

[ "$#" -ge 2 ] || { usage; exit 2; }

BOOK="$1"; shift

# ── The book directory must actually be a book ────────────────────────────
# Same spirit as resolve-repo.sh: derive nothing from a directory that does not
# look the part. Without this, a caller standing in the wrong place vendors
# into whatever cwd happened to be.
[ -d "$BOOK" ] || { echo "vendor.sh: no such book directory: $BOOK" >&2; exit 2; }
BOOK="$(cd "$BOOK" && pwd -P)"

if [ ! -f "$BOOK/book.json" ]; then
  {
    echo "vendor.sh: $BOOK has no book.json, so it is not a book directory."
    echo "  Pass the book's own folder — <books-root>/books/<book-id>."
  } >&2
  exit 2
fi

# ── The plugin is read-only, always ───────────────────────────────────────
# The one rule this script exists to enforce. A book living inside the plugin
# tree is either a mistake or the exact misdirected-write bug; either way it is
# a stop, not a warning.
case "$BOOK/" in
  "$ROOT"/*)
    {
      echo "vendor.sh: refusing to write inside the plugin root."
      echo "  book:   $BOOK"
      echo "  plugin: $ROOT"
      echo "  The plugin ships the master copies and is never written to."
      echo "  Vendor into the book under your books checkout instead."
    } >&2
    exit 2
    ;;
esac

vendor_one() {
  local asset="$1" src dest mode
  mode=copy
  case "$asset" in
    book-progress.js) src="skills/book-progress/assets/book-progress.js"
                      dest="assets/book-progress.js" ;;
    book-widgets.js)  src="widgets/book-widgets.js"
                      dest="assets/vendor/book-widgets.js" ;;
    book-three.js)    src="skills/webgl-animations/assets/book-three.js"
                      dest="assets/vendor/book-three.js" ;;
    diagram-kit.css)  src="skills/book-diagrams/assets/diagram-kit.css"
                      dest="assets/book.css"; mode=append ;;
    *) echo "vendor.sh: unknown asset: $asset" >&2; usage; return 2 ;;
  esac

  [ -f "$ROOT/$src" ] || { echo "vendor.sh: missing in plugin: $ROOT/$src" >&2; return 2; }

  if [ "$mode" = append ]; then
    # book.css is the book's own stylesheet; diagram-kit is appended to it so
    # figures share one vocabulary library-wide. Marker-guarded so re-running
    # (a resumed build, a revision) never duplicates the block.
    local marker="/* bookbank:diagram-kit */"
    [ -f "$BOOK/$dest" ] || { echo "vendor.sh: $BOOK/$dest does not exist yet — write book.css first" >&2; return 2; }
    if grep -qF "$marker" "$BOOK/$dest"; then
      echo "vendor.sh: $dest already carries $asset — unchanged"
      return 0
    fi
    { printf '\n%s\n' "$marker"; cat "$ROOT/$src"; } >> "$BOOK/$dest"
    echo "vendor.sh: appended $asset -> $dest"
    return 0
  fi

  mkdir -p "$BOOK/$(dirname "$dest")"
  cp "$ROOT/$src" "$BOOK/$dest"
  echo "vendor.sh: $asset -> $dest"
}

status=0
for asset in "$@"; do
  vendor_one "$asset" || status=$?
done
exit "$status"
