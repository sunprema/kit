// End-to-end check of the WebMCP tools build-library.py generates, run in a
// real Chrome against a locally served library:
//
//   cd <books repo> && python3 -m http.server 8765
//   NODE_PATH=<any project with playwright installed>/node_modules \
//     BASE=http://127.0.0.1:8765/ node test-webmcp.js
//
// Uses the installed Chrome (channel "chrome") with --enable-features=WebMCP;
// Chrome >= 146 exposes document.modelContext natively with that flag. If the
// browser has no document.modelContext, a spec-shaped shim is installed so the
// registration path and every execute() still run for real.
//
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:8765/';
let failures = 0;
function check(cond, label, extra) {
  console.log((cond ? '  ok   ' : '  FAIL ') + label + (extra !== undefined ? '  ' + JSON.stringify(extra).slice(0, 220) : ''));
  if (!cond) failures++;
}
const SHIM = `(() => {
  const tools = new Map();
  const mc = {
    __shim: true,
    registerTool(t) {
      if (!t || !t.name || !t.description || typeof t.execute !== 'function') return Promise.reject(new TypeError('bad tool'));
      if (tools.has(t.name)) return Promise.reject(new DOMException('dup ' + t.name, 'InvalidStateError'));
      tools.set(t.name, t); return Promise.resolve();
    },
    getTools() { return Promise.resolve([...tools.values()].map(t => ({ name: t.name, title: t.title, description: t.description, inputSchema: t.inputSchema, annotations: t.annotations }))); },
    async executeTool(tool, input) {
      const name = typeof tool === 'string' ? tool : tool.name;
      const t = tools.get(name); if (!t) throw new Error('no tool ' + name);
      const parsed = typeof input === 'string' ? JSON.parse(input) : JSON.parse(JSON.stringify(input || {}));
      const r = await t.execute(parsed, { signal: new AbortController().signal });
      return JSON.stringify(r);
    }
  };
  Object.defineProperty(Document.prototype, 'modelContext', { get() { return mc; }, configurable: true });
})();`;

async function call(page, name, input) {
  // Spec: executeTool(tool, inputObject) takes the RegisteredTool from getTools().
  const s = await page.evaluate(async ([n, i]) => {
    const ts = await document.modelContext.getTools();
    const t = ts.find(t => t.name === n);
    if (!t) throw new Error('no tool ' + n);
    // Chrome 151 takes the input as a JSON string (the draft says object); both
    // shapes reach execute() as a parsed object.
    return document.modelContext.executeTool(t, JSON.stringify(i || {}));
  }, [name, input]);
  return JSON.parse(s);
}
async function names(page) {
  return page.evaluate(() => document.modelContext.getTools().then(ts => ts.map(t => t.name).sort()));
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ channel: 'chrome', headless: true,
      args: ['--enable-features=WebMCP,WebMCPTesting', '--enable-blink-features=WebMCP'] });
  } catch (e) {
    console.log('chrome channel failed (' + e.message.split('\n')[0] + '), using bundled chromium');
    browser = await chromium.launch({ headless: true });
  }
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const probe = await ctx.newPage();
  await probe.goto(BASE);
  const native = await probe.evaluate(() => typeof document.modelContext === 'object' && document.modelContext !== null);
  const navOnly = await probe.evaluate(() => !!(navigator.modelContext));
  console.log('browser:', await browser.version(), '| native document.modelContext:', native, '| navigator.modelContext:', navOnly);
  await probe.close();
  if (!native) await ctx.addInitScript(SHIM);

  const page = await ctx.newPage();
  page.on('pageerror', e => { console.log('  PAGE ERROR', e.message); failures++; });

  // ---------------- shelf ----------------
  console.log('\n# shelf ' + BASE);
  await page.goto(BASE);
  let t = await names(page);
  check(t.length === 8, 'registers 8 shelf tools', t);

  let r = await call(page, 'search_books', { query: 'rust' });
  check(r.total >= 3 && r.books[0].url.startsWith(BASE + 'books/'), 'search_books "rust"', { total: r.total, first: r.books.slice(0, 3).map(b => b.id) });
  r = await call(page, 'search_books', { query: 'ownership' });
  check(r.total >= 1, 'search_books matches chapter titles ("ownership")', { total: r.total, ids: r.books.map(b => b.id).slice(0, 4) });
  r = await call(page, 'search_books', { query: 'zzzqqq' });
  check(r.total === 0 && r.books.length === 0, 'search_books no hits');
  r = await call(page, 'search_books', {});
  check(r.total > 50 && r.books.length === 12, 'search_books empty query lists newest (limit 12)', { total: r.total });
  r = await call(page, 'search_books', { query: 'rust', voice: 'thing-explainer' });
  check(r.total >= 1 && r.books.every(b => b.voice_id === 'thing-explainer'), 'search_books voice filter', r.books.map(b => b.id));

  r = await call(page, 'list_voices', {});
  check(r.voices.length > 3 && r.voices[0].books > 0, 'list_voices', r.voices.slice(0, 3));

  r = await call(page, 'get_book', { id: 'http-caching-headers' });
  check(r.chapters.length === 3 && r.chapters[1].n === 2 && r.cheatsheet && r.offline === false, 'get_book outline', { chapters: r.chapters.map(c => c.title), cheatsheet: r.cheatsheet });
  r = await call(page, 'get_book', { id: 'nope' });
  check(!!r.error, 'get_book unknown id → error', r.error);

  r = await call(page, 'filter_shelf', { query: 'rust' });
  const visible = await page.evaluate(() => [...document.querySelectorAll('.card')].filter(c => c.style.display !== 'none').length);
  const boxVal = await page.inputValue('#q');
  check(r.shown === visible && r.shown > 0 && boxVal === 'rust', 'filter_shelf updates UI', { shown: r.shown, visible, boxVal });
  r = await call(page, 'filter_shelf', { voice: 'thing-explainer' });
  const activeChip = await page.evaluate(() => document.querySelector('.chip.is-active').getAttribute('data-voice'));
  check(r.shown >= 1 && activeChip === 'thing-explainer', 'filter_shelf voice chip', { shown: r.shown, activeChip });
  r = await call(page, 'filter_shelf', {});
  check(r.shown > 50, 'filter_shelf reset', r);

  r = await call(page, 'list_offline_books', {});
  check(r.books.length === 0, 'list_offline_books empty');
  r = await call(page, 'save_book_offline', { id: 'http-caching-headers' });
  check(r.offline === true && r.files === 11, 'save_book_offline downloads', r);
  const btn = await page.textContent('.dl[data-book="http-caching-headers"]');
  check(btn.indexOf('Offline') !== -1 && btn.indexOf('✓') !== -1, 'offline button shows done', btn);
  r = await call(page, 'list_offline_books', {});
  check(r.books.length === 1 && r.books[0].id === 'http-caching-headers', 'list_offline_books after save', r.books.map(b => b.id));
  r = await call(page, 'get_book', { id: 'http-caching-headers' });
  check(r.offline === true, 'get_book reflects offline');
  r = await call(page, 'remove_offline_book', { id: 'http-caching-headers' });
  check(r.offline === false, 'remove_offline_book', r);
  r = await call(page, 'list_offline_books', {});
  check(r.books.length === 0, 'list_offline_books after remove');

  r = await call(page, 'open_book', { id: 'http-caching-headers', chapter: 'etag' });
  await page.waitForURL(/02-etag-and-conditional-get\.html$/);
  check(true, 'open_book navigates to chapter by title fragment', r);

  // ---------------- book page ----------------
  const ch1 = BASE + 'books/http-caching-headers/concepts/01-cache-control-directives.html';
  console.log('\n# book page ' + ch1);
  await page.goto(ch1);
  t = await names(page);
  check(t.length === 7, 'registers 7 book-page tools', t);

  r = await call(page, 'get_book_outline', {});
  check(r.current.kind === 'chapter' && r.current.n === 1 && r.chapters.length === 3 && !!r.cheatsheet && r.library === BASE + 'index.html', 'get_book_outline', { current: r.current, spread: r.spread, library: r.library });

  r = await call(page, 'get_page_text', {});
  check(r.length > 2000 && /^Chapter 01/.test(r.text) && r.text.indexOf('Library') === -1 && r.text.indexOf('Next ›') === -1 && r.text.indexOf('Cache-Control') !== -1, 'get_page_text clean chapter text', { length: r.length, head: r.text.slice(0, 80) });
  r = await call(page, 'get_page_text', { maxChars: 100, offset: 50 });
  check(r.text.length === 100 && r.offset === 50 && r.truncated === true, 'get_page_text paging');

  r = await call(page, 'find_in_book', { query: 'etag' });
  check(r.searched === 4 && r.hits.length >= 2 && r.hits[0].snippets.length > 0, 'find_in_book', { searched: r.searched, hits: r.hits.map(h => [h.title, h.matches]) });
  r = await call(page, 'find_in_book', { query: 'zzzqqq' });
  check(r.hits.length === 0, 'find_in_book no hits');

  const before = await page.textContent('.book-pageno');
  r = await call(page, 'next_page', {});
  const after = await page.textContent('.book-pageno');
  check(r.turned === 'next' && before !== after, 'next_page turns a spread', { before, after, r });
  r = await call(page, 'previous_page', {});
  check(r.turned === 'prev' && (await page.textContent('.book-pageno')) === before, 'previous_page turns back', r);
  // walk to the end of the chapter, then next_page must move to chapter 2
  for (let i = 0; i < 20; i++) { r = await call(page, 'next_page', {}); if (!r.turned) break; }
  check(!!r.navigating_to, 'next_page at chapter end navigates', r);
  await page.waitForURL(/02-etag-and-conditional-get\.html$/);
  check(true, 'landed on chapter 2');

  r = await call(page, 'go_to_chapter', { chapter: 'cheatsheet' });
  await page.waitForURL(/cheatsheet\.html$/);
  check(true, 'go_to_chapter cheatsheet', r);
  r = await call(page, 'get_book_outline', {});
  check(r.current.kind === 'cheatsheet', 'cheatsheet page identifies itself');
  r = await call(page, 'go_to_chapter', { chapter: '3' });
  await page.waitForURL(/03-caching-in-practice\.html$/);
  check(true, 'go_to_chapter by number');
  r = await call(page, 'go_to_chapter', { chapter: 'no such chapter' });
  check(!!r.error && r.chapters.length === 3, 'go_to_chapter unknown → error + chapter list');
  r = await call(page, 'open_library', {});
  await page.waitForURL(BASE + 'index.html');
  check(true, 'open_library');

  // ---------------- a book without the spread pager ----------------
  const alt = BASE + 'books/algorithms-for-modern-developers/concepts/02-binary-search.html';
  console.log('\n# non-pager book ' + alt);
  await page.goto(alt);
  r = await call(page, 'get_book_outline', {});
  check(r.current.kind === 'chapter' && r.chapters.length > 3, 'outline on non-pager book', { current: r.current.title, chapters: r.chapters.length });
  r = await call(page, 'get_page_text', {});
  check(r.length > 1000, 'page text on non-pager book', { length: r.length, head: r.text.slice(0, 80) });
  r = await call(page, 'next_page', {});
  check(!!r.navigating_to || !!r.turned, 'next_page falls through to rel=next', r);

  // ---------------- cover page ----------------
  await page.goto(BASE + 'books/http-caching-headers/');
  r = await call(page, 'get_book_outline', {});
  check(r.current.kind === 'contents', 'cover page identifies as contents', r.current);

  console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'ALL PASSED'));
  await browser.close();
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
