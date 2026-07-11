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
import html
import json
import os
import shutil
import subprocess
import sys
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
        # Prefer a small compressed share JPEG (WhatsApp-safe); fall back to the
        # full cover if sips isn't available.
        share_rel = f"books/{entry['id']}/assets/img/og-share.jpg"
        ok, w, h = make_share_jpeg(out / cover, out / share_rel)
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

    # data-* attributes power the client-side search/filter.
    hay = " ".join([e["title"], e["topic"], voice, e["summary"]]).lower()
    return f"""      <a class="card" href="{esc(e['url'])}" data-search="{esc(hay)}" data-voice="{esc(e['persona']['id'])}">
        <div class="{cover_cls}" {style}>{art}</div>
        <div class="card-body">
          <h2 class="card-title">{esc(e['title'])}</h2>
          {voice_line}
          <p class="card-summary">{esc(e['summary'])}</p>
          <div class="card-meta">{meta_line}</div>
        </div>
        <span class="card-open">Read →</span>
      </a>"""


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
<link rel="preconnect" href="/" />
<link rel="stylesheet" href="assets/library.css" />
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
<script src="assets/library.js"></script>
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
.card-open{
  padding:.7rem 1.2rem 1.1rem;color:var(--accent);font-weight:700;font-size:.9rem;
}

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
})();
"""

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

    (out / "index.html").write_text(render_index(entries), encoding="utf-8")
    (out / "catalog.json").write_text(
        json.dumps({"books": entries}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "assets" / "library.css").write_text(LIBRARY_CSS, encoding="utf-8")
    (out / "assets" / "library.js").write_text(LIBRARY_JS, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    if not (out / "README.md").exists():
        (out / "README.md").write_text(render_readme(base_url), encoding="utf-8")

    # --- Share previews: stamp OG/Twitter tags into every book + the shelf ---
    stamped = 0
    for e in entries:
        if inject_book_og(out, e, base_url):
            stamped += 1
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
