/* book-progress.js — quiet, automatic reading progress for a BookBank book.
   Vendor into <book>/assets/book-progress.js and load it AFTER book.js on
   every page:
     <script src="../assets/book.js"></script>
     <script src="../assets/book-progress.js"></script>

   Philosophy, and the reason this file has no buttons: a course lesson is
   completed by an act; a book chapter is completed BY READING IT. So nothing
   here asks the reader for anything. A chapter marks itself read when the
   reader reaches its last spread (or, on the mobile scroll layout, the end
   of the page), the contents page grows quiet read-marks, and a small
   resume link deep-links back to the exact spread via the pager's existing
   #s<N> support. With JS off, or on a book that never installs this file,
   nothing is missing — the reading experience is byte-for-byte the same.

   How the runtime learns the reader's position, in preference order:
   1. `bookbank:spread` CustomEvent with detail {i, total} — new books'
      pagers dispatch it from render() (see write-book's pager reference).
   2. Watching `.book-pageno`, which the stock pager rewrites as "i+1 / total"
      on every turn — existing books work with no pager changes.
   3. On the <=900px scroll layout there are no spreads: reaching ~85% scroll
      counts, and a page too short to scroll counts after a short dwell.

   State lives in localStorage under 'bb-progress:<bookId>'. Chapters are
   keyed by file basename (01-ownership.html), which survives everything
   except renumbering — and write-book already forbids renumbering. */
(function () {
  'use strict';

  var doc = document, body = doc.body;
  if (!body) return;

  // ── Identity ──────────────────────────────────────────────────────────
  // Explicit data-book on <body> (or <html>) wins; otherwise derive the id
  // from the URL: .../<book-id>/index.html, .../<book-id>/concepts/NN-x.html.
  var path = location.pathname;
  var endsSlash = path.charAt(path.length - 1) === '/';
  var parts = path.split('/').filter(Boolean);
  var file = endsSlash ? 'index.html' : (parts[parts.length - 1] || 'index.html');
  var dirs = endsSlash ? parts : parts.slice(0, -1);
  var inConcepts = dirs[dirs.length - 1] === 'concepts';
  var bookId = body.getAttribute('data-book') ||
    doc.documentElement.getAttribute('data-book') ||
    (inConcepts ? dirs[dirs.length - 2] : dirs[dirs.length - 1]);
  if (!bookId) return;

  var KEY = 'bb-progress:' + bookId;
  var isIndex = file === 'index.html';

  // ── Storage (tolerate private mode / disabled localStorage) ───────────
  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* fresh state */ }
    return { v: 1, read: {}, last: null };
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* best effort */ }
  }
  var state = load();

  function isRead(bn) { return !!state.read[bn]; }
  function markRead(bn, val) {
    if (val === false) delete state.read[bn];
    else if (!state.read[bn]) state.read[bn] = Date.now();
    else return;
    save();
    render();
  }

  // ── Content pages: track position, detect "read" ──────────────────────
  if (!isIndex) {
    var rel = (inConcepts ? 'concepts/' : '') + file;
    var spread = 0;

    function saveLast() {
      state.last = { file: rel, spread: spread, ts: Date.now() };
      save();
    }
    saveLast(); // arriving on the page is progress, even before a turn

    function onSpread(i, total) {
      spread = i;
      saveLast();
      if (total >= 1 && i >= total - 1) markRead(file);
    }

    // 1. The explicit event, if this book's pager dispatches it.
    window.addEventListener('bookbank:spread', function (e) {
      if (e.detail && typeof e.detail.i === 'number') onSpread(e.detail.i, e.detail.total);
    });

    // 2. The stock pager's page number — works on unmodified books.
    var pageno = doc.querySelector('.book-pageno');
    if (pageno && typeof MutationObserver !== 'undefined') {
      var parse = function () {
        var m = /^(\d+)\s*\/\s*(\d+)$/.exec((pageno.textContent || '').trim());
        if (m) onSpread(parseInt(m[1], 10) - 1, parseInt(m[2], 10));
      };
      new MutationObserver(parse).observe(pageno, { childList: true, characterData: true, subtree: true });
      parse();
    }

    // 3. Mobile scroll layout (the pager's own <=900px breakpoint): the end
    // of the page is the end of the chapter. A page too short to scroll
    // counts after a short dwell — landing on it IS reading it.
    function mobile() { return !window.matchMedia('(min-width: 901px)').matches; }
    function onScroll() {
      if (!mobile()) return;
      var d = doc.documentElement;
      if ((d.scrollTop + d.clientHeight) / d.scrollHeight >= 0.85) markRead(file);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('load', function () {
      onScroll();
      setTimeout(function () {
        var d = doc.documentElement;
        if (mobile() && d.scrollHeight <= d.clientHeight * 1.05) markRead(file);
      }, 2500);
    });
  }

  // ── Rendering (contents page, or anywhere the hooks appear) ───────────
  function basenameOf(href) {
    if (!href) return null;
    var clean = href.split('#')[0].split('?')[0];
    var bn = clean.split('/').pop();
    return bn || null;
  }

  function render() {
    // Quiet read-marks: any link whose target chapter has been read gets
    // .bb-read — the book's own CSS decides how softly to show it.
    var links = doc.querySelectorAll('a[href]');
    var concepts = {}, readCount = 0;
    Array.prototype.forEach.call(links, function (a) {
      var href = a.getAttribute('href') || '';
      var bn = basenameOf(href);
      if (!bn || !/\.html$/.test(bn) || bn === 'index.html') return;
      a.classList.toggle('bb-read', isRead(bn));
      if (href.indexOf('concepts/') !== -1 && !(bn in concepts)) {
        concepts[bn] = true;
        if (isRead(bn)) readCount++;
      }
    });

    // Optional whisper of overall progress: <span class="book-progress-note">
    var totalConcepts = Object.keys(concepts).length;
    Array.prototype.forEach.call(doc.querySelectorAll('.book-progress-note'), function (el) {
      if (!totalConcepts || !readCount) { el.textContent = ''; return; }
      el.textContent = readCount >= totalConcepts
        ? 'All ' + totalConcepts + ' chapters read'
        : readCount + ' of ' + totalConcepts + ' chapters read';
    });

    // Resume link: <a class="book-resume" hidden>Resume reading</a> —
    // stays hidden until there is genuinely somewhere to go back to.
    Array.prototype.forEach.call(doc.querySelectorAll('.book-resume'), function (a) {
      if (state.last && state.last.file && basenameOf(state.last.file) !== 'index.html') {
        a.href = state.last.file + (state.last.spread > 0 ? '#s' + (state.last.spread + 1) : '');
        a.removeAttribute('hidden');
        a.classList.add('bb-show');
      } else {
        a.setAttribute('hidden', '');
        a.classList.remove('bb-show');
      }
    });
  }

  // Another tab (or the app's WebView) advanced the book — reflect it.
  window.addEventListener('storage', function (e) {
    if (e.key === KEY) { state = load(); render(); }
  });

  // ── Public API (console + app integration; no UI depends on it) ───────
  window.bookProgress = {
    bookId: bookId,
    isRead: isRead,
    markRead: markRead,
    resumeHref: function () { return state.last ? state.last.file + (state.last.spread > 0 ? '#s' + (state.last.spread + 1) : '') : null; },
    export: function () { return JSON.parse(JSON.stringify(state)); },
    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) { /* best effort */ }
      state = load();
      render();
    }
  };

  render();
})();
