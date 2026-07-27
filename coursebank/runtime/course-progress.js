/* CourseBank progress runtime — offline-first lesson completion, quiz scoring,
 * resume, and certificate gating. Classic script, no dependencies, safe from
 * file:// and inside a service-worker-cached PWA. Vendor per course:
 *   cp runtime/course-progress.js <course>/assets/vendor/course-progress.js
 * and load it after the page content on every page (index, lessons,
 * certificate). Full markup contract in runtime/README.md.
 *
 * State lives in localStorage under 'cb-progress:<courseId>' — one record per
 * course, shared by every page on the same origin (and by the installed PWA,
 * which shares the origin's storage). The runtime also queues xAPI-shaped
 * statements in the same record; a future sync layer drains `events` when a
 * network and an endpoint exist. Nothing here requires a server.
 */
(function () {
  'use strict';

  var root = document.body;
  if (!root) return;
  var courseId = root.getAttribute('data-course');
  if (!courseId) return; // not a CourseBank page

  var KEY = 'cb-progress:' + courseId;
  var PASS = 0.8; // checkpoint pass threshold for certificate eligibility

  // -- storage (tolerate private-mode / disabled localStorage) ---------------
  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* fall through to fresh state */ }
    return { v: 1, lessons: {}, last: null, name: '', events: [] };
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* best effort */ }
  }
  var state = load();

  function record(verb, object, extra) {
    var ev = { verb: verb, object: object, ts: Date.now() };
    if (extra) ev.result = extra;
    state.events.push(ev);
    if (state.events.length > 200) state.events = state.events.slice(-200);
  }

  // -- canonical lesson list -------------------------------------------------
  // Pages that render progress carry the full ordered id list (generated from
  // course.json) so the denominator never depends on which page you're on:
  //   <body data-course="x" data-lessons="a,b,c,c1">
  function lessonIds() {
    var attr = root.getAttribute('data-lessons');
    if (!attr) return null;
    return attr.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function lessonState(id) { return state.lessons[id] || null; }
  function isDone(id) { var l = lessonState(id); return !!(l && l.done); }

  function pct() {
    var ids = lessonIds();
    if (!ids || !ids.length) return 0;
    var done = ids.filter(isDone).length;
    return Math.round((done / ids.length) * 100);
  }

  // Eligible when every lesson is done and every recorded quiz score passes.
  function certificateEligible() {
    var ids = lessonIds();
    if (!ids || !ids.length) return false;
    return ids.every(function (id) {
      var l = lessonState(id);
      if (!l || !l.done) return false;
      if (l.score && l.score.total > 0) return l.score.correct / l.score.total >= PASS;
      return true;
    });
  }

  // -- this page -------------------------------------------------------------
  var lessonId = root.getAttribute('data-lesson');   // set on lesson/checkpoint pages
  var pagePath = root.getAttribute('data-path');     // course-root-relative, e.g. lessons/01-01-schemas.html
  // index.html sits at the course root; lesson pages sit one level down.
  var toRoot = /\//.test(pagePath || '') ? '../' : '';

  if (lessonId && pagePath) {
    state.last = { id: lessonId, href: pagePath, ts: Date.now() };
    save(state);
  }

  function markDone(id, done) {
    var l = state.lessons[id] || (state.lessons[id] = {});
    l.done = done !== false;
    l.ts = Date.now();
    record(l.done ? 'completed' : 'reset', 'lesson:' + id);
    save(state);
    render();
  }

  function quizResult(id, correct, total) {
    var l = state.lessons[id] || (state.lessons[id] = {});
    l.score = { correct: correct, total: total, ts: Date.now() };
    record('scored', 'lesson:' + id, { correct: correct, total: total });
    save(state);
    render();
  }

  // -- quiz auto-scoring -----------------------------------------------------
  // Watches the bookbank exercise kit's markup: each .quiz scores once, on the
  // first option the reader picks. The tally is per page (per lesson).
  var quizzes = lessonId ? Array.prototype.slice.call(document.querySelectorAll('.quiz')) : [];
  var answered = 0, correctCount = 0;
  document.addEventListener('click', function (e) {
    if (!lessonId) return;
    var opt = e.target.closest && e.target.closest('.quiz-opt');
    if (!opt) return;
    var quiz = opt.closest('.quiz');
    if (!quiz || quiz.hasAttribute('data-cb-scored')) return;
    quiz.setAttribute('data-cb-scored', '1');
    answered++;
    if (opt.hasAttribute('data-correct')) correctCount++;
    if (answered === quizzes.length) quizResult(lessonId, correctCount, quizzes.length);
  }, true); // capture: runs even though the kit's own handler stops propagation

  // -- rendering -------------------------------------------------------------
  function render() {
    // "Mark complete" button on lesson pages: <button class="lesson-done">
    Array.prototype.forEach.call(document.querySelectorAll('.lesson-done'), function (btn) {
      var id = btn.getAttribute('data-lesson') || lessonId;
      if (!id) return;
      var done = isDone(id);
      btn.classList.toggle('cb-done', done);
      btn.setAttribute('aria-pressed', done ? 'true' : 'false');
      btn.textContent = done
        ? (btn.getAttribute('data-done-label') || '✓ Completed')
        : (btn.getAttribute('data-todo-label') || 'Mark lesson complete');
    });

    // Syllabus rows: <a data-lesson-link="<id>" …> gets .cb-done when done.
    Array.prototype.forEach.call(document.querySelectorAll('[data-lesson-link]'), function (el) {
      el.classList.toggle('cb-done', isDone(el.getAttribute('data-lesson-link')));
    });

    // Progress bar + label: <div class="course-progress"><i></i></div> and
    // any <span class="course-progress-label">.
    var p = pct();
    Array.prototype.forEach.call(document.querySelectorAll('.course-progress > i'), function (bar) {
      bar.style.width = p + '%';
    });
    Array.prototype.forEach.call(document.querySelectorAll('.course-progress-label'), function (el) {
      el.textContent = p + '%';
    });

    // Resume: <a class="course-resume"> — hidden until there's somewhere to go.
    Array.prototype.forEach.call(document.querySelectorAll('.course-resume'), function (a) {
      if (state.last && state.last.href) {
        a.href = toRoot + state.last.href;
        a.classList.remove('cb-hidden');
      } else {
        a.classList.add('cb-hidden');
      }
    });

    // Certificate page: <body data-certificate> unlocks when eligible.
    if (root.hasAttribute('data-certificate')) {
      var ok = certificateEligible();
      root.classList.toggle('cb-unlocked', ok);
      Array.prototype.forEach.call(document.querySelectorAll('[data-cert-date]'), function (el) {
        if (ok) el.textContent = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      });
      Array.prototype.forEach.call(document.querySelectorAll('[data-cert-name-out]'), function (el) {
        el.textContent = state.name || el.getAttribute('data-placeholder') || '';
      });
    }
  }

  // Certificate name input: <input data-cert-name> persists across visits.
  document.addEventListener('input', function (e) {
    var t = e.target;
    if (t && t.hasAttribute && t.hasAttribute('data-cert-name')) {
      state.name = t.value;
      save(state);
      render();
    }
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-cert-name]'), function (input) {
    if (state.name && !input.value) input.value = state.name;
  });

  // The mark-complete button (delegated; exercises' stopPropagation never
  // reaches it because .lesson-done sits outside .exercise/.quiz).
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.lesson-done');
    if (!btn) return;
    var id = btn.getAttribute('data-lesson') || lessonId;
    if (id) markDone(id, !isDone(id));
  });

  // Another tab / the installed PWA changed the record — re-render.
  window.addEventListener('storage', function (e) {
    if (e.key === KEY) { state = load(); render(); }
  });

  // -- public API ------------------------------------------------------------
  window.courseProgress = {
    courseId: courseId,
    isDone: isDone,
    markDone: markDone,
    quizResult: quizResult,
    pct: pct,
    certificateEligible: certificateEligible,
    resumeHref: function () { return state.last ? toRoot + state.last.href : null; },
    export: function () { return JSON.parse(JSON.stringify(state)); },
    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) { /* best effort */ }
      state = load();
      render();
    }
  };

  render();
})();
