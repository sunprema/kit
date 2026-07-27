---
name: book-exercises
description: Add self-check exercises, reveal-answer blocks, and multiple-choice questions to a BookBank book, without breaking its paginated layout. Use when a chapter should give the reader something to do, when a book reads as passive prose, or when a concept is best tested rather than explained again. Triggers include "add exercises", "add a quiz", "check-yourself questions", "make this chapter interactive", "give the reader something to practice".
---

# book-exercises

Every good technical book ends a chapter with something to *do*. BookBank books
currently end with prose. This skill adds the three formats worth having —
**reveal-answer exercises**, **multiple choice**, and **worked challenges** —
using markup that survives the two-page spread.

## The constraint that shapes everything

A BookBank page is a **fixed-height multicolumn spread that cannot scroll**. If
revealing an answer made the page taller, the columns would re-flow and the
spread would rearrange under the reader's hands — the paragraph they were
reading would jump to the other page mid-sentence.

So the rule is absolute:

> **An answer is always laid out and always occupies its space. Revealing it
> changes only whether it is legible, never how much room it takes.**

The kit implements this by blurring rather than hiding. Never use
`display:none`, `height:0`, or `hidden` on an answer in a book. This is easy to
get wrong in a way that looks fine on a scrolling page and is broken in a book —
the kit's own reveal button originally used `display:none` and shrank its block
by 31px, which is exactly the bug this rule exists to prevent.

## Install (once per book)

1. Append `assets/exercises.css` (this skill) to the book's `assets/book.css`.
   Token-driven; no hardcoded colors, so it inherits the theme.
2. Copy `assets/exercises.js` to `<book>/assets/exercises.js` and load it
   **after** `book.js` on any page with an exercise:
   ```html
   <script src="../assets/book.js"></script>
   <script src="../assets/exercises.js"></script>
   ```

## Markup

**Reveal-answer** — the workhorse:

```html
<div class="exercise">
  <span class="ex-label">Check yourself — 01</span>
  <p class="ex-q">A service verifies with an RSA <em>public</em> key and passes
  the token's own <code>alg</code> into its verify call. Name the attack.</p>
  <button type="button" class="ex-reveal">Show answer</button>
  <div class="ex-answer">
    <p>Algorithm confusion — sign with the public key as the HMAC secret.</p>
    <p>Fix: pin <code>algorithms</code> server-side.</p>
  </div>
</div>
```

**Multiple choice** — mark the right option with `data-correct`, and give every
option a `data-why` so a wrong guess still teaches:

```html
<div class="quiz">
  <button type="button" class="quiz-opt"
          data-why="exp bounds how long a token lives, not who may accept it.">exp</button>
  <button type="button" class="quiz-opt" data-correct
          data-why="Correct — aud names the intended recipient.">aud</button>
  <button type="button" class="quiz-opt"
          data-why="sub identifies the principal, not the recipient.">sub</button>
  <p class="quiz-note"></p>
</div>
```

`.quiz-note` must be present and empty — it reserves the feedback line's space.
On answer, the kit marks the chosen option ✗ (or ✓) **and always marks the
correct one**, so the reader learns even when wrong.

## Writing good exercises

**Test the trap, not the definition.** "What does `aud` mean?" is a lookup.
"Which claim would have stopped this token from working against the payments
API?" makes the reader use the idea. Every exercise should have a plausible
wrong answer that a reader who half-understood would pick.

**One per concept page, at the end.** Exercises are a closing beat, not a
running interruption. A page with three quizzes reads like a form.

**The answer teaches; it does not merely confirm.** Two short paragraphs: what
the answer is, and the principle it comes from. A one-word answer wastes the
reveal.

**Match the persona.** `the-adversary` asks the reader to find the flaw;
`the-crafter` asks them to predict what the code prints; `feynman` asks what
would happen if a quantity were doubled; `isaac-newton` asks them to derive the
next step. An exercise in the wrong voice is more jarring than prose in the
wrong voice, because the reader is actively engaged when they hit it.

**Never make the exercise load-bearing.** A reader who skips every exercise must
still get the whole argument. Nothing in the answer may be a fact the rest of
the book depends on.

## Rules the kit already obeys — don't break them

- **Never bind arrow keys.** The pager owns ← → ↑, and the BookBank app binds
  them itself. Clicks inside an exercise call `stopPropagation()` so they can
  never reach a nav link.
- **Degrades to nothing.** With JS off the answer stays blurred but present, and
  prints unblurred. No dead buttons that look interactive but aren't.
- **No network, no dependencies.** Classic script, works from `file://`.

## Verification

1. Open the page from `file://`, reveal an answer, answer a quiz.
2. **Confirm nothing moved.** Measure it — do not eyeball it:
   ```js
   var ex = document.querySelector('.exercise');
   var before = ex.getBoundingClientRect().height;
   ex.querySelector('.ex-reveal').click();
   before === ex.getBoundingClientRect().height   // must be true
   ```
   A shift here means an answer is changing layout, and the spread will
   scramble for a real reader.
3. Confirm ← → still turn pages with an exercise focused.
4. Run `/book-visual-qa` — a tall exercise block can push a page into an extra
   spread or strand a heading.

## Report

Say how many exercises you added and where, which format each uses, and confirm
the no-reflow measurement passed. If you skipped exercises on some pages, say
why — usually because the concept is expository and has nothing to test.
