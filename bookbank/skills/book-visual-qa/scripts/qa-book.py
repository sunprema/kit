#!/usr/bin/env python3
"""qa-book.py — visual QA for a BookBank book, in a real browser.

`validate_book.py` is structural: it reads files and checks contracts. It
cannot see LAYOUT, so it passes a book whose heading is stranded alone at the
foot of a column, whose image overflows its box, or whose spread scrolls
sideways on a phone. Those bugs are invisible in the source and obvious on
screen. This script opens every page in headless Chrome, measures the
rendered geometry, and reports what only eyes would otherwise catch.

Checks (severity in brackets):

  page-overflow     [error]   the document scrolls horizontally. Wide content
                              must scroll inside its own overflow-x:auto box
                              (a <pre>, a table wrapper) — never the page.
  broken-image      [error]   an <img> that failed to load and is NOT an
                              unfilled image-slot placeholder (those legitimately
                              404 until the art is dropped).
  orphan-heading    [warning] a heading whose following block starts in the NEXT
                              column — the heading is stranded at a column foot,
                              divorced from the content it introduces. This is
                              the real bug that shipped in the JWT book's cover
                              while validate_book.py reported it clean.
  escapes-column    [warning] an element extending past the viewport that is not
                              inside a scrollable ancestor — it is being clipped
                              with no way to reveal it.
  oversized-image   [warning] a rendered image taller than the cap the skill
                              requires, which shoves the rest of the spread.
  sparse-tail       [info]    the final column of a page is nearly empty. Often
                              fine, sometimes a sign the page ends awkwardly.

Usage:
  qa-book.py <book-dir> [--out DIR] [--desktop 1440] [--mobile 500]
             [--no-screenshots] [--json]

Exit status: 1 if any error-severity finding, else 0. Warnings never fail —
they are judgement calls a human should look at, exactly like
validate_book.py's warning tier.

Note on --mobile: headless Chrome clamps its viewport to a 500px minimum, so
360 and 500 measure identically. That is a browser limitation, not a bug here;
500px is still below the 900px breakpoint, so it exercises the single-column
fallback, which is what matters.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome") or "",
    shutil.which("google-chrome-stable") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]

# Injected into a COPY of each page. Writes its findings into a marker element
# the DOM dump can be regexed for. Everything here is measurement only — it
# must never mutate layout, or it would report on a page that doesn't exist.
PROBE = r"""
<script id="__qa_probe__">
window.addEventListener('load', function(){ setTimeout(function(){
  var out = { findings: [], meta: {} };
  function add(kind, sev, msg, extra){
    out.findings.push(Object.assign({kind:kind, severity:sev, message:msg}, extra||{}));
  }
  var vw = window.innerWidth, vh = window.innerHeight;
  out.meta.viewport = [vw, vh];
  out.meta.scrollWidth = document.documentElement.scrollWidth;

  // --- page-level horizontal scroll -------------------------------------
  if (document.documentElement.scrollWidth > vw + 2) {
    add('page-overflow', 'error',
        'document scrolls horizontally (' + document.documentElement.scrollWidth +
        'px wide in a ' + vw + 'px viewport)');
  }

  function scrollableAncestor(el){
    for (var n = el.parentElement; n; n = n.parentElement){
      var ov = getComputedStyle(n).overflowX;
      if (ov === 'auto' || ov === 'scroll') return n;
      if (n.classList && n.classList.contains('book-leaf')) return null;
    }
    return null;
  }

  // --- elements clipped by the viewport with no way to scroll to them ----
  var leaf = document.querySelector('.book-leaf');
  var all = document.querySelectorAll('.book-leaf *');
  var reported = 0;
  for (var i = 0; i < all.length && reported < 6; i++){
    var el = all[i];
    if (!el.getClientRects().length) continue;
    var r = el.getBoundingClientRect();
    // Multicolumn shifts later columns off-viewport by design; only flag
    // elements on the CURRENT spread (left edge already within the viewport).
    if (r.left < vw && r.right > vw + 2 && !scrollableAncestor(el)){
      var tag = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
                ? '.' + el.className.trim().split(/\s+/).join('.') : '');
      add('escapes-column', 'warning',
          tag + ' extends ' + Math.round(r.right - vw) + 'px past the viewport with no scrollable ancestor',
          {element: tag});
      reported++;
    }
  }

  // --- orphaned headings -------------------------------------------------
  // In a multicolumn spread, a following sibling that begins in the NEXT
  // column has a visibly larger left edge. A heading whose content moved on
  // without it is stranded.
  if (leaf && getComputedStyle(leaf).columnWidth !== 'auto'){
    var kids = Array.prototype.slice.call(leaf.children);
    for (var k = 0; k < kids.length - 1; k++){
      var el2 = kids[k];
      var isHead = /^H[1-6]$/.test(el2.tagName) ||
                   (el2.classList && (el2.classList.contains('toc-head') ||
                                      el2.classList.contains('chapter-head')));
      if (!isHead) continue;
      var next = kids[k+1];
      if (!el2.getClientRects().length || !next.getClientRects().length) continue;
      var a = el2.getBoundingClientRect(), b = next.getBoundingClientRect();
      if (b.left > a.left + 40){
        add('orphan-heading', 'warning',
            '"' + (el2.textContent || '').trim().slice(0, 48) +
            '" sits at the foot of a column; the block it introduces starts in the next one',
            {element: el2.tagName.toLowerCase()});
      }
    }
  }

  // --- images ------------------------------------------------------------
  var imgs = document.images;
  for (var j = 0; j < imgs.length; j++){
    var im = imgs[j];
    var slot = im.closest ? im.closest('.img-slot') : null;
    if (im.complete && im.naturalWidth === 0){
      if (!slot){
        add('broken-image', 'error', 'image failed to load: ' + (im.getAttribute('src') || '(no src)'),
            {element: im.getAttribute('src') || ''});
      }
      continue;                       // an unfilled slot is expected to 404
    }
    var ir = im.getBoundingClientRect();
    if (ir.height > vh * 0.62){
      add('oversized-image', 'warning',
          'image renders ' + Math.round(ir.height) + 'px tall (' +
          Math.round(100 * ir.height / vh) + '% of the viewport) — cap it so it cannot shove the spread',
          {element: im.getAttribute('src') || ''});
    }
  }

  // --- how full is the last column ---------------------------------------
  if (leaf && getComputedStyle(leaf).columnWidth !== 'auto'){
    var cs = getComputedStyle(leaf);
    var colW = parseFloat(cs.columnWidth), gap = parseFloat(cs.columnGap) || 0;
    var base = leaf.getBoundingClientRect().left, right = 0;
    var ch = leaf.children;
    for (var m = 0; m < ch.length; m++){
      var rr = ch[m].getBoundingClientRect().right - base;
      if (rr > right) right = rr;
    }
    if (colW > 0){
      var stride = colW + gap;
      var cols = Math.max(1, Math.ceil((right - 1) / stride));
      var fill = (right - (cols - 1) * stride) / colW;
      out.meta.columns = cols;
      out.meta.lastColumnFill = Math.round(fill * 100) / 100;
      if (cols > 1 && fill < 0.22){
        add('sparse-tail', 'info',
            'the last column is only ' + Math.round(fill * 100) + '% filled');
      }
    }
  }

  var el3 = document.createElement('div');
  el3.id = '__qa_result__';
  el3.textContent = JSON.stringify(out);
  document.body.appendChild(el3);
}, 700); });
</script>
"""

RESULT_RE = re.compile(r'<div id="__qa_result__">(.*?)</div>', re.S)
SEV_RANK = {"error": 0, "warning": 1, "info": 2}


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists() and os.access(c, os.X_OK):
            return c
    return None


CALIBRATION_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<script>window.addEventListener('load',function(){setTimeout(function(){
var d=document.createElement('div');d.id='__qa_result__';
d.textContent=window.innerWidth+','+window.innerHeight;document.body.appendChild(d);},200)});
</script></body></html>"""


def calibrate(chrome, width, height, _cache={}):
    """Find the window-size that yields the viewport we actually want.

    Chrome's --dump-dom mode honors --window-size WIDTH but NOT HEIGHT: it
    quietly loses ~87px to browser chrome, so asking for 900 gives an 813px
    viewport. That matters enormously here — a shorter viewport means shorter
    columns, which pushes blocks into the next column and manufactures
    orphan-heading findings for a layout no reader will ever see. (It also
    clamps width to a 500px minimum, so sub-500 mobile widths all measure the
    same.) Measure the deltas once per size, then compensate.

    Returns (window_arg_w, window_arg_h, effective_w, effective_h).
    """
    key = (width, height)
    if key in _cache:
        return _cache[key]
    tmp = Path(tempfile.mkdtemp(prefix="bookbank-qa-cal-")) / "cal.html"
    tmp.write_text(CALIBRATION_HTML, encoding="utf-8")
    try:
        r = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={width},{height}", "--virtual-time-budget=2000",
             "--dump-dom", f"file://{tmp.resolve()}"],
            capture_output=True, text=True, timeout=60)
        m = RESULT_RE.search(r.stdout or "")
        if m:
            iw, ih = (int(x) for x in m.group(1).split(","))
            # Ask for height + the shortfall so the real viewport lands on target.
            win_h = height + (height - ih)
            _cache[key] = (width, win_h, iw, height)
            return _cache[key]
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    _cache[key] = (width, height, width, height)
    return _cache[key]


def pages_of(book: Path):
    """index → concepts in order → cheatsheet: the reading order."""
    out = []
    if (book / "index.html").is_file():
        out.append(book / "index.html")
    cdir = book / "concepts"
    if cdir.is_dir():
        out.extend(sorted(cdir.glob("*.html")))
    if (book / "cheatsheet.html").is_file():
        out.append(book / "cheatsheet.html")
    return out


def probe_page(chrome, page: Path, book: Path, width: int, height: int):
    """Copy the page beside its originals (so relative assets still resolve),
    append the probe, dump the post-script DOM, and read the result back."""
    html = page.read_text(encoding="utf-8", errors="replace")
    if "</body>" in html:
        html = html.replace("</body>", PROBE + "</body>", 1)
    else:
        html += PROBE
    win_w, win_h, _, _ = calibrate(chrome, width, height)
    tmp = page.with_name("__qa_tmp__" + page.name)
    tmp.write_text(html, encoding="utf-8")
    try:
        r = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={win_w},{win_h}", "--virtual-time-budget=5000",
             "--dump-dom", f"file://{tmp.resolve()}"],
            capture_output=True, text=True, timeout=90)
        m = RESULT_RE.search(r.stdout or "")
        if not m:
            return None, "probe did not report (page script error, or the browser timed out)"
        raw = (m.group(1)
               .replace("&quot;", '"').replace("&amp;", "&")
               .replace("&lt;", "<").replace("&gt;", ">"))
        return json.loads(raw), None
    except subprocess.TimeoutExpired:
        return None, "browser timed out"
    except json.JSONDecodeError as e:
        return None, f"could not parse probe output: {e}"
    finally:
        tmp.unlink(missing_ok=True)


def shoot(chrome, page: Path, out_png: Path, width: int, height: int):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={width},{height}", "--virtual-time-budget=4000",
         f"--screenshot={out_png}", f"file://{page.resolve()}"],
        capture_output=True, text=True, timeout=90)


def main():
    ap = argparse.ArgumentParser(description="Visual QA for a BookBank book.")
    ap.add_argument("book_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="where screenshots go (default: a temp dir, reported at the end)")
    ap.add_argument("--desktop", type=int, default=1440)
    ap.add_argument("--mobile", type=int, default=500)
    ap.add_argument("--no-screenshots", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    book = args.book_dir
    if not (book / "book.json").is_file():
        print(f"qa-book.py: {book} is not a book folder (no book.json)", file=sys.stderr)
        return 2

    chrome = find_chrome()
    if not chrome:
        print("qa-book.py: no Chromium-family browser found; set CHROME_BIN.", file=sys.stderr)
        return 3

    pages = pages_of(book)
    if not pages:
        print(f"qa-book.py: no pages found under {book}", file=sys.stderr)
        return 2

    shots = args.out or Path(tempfile.mkdtemp(prefix="bookbank-qa-"))
    book_id = book.resolve().name
    all_findings = []

    for page in pages:
        rel = page.relative_to(book)
        for label, w, h in (("desktop", args.desktop, 900), ("mobile", args.mobile, 940)):
            res, err = probe_page(chrome, page, book, w, h)
            if err:
                all_findings.append({"page": str(rel), "viewport": label, "kind": "probe-failed",
                                     "severity": "warning", "message": err})
                continue
            for f in res["findings"]:
                # An orphan can only exist where there are columns; skip the
                # concept at mobile, where the spread is deliberately gone.
                if label == "mobile" and f["kind"] in ("orphan-heading", "sparse-tail"):
                    continue
                all_findings.append({"page": str(rel), "viewport": label, **f})
        if not args.no_screenshots:
            stem = str(rel).replace("/", "__").replace(".html", "")
            shoot(chrome, page, shots / f"{stem}.desktop.png", args.desktop, 900)
            shoot(chrome, page, shots / f"{stem}.mobile.png", args.mobile, 940)

    all_findings.sort(key=lambda f: (SEV_RANK.get(f["severity"], 9), f["page"]))
    errors = sum(1 for f in all_findings if f["severity"] == "error")
    warnings = sum(1 for f in all_findings if f["severity"] == "warning")
    infos = sum(1 for f in all_findings if f["severity"] == "info")

    if args.json:
        print(json.dumps({"book": book_id, "pages": len(pages),
                          "screenshots": str(shots) if not args.no_screenshots else None,
                          "findings": all_findings}, indent=2))
    else:
        for f in all_findings:
            print(f"[{book_id}] {f['severity'].upper()} {f['kind']}: "
                  f"{f['page']} ({f['viewport']}) — {f['message']}")
        print(f"\n{len(pages)} page(s) checked at {args.desktop}px and {args.mobile}px. "
              f"{errors} error(s), {warnings} warning(s), {infos} note(s).")
        if not args.no_screenshots:
            print(f"screenshots: {shots}")
            print("Look at them. A page can measure clean and still be ugly.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
