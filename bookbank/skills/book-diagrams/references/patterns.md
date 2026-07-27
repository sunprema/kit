# Diagram patterns

Copy-paste starting points. Every one uses only `diagram-kit.css` classes, so
they inherit the book's theme with no edits. All use a **560-unit-wide
viewBox** — keep that constant across a book so stroke weights and label sizes
stay visually identical from page to page.

Conventions used throughout:

- **Arrowheads are drawn, not markers.** A three-point path inherits the
  stroke class; SVG markers need per-color `<defs>` and break on re-skin.
- **`<title>` first, always** — it is the accessible name and the print fallback.
- The **accent color marks the one thing that matters** (the attack, the
  failure, the answer) — never more than one idea per diagram.
- Coordinates are integers. Sub-pixel positions blur hairlines.

---

## 1. Flow / pipeline

Left-to-right stages. The workhorse: request lifecycles, build pipelines,
transform chains.

```html
<figure class="diagram-fig">
  <svg class="diagram" viewBox="0 0 560 120" role="img" aria-labelledby="d1t">
    <title id="d1t">Source is lexed to tokens, parsed to an AST, then lowered to IR</title>
    <rect x="16"  y="34" width="120" height="40" class="stroke fill-soft"/>
    <rect x="180" y="34" width="120" height="40" class="stroke fill-soft"/>
    <rect x="344" y="34" width="120" height="40" class="stroke fill-soft"/>
    <text x="26"  y="58" class="big">Source</text>
    <text x="190" y="58" class="big">Tokens</text>
    <text x="354" y="58" class="big">AST</text>

    <path d="M136 54 L180 54" class="stroke"/>
    <path d="M172 50 L180 54 L172 58" class="stroke"/>
    <path d="M300 54 L344 54" class="stroke"/>
    <path d="M336 50 L344 54 L336 58" class="stroke"/>

    <text x="140" y="30">lex</text>
    <text x="304" y="30">parse</text>
  </svg>
  <figcaption><b>Three passes, three shapes.</b> Each stage's output is the
  next stage's only input.</figcaption>
</figure>
```

**Spacing rule:** boxes 120 wide with 44 between them fits three across 560
with margins. For four stages use 100/32; beyond five, switch to a vertical
stack — a cramped horizontal flow is unreadable at column width.

---

## 2. Before / after (the failure diagram)

Two stacked bands separated by a rule: the intended path on top, the subverted
one below in accent. This is the highest-value shape for an
`the-adversary`-voiced book, and the one the JWT book used for the RS256→HS256
downgrade.

```html
<svg class="diagram" viewBox="0 0 560 180" role="img" aria-labelledby="d2t">
  <title id="d2t">Intended flow above; the attack below reuses the public key as a secret</title>
  <text x="16" y="20">Intended</text>
  <rect x="16"  y="30" width="120" height="32" class="stroke fill-soft"/>
  <rect x="250" y="30" width="130" height="32" class="stroke fill-soft"/>
  <text x="24"  y="51" class="big">private key</text>
  <text x="258" y="51" class="big">signed token</text>
  <text x="148" y="51">signs</text>

  <path d="M16 84 L544 84" class="stroke-soft"/>

  <text x="16" y="112" class="red">Attack</text>
  <rect x="16"  y="122" width="120" height="32" class="stroke-red"/>
  <rect x="250" y="122" width="130" height="32" class="stroke-red"/>
  <text x="24"  y="143" class="big red">public key</text>
  <text x="258" y="143" class="big red">forged token</text>
  <text x="148" y="143">used as secret</text>
</svg>
```

Keep the two bands **geometrically identical** — same x, same widths. The
reader should see one thing change, not two layouts.

---

## 3. Timeline / window

A line with marks, and a shaded span for the interval that matters (a token's
validity, an outage, a retry window).

```html
<svg class="diagram" viewBox="0 0 560 150" role="img" aria-labelledby="d3t">
  <title id="d3t">The window between logout and expiry during which a stolen token still works</title>
  <path d="M16 60 L544 60" class="stroke"/>
  <path d="M16 54 L16 66"   class="stroke"/>
  <path d="M180 46 L180 74" class="stroke"/>
  <path d="M520 54 L520 66" class="stroke"/>
  <text x="16"  y="40">issued</text>
  <text x="150" y="40" class="red">logout</text>
  <text x="470" y="40">expiry</text>

  <rect x="180" y="82" width="340" height="26" class="stroke-red"/>
  <text x="190" y="100" class="big red">still valid</text>

  <path d="M180 122 L520 122" class="stroke-red"/>
  <path d="M188 118 L180 122 L188 126" class="stroke-red"/>
  <path d="M512 118 L520 122 L512 126" class="stroke-red"/>
  <text x="180" y="142">this gap is the token lifetime</text>
</svg>
```

---

## 4. Sequence (two actors)

Vertical lifelines, messages as horizontal arrows. Use for protocols and
handshakes. Cap it at **three actors and six messages** — past that a table
reads better than a diagram.

```html
<svg class="diagram" viewBox="0 0 560 200" role="img" aria-labelledby="d4t">
  <title id="d4t">Client requests a token, the server issues one, the client presents it</title>
  <text x="60"  y="20" class="big">Client</text>
  <text x="440" y="20" class="big">Server</text>
  <path d="M90 30 L90 180"   class="stroke-soft dash"/>
  <path d="M470 30 L470 180" class="stroke-soft dash"/>

  <path d="M90 60 L470 60" class="stroke"/>
  <path d="M462 56 L470 60 L462 64" class="stroke"/>
  <text x="150" y="52">credentials</text>

  <path d="M470 100 L90 100" class="stroke"/>
  <path d="M98 96 L90 100 L98 104" class="stroke"/>
  <text x="150" y="92">signed token</text>

  <path d="M90 150 L470 150" class="stroke-red"/>
  <path d="M462 146 L470 150 L462 154" class="stroke-red"/>
  <text x="150" y="142" class="red">token on every later request</text>
</svg>
```

---

## 5. Layered stack

Bands stacked bottom-up. For abstraction layers, network stacks, storage tiers.

```html
<svg class="diagram" viewBox="0 0 560 170" role="img" aria-labelledby="d5t">
  <title id="d5t">Application over transport over network over link</title>
  <rect x="120" y="16"  width="320" height="32" class="stroke fill-red"/>
  <rect x="120" y="52"  width="320" height="32" class="stroke fill-soft"/>
  <rect x="120" y="88"  width="320" height="32" class="stroke fill-soft"/>
  <rect x="120" y="124" width="320" height="32" class="stroke fill-soft"/>
  <text x="132" y="37" class="big on-ink">Application</text>
  <text x="132" y="73" class="big">Transport</text>
  <text x="132" y="109" class="big">Network</text>
  <text x="132" y="145" class="big">Link</text>
  <text x="452" y="37">you are here</text>
</svg>
```

Highlight **one** layer with `fill-red` + `on-ink` text — the layer the chapter
is about.

---

## 6. State machine

Nodes and labelled transitions. Keep to four states; more belongs in a table.

```html
<svg class="diagram" viewBox="0 0 560 170" role="img" aria-labelledby="d6t">
  <title id="d6t">Requested becomes building, then ready; a revision returns it to revising</title>
  <rect x="16"  y="60" width="110" height="36" class="stroke fill-soft"/>
  <rect x="225" y="60" width="110" height="36" class="stroke fill-soft"/>
  <rect x="434" y="60" width="110" height="36" class="stroke fill-red"/>
  <text x="26"  y="83" class="big">requested</text>
  <text x="235" y="83" class="big">building</text>
  <text x="444" y="83" class="big on-ink">ready</text>

  <path d="M126 78 L225 78" class="stroke"/>
  <path d="M217 74 L225 78 L217 82" class="stroke"/>
  <path d="M335 78 L434 78" class="stroke"/>
  <path d="M426 74 L434 78 L426 82" class="stroke"/>
  <text x="146" y="70">build</text>
  <text x="355" y="70">publish</text>

  <path d="M489 60 L489 24 L71 24 L71 60" class="stroke-soft"/>
  <path d="M67 52 L71 60 L75 52" class="stroke-soft"/>
  <text x="240" y="18" class="dim">revise</text>
</svg>
```

---

## 7. Comparison (two columns of shapes)

When the point is *difference*, not flow — JWS versus JWE, sync versus async.
Draw both at the same scale so the difference is the only variable.

```html
<svg class="diagram" viewBox="0 0 560 160" role="img" aria-labelledby="d7t">
  <title id="d7t">A three-part signed token versus a five-part encrypted one</title>
  <text x="16" y="22">Signed — three parts</text>
  <rect x="16"  y="32" width="150" height="30" class="stroke fill-soft"/>
  <rect x="176" y="32" width="210" height="30" class="stroke fill-soft"/>
  <rect x="396" y="32" width="120" height="30" class="stroke"/>
  <text x="24"  y="51" class="big">header</text>
  <text x="184" y="51" class="big">payload — readable</text>
  <text x="404" y="51" class="big">signature</text>

  <text x="16" y="108">Encrypted — five parts</text>
  <rect x="16"  y="118" width="96"  height="30" class="stroke fill-soft"/>
  <rect x="120" y="118" width="96"  height="30" class="stroke"/>
  <rect x="224" y="118" width="60"  height="30" class="stroke"/>
  <rect x="292" y="118" width="140" height="30" class="stroke-red"/>
  <rect x="440" y="118" width="76"  height="30" class="stroke"/>
  <text x="24"  y="137" class="big">header</text>
  <text x="128" y="137" class="big">enc key</text>
  <text x="232" y="137" class="big">iv</text>
  <text x="300" y="137" class="big red">ciphertext</text>
  <text x="448" y="137" class="big">tag</text>
</svg>
```

---

## Sizing cheat sheet

| Element | Value | Why |
|---------|-------|-----|
| viewBox width | `560` | One constant per book; keeps weights consistent |
| viewBox height | 110–220 | Taller than ~240 crowds a column; split the diagram instead |
| Box height | 30–40 | Fits an 11px `.big` label with breathing room |
| Gap between boxes | 40–48 | Enough for an arrow plus its label |
| Hairline | `stroke-width:1` | 2 only for emphasis (`.stroke-thick`) |
| Arrowhead | 8 long, 4 half-height | Legible without becoming a shape |
| Label baseline | box `y` + 21 | Optically centres an 11px label in a 32px box |
