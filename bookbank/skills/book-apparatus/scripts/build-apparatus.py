#!/usr/bin/env python3
"""build-apparatus.py — derive a book's index and further-reading from what
the book already contains.

Two things a finished BookBank book is sitting on and never uses:

  * `research.json` records every source with per-claim, per-concept
    citations. That is a further-reading list already — including which
    chapter leans on which source, and which sources the book leans on most.
  * Concept pages mark key terms with `<span class="term">`. That is an index
    already — the author has hand-picked exactly the words worth indexing.

So neither has to be written by hand, and neither can drift from the book,
because both are read back out of it.

Usage:
  build-apparatus.py <book-dir> [--what index|reading|both] [--out DIR]

Writes HTML fragments (not whole pages) to stdout, or to
<out>/further-reading.frag.html and <out>/index.frag.html with --out. The
skill wires them into a page — this script has no opinion about nav chains
or where the apparatus lives.
"""

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TERM_RE = re.compile(r'<span class="term"[^>]*>(.*?)</span>', re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean(s):
    """Strip inner markup and entities from a captured span."""
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()


def sort_key(term):
    """Alphabetical, ignoring case and leading punctuation/backticks."""
    return re.sub(r"^[^0-9a-z]+", "", term.lower())


def load(book: Path, name: str):
    p = book / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"build-apparatus.py: {name} is not valid JSON: {e}", file=sys.stderr)
        return None


def short_title(title):
    """Concept titles are often 'Name — a long descriptive tail'. In a
    cross-reference the tail is noise; keep the name."""
    for sep in (" — ", " – ", " -- ", ": "):
        if sep in title:
            head = title.split(sep, 1)[0].strip()
            if len(head) >= 4:
                return head
    return title.strip()


def concept_titles(bookjson):
    out = {}
    for c in (bookjson or {}).get("concepts", []):
        out[c.get("id", "")] = (short_title(c.get("title", "") or c.get("id", "")),
                                c.get("file", ""))
    return out


def build_reading(book: Path, bookjson, research):
    """Sources, most-cited first, each listing the chapters that rely on it."""
    if not research:
        return None, "no research.json — nothing to derive a reading list from"

    sources = {s["id"]: s for s in research.get("sources", []) if "id" in s}
    if not sources:
        return None, "research.json has no sources[]"

    titles = concept_titles(bookjson)
    cites = defaultdict(set)          # source id -> {concept id}
    for cid, entry in (research.get("concepts") or {}).items():
        for claim in (entry.get("claims") or []):
            for sid in (claim.get("sources") or []):
                cites[sid].add(cid)
        for sid in (entry.get("furtherReading") or []):
            cites[sid].add(cid)

    unknown = sorted({sid for sid in cites if sid not in sources})
    ranked = sorted(
        sources.values(),
        key=lambda s: (-len(cites.get(s["id"], ())), (s.get("title") or "").lower()))

    rows = []
    for s in ranked:
        used = sorted(cites.get(s["id"], ()), key=lambda c: list(titles).index(c) if c in titles else 999)
        where = ", ".join(titles.get(c, (c, ""))[0] for c in used)
        kind = s.get("kind", "")
        rows.append(
            '  <li class="fr-item">\n'
            f'    <a class="fr-title" href="{html.escape(s.get("url", "#"))}">'
            f'{html.escape(s.get("title", s["id"]))}</a>\n'
            + (f'    <span class="fr-kind">{html.escape(kind)}</span>\n' if kind else "")
            + (f'    <span class="fr-where">Cited in: {html.escape(where)}</span>\n' if where else
               '    <span class="fr-where fr-unused">Background — not cited directly</span>\n')
            + "  </li>"
        )

    frag = ('<section class="further-reading" data-anchor="further-reading">\n'
            '  <h2>Further reading</h2>\n'
            '  <p class="fr-note">Every source this book draws on, the most-used first.</p>\n'
            '  <ul class="fr-list">\n' + "\n".join(rows) + "\n  </ul>\n</section>\n")
    warn = (f"{len(unknown)} claim(s) cite source ids not in sources[]: {', '.join(unknown)}"
            if unknown else None)
    return frag, warn


def build_index(book: Path, bookjson):
    """Every <span class="term"> in the book, alphabetised, with its pages."""
    titles = concept_titles(bookjson)
    order = list(titles)
    pages = []
    if (book / "index.html").is_file():
        pages.append(("index.html", "Cover"))
    for cid in order:
        _, f = titles[cid]
        if f and (book / f).is_file():
            pages.append((f, titles[cid][0]))
    for extra in ("cheatsheet.html",):
        if (book / extra).is_file() and not any(p[0] == extra for p in pages):
            pages.append((extra, "Cheatsheet"))

    hits = defaultdict(list)          # normalised term -> [(display, file, title)]
    for f, title in pages:
        text = (book / f).read_text(encoding="utf-8", errors="replace")
        for raw in TERM_RE.findall(text):
            t = clean(raw)
            if not t or len(t) > 60:
                continue
            hits[t.lower()].append((t, f, title))

    if not hits:
        return None, ('no <span class="term"> markup found — the index is derived '
                      "from the terms the author marked, so mark them first")

    rows = []
    for key in sorted(hits, key=sort_key):
        entries = hits[key]
        display = entries[0][0]
        seen, links = set(), []
        for _, f, title in entries:
            if f in seen:
                continue
            seen.add(f)
            links.append(f'<a href="{html.escape(f)}">{html.escape(title)}</a>')
        rows.append(f'  <li><span class="ix-term">{html.escape(display)}</span>'
                    f'<span class="ix-refs">{" · ".join(links)}</span></li>')

    frag = ('<section class="book-index" data-anchor="book-index">\n'
            '  <h2>Index</h2>\n'
            '  <ul class="ix-list">\n' + "\n".join(rows) + "\n  </ul>\n</section>\n")
    return frag, None


def main():
    ap = argparse.ArgumentParser(description="Derive index / further reading for a BookBank book.")
    ap.add_argument("book_dir", type=Path)
    ap.add_argument("--what", choices=["index", "reading", "both"], default="both")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    book = args.book_dir
    bookjson = load(book, "book.json")
    if bookjson is None:
        print(f"build-apparatus.py: {book} is not a book folder (no book.json)", file=sys.stderr)
        return 2
    research = load(book, "research.json")

    produced = []
    if args.what in ("reading", "both"):
        frag, warn = build_reading(book, bookjson, research)
        if warn:
            print(f"build-apparatus.py: NOTE (further reading): {warn}", file=sys.stderr)
        if frag:
            produced.append(("further-reading.frag.html", frag))
    if args.what in ("index", "both"):
        frag, warn = build_index(book, bookjson)
        if warn:
            print(f"build-apparatus.py: NOTE (index): {warn}", file=sys.stderr)
        if frag:
            produced.append(("index.frag.html", frag))

    if not produced:
        print("build-apparatus.py: nothing to produce", file=sys.stderr)
        return 1

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, frag in produced:
            (args.out / name).write_text(frag, encoding="utf-8")
            print(f"wrote {args.out / name}")
    else:
        for name, frag in produced:
            print(f"<!-- ==== {name} ==== -->")
            print(frag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
