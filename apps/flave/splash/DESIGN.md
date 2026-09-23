---
name: flave — Press Room
description: >-
  Visual identity for the flave splash. A press-room aesthetic: graphite ground,
  bone type, vermilion ink, and a semantic clearance ramp that turns the
  product's core idea — content carries a visibility level — into the palette
  itself. Print-registration ornament and a deliberate misregistration on
  display type give it the creative edge; the grid, the hairlines, and the
  ledger rows keep it professional.
version: 0.1.1.0
date_created: 2026-08-15
date_modified: 2026-08-20
authors:
  - Michael Staton
augmented_with:
  - Claude Code on Claude Opus 5
default_mode: dark

colors:
  # ── Tier 1: raw brand values ──────────────────────────────────────────
  ink-900: "#0E0F11"      # ground — cool near-black, the press-room dark
  ink-800: "#16181C"      # raised surface
  ink-700: "#1D2025"      # soft surface
  ink-600: "#282C33"      # hairline border
  ink-500: "#3A3F48"      # strong border
  bone-100: "#ECEDEF"     # primary type on dark
  bone-300: "#A8ADB6"      # secondary type
  bone-500: "#6E747E"     # tertiary type / disabled
  paper-50: "#F7F6F3"     # ground — light mode, warm bone paper
  paper-200: "#E7E5E0"    # light raised surface
  vermilion-500: "#FF4D2E"  # THE accent — print ink, hot, confident
  vermilion-300: "#FF7A5F"  # accent hover / soft
  vermilion-700: "#C8341A"  # accent pressed / light-mode accent

  # ── The clearance ramp — semantic, cool→hot as exposure increases ─────
  # This is the spine. It is not decoration: it encodes §11.1 of the spec.
  clearance-private: "#6E747E"   # graphite — held back, muted, nearly ground
  clearance-team: "#4C9BE8"      # slate blue — internal circulation
  clearance-lp: "#E0A33C"        # amber — shared under care
  clearance-public: "#FF4D2E"    # vermilion — fully exposed

  # ── Callout tones — semantic STATE, deliberately NOT the clearance ramp ──
  # Same tier-1 raws, different names. A warning callout makes no claim about
  # who may see it; fusing the two would make the clearance ramp unverifiable.
  tone-neutral: "#6E747E"        # graphite — unknown or untyped callout
  tone-info: "#4C9BE8"           # slate — note / tip / abstract / question
  tone-warning: "#E0A33C"        # amber — warning / caution / attention
  tone-danger: "#FF4D2E"         # vermilion — danger / error / bug / failure

typography:
  display: "'Space Grotesk', system-ui, sans-serif"
  sans: "'Instrument Sans', system-ui, sans-serif"
  mono: "'JetBrains Mono', ui-monospace, monospace"
  scale_ratio: 1.25
  display_tracking: "-0.03em"
  mono_tracking: "0.02em"

rounded:
  none: "0"
  sm: "2px"
  md: "3px"
  pill: "999px"

spacing:
  base: "4px"
  rhythm: "geometric — 1 2 3 4 6 8 12 16 24 units"

components:
  card: "ledger row — hairline top/bottom, 3px clearance-colored left rule, zero radius"
  chip: "mono, uppercase, 2px radius, hairline border, clearance-tinted"
  hero: "strata stack — offset translucent planes, one per clearance level"
  ornament: "corner registration crosshairs + misregistered display type"
---

# flave — Press Room

## 1 · Concept

flave is a document that keeps its workings. The visual identity has one job:
make *layers* legible before anyone reads a word.

The reference is a **press room** — the place where a document becomes an
artifact. Registration marks, ink density, plate alignment, the moment where
misalignment is visible and consequential. It is a professional environment that
happens to be full of striking marks, which is exactly the register the brief
asked for: **between Figma's grotesk confidence and Adobe's institutional
restraint.**

The identity's one non-negotiable idea: **the palette is the product's thesis.**
Content in a `.flave` carries a clearance — `private → team → lp → public` — and
each level owns a color. The ramp runs cool to hot as exposure increases, so a
reader learns the model from the interface before encountering the prose.

## 2 · Divergence from sibling splashes

Per the `maintain-splash-pages` divergence discipline, this splash must not read
as a recolor of its siblings.

| Axis | memopop-site | lfm/splash | **flave/splash** |
|---|---|---|---|
| Default mode | dark | light | **dark** |
| Type | Fraunces + Inter | Newsreader + Manrope | **Space Grotesk + Instrument Sans** |
| Hero | centered, stacked CTAs | asymmetric, diagram-dominant | **two acts: an incumbent-flip opener, then the strata stack** |
| Card chrome | rounded glass + glow | hairline + printer's corner ticks | **ledger row, zero radius, clearance left-rule** |
| Ornament | radial mesh + grid | paper grain + margin rule | **registration crosshairs + misregistered display type** |
| Brand spine | cyan / aquamarine / plum | ink-violet / sienna / moss | **graphite / bone / vermilion + clearance ramp** |
| Voice | matter-of-fact | literary | **editorial-precise** |

It shares `dark` with memopop, so the separation has to be carried by
composition and palette — and it is: strata versus radial mesh, vermilion
versus cyan, zero-radius ledger rows versus rounded glass.

## 3 · Color

**Two tiers, per the `theme-system` contract.** Tier 1 is the raw brand values
in the frontmatter above; Tier 2 is the semantic layer components consume.
Components reference `--color-text`, never `--bone-100`.

```css
--color-bg          /* ground */
--color-bg-raised   /* cards, header */
--color-bg-soft     /* chips, code */
--color-border      /* hairline */
--color-border-strong
--color-text / --color-text-soft / --color-text-dim
--color-accent / --color-accent-soft
--color-clearance-private | -team | -lp | -public
--color-tone-neutral | -info | -warning | -danger
--color-misreg-a / --color-misreg-b   /* the two offset plates */
```

### The clearance ramp is semantic, not decorative

`--color-clearance-*` must only ever mean *"the visibility level of this
content."* Do not reach for amber because a card needs warmth. If a surface
uses a clearance color, that surface is making a claim about who can see
something. This is the one rule in this document worth enforcing in review.

### Callout tones are state, and they are a different axis

Added 2026-08-20, when the editor grew real `Callout` and `Table` components.

Callouts needed semantic state colour and the palette had none — only the
accent, the clearance ramp, and the misregistration pair. The tempting move was
to reuse the ramp: amber is right there, and `> [!warning]` wants amber.

**That would have been a mistake**, and the rule above says why. Clearance means
*who may see this*. A warning callout makes no claim about visibility — a public
document can carry a warning, and a private one can carry none. Two meanings on
one token makes the clearance scan (§11.1 of the spec, the core promise)
unverifiable, because you could no longer tell whether an amber rule meant
"LP-visible" or "be careful."

So `--color-tone-*` draws from the same tier-1 raws — the palette does not grow
— under its own names. Four tones, not one per callout type, because **lfm's
callout vocabulary is open**: it accepts any `[A-Za-z0-9_-]+`, so
`> [!spaceship-status]` is valid input. Unknown types resolve to
`tone-neutral` and keep their raw type on the element, so nothing is ever
dropped — only its colour is defaulted.

Tone is carried on a `data-callout-tone` attribute rather than a class, and
paired with a marker bar so the distinction never rests on hue alone.

### Three modes

- **dark (default)** — "press room." Graphite ground, bone type. The strata
  read as backlit plates. This is the splash's voice.
- **light** — "proof sheet." Warm bone paper, ink type, the same ramp darkened
  for contrast on light ground. Registration marks go from bone to graphite.
- **vibrant** — "full ink." Saturation pushed, misregistration offset doubled
  (2px → 4px), accent glow permitted on interactive surfaces only.

All three satisfy WCAG AA on body text. The clearance ramp is verified against
its own ground in each mode — amber on graphite is the tightest pair and sets
the floor.

## 4 · Typography

Two working faces and a mono, which is the brief made literal:

- **Space Grotesk** — display. The creative pole. Geometric grotesque with odd,
  slightly mechanical terminals. Used at `-0.03em` tracking, weights 500/700,
  for h1–h3 and the wordmark. Never for running prose.
- **Instrument Sans** — body. The professional pole. Neutral, quiet, high
  legibility at small sizes. Everything a reader actually reads.
- **JetBrains Mono** — internals. Metadata, clearance chips, file paths, code,
  registration labels. The house mono, per convention.

The pairing is the whole positioning argument: Space Grotesk keeps it from
being Adobe-boring, Instrument Sans keeps it from being a design-tool pastiche.

### Misregistration — the signature move

Display headings render three times: a vermilion plate and a slate plate offset
by 2px in opposing directions, with the bone text on top. It reads as an
almost-aligned print run — a professional artifact with a visible human error,
which is precisely the tone.

**The offset plates are outlined, not solid** — revised 2026-08-15 after the
first solid version made h1 look out of focus rather than out of register.
Solid copies behind solid text read as blur; a hairline stroke offset from
crisp text reads as two plates that didn't quite line up. Keep the stroke at
1px — thicker returns to mush.

```css
.misreg::before,
.misreg::after {
  content: attr(data-text);
  position: absolute; inset: 0; z-index: -1;
  color: transparent;
  -webkit-text-stroke: 1px currentColor;   /* outline, never fill */
  opacity: 0.85;
}
.misreg::before { -webkit-text-stroke-color: var(--color-misreg-a); transform: translate(-2px, -1px); }
.misreg::after  { -webkit-text-stroke-color: var(--color-misreg-b); transform: translate(2px, 1px); }
```

Browsers without `-webkit-text-stroke` would fall back to solid fills and
reintroduce the blur, so an `@supports not` block hides the plates entirely
there. The headline stays crisp either way; it just loses the ornament.

**Constraints:** h1 and h2 only, never body. Disabled under
`prefers-reduced-motion` is not sufficient — it is static, so it stays; but it
must be `aria-hidden` via `::before/::after` (which it is) so screen readers
never hear the text three times.

## 5 · Space and shape

Zero radius is the default. `2px` is the maximum on anything that isn't a pill.
Rounded corners read as "app"; this should read as "artifact."

Spacing is a geometric rhythm on a 4px base: `1 2 3 4 6 8 12 16 24`. Vertical
rhythm between major sections is `--space-16` or `--space-24`; inside a card,
never more than `--space-4`.

Density is **dense-but-breathing**: ledger rows sit close together because a
list of them should scan like a manifest, but section gaps are generous.

## 6 · Components

- **Ledger row (`.ledger`)** — the card primitive. Hairline top and bottom, no
  side borders, a 3px left rule in the entry's clearance color, mono metadata
  in a fixed-width left column, title and lede flowing right. Zero radius.
- **Clearance chip (`.chip--clearance`)** — mono, uppercase, letter-spaced, 2px
  radius, hairline border tinted to its level, background at 12% of the level
  color.
- **Flip slot (`.flip`)** — the opener. A fixed-height window with the
  incumbent formats (Keynote, PowerPoint, Pages, Word, InDesign) rotating
  behind it on a pure-CSS reel, underlined in accent so the slot reads as a
  plate window rather than a glitch. Pinned to the first name under
  `prefers-reduced-motion`; the animated stack is `aria-hidden` with an
  `sr-only` list beside it so the sentence still parses aloud.
- **Strata stack (`.strata`)** — the second act. Four offset planes, `z`-ordered,
  each carrying a clearance label at its exposed edge. Clicking a level's chip
  brings that plane forward and swaps the specimen text to what that audience
  sees. This is a live demonstration of the thesis, not an illustration of it.
- **Registration mark (`.regmark`)** — a 16px crosshair in section corners,
  hairline, `--color-border-strong`. Purely ornamental, `aria-hidden`.

## 7 · Voice

**Editorial-precise.** Declarative sentences. Specific nouns. No exclamation
marks, no "simply," no "just." The copy should read like a well-run studio's
case study — confident about what the thing is, unembarrassed about what it
isn't yet.

The splash says plainly that flave is pre-implementation. Overclaiming would
undercut a product whose entire pitch is that documents should be honest about
what they contain.

## 8 · Imagery

No OG image yet. When one is generated per `generate-consistent-og-images`, the
recipe:

> A press-room plate stack seen at a shallow angle — four offset translucent
> sheets in graphite, slate, amber, and vermilion, registration crosshairs at
> the corners, one sheet crisply legible and the ones beneath progressively
> softer. Flat, precise, no gloss. Deep graphite ground, generous empty region
> at upper-left for an SVG title overlay.

Aspect ratios per the skill: 1.91:1 primary, 1:1 square, 9:16 portrait. JPEG
out, never WebP, per `open-graph-share-seo-geo`.
