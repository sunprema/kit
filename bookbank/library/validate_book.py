#!/usr/bin/env python3
"""
validate_book.py — deterministic structural checks for a BookBank book folder.

Catches the known BookBank failure modes documented in the write-book skill
and prior incident fixes, so they're caught in CI / a Claude Code hook instead
of a human noticing mojibake or a broken page-fold after the fact:

  charset          <meta charset="utf-8"> must appear before any non-ASCII
                   byte in every HTML page, or file:// WKWebView renders
                   mojibake (headless-Chrome screenshots won't show this).
  self-contained   no CDN <script>/<link> and no <script type="module">
                   (module scripts are blocked loading from file://; three.js
                   must be vendored as a classic IIFE — see the write-book
                   skill's "Loading three.js offline" section).
  nav-contract     rel="next"/"prev"/"home" wired per the skill's page-turn
                   keyboard contract.
  fold-padding     assets/book.js's multicolumn layout() must subtract the
                   leaf's horizontal padding, or the two-page spread overflows
                   (the `guitar` book is the canonical correct fold).
  click-routing    assets/book.js must route clicks on rel~="next"/"prev"
                   through the pager, or a mouse click skips a chapter's
                   remaining spreads (real bug, 2026-07-04).
  mobile-fallback  book.css must collapse the spread below ~900px.
  book-json        book.json is valid JSON, has the required fields, and is
                   internally consistent (every concept a "ready" status
                   claims has its file on disk).
  image-slots      [warning] every images[] entry's declared file exists on
                   disk. Non-fatal: a book's text can legitimately be "ready"
                   before its art is dropped (build-library.py falls back to
                   a gradient cover for exactly this case).
  research         research.json (the research/prose split's durable research
                   artifact — see docs/research-prose-split.md). Missing file
                   is a [warning] (legacy book, backfilled lazily); a present
                   but malformed file is an error; a "ready" concept with no
                   (or an empty) entry, an unsourced claim, or a claim citing
                   an unknown source id are [warning]s.

Every finding has a severity, "error" (default) or "warning" — only an
"error"-severity finding fails the run (see Finding.severity).

Usage:
  validate_book.py <book-dir> [<book-dir> ...]
  validate_book.py --root <bookbank-root> [--only id1,id2]   # validate many
  validate_book.py --root <bookbank-root> --changed-under <path>  # only book
                   dirs that contain at least one path under <path> (CI diff)

Exits 0 if every book has no error-severity finding, 1 otherwise. Warnings
are printed but never fail the run.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def default_root():
    """$BOOKBANK_ROOT, else cwd if it looks like a content-repo clone (has
    books/, catalog.json, or a sunprema/books-ish git remote), else ~/bookbank.
    Same cascade as build-library.py's --root default."""
    if os.environ.get("BOOKBANK_ROOT"):
        return Path(os.environ["BOOKBANK_ROOT"])
    cwd = Path.cwd()
    repo_hint = os.environ.get("BOOKBANK_BOOKS_REPO", "sunprema/books")
    if (cwd / "books").is_dir() or (cwd / "catalog.json").is_file():
        return cwd
    try:
        remotes = subprocess.run(["git", "remote", "-v"], cwd=cwd,
                                  capture_output=True, text=True, timeout=3).stdout
        if repo_hint in remotes:
            return cwd
    except Exception:
        pass
    return Path.home() / "bookbank"


class Finding:
    def __init__(self, book, rule, path, message, severity="error"):
        self.book = book
        self.rule = rule
        self.path = path
        self.message = message
        self.severity = severity  # "error" (default, fails the run) or "warning"

    def __str__(self):
        loc = f"{self.path}: " if self.path else ""
        tag = "" if self.severity == "error" else f"{self.severity.upper()} "
        return f"[{self.book}] {tag}{self.rule}: {loc}{self.message}"


def iter_html(book_dir: Path):
    for f in sorted(book_dir.glob("*.html")):
        yield f
    concepts = book_dir / "concepts"
    if concepts.is_dir():
        for f in sorted(concepts.glob("*.html")):
            yield f


REL_RE = re.compile(r'rel=["\']([^"\']*)["\']')


def _rels(text):
    out = set()
    for m in REL_RE.finditer(text):
        out.update(m.group(1).split())
    return out


def check_charset(book_dir: Path, book_id: str, findings: list):
    charset_re = re.compile(rb'<meta\s+charset\s*=\s*["\']?utf-8["\']?', re.IGNORECASE)
    for f in iter_html(book_dir):
        data = f.read_bytes()
        m = charset_re.search(data)
        rel = f.relative_to(book_dir)
        if not m:
            findings.append(Finding(book_id, "charset", rel,
                'missing <meta charset="utf-8"> — page will render as mojibake '
                "in the app's file:// WKWebView"))
            continue
        prefix = data[:m.start()]
        try:
            prefix.decode("ascii")
        except UnicodeDecodeError:
            findings.append(Finding(book_id, "charset", rel,
                "non-ASCII byte appears before the charset declaration — move "
                "<meta charset=\"utf-8\"> earlier (before <title>, right after <head>)"))


# Plain <a href="https://…"> source citations are expected (the skill asks
# authors to "cite sources at the foot of a page") — only flag references that
# the browser must actually fetch to render/run the page: a <script src>, a
# <link href> (stylesheet/etc.), or a CSS @import/url().
SCRIPT_SRC_RE = re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']https?://', re.IGNORECASE)
LINK_HREF_RE = re.compile(r'<link\b[^>]*\bhref\s*=\s*["\']https?://', re.IGNORECASE)
CSS_REMOTE_RE = re.compile(r'@import\s+["\']https?://|url\(\s*["\']?https?://', re.IGNORECASE)
MODULE_SCRIPT_RE = re.compile(r'<script[^>]+type\s*=\s*["\']module["\']', re.IGNORECASE)


def check_self_contained(book_dir: Path, book_id: str, findings: list):
    for f in iter_html(book_dir):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(book_dir)
        if SCRIPT_SRC_RE.search(text) or LINK_HREF_RE.search(text):
            findings.append(Finding(book_id, "self-contained", rel,
                "loads a <script>/<link> from a remote http(s):// URL — the book "
                "must render fully offline from file://"))
        if CSS_REMOTE_RE.search(text):
            findings.append(Finding(book_id, "self-contained", rel,
                "references a remote http(s):// URL in a style — the book must "
                "render fully offline from file://"))
        if MODULE_SCRIPT_RE.search(text):
            findings.append(Finding(book_id, "self-contained", rel,
                '<script type="module"> is blocked loading from file:// in '
                "WKWebView/Safari — vendor three.js etc. as a classic IIFE instead"))

    assets = book_dir / "assets"
    if assets.is_dir():
        for f in sorted(assets.rglob("*.css")) + sorted(assets.rglob("*.js")):
            text = f.read_text(encoding="utf-8", errors="replace")
            rel = f.relative_to(book_dir)
            if CSS_REMOTE_RE.search(text):
                findings.append(Finding(book_id, "self-contained", rel,
                    "references a remote http(s):// URL — the book must render "
                    "fully offline from file://"))


def check_nav_contract(book_dir: Path, book_id: str, findings: list):
    concepts = sorted((book_dir / "concepts").glob("*.html")) if (book_dir / "concepts").is_dir() else []
    for i, f in enumerate(concepts):
        text = f.read_text(encoding="utf-8", errors="replace")
        rels = _rels(text)
        rel = f.relative_to(book_dir)
        if "home" not in rels:
            findings.append(Finding(book_id, "nav-contract", rel, 'missing rel="home" link back to the contents page'))
        if i > 0 and "prev" not in rels:
            findings.append(Finding(book_id, "nav-contract", rel, 'missing rel="prev" link (not the first concept)'))
        if i < len(concepts) - 1 and "next" not in rels:
            findings.append(Finding(book_id, "nav-contract", rel, 'missing rel="next" link (not the last concept)'))

    for name in ("index.html", "cheatsheet.html"):
        f = book_dir / name
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            if name == "cheatsheet.html" and "home" not in _rels(text):
                findings.append(Finding(book_id, "nav-contract", name, 'missing rel="home" link back to the contents page'))


def check_fold_padding(book_dir: Path, book_id: str, findings: list):
    js = book_dir / "assets" / "book.js"
    if not js.is_file():
        return
    text = js.read_text(encoding="utf-8", errors="replace")
    if "columnWidth" not in text and "colW" not in text:
        return  # not using the two-page multicolumn pager pattern
    if "paddingLeft" not in text or "paddingRight" not in text:
        findings.append(Finding(book_id, "fold-padding", "assets/book.js",
            "layout() sizes spread columns without subtracting the leaf's "
            "horizontal padding — two columns + gap can overflow the content "
            "box. Reference the `guitar` book's book.js for the fix "
            "(getComputedStyle(leaf).paddingLeft/paddingRight)."))


def check_click_routing(book_dir: Path, book_id: str, findings: list):
    js = book_dir / "assets" / "book.js"
    if not js.is_file():
        return
    text = js.read_text(encoding="utf-8", errors="replace")
    if "bookbankPager" not in text:
        return
    if "rel~=" not in text:
        findings.append(Finding(book_id, "click-routing", "assets/book.js",
            'no click handler routes rel~="next"/"prev" link clicks through '
            "bookbankPager — a mouse click will jump straight to the next "
            "file and skip the rest of the chapter's spreads"))


MEDIA_900_RE = re.compile(r'@media\s*\([^)]*max-width\s*:\s*9\d\d\s*px[^)]*\)')


def check_mobile_fallback(book_dir: Path, book_id: str, findings: list):
    css = book_dir / "assets" / "book.css"
    js = book_dir / "assets" / "book.js"
    if not css.is_file() or not js.is_file():
        return
    js_text = js.read_text(encoding="utf-8", errors="replace")
    if "columnWidth" not in js_text and "colW" not in js_text:
        return  # not using the two-page spread, so there's no fallback to check
    css_text = css.read_text(encoding="utf-8", errors="replace")
    if not MEDIA_900_RE.search(css_text):
        findings.append(Finding(book_id, "mobile-fallback", "assets/book.css",
            "no @media (max-width: ~900px) rule collapses the two-page spread "
            "to a single scrolling column — required so the book is readable "
            "on a phone"))


REQUIRED_BOOK_FIELDS = ("id", "title", "topic", "status", "concepts")


def check_book_json(book_dir: Path, book_id: str, findings: list):
    bj = book_dir / "book.json"
    if not bj.is_file():
        findings.append(Finding(book_id, "book-json", "book.json", "missing"))
        return
    try:
        data = json.loads(bj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        findings.append(Finding(book_id, "book-json", "book.json", f"invalid JSON: {e}"))
        return

    for key in REQUIRED_BOOK_FIELDS:
        if key not in data:
            findings.append(Finding(book_id, "book-json", "book.json", f"missing required field {key!r}"))

    concepts = data.get("concepts", [])
    all_ready = True
    for c in concepts:
        cid = c.get("id", "<no id>")
        if c.get("status") == "ready":
            f = c.get("file")
            if not f or not (book_dir / f).is_file():
                findings.append(Finding(book_id, "book-json", "book.json",
                    f'concept {cid!r} is "ready" but its file {f!r} does not exist on disk'))
        else:
            all_ready = False

    if data.get("status") == "ready" and not all_ready:
        findings.append(Finding(book_id, "book-json", "book.json",
            'book status is "ready" but at least one concept is not'))

    index_html = book_dir / "index.html"
    if data.get("status") == "ready" and not index_html.is_file():
        findings.append(Finding(book_id, "book-json", "book.json",
            'book status is "ready" but index.html does not exist'))


def check_image_slots(book_dir: Path, book_id: str, findings: list):
    bj = book_dir / "book.json"
    if not bj.is_file():
        return
    try:
        data = json.loads(bj.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return  # check_book_json already reports this as an error

    for img in data.get("images", []):
        f = img.get("file")
        if f and not (book_dir / f).is_file():
            findings.append(Finding(book_id, "image-slots", "book.json",
                f'image slot {img.get("id", "<no id>")!r} declares file {f!r} '
                "which does not exist on disk yet — a book's text can "
                'legitimately be "ready" before its art is dropped (the shelf '
                "falls back to a gradient cover); drop the file with "
                "place_image.py to clear this",
                severity="warning"))


def check_research(book_dir: Path, book_id: str, findings: list):
    rj = book_dir / "research.json"
    if not rj.is_file():
        findings.append(Finding(book_id, "research", "research.json",
            "missing — legacy book built before the research/prose split; "
            "consumers fall back to full re-research, and a revising pass "
            "backfills entries for the concepts it touches",
            severity="warning"))
        return
    try:
        data = json.loads(rj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        findings.append(Finding(book_id, "research", "research.json", f"invalid JSON: {e}"))
        return
    if not isinstance(data, dict):
        findings.append(Finding(book_id, "research", "research.json",
            "top level must be an object"))
        return

    sources = data.get("sources")
    concepts = data.get("concepts")
    if not isinstance(sources, list):
        findings.append(Finding(book_id, "research", "research.json",
            '"sources" must be a list of {id, url, ...} objects'))
        sources = []
    if not isinstance(concepts, dict):
        findings.append(Finding(book_id, "research", "research.json",
            '"concepts" must be an object keyed by concept id'))
        concepts = {}

    source_ids = {s.get("id") for s in sources if isinstance(s, dict) and s.get("id")}

    for cid, entry in concepts.items():
        if not isinstance(entry, dict):
            findings.append(Finding(book_id, "research", "research.json",
                f'concept entry {cid!r} must be an object (got {type(entry).__name__})'))
            continue
        for claim in entry.get("claims", []) if isinstance(entry.get("claims"), list) else []:
            if not isinstance(claim, dict):
                continue
            cites = claim.get("sources")
            text = str(claim.get("text", ""))[:60]
            if not cites:
                findings.append(Finding(book_id, "research", "research.json",
                    f'concept {cid!r} has an unsourced claim ({text!r}…) — '
                    "flagged for a later verify pass", severity="warning"))
            else:
                unknown = [s for s in cites if s not in source_ids]
                if unknown:
                    findings.append(Finding(book_id, "research", "research.json",
                        f'concept {cid!r} claim ({text!r}…) cites unknown source '
                        f'id(s) {unknown} — not in sources[]', severity="warning"))

    # A "ready" concept in book.json should have a non-empty research entry.
    bj = book_dir / "book.json"
    if bj.is_file():
        try:
            book = json.loads(bj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return  # check_book_json already reports this as an error
        for c in book.get("concepts", []):
            if c.get("status") != "ready":
                continue
            cid = c.get("id")
            if not concepts.get(cid):
                findings.append(Finding(book_id, "research", "research.json",
                    f'concept {cid!r} is "ready" but has no (or an empty) entry '
                    "under concepts — the build skipped the research-artifact "
                    "contract", severity="warning"))


CHECKS = [
    check_charset,
    check_self_contained,
    check_nav_contract,
    check_fold_padding,
    check_click_routing,
    check_mobile_fallback,
    check_book_json,
    check_image_slots,
    check_research,
]


def validate_book(book_dir: Path):
    book_id = book_dir.name
    findings = []
    for check in CHECKS:
        check(book_dir, book_id, findings)
    return findings


def discover_books(root: Path, only=None):
    books_dir = root / "books"
    if not books_dir.is_dir():
        return []
    out = []
    for d in sorted(books_dir.iterdir()):
        if not d.is_dir():
            continue
        if only and d.name not in only:
            continue
        if (d / "book.json").is_file():
            out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book_dirs", nargs="*", type=Path, help="one or more book directories to validate")
    ap.add_argument("--root", type=Path, help="BookBank data root — validate every book under <root>/books")
    ap.add_argument("--only", help="comma-separated book ids (used with --root)")
    args = ap.parse_args()

    targets = list(args.book_dirs)
    if args.root:
        only = set(args.only.split(",")) if args.only else None
        targets += discover_books(args.root, only)
    elif not targets:
        # No explicit dir(s) and no --root: sweep the same default root
        # build-library.py uses (cwd content-repo clone, else ~/bookbank).
        only = set(args.only.split(",")) if args.only else None
        targets += discover_books(default_root(), only)

    if not targets:
        ap.error("no book directories given — pass one or more paths, or --root")

    total_errors = 0
    total_warnings = 0
    for book_dir in targets:
        if not book_dir.is_dir():
            print(f"[{book_dir.name}] ERROR: not a directory: {book_dir}", file=sys.stderr)
            total_errors += 1
            continue
        findings = validate_book(book_dir)
        errors = [f for f in findings if f.severity == "error"]
        warnings = [f for f in findings if f.severity != "error"]
        if findings:
            for f in findings:
                print(str(f))
        else:
            print(f"[{book_dir.name}] OK")
        total_errors += len(errors)
        total_warnings += len(warnings)

    if total_errors or total_warnings:
        print(f"\n{total_errors} error(s), {total_warnings} warning(s) found.")
    # Only error-severity findings fail the run — a warning (e.g. a dangling
    # image slot) is surfaced but doesn't block a book from being "ready".
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
