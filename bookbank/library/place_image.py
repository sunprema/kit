#!/usr/bin/env python3
"""
place_image.py — drop a generated image into a BookBank image slot without
the BookBank.app (which just writes bytes to the declared path and
re-encodes to match the slot's extension — see WebView.swift's drag-and-drop
handler; no AI generation happens there either).

Looks up the slot's declared `file`/`aspect` in book.json, converts the
source image to the declared extension, writes it to the exact declared
path, and warns (non-fatal) if the actual aspect ratio is off from the
declared one by more than ~10% — the same "over-tall image blows out the
fixed-height column" failure the write-book skill's docs warn about.

Usage:
  place_image.py <book-dir> <slot-id> <source-file> [--force]

  <book-dir>     path to the book folder (has book.json)
  <slot-id>      an id in book.json's images[]
  <source-file>  the image to place (any format Pillow/sips can read)
  --force        overwrite even if the destination already has a real file
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ASPECT_TOLERANCE = 0.10  # ~10%


def parse_aspect(aspect_str):
    """"16:9" -> 16/9, or None if unparseable."""
    if not aspect_str or ":" not in aspect_str:
        return None
    try:
        w, h = aspect_str.split(":", 1)
        w, h = float(w), float(h)
        return w / h if h else None
    except ValueError:
        return None


def image_size(path: Path):
    """(width, height) via Pillow if available, else macOS `sips`."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        pass
    except Exception:
        return None, None
    try:
        r = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True, text=True)
        w = h = None
        for line in r.stdout.splitlines():
            s = line.strip()
            if s.startswith("pixelWidth:"):
                w = int(s.split(":")[1])
            elif s.startswith("pixelHeight:"):
                h = int(s.split(":")[1])
        return w, h
    except Exception:
        return None, None


def convert_image(src: Path, dst: Path):
    """Write src to dst, converting to dst's extension if they differ.
    Prefers Pillow; falls back to macOS `sips`; copies verbatim if the
    extensions already match. Raises on failure rather than risking a
    silently mismatched-extension file."""
    src_ext = src.suffix.lower().lstrip(".")
    dst_ext = dst.suffix.lower().lstrip(".")
    if src_ext == dst_ext or (src_ext in ("jpg", "jpeg") and dst_ext in ("jpg", "jpeg")):
        shutil.copyfile(src, dst)
        return

    try:
        from PIL import Image
        with Image.open(src) as im:
            if dst_ext in ("jpg", "jpeg") and im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            im.save(dst)
        return
    except ImportError:
        pass

    sips_fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(dst_ext)
    if sips_fmt:
        r = subprocess.run(
            ["sips", "-s", "format", sips_fmt, str(src), "--out", str(dst)],
            capture_output=True, text=True)
        if r.returncode == 0 and dst.is_file():
            return
        raise RuntimeError(f"sips failed to convert {src} -> {dst}: {r.stderr.strip()}")

    raise RuntimeError(
        f"don't know how to convert .{src_ext} -> .{dst_ext} (no Pillow, and "
        f"sips only handles jpeg/png) — convert it yourself and re-run")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book_dir", type=Path)
    ap.add_argument("slot_id")
    ap.add_argument("source_file", type=Path)
    ap.add_argument("--force", action="store_true",
                     help="overwrite even if the destination already exists")
    args = ap.parse_args()

    book_dir = args.book_dir
    bj = book_dir / "book.json"
    if not bj.is_file():
        sys.exit(f"error: no book.json under {book_dir}")
    if not args.source_file.is_file():
        sys.exit(f"error: source file not found: {args.source_file}")

    data = json.loads(bj.read_text(encoding="utf-8"))
    images = data.get("images", [])
    slot = next((im for im in images if im.get("id") == args.slot_id), None)
    if slot is None:
        known = ", ".join(im.get("id", "<no id>") for im in images) or "(none declared)"
        sys.exit(f"error: no image slot {args.slot_id!r} in book.json. Known slots: {known}")

    declared_file = slot.get("file")
    if not declared_file:
        sys.exit(f"error: slot {args.slot_id!r} has no declared 'file' in book.json")
    dst = book_dir / declared_file

    if dst.is_file() and dst.stat().st_size > 0 and not args.force:
        sys.exit(f"error: {dst} already exists — pass --force to overwrite")

    dst.parent.mkdir(parents=True, exist_ok=True)
    convert_image(args.source_file, dst)
    print(f"wrote {dst}")
    sys.stdout.flush()  # keep stdout ahead of the stderr warning below

    declared_aspect = parse_aspect(slot.get("aspect"))
    w, h = image_size(dst)
    if declared_aspect and w and h:
        actual_aspect = w / h
        off_by = abs(actual_aspect - declared_aspect) / declared_aspect
        if off_by > ASPECT_TOLERANCE:
            print(
                f"warning: {dst} is {w}x{h} (aspect {actual_aspect:.3f}) but the "
                f"slot declares aspect {slot.get('aspect')!r} ({declared_aspect:.3f}) — "
                f"off by {off_by * 100:.0f}%. An over-tall image can blow out the "
                "fixed-height column; consider re-cropping/re-generating.",
                file=sys.stderr)
    elif not declared_aspect:
        print(f"warning: slot {args.slot_id!r} has no parseable 'aspect' to check against",
              file=sys.stderr)


if __name__ == "__main__":
    main()
