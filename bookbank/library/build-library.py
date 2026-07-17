#!/usr/bin/env python3
"""
build-library.py — generate the public BookBank Library (a static GitHub Pages
site) from the BookBank data root.

It syncs the selected books verbatim into <out>/books/<id>/ (they are already
self-contained HTML), then GENERATES the front door from every book.json:

  <out>/index.html      a responsive cover-card grid of all published books
  <out>/catalog.json    machine catalog (drives client-side search/filter)
  <out>/assets/library.css
  <out>/.nojekyll        serve folders verbatim (never delete)

Books that ship real cover art (assets/img/cover-art.png or cover.png) show it;
books without get a deterministic gradient cover with the title typeset — the
same fallback idea the native app's gallery uses, so the shelf looks whole.

Usage:
  build-library.py --out <repo-dir> [--root <bookbank-root>] [--only id1,id2]

  --root   BookBank data root (default: $BOOKBANK_ROOT, else cwd if it looks
           like a content-repo clone, else ~/bookbank — see default_root())
  --out    output site dir (a clone of the books repo). Required.
  --only   comma-separated book ids to publish (default: every "ready" book).
           Books not listed but already present in <out>/books are KEPT and
           still appear on the shelf, so incremental publishing is additive.

The public repo (`owner/name`) and the live GitHub Pages URL are configurable
so this can target a fork or a different Pages layout:
  --repo       or $BOOKBANK_BOOKS_REPO   (default: sunprema/books)
  --base-url   or $BOOKBANK_SITE_URL     (default: derived from --repo as
               https://<owner>.github.io/<name>)
"""
import argparse
import hashlib
import html
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

SITE_TITLE = "The BookBank Library"
SITE_TAGLINE = "Beautiful, web-researched books — one topic at a time."

# Public GitHub repo the library is published to, as "owner/name". Override
# with --repo or $BOOKBANK_BOOKS_REPO to target a fork or a different account.
DEFAULT_REPO = "sunprema/books"


def default_site_url(repo):
    """Derive the GitHub Pages URL for an "owner/name" repo slug."""
    owner, _, name = repo.partition("/")
    return f"https://{owner}.github.io/{name}" if name else f"https://{owner}.github.io"


def default_root():
    """$BOOKBANK_ROOT, else cwd if it looks like a content-repo clone (has
    books/, catalog.json, or a sunprema/books-ish git remote), else ~/bookbank."""
    if os.environ.get("BOOKBANK_ROOT"):
        return os.environ["BOOKBANK_ROOT"]
    cwd = Path.cwd()
    repo_hint = os.environ.get("BOOKBANK_BOOKS_REPO", DEFAULT_REPO)
    if (cwd / "books").is_dir() or (cwd / "catalog.json").is_file():
        return str(cwd)
    try:
        remotes = subprocess.run(["git", "remote", "-v"], cwd=cwd,
                                  capture_output=True, text=True, timeout=3).stdout
        if repo_hint in remotes:
            return str(cwd)
    except Exception:
        pass
    return str(Path.home() / "bookbank")

# Curated gradient pairs; a book with no cover art gets one deterministically by
# hashing its id, so the same book always lands on the same palette.
GRADIENTS = [
    ("#b45309", "#7c2d12"),  # oxide / rust
    ("#0f766e", "#134e4a"),  # teal
    ("#4338ca", "#1e1b4b"),  # indigo
    ("#9d174d", "#4a044e"),  # magenta / plum
    ("#0369a1", "#082f49"),  # deep blue
    ("#15803d", "#052e16"),  # forest
    ("#a16207", "#422006"),  # amber / umber
    ("#7c3aed", "#2e1065"),  # violet
    ("#be123c", "#4c0519"),  # crimson
    ("#0891b2", "#083344"),  # cyan
    ("#c2410c", "#431407"),  # burnt orange
    ("#334155", "#0f172a"),  # slate
]


def load_json(p: Path):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def personas(root: Path) -> dict:
    """Persona id -> {name, tagline, voice}, resolved via the same 3-tier
    cascade as write-book: plugin defaults, then a per-user override, then a
    per-clone override (each layer's ids win over the previous). A plain
    content-repo clone (the common --root when standing inside sunprema/books)
    has no personas/ dir of its own — without the plugin-defaults and
    per-user tiers here, every persona name/tagline in the catalog goes
    blank (a real regression this caught: 2026-07-10)."""
    out = {}
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    tiers = []
    if plugin_root:
        tiers.append(Path(plugin_root) / "defaults" / "personas")
    tiers.append(Path.home() / ".claude" / "bookbank" / "personas")
    tiers.append(root / "personas")
    for pdir in tiers:
        if not pdir.is_dir():
            continue
        for f in pdir.glob("*.json"):
            try:
                out[f.stem] = load_json(f)
            except Exception:
                pass
    return out


def cover_rel(book_dir: Path, book_id: str):
    """Site-root-relative path to the book's cover art, or None for a gradient."""
    for cand in ("cover.png", "assets/img/cover-art.png", "assets/img/cover.png"):
        if (book_dir / cand).is_file():
            return f"books/{book_id}/{cand}"
    return None


def grad_for(book_id: str):
    h = 0
    for ch in book_id:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return GRADIENTS[h % len(GRADIENTS)]


def sync_book(src: Path, dst: Path):
    # When --root and --out are the same clone (the recommended workflow when
    # you're already standing inside the content repo), src and dst are the
    # identical path. rmtree(dst) would then delete src out from under itself
    # before copytree could read it — destroying the book with no recovery
    # short of `git checkout`. Skip the sync entirely in that case; the book
    # is already exactly where it needs to be.
    if src.resolve() == dst.resolve():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(".DS_Store", ".git", "*.tmp"),
    )


def esc(s):
    return html.escape(str(s or ""), quote=True)


# ---- Open Graph / Twitter Card share previews -----------------------------
# Unfurlers (Slack, iMessage, WhatsApp, Twitter/X, LinkedIn, Facebook…) read
# these static <meta> tags from the page <head> and show the cover as a
# thumbnail. They do NOT run JS and they REQUIRE absolute image URLs.

OG_BEGIN = "<!-- og:begin (generated by build-library) -->"
OG_END = "<!-- og:end -->"


def png_size(path: Path):
    """(width, height) of a PNG from its IHDR header, without any deps."""
    try:
        with path.open("rb") as f:
            head = f.read(24)
        if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    except Exception:
        pass
    return None, None


def jpeg_size(path: Path):
    """(width, height) of a baseline/progressive JPEG from its SOF marker,
    without any deps. Returns (None, None) on anything unexpected."""
    try:
        data = path.read_bytes()
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return w, h
            i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    except Exception:
        pass
    return None, None


def make_share_jpeg(cover_fs: Path, dst_fs: Path):
    """Downscale + compress a cover into a small JPEG for strict unfurlers.
    WhatsApp (and some others) refuse preview images over a few hundred KB, so
    the multi-MB cover PNGs never show. A 1200px q72 JPEG lands ~150 KB and looks
    identical in a card. Uses macOS `sips`; returns (ok, width, height)."""
    try:
        dst_fs.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["sips", "-Z", "1200", "-s", "format", "jpeg",
             "-s", "formatOptions", "72", str(cover_fs), "--out", str(dst_fs)],
            capture_output=True, text=True)
        if r.returncode != 0 or not dst_fs.is_file():
            return False, None, None
        g = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(dst_fs)],
            capture_output=True, text=True)
        w = h = None
        for line in g.stdout.splitlines():
            s = line.strip()
            if s.startswith("pixelWidth:"):
                w = int(s.split(":")[1])
            elif s.startswith("pixelHeight:"):
                h = int(s.split(":")[1])
        return True, w, h
    except Exception:
        return False, None, None


def og_block(*, title, description, image_url, page_url, size=(None, None),
             og_type="article"):
    """Build the <meta> block (wrapped in idempotency markers)."""
    lines = [OG_BEGIN]

    def m(prop, content, name=False):
        if content in (None, ""):
            return
        attr = "name" if name else "property"
        lines.append(f'<meta {attr}="{prop}" content="{esc(content)}" />')

    m("og:type", og_type)
    m("og:site_name", SITE_TITLE)
    m("og:title", title)
    m("og:description", description)
    m("og:url", page_url)
    if image_url:
        m("og:image", image_url)
        m("og:image:alt", f"Cover of {title}")
        w, h = size
        if w and h:
            m("og:image:width", str(w))
            m("og:image:height", str(h))
    m("twitter:card", "summary_large_image" if image_url else "summary", name=True)
    m("twitter:title", title, name=True)
    m("twitter:description", description, name=True)
    if image_url:
        m("twitter:image", image_url, name=True)
        m("twitter:image:alt", f"Cover of {title}", name=True)
    lines.append(OG_END)
    return "\n".join(lines)


def inject_head(html_text, block):
    """Insert `block` just after the opening <head> tag, replacing any prior
    generated block so re-publishing is byte-stable (no spurious git churn)."""
    import re
    # Also eat the newline inject_head prepended before OG_BEGIN on the prior
    # run, or that newline accumulates by one on every republish forever.
    html_text = re.sub(
        r"\n?" + re.escape(OG_BEGIN) + r".*?" + re.escape(OG_END), "", html_text, flags=re.S)
    mo = re.search(r"<head\b[^>]*>", html_text, flags=re.I)
    if mo:
        i = mo.end()
        return html_text[:i] + "\n" + block + html_text[i:]
    return block + html_text  # fallback: no <head> found


def inject_book_og(out: Path, entry, base_url):
    """Stamp OG/Twitter tags into one book's index.html (in the output clone)."""
    idx = out / "books" / entry["id"] / "index.html"
    if not idx.is_file():
        return False
    cover = entry.get("cover")
    image_url = None
    size = (None, None)
    if cover:
        # Prefer a small compressed share JPEG (WhatsApp-safe). REUSE one that
        # already exists rather than re-encoding: `sips` only exists on macOS,
        # and the books repo's publish-on-merge bot (Ubuntu) must regenerate
        # byte-identical pages or every book merge spawns a drift commit.
        share_rel = f"books/{entry['id']}/assets/img/og-share.jpg"
        share_fs = out / share_rel
        if share_fs.is_file():
            image_url = f"{base_url}/{share_rel}"
            size = jpeg_size(share_fs)
        else:
            ok, w, h = make_share_jpeg(out / cover, share_fs)
            if ok:
                image_url = f"{base_url}/{share_rel}"
                size = (w, h)
            else:
                image_url = f"{base_url}/{cover}"
                size = png_size(out / cover)
    block = og_block(
        title=entry["title"],
        description=entry.get("summary") or SITE_TAGLINE,
        image_url=image_url,
        page_url=f"{base_url}/{entry['url']}",
        size=size,
        og_type="article",
    )
    idx.write_text(inject_head(idx.read_text(encoding="utf-8"), block), encoding="utf-8")
    return True


def build_catalog(root: Path, out: Path, only):
    pers = personas(root)
    books_src = root / "books"
    published_ids = []

    # Publish the requested (or every ready) book.
    if only:
        want = only
    else:
        want = []
        for d in sorted(books_src.iterdir()):
            bj = d / "book.json"
            if bj.is_file():
                try:
                    if load_json(bj).get("status") == "ready":
                        want.append(d.name)
                except Exception:
                    pass

    for bid in want:
        src = books_src / bid
        bj = src / "book.json"
        if not bj.is_file():
            print(f"  ! skip {bid}: no book.json", file=sys.stderr)
            continue
        if load_json(bj).get("status") != "ready":
            print(f"  ! skip {bid}: not ready", file=sys.stderr)
            continue
        sync_book(src, out / "books" / bid)
        published_ids.append(bid)
        print(f"  + synced {bid}")

    # Build catalog from EVERYTHING currently in out/books (additive publishing).
    out_books = out / "books"
    entries = []
    for d in sorted(out_books.iterdir()) if out_books.is_dir() else []:
        bj = d / "book.json"
        if not bj.is_file():
            continue
        try:
            b = load_json(bj)
        except Exception:
            continue
        bid = d.name
        p = pers.get(b.get("persona") or "", {})
        entries.append({
            "id": bid,
            "title": b.get("title") or bid,
            "topic": b.get("topic") or "",
            "summary": b.get("summary") or "",
            "created": b.get("created") or "",
            "concepts": len([c for c in b.get("concepts", [])
                             if c.get("status") == "ready"]),
            "persona": {
                "id": b.get("persona") or "",
                "name": p.get("name") or "",
                "tagline": p.get("tagline") or "",
            },
            "cover": cover_rel(d, bid),
            "url": f"books/{bid}/",
        })

    # Newest first, then alphabetical by title.
    entries.sort(key=lambda e: (e["created"], e["title"]), reverse=True)
    return entries


def card_html(e):
    cover = e["cover"]
    voice = e["persona"]["name"]
    voice_line = (f'<span class="voice">in the voice of {esc(voice)}</span>'
                  if voice else "")
    meta = []
    if e["concepts"]:
        meta.append(f'{e["concepts"]} chapters')
    if e["topic"]:
        meta.append(esc(e["topic"]))
    meta_line = " · ".join(meta)

    if cover:
        art = f'<img class="cover-art" src="{esc(cover)}" alt="Cover of {esc(e["title"])}" loading="lazy" />'
        cover_cls = "cover has-art"
        style = ""
    else:
        c1, c2 = grad_for(e["id"])
        art = f'<span class="cover-title">{esc(e["title"])}</span>'
        cover_cls = "cover gradient"
        style = f'style="--g1:{c1};--g2:{c2}"'

    # data-* attributes power the client-side search/filter. The card is a div
    # with a stretched .card-link overlay (not one big <a>) so the offline
    # download <button> isn't nested inside an anchor.
    hay = " ".join([e["title"], e["topic"], voice, e["summary"]]).lower()
    return f"""      <div class="card" data-search="{esc(hay)}" data-voice="{esc(e['persona']['id'])}">
        <a class="card-link" href="{esc(e['url'])}" aria-label="Read {esc(e['title'])}"></a>
        <div class="{cover_cls}" {style}>{art}</div>
        <div class="card-body">
          <h2 class="card-title">{esc(e['title'])}</h2>
          {voice_line}
          <p class="card-summary">{esc(e['summary'])}</p>
          <div class="card-meta">{meta_line}</div>
        </div>
        <div class="card-foot">
          <span class="card-open">Read →</span>
          <button class="dl" type="button" data-book="{esc(e['id'])}" data-bytes="{e.get('offline_bytes', 0)}">⤓ Offline</button>
        </div>
      </div>"""


def voice_filters(entries):
    seen = {}
    for e in entries:
        pid, name = e["persona"]["id"], e["persona"]["name"]
        if pid and name:
            seen[pid] = name
    btns = ['<button class="chip is-active" data-voice="">All voices</button>']
    for pid, name in sorted(seen.items(), key=lambda kv: kv[1]):
        btns.append(f'<button class="chip" data-voice="{esc(pid)}">{esc(name)}</button>')
    return "\n        ".join(btns)


def asset_v():
    """Short content hash of the shelf's CSS+JS, used as a ?v= cache-buster on
    their URLs (in index.html and the service worker's precache list). The
    shelf HTML is network-first but assets are cache-first — without versioned
    URLs, every publish pairs fresh markup with stale CSS/JS on first view
    (real bug this caught: unstyled .card-link overlay, cards not clickable)."""
    return hashlib.sha1((LIBRARY_CSS + LIBRARY_JS).encode("utf-8")).hexdigest()[:10]


def render_index(entries):
    cards = "\n".join(card_html(e) for e in entries)
    filters = voice_filters(entries)
    count = len(entries)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(SITE_TITLE)}</title>
<meta name="description" content="{esc(SITE_TAGLINE)}" />
<meta name="theme-color" content="{PWA_THEME}" />
<link rel="manifest" href="manifest.webmanifest" />
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png" />
<link rel="preconnect" href="/" />
<link rel="stylesheet" href="assets/library.css?v={asset_v()}" />
</head>
<body>
<header class="hero">
  <div class="hero-inner">
    <div class="mark">📚</div>
    <h1>{esc(SITE_TITLE)}</h1>
    <p class="tagline">{esc(SITE_TAGLINE)}</p>
    <div class="controls">
      <input id="q" type="search" placeholder="Search {count} book{'s' if count != 1 else ''}…" autocomplete="off" spellcheck="false" />
      <div class="chips">
        {filters}
      </div>
    </div>
  </div>
</header>
<main>
  <section class="grid" id="grid">
{cards}
  </section>
  <p class="empty" id="empty" hidden>No books match that search.</p>
</main>
<footer>
  <p>Built with <strong>BookBank</strong> · {count} book{'s' if count != 1 else ''} · researched and written page by page.</p>
</footer>
<script src="assets/library.js?v={asset_v()}"></script>
</body>
</html>
"""


LIBRARY_CSS = """/* The BookBank Library — shelf shell (the books bring their own styles). */
:root{
  --bg:#f7f5f1; --panel:#fffdf9; --ink:#1c1a17; --muted:#6b6459;
  --edge:#e6e0d6; --accent:#b45309; --accent-ink:#fff;
  --shadow:0 1px 2px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.08);
  --radius:16px;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#14120f; --panel:#1e1b17; --ink:#f2ede4; --muted:#a89f90;
    --edge:#2c2822; --accent:#f59e0b; --accent-ink:#1a1206;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.5);
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:none}

.hero{
  padding:clamp(3rem,8vw,6rem) 1.5rem 2rem;
  text-align:center;
  background:
    radial-gradient(60% 100% at 50% 0%, color-mix(in srgb,var(--accent) 14%,transparent), transparent 70%),
    var(--bg);
  border-bottom:1px solid var(--edge);
}
.hero-inner{max-width:820px;margin:0 auto}
.mark{font-size:2.6rem;line-height:1}
.hero h1{
  font-size:clamp(2rem,5vw,3.4rem); margin:.4rem 0 .2rem;
  letter-spacing:-.02em; font-weight:800;
}
.tagline{color:var(--muted);font-size:clamp(1rem,2.2vw,1.2rem);margin:0 0 1.8rem}

.controls{display:flex;flex-direction:column;gap:1rem;align-items:center}
#q{
  width:min(520px,100%); padding:.85rem 1.1rem; font-size:1rem;
  border:1px solid var(--edge); border-radius:999px; background:var(--panel);
  color:var(--ink); box-shadow:var(--shadow); outline:none;
  transition:border-color .15s,box-shadow .15s;
}
#q:focus{border-color:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 22%,transparent)}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;justify-content:center}
.chip{
  border:1px solid var(--edge); background:var(--panel); color:var(--muted);
  padding:.4rem .9rem; border-radius:999px; font-size:.86rem; cursor:pointer;
  transition:all .15s; font-weight:600;
}
.chip:hover{color:var(--ink);border-color:var(--accent)}
.chip.is-active{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}

main{max-width:1180px;margin:0 auto;padding:2.5rem 1.5rem 1rem}
.grid{
  display:grid; gap:1.6rem;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
}
.card{
  display:flex; flex-direction:column; background:var(--panel);
  border:1px solid var(--edge); border-radius:var(--radius); overflow:hidden;
  box-shadow:var(--shadow); transition:transform .18s ease,box-shadow .18s ease;
  position:relative;
}
.card:hover{transform:translateY(-4px);box-shadow:0 6px 12px rgba(0,0,0,.1),0 20px 44px rgba(0,0,0,.16)}

.cover{aspect-ratio:16/10;position:relative;overflow:hidden;background:#000}
.cover-art{width:100%;height:100%;object-fit:cover;display:block}
.cover.gradient{
  background:linear-gradient(135deg,var(--g1),var(--g2));
  display:flex;align-items:center;justify-content:center;padding:1.4rem;
}
.cover.gradient::after{
  content:"";position:absolute;inset:0;
  background:radial-gradient(120% 120% at 15% 10%,rgba(255,255,255,.18),transparent 55%);
}
.cover-title{
  position:relative;color:#fff;font-weight:800;font-size:1.5rem;line-height:1.2;
  letter-spacing:-.01em;text-align:center;text-shadow:0 2px 12px rgba(0,0,0,.35);
}

.card-body{padding:1.1rem 1.2rem .6rem;flex:1;display:flex;flex-direction:column;gap:.35rem}
.card-title{font-size:1.18rem;font-weight:750;margin:0;letter-spacing:-.01em}
.voice{font-size:.82rem;color:var(--accent);font-weight:650}
.card-summary{
  margin:.2rem 0 0;color:var(--muted);font-size:.92rem;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}
.card-meta{margin-top:auto;padding-top:.7rem;color:var(--muted);font-size:.8rem;font-weight:600}
.card-foot{
  display:flex;align-items:center;justify-content:space-between;gap:.6rem;
  padding:.7rem 1.2rem 1.1rem;
}
.card-open{color:var(--accent);font-weight:700;font-size:.9rem}
.card-link{position:absolute;inset:0;z-index:1;border-radius:var(--radius)}
.dl{
  position:relative;z-index:2;border:1px solid var(--edge);background:var(--panel);
  color:var(--muted);padding:.3rem .7rem;border-radius:999px;font:inherit;
  font-size:.78rem;font-weight:650;cursor:pointer;transition:all .15s;
}
.dl:hover{color:var(--ink);border-color:var(--accent)}
.dl.is-busy{color:var(--accent);border-color:var(--accent);cursor:progress}
.dl.is-done{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.dl[hidden]{display:none}

.empty{text-align:center;color:var(--muted);padding:3rem 1rem}
footer{
  text-align:center;color:var(--muted);font-size:.86rem;
  padding:2.5rem 1.5rem 3.5rem;border-top:1px solid var(--edge);margin-top:2rem;
}
footer strong{color:var(--ink)}
@media (max-width:520px){ .grid{grid-template-columns:1fr} }
"""

LIBRARY_JS = """// Client-side search + voice filter for the shelf. No dependencies.
(function () {
  var q = document.getElementById('q');
  var grid = document.getElementById('grid');
  var empty = document.getElementById('empty');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var voice = '';

  function apply() {
    var term = (q.value || '').trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {
      var okText = !term || c.getAttribute('data-search').indexOf(term) !== -1;
      var okVoice = !voice || c.getAttribute('data-voice') === voice;
      var show = okText && okVoice;
      c.style.display = show ? '' : 'none';
      if (show) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
  }

  q && q.addEventListener('input', apply);
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      chips.forEach(function (c) { c.classList.remove('is-active'); });
      chip.classList.add('is-active');
      voice = chip.getAttribute('data-voice') || '';
      apply();
    });
  });

  // PWA: register the service worker (resolves to <site>/sw.js under the
  // shelf's own path, so the scope covers the whole library incl. books/).
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }

  // Offline downloads: each card's "⤓ Offline" button precaches the book's
  // full file list (its generated offline.json) into a persistent cache the
  // service worker serves from. Click again to remove the download.
  var OFFLINE = 'bookbank-offline';
  var dls = Array.prototype.slice.call(document.querySelectorAll('.dl'));
  if (!('caches' in window)) {
    dls.forEach(function (b) { b.hidden = true; });
    dls = [];
  }
  function setUI(btn, state, pct) {
    var bytes = +btn.getAttribute('data-bytes');
    var size = bytes > 0 ? ' (' + (bytes / 1048576).toFixed(1) + ' MB)' : '';
    btn.classList.remove('is-busy', 'is-done');
    if (state === 'busy') {
      btn.classList.add('is-busy');
      btn.textContent = pct + '%';
    } else if (state === 'done') {
      btn.classList.add('is-done');
      btn.textContent = '✓ Offline';
      btn.title = 'Saved for offline reading — click to remove the download';
    } else {
      btn.textContent = '⤓ Offline';
      btn.title = 'Download this book for offline reading' + size;
    }
  }
  dls.forEach(function (btn) {
    var id = btn.getAttribute('data-book');
    var base = new URL('books/' + id + '/', location.href).href;
    var key = 'bb-offline-' + id;
    setUI(btn, localStorage.getItem(key) ? 'done' : 'idle');

    btn.addEventListener('click', function () {
      if (btn.classList.contains('is-busy')) return;

      if (localStorage.getItem(key)) {  // downloaded → remove
        caches.open(OFFLINE).then(function (c) {
          return c.keys().then(function (reqs) {
            return Promise.all(reqs
              .filter(function (r) { return r.url.indexOf(base) === 0; })
              .map(function (r) { return c.delete(r); }));
          });
        }).then(function () {
          localStorage.removeItem(key);
          setUI(btn, 'idle');
        });
        return;
      }

      setUI(btn, 'busy', 0);
      fetch(base + 'offline.json').then(function (r) {
        if (!r.ok) throw new Error('offline.json ' + r.status);
        return r.json();
      }).then(function (m) {
        var urls = [base].concat(m.files.map(function (p) { return base + p; }));
        return caches.open(OFFLINE).then(function (c) {
          var i = 0, done = 0;
          function next() {
            if (i >= urls.length) return Promise.resolve();
            return c.add(urls[i++]).then(function () {
              done++;
              setUI(btn, 'busy', Math.round(done / urls.length * 100));
              return next();
            });
          }
          // A few parallel lanes keep it quick without hammering the host.
          var lanes = [];
          for (var n = 0; n < 6 && n < urls.length; n++) lanes.push(next());
          return Promise.all(lanes);
        });
      }).then(function () {
        localStorage.setItem(key, '1');
        setUI(btn, 'done');
      }).catch(function (err) {
        setUI(btn, 'idle');
        btn.title = 'Download failed (' + err.message + ') — click to retry';
      });
    });
  });
})();
"""

# ---- PWA: installable shelf (manifest + icons + service worker) ------------
# The site is already self-contained static HTML; these three pieces make it
# installable ("Add to Home Screen" on phones, app-window install on desktop)
# and give visited pages basic offline behavior. All generated — never
# hand-edit them in the repo. Icons are drawn in pure Python (no Pillow on the
# publish machine): a diagonal accent gradient with a white books-on-a-shelf
# glyph, kept inside the maskable safe zone.

PWA_THEME = "#b45309"      # matches the shelf's light-mode accent
PWA_BG = "#f7f5f1"         # matches the shelf's light-mode background
ICON_G1 = (0xB4, 0x53, 0x09)
ICON_G2 = (0x7C, 0x2D, 0x12)
ICON_INK = (255, 251, 245)

# Relative (x0, x1, y0, y1) rects: four book spines standing on a shelf.
ICON_GLYPH = [
    (0.270, 0.360, 0.340, 0.660),
    (0.385, 0.475, 0.280, 0.660),
    (0.500, 0.590, 0.360, 0.660),
    (0.615, 0.705, 0.310, 0.660),
    (0.250, 0.730, 0.660, 0.700),  # the shelf
]


def write_png(path: Path, size: int):
    """Render one square icon and write it as an RGB PNG, no dependencies."""
    rects = [(x0 * size, x1 * size, y0 * size, y1 * size)
             for (x0, x1, y0, y1) in ICON_GLYPH]
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter: none
        for x in range(size):
            t = (x + y) / (2 * size)
            px = [round(a + (b - a) * t) for a, b in zip(ICON_G1, ICON_G2)]
            for (x0, x1, y0, y1) in rects:
                if x0 <= x < x1 and y0 <= y < y1:
                    px = ICON_INK
                    break
            raw.extend(px)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                     chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
                     chunk(b"IEND", b""))


def render_manifest():
    return json.dumps({
        "name": SITE_TITLE,
        "short_name": "BookBank",
        "description": SITE_TAGLINE,
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": PWA_BG,
        "theme_color": PWA_THEME,
        "icons": [
            {"src": "assets/icon-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": "assets/icon-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
            {"src": "assets/icon-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }, indent=2) + "\n"


# Version placeholder is filled with a hash of the catalog so the cache turns
# over exactly when content changes (deterministic — republish stays byte-
# stable when nothing changed). Navigations + catalog.json are network-first
# so a fresh publish shows up immediately; everything else (book pages, art,
# the shell) is cache-first with a background refresh, which is what makes
# already-visited books readable offline.
SERVICE_WORKER = """// BookBank Library service worker — generated by build-library.py.
var VERSION = 'bookbank-@VERSION@';
// Persistent cache holding user-requested full-book downloads (the shelf's
// "⤓ Offline" button fills it). Never dropped on version bumps.
var OFFLINE = 'bookbank-offline';
var SHELL = ['./', 'assets/library.css?v=@ASSETV@', 'assets/library.js?v=@ASSETV@',
             'catalog.json', 'manifest.webmanifest',
             'assets/icon-192.png', 'assets/icon-512.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys
      .filter(function (k) { return k !== VERSION && k !== OFFLINE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== location.origin) return;

  var put = function (res) {
    if (res && res.ok) {
      var copy = res.clone();
      caches.open(VERSION).then(function (c) { c.put(req, copy); });
    }
    return res;
  };

  if (req.mode === 'navigate' || url.pathname.slice(-13) === '/catalog.json') {
    e.respondWith(fetch(req).then(put).catch(function () {
      return caches.match(req).then(function (hit) {
        return hit || caches.match('./');
      });
    }));
  } else {
    e.respondWith(caches.match(req).then(function (hit) {
      var refresh = fetch(req).then(put).catch(function () { return hit; });
      return hit || refresh;
    }));
  }
});
"""


def write_offline_manifest(book_dir: Path):
    """Write books/<id>/offline.json — the complete file list the shelf's
    "⤓ Offline" button precaches — and return the book's total bytes (shown
    on the button). Deterministic (sorted paths, version hashed from
    path+size pairs) so republishing an unchanged book is byte-stable.
    Must run AFTER OG stamping, which adds og-share.jpg and edits pages."""
    if not book_dir.is_dir():
        return 0
    files = []
    for p in sorted(book_dir.rglob("*")):
        rel = p.relative_to(book_dir).as_posix()
        if not p.is_file() or p.name == ".DS_Store" or rel == "offline.json":
            continue
        files.append((rel, p.stat().st_size))
    version = hashlib.sha1(json.dumps(files).encode("utf-8")).hexdigest()[:10]
    total = sum(s for _, s in files)
    (book_dir / "offline.json").write_text(json.dumps({
        "version": version,
        "bytes": total,
        "files": [f for f, _ in files],
    }, indent=1) + "\n", encoding="utf-8")
    return total


def render_readme(base_url):
    return f"""# The BookBank Library

Public home for books written with **BookBank** — each one web-researched and
written page by page in a chosen narrator's voice, then rendered as a
self-contained multi-page HTML book.

**Live:** {base_url}/

Every book under [`books/`](books/) is static HTML with no network
dependencies. The front page (`index.html`) and `catalog.json` are generated
from each book's `book.json` by `build-library.py` in the BookBank project —
do not hand-edit them; re-run the publisher instead.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=default_root())
    ap.add_argument("--only", default="")
    ap.add_argument("--repo",
                    default=os.environ.get("BOOKBANK_BOOKS_REPO") or DEFAULT_REPO,
                    help="Public GitHub repo as owner/name (default: sunprema/books).")
    ap.add_argument("--base-url",
                    default=os.environ.get("BOOKBANK_SITE_URL"),
                    help="Absolute site URL for share-preview (OG/Twitter) tags. "
                         "Default: derived from --repo as https://<owner>.github.io/<name>.")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    out = Path(args.out).expanduser()
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    base_url = (args.base_url or default_site_url(args.repo)).rstrip("/")

    if not (root / "books").is_dir():
        sys.exit(f"no books dir under root: {root}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)

    print(f"root={root}\nout={out}\nonly={only or '(all ready)'}")
    entries = build_catalog(root, out, only)

    # Book share previews FIRST (creates og-share.jpg, edits book pages), so
    # the offline manifests below capture each book's final file set. The
    # shelf's own OG block is stamped after index.html is written.
    stamped = 0
    for e in entries:
        if inject_book_og(out, e, base_url):
            stamped += 1

    # Offline manifests: per-book file lists driving the download buttons.
    for e in entries:
        e["offline_bytes"] = write_offline_manifest(out / "books" / e["id"])

    (out / "index.html").write_text(render_index(entries), encoding="utf-8")
    (out / "catalog.json").write_text(
        json.dumps({"books": entries}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "assets" / "library.css").write_text(LIBRARY_CSS, encoding="utf-8")
    (out / "assets" / "library.js").write_text(LIBRARY_JS, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    # PWA: manifest + icons + service worker. The SW cache version is a hash
    # of the catalog, so it changes exactly when the published content does.
    (out / "manifest.webmanifest").write_text(render_manifest(), encoding="utf-8")
    catalog_hash = hashlib.sha1(
        json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    (out / "sw.js").write_text(
        SERVICE_WORKER.replace("@VERSION@", catalog_hash)
                      .replace("@ASSETV@", asset_v()), encoding="utf-8")
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512),
                       ("apple-touch-icon.png", 180)):
        write_png(out / "assets" / name, size)
    print(f"PWA: manifest + sw.js (cache {catalog_hash}) + 3 icons.")
    if not (out / "README.md").exists():
        (out / "README.md").write_text(render_readme(base_url), encoding="utf-8")

    # --- Share preview for the shelf itself (books were stamped above) ---
    shelf_cover = next((e for e in entries if e.get("cover")), None)
    shelf_img = None
    if shelf_cover:
        # Reuse the compressed share JPEG generated for that book above.
        share_rel = f"books/{shelf_cover['id']}/assets/img/og-share.jpg"
        if (out / share_rel).is_file():
            shelf_img = f"{base_url}/{share_rel}"
        else:
            shelf_img = f"{base_url}/{shelf_cover['cover']}"
    shelf_block = og_block(
        title=SITE_TITLE,
        description=SITE_TAGLINE,
        image_url=shelf_img,
        page_url=f"{base_url}/",
        og_type="website",
    )
    shelf_idx = out / "index.html"
    shelf_idx.write_text(inject_head(shelf_idx.read_text(encoding="utf-8"), shelf_block),
                         encoding="utf-8")
    print(f"Stamped share-preview tags on {stamped} book page(s) + the shelf "
          f"(base {base_url}).")

    print(f"\nGenerated shelf with {len(entries)} book(s):")
    for e in entries:
        art = "art" if e["cover"] else "gradient"
        print(f"  - {e['id']}  [{art}]  {e['title']}")


if __name__ == "__main__":
    main()
