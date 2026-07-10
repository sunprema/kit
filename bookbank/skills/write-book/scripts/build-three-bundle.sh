#!/usr/bin/env bash
# build-three-bundle.sh — vendor three.js (+ addons) into a book as one offline
# classic IIFE that sets window.THREE. This is the ONLY three.js loading path that
# works from a BookBank book's file:// origin (CDN = no network; ES modules =
# CORS-blocked from the null file:// origin in WKWebView; the old UMD global was
# removed in r161). See SKILL.md → "3D figures (three.js)".
#
# Usage:
#   build-three-bundle.sh <book-dir> [Name=import-spec ...]
#
#   <book-dir>        Path to the book folder (e.g. "$BOOKBANK_ROOT/books/my-book").
#                     Output is written to <book-dir>/assets/vendor/three.iife.js
#                     and loaded on a page one level down with:
#                       <script src="../assets/vendor/three.iife.js"></script>
#   Name=import-spec  Extra addons to fold onto window.THREE. Defaults to
#                     OrbitControls if none given. Examples:
#                       OrbitControls=three/addons/controls/OrbitControls.js
#                       GLTFLoader=three/addons/loaders/GLTFLoader.js
#                       RoomEnvironment=three/addons/environments/RoomEnvironment.js
#
# Env:
#   THREE_VERSION   Pin the three release (default: latest). e.g. THREE_VERSION=0.185.1
#   FORCE=1         Rebuild even if the bundle already exists.
#
# Examples:
#   build-three-bundle.sh "$BOOKBANK_ROOT/books/solar-system"
#   build-three-bundle.sh "$BOOKBANK_ROOT/books/gltf-demo" \
#       OrbitControls=three/addons/controls/OrbitControls.js \
#       GLTFLoader=three/addons/loaders/GLTFLoader.js
set -euo pipefail

BOOK_DIR="${1:-}"
if [[ -z "$BOOK_DIR" ]]; then
  echo "usage: build-three-bundle.sh <book-dir> [Name=import-spec ...]" >&2
  exit 2
fi
if [[ ! -d "$BOOK_DIR" ]]; then
  echo "error: book dir not found: $BOOK_DIR" >&2
  exit 2
fi
shift || true

OUT="$BOOK_DIR/assets/vendor/three.iife.js"
if [[ -f "$OUT" && "${FORCE:-0}" != "1" ]]; then
  echo "✓ bundle already present: $OUT  (set FORCE=1 to rebuild)"
  exit 0
fi

# Default addon set.
ADDONS=("$@")
if [[ ${#ADDONS[@]} -eq 0 ]]; then
  ADDONS=("OrbitControls=three/addons/controls/OrbitControls.js")
fi

command -v npx >/dev/null || { echo "error: npx/node not found on PATH" >&2; exit 1; }

# Shared build cache so we install three+esbuild once, not per book.
CACHE="${TMPDIR:-/tmp}/bookbank-three-build"
mkdir -p "$CACHE"
cd "$CACHE"

THREE_PKG="three${THREE_VERSION:+@$THREE_VERSION}"
if [[ ! -d node_modules/three || -n "${THREE_VERSION:-}" || ! -d node_modules/esbuild ]]; then
  echo "• installing $THREE_PKG + esbuild in $CACHE …"
  npm i "$THREE_PKG" esbuild >/dev/null 2>&1
fi

# Generate the bundle entry: import THREE, import each addon, attach to window.THREE.
{
  echo "import * as THREE from 'three'"
  for a in "${ADDONS[@]}"; do
    name="${a%%=*}"; spec="${a#*=}"
    if [[ "$name" == "$a" || -z "$spec" ]]; then
      echo "error: addon must be Name=import-spec (got '$a')" >&2; exit 2
    fi
    echo "import { $name } from '$spec'"
  done
  printf 'Object.assign(THREE, {'
  for a in "${ADDONS[@]}"; do printf ' %s,' "${a%%=*}"; done
  echo ' })'
  echo "window.THREE = THREE"
} > "$CACHE/entry.js"

mkdir -p "$(dirname "$OUT")"
npx esbuild "$CACHE/entry.js" --bundle --minify --format=iife --outfile="$OUT"

VER=$(node -p "require('$CACHE/node_modules/three/package.json').version")
echo "✓ three r${VER} + [${ADDONS[*]%%=*}] → $OUT ($(du -h "$OUT" | cut -f1))"
echo "  load it (concept page, one level down) with:"
echo "    <script src=\"../assets/vendor/three.iife.js\"></script>"
