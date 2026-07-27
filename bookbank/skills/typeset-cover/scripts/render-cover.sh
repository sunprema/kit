#!/usr/bin/env bash
# render-cover.sh — render a typeset cover page to <book-dir>/cover.webp.
#
# The gallery (build-library.py's cover_rel) looks for a book's cover in this
# order: cover.{webp,png} at the book root, then assets/img/cover-art.*, then
# assets/img/cover.*. So a root cover.webp WINS over any image slot — which is
# the whole point of this skill: a book can ship a finished cover with no art
# round-trip at all.
#
# Shelf cards are 16:10 with object-fit:cover (build-library.py's .cover rule),
# so anything that isn't 16:10 gets cropped. We render and encode exactly 16:10.
#
# Usage:
#   render-cover.sh <cover.html> <book-dir> [--width 1600]
#
#   <cover.html>  A self-contained HTML page (inline CSS, no network). Composed
#                 by the skill from the book's theme — see SKILL.md.
#   <book-dir>    The book folder; output goes to <book-dir>/cover.webp
#
# Env:
#   COVER_QUALITY  WebP quality (default 90 — higher than place_image.py's 82
#                  because flat type has hard edges that show ringing, and a
#                  typeset cover compresses tiny anyway).
#   KEEP_PNG=1     Also keep the intermediate PNG next to the HTML, for
#                  inspecting what the browser actually drew.
#
# Rendering notes:
#   We rasterize at 2x (device-scale-factor) and downsample with LANCZOS. Large
#   flat type aliases badly at 1x; supersampling is what makes the edges look
#   printed rather than screenshotted.
set -euo pipefail

usage(){ sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

[ $# -ge 2 ] || usage
COVER_HTML="$1"; shift
BOOK_DIR="$1"; shift

WIDTH=1600
while [ $# -gt 0 ]; do
  case "$1" in
    --width) WIDTH="${2:?--width needs a value}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "render-cover.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

[ -f "$COVER_HTML" ] || { echo "render-cover.sh: no such file: $COVER_HTML" >&2; exit 2; }
[ -d "$BOOK_DIR" ]   || { echo "render-cover.sh: no such directory: $BOOK_DIR" >&2; exit 2; }

# 16:10 — matches the shelf card so nothing is cropped.
HEIGHT=$(( WIDTH * 10 / 16 ))
QUALITY="${COVER_QUALITY:-90}"

# ── Find a Chromium-family browser ───────────────────────────────────────────
CHROME=""
for c in \
  "${CHROME_BIN:-}" \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium" \
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  "$(command -v google-chrome     2>/dev/null || true)" \
  "$(command -v google-chrome-stable 2>/dev/null || true)" \
  "$(command -v chromium          2>/dev/null || true)" \
  "$(command -v chromium-browser  2>/dev/null || true)"
do
  [ -n "$c" ] && [ -x "$c" ] && { CHROME="$c"; break; }
done

if [ -z "$CHROME" ]; then
  echo "render-cover.sh: no Chromium-family browser found." >&2
  echo "  Install Google Chrome, or set CHROME_BIN=/path/to/chrome." >&2
  echo "  (Safari cannot be driven headlessly for this.)" >&2
  exit 3
fi

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/bookbank-cover.XXXXXX")"
trap 'rm -rf "$TMPDIR_RUN"' EXIT
RAW_PNG="$TMPDIR_RUN/cover-raw.png"

# --virtual-time-budget lets fonts settle before the shot; without it, a cover
# can be captured mid-layout with fallback metrics and the type jumps.
"$CHROME" \
  --headless \
  --disable-gpu \
  --hide-scrollbars \
  --force-device-scale-factor=2 \
  --window-size="${WIDTH},${HEIGHT}" \
  --virtual-time-budget=4000 \
  --screenshot="$RAW_PNG" \
  "file://$(cd "$(dirname "$COVER_HTML")" && pwd)/$(basename "$COVER_HTML")" \
  >/dev/null 2>&1 || true

[ -s "$RAW_PNG" ] || { echo "render-cover.sh: browser produced no screenshot" >&2; exit 4; }

OUT="$BOOK_DIR/cover.webp"

# ── Downsample + encode ──────────────────────────────────────────────────────
if python3 -c "import PIL" 2>/dev/null; then
  python3 - "$RAW_PNG" "$OUT" "$WIDTH" "$HEIGHT" "$QUALITY" <<'PY'
import sys
from PIL import Image
raw, out, w, h, q = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
im = Image.open(raw).convert("RGB")
if im.size != (w, h):
    im = im.resize((w, h), Image.LANCZOS)   # supersample down from the 2x raster
im.save(out, "WEBP", quality=q, method=6)
PY
elif command -v cwebp >/dev/null 2>&1; then
  # cwebp resizes on the way in, so we still get the supersampling benefit.
  cwebp -quiet -q "$QUALITY" -m 6 -resize "$WIDTH" "$HEIGHT" "$RAW_PNG" -o "$OUT"
else
  echo "render-cover.sh: need Pillow (pip install pillow) or cwebp (brew install webp)" >&2
  echo "  to encode WebP — macOS sips cannot write it." >&2
  exit 5
fi

[ -s "$OUT" ] || { echo "render-cover.sh: failed to write $OUT" >&2; exit 6; }

if [ "${KEEP_PNG:-}" = "1" ]; then
  cp "$RAW_PNG" "$(dirname "$COVER_HTML")/cover-raw.png"
  echo "kept: $(dirname "$COVER_HTML")/cover-raw.png"
fi

BYTES=$(wc -c < "$OUT" | tr -d ' ')
echo "wrote $OUT (${WIDTH}x${HEIGHT}, ${BYTES} bytes, q${QUALITY})"
