/* exercises.js — self-check behavior for a BookBank book.
   Vendor into <book>/assets/exercises.js and load it AFTER book.js:
     <script src="../assets/book.js"></script>
     <script src="../assets/exercises.js"></script>

   Design rules this file obeys, all of them load-bearing:

   1. NEVER bind arrow keys. The pager owns ← → ↑ (and the BookBank app binds
      them itself). An exercise that stole them would trap the reader on a page.
   2. NEVER change layout size. Answers are revealed by un-blurring content
      that was always laid out, so the fixed-height columns cannot re-flow.
      See exercises.css for why that matters.
   3. Degrade to nothing. With JS off, or if this file fails to load, the
      answer stays blurred but present — and prints fine. Nothing 404s, no
      dead buttons that look interactive but aren't (the button is hidden by
      CSS until wired).
   4. No dependencies, no network. Classic script, works from file://. */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  // Space is reserved, so nothing should reflow — but tell the runtime anyway
  // so canvas widgets on the same spread re-fit if a book does something
  // fancier than the stock markup.
  function relayout() {
    try { window.dispatchEvent(new CustomEvent('bookbank:relayout')); } catch (e) {}
  }

  ready(function () {
    // ── Reveal buttons ───────────────────────────────────────────────────
    Array.prototype.forEach.call(
      document.querySelectorAll('.exercise'),
      function (ex) {
        var btn = ex.querySelector('.ex-reveal');
        var ans = ex.querySelector('.ex-answer');
        if (!btn || !ans) return;

        // Wire up accessibility only once we know JS is alive — a blurred
        // answer with no working button should not claim to be expandable.
        if (!ans.id) ans.id = 'exa-' + Math.abs(hash(ex.textContent)).toString(36);
        btn.setAttribute('aria-controls', ans.id);
        btn.setAttribute('aria-expanded', 'false');
        ans.setAttribute('aria-hidden', 'true');

        btn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();          // never let a click reach a nav link
          ex.classList.add('revealed');
          btn.setAttribute('aria-expanded', 'true');
          ans.setAttribute('aria-hidden', 'false');
          relayout();
        });
      }
    );

    // ── Multiple choice ──────────────────────────────────────────────────
    Array.prototype.forEach.call(
      document.querySelectorAll('.quiz'),
      function (quiz) {
        var note = quiz.querySelector('.quiz-note');
        var opts = quiz.querySelectorAll('.quiz-opt');

        Array.prototype.forEach.call(opts, function (opt) {
          if (!opt.querySelector('.mark')) {
            var m = document.createElement('span');
            m.className = 'mark';
            m.textContent = '·';
            opt.insertBefore(m, opt.firstChild);
          }
          opt.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (quiz.classList.contains('answered')) return;
            quiz.classList.add('answered');

            Array.prototype.forEach.call(opts, function (o) {
              var right = o.getAttribute('data-correct') !== null;
              // Always mark the correct one, so a wrong guess still teaches.
              if (right) { o.classList.add('correct'); o.querySelector('.mark').textContent = '✓'; }
              else if (o === opt) { o.classList.add('wrong'); o.querySelector('.mark').textContent = '✗'; }
            });

            if (note) {
              var why = opt.getAttribute('data-why');
              if (why) note.textContent = why;
            }
            relayout();
          });
        });
      }
    );
  });

  function hash(s) {
    var h = 0, i;
    s = (s || '').slice(0, 120);
    for (i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
    return h;
  }
})();
