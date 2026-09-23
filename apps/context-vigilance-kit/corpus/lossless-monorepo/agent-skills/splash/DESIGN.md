---
version: alpha
name: Lossless Agent Skills — Operator (Astro Knots · CLI / handbook)
description: Design system for the lossless-agent-skills splash. Operator/CLI posture
  — the splash reads like a `man` page rendered on a high-end terminal. Mono- forward
  (JetBrains Mono is the headline AND the meta), brutalist hairline cards (no glow,
  sharp 2-3px radii), blueprint-grid backdrop. Dark ("operator") is the default mode;
  light ("daylight inspection") and vibrant ("demo") are first-class. Brand spine
  is terminal-teal + amber + magenta — deliberately diverged from sibling Lossless
  splashes (memopop's cyan-led, lfm's ink-violet, ai-labs's sodium-led). Tokens mirror
  the CSS custom properties in `src/styles/theme.css`; that file is the runtime source
  of truth, this DESIGN.md is the human- and agent-readable contract.
colors:
  teal: '#5eead4'
  teal-deep: '#14b8a6'
  teal-soft: '#99f6e4'
  amber: '#fbbf24'
  amber-deep: '#d97706'
  amber-soft: '#fde68a'
  magenta: '#e879f9'
  magenta-deep: '#c026d3'
  magenta-soft: '#f5d0fe'
  neon-teal: '#2dd4bf'
  neon-amber: '#fcd34d'
  neon-pink: '#ff66c4'
  console-bg: '#0a0e14'
  console-soft: '#11161f'
  console-card: '#161b26'
  console-line: '#1f2632'
  console-rule: '#2a3441'
  paper: '#f5f4f0'
  paper-soft: '#ebe9e3'
  paper-deep: '#ddd9d0'
  ink: '#0a0e14'
  ink-soft: '#1c2230'
  slate-700: '#334155'
  slate-500: '#64748b'
  slate-400: '#94a3b8'
  slate-300: '#cbd5e1'
  slate-200: '#e2e8f0'
  bg: '{colors.console-bg}'
  bg-soft: '{colors.console-soft}'
  bg-elevated: '{colors.console-card}'
  bg-card: '{colors.console-card}'
  bg-code: '#060a10'
  text: '#e6edf3'
  text-soft: '#b1bac4'
  text-dim: '#8b949e'
  text-dimmer: '#6e7681'
  text-faint: '#484f58'
  accent: '{colors.teal}'
  accent-soft: '{colors.teal-soft}'
  accent-warm: '{colors.amber}'
  accent-hot: '{colors.amber-deep}'
  thread: '{colors.magenta}'
  thread-soft: '{colors.magenta-soft}'
  border: '#e6edf3'
  border-strong: '#e6edf3'
  border-accent: '{colors.teal}'
typography:
  display-hero:
    fontFamily: JetBrains Mono
    fontSize: 2.9rem
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -0.02em
  display-h2:
    fontFamily: JetBrains Mono
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.012em
  display-h3:
    fontFamily: JetBrains Mono
    fontSize: 1.18rem
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.012em
  card-title:
    fontFamily: JetBrains Mono
    fontSize: 1.04rem
    fontWeight: 600
    letterSpacing: -0.005em
  body:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: '''cv11'' on'
  prose-body:
    fontFamily: Inter
    fontSize: 1.02rem
    fontWeight: 400
    lineHeight: 1.7
  tagline:
    fontFamily: Inter
    fontSize: 1.1rem
    fontWeight: 400
    lineHeight: 1.55
  folio:
    fontFamily: JetBrains Mono
    fontSize: 0.74rem
    fontWeight: 500
    letterSpacing: 0.18em
  eyebrow:
    fontFamily: JetBrains Mono
    fontSize: 0.7rem
    fontWeight: 500
    letterSpacing: 0.24em
  pill:
    fontFamily: JetBrains Mono
    fontSize: 0.68rem
    fontWeight: 500
    letterSpacing: 0.08em
  chip:
    fontFamily: JetBrains Mono
    fontSize: 0.8em
    fontWeight: 400
  meta:
    fontFamily: JetBrains Mono
    fontSize: 0.76rem
    fontWeight: 400
    letterSpacing: 0.04em
  code:
    fontFamily: JetBrains Mono
    fontSize: 0.88em
    fontWeight: 400
rounded:
  sm: 2px
  md: 3px
  lg: 4px
  xl: 6px
  full: 999px
spacing:
  '1': 0.25rem
  '2': 0.5rem
  '3': 0.75rem
  '4': 1rem
  '5': 1.25rem
  '6': 1.5rem
  '8': 2rem
  '10': 2.5rem
  '12': 3rem
  '16': 4rem
  '20': 5rem
  '24': 6rem
  container-max: 1200px
  container-narrow-max: 820px
  container-padding: 24px
  grid-pitch: 32px
  header-height: 60px
  transition-fast: 140ms
  transition-mid: 280ms
components:
  skill-card:
    backgroundColor: '{colors.bg-card}'
    borderColor: '{colors.border}'
    borderWidth: 1px
    rounded: 0
    padding: '{spacing.5}'
    hover-borderColor: '{colors.border-strong}'
    hover-titleColor: '{colors.accent}'
  pill:
    typography: '{typography.pill}'
    padding: 3px 8px
    rounded: '{rounded.sm}'
    borderColor: '{colors.border-strong}'
    backgroundColor: '{colors.text}'
    color: '{colors.text-soft}'
    textTransform: uppercase
  pill-active:
    color: '{colors.accent}'
    borderColor: '{colors.accent}'
    backgroundColor: '{colors.accent}'
  pill-iterating:
    color: '{colors.thread}'
    borderColor: '{colors.thread}'
    backgroundColor: '{colors.thread}'
  pill-experimental:
    color: '{colors.accent-warm}'
    borderColor: '{colors.accent-warm}'
    backgroundColor: '{colors.accent-warm}'
  chip:
    typography: '{typography.chip}'
    padding: 2px 7px
    rounded: '{rounded.sm}'
    backgroundColor: '{colors.bg-code}'
    borderColor: '{colors.border}'
    color: '{colors.text-soft}'
  folio:
    typography: '{typography.folio}'
    color: '{colors.text-dim}'
    prefix-color: '{colors.accent}'
    textTransform: uppercase
  eyebrow:
    typography: '{typography.eyebrow}'
    color: '{colors.text-dim}'
    textTransform: uppercase
  btn:
    typography: '{typography.pill}'
    padding: 9px 16px
    rounded: '{rounded.sm}'
    borderColor: '{colors.border-strong}'
    backgroundColor: '{colors.bg-elevated}'
    color: '{colors.text}'
    hover-borderColor: '{colors.accent}'
    hover-color: '{colors.accent}'
  btn-primary:
    backgroundColor: '{colors.accent}'
    borderColor: '{colors.accent}'
    color: '{colors.bg}'
    hover-backgroundColor: '{colors.accent-soft}'
  mode-toggle:
    backgroundColor: '{colors.bg-elevated}'
    borderColor: '{colors.border-strong}'
    rounded: '{rounded.sm}'
    button-size: 30px
    button-active-bg: '{colors.accent}'
    button-active-color: '{colors.bg}'
    button-rest-color: '{colors.text-dim}'
  site-header:
    position: sticky
    height: '{spacing.header-height}'
    backgroundColor: '{colors.bg}'
    borderBottomColor: '{colors.border}'
    backdropFilter: blur(10px)
  brand-mark:
    prompt-text: $_
    prompt-color: '{colors.accent}'
    name-fontFamily: '{typography.display-hero.fontFamily}'
    name-fontWeight: 600
  hero-panel:
    backgroundColor: '{colors.bg-elevated}'
    borderColor: '{colors.border-strong}'
    rounded: '{rounded.sm}'
    head-backgroundColor: '{colors.bg-soft}'
    head-borderBottomColor: '{colors.border}'
    dot-1-color: '{colors.accent-warm}'
    dot-2-color: '{colors.thread}'
    dot-3-color: '{colors.accent}'
  hero-install:
    backgroundColor: '{colors.bg-code}'
    borderColor: '{colors.border}'
    rounded: '{rounded.sm}'
    fontSize: 0.86rem
    color: '{colors.text-soft}'
    prompt-color: '{colors.accent}'
  gradient-text:
    background: linear-gradient(90deg, {colors.teal} 0%, {colors.amber} 55%, {colors.magenta}
      100%)
    backgroundClip: text
    color: transparent
  blueprint-grid:
    pitch: '{spacing.grid-pitch}'
    pitch-major: 128px
    line-color: '{colors.accent}'
    line-color-major: '{colors.accent-warm}'
    mask: radial-gradient(ellipse at center, black 40%, transparent 92%)
modes:
  dark:
    role: operator (default)
    bg: '{colors.console-bg}'
    text: '#e6edf3'
    accent: '{colors.teal}'
    thread: '{colors.magenta}'
    grid-line: '{colors.teal}'
    color-scheme: dark
  light:
    role: daylight inspection
    bg: '{colors.paper}'
    text: '{colors.ink}'
    accent: '{colors.teal-deep}'
    thread: '{colors.magenta-deep}'
    grid-line: '{colors.teal-deep}'
    color-scheme: light
  vibrant:
    role: demo
    bg: '#050810'
    text: '#f0f9ff'
    accent: '{colors.neon-teal}'
    thread: '{colors.neon-pink}'
    grid-line: '{colors.neon-teal}'
    shadow-elevated: 0 0 0 1px rgba(252, 211, 77, 0.25)
    color-scheme: dark
imagery:
  provider: ideogram
  endpoint: POST https://api.ideogram.ai/v1/ideogram-v3/generate
  content_type: multipart/form-data
  defaults:
    style_type: AUTO
    magic_prompt: false
    rendering_speed: QUALITY
    seed: 2048
  negative_prompt: text, typography, lettering, logos, watermarks, central subject
    filling frame, photorealistic human faces, saturated, rainbow, vibrant, oversized
    subject, subject in top half
  color_palette:
    members:
    - color_hex: '#0a0e14'
      color_weight: 0.45
    - color_hex: '#5eead4'
      color_weight: 0.2
    - color_hex: '#fbbf24'
      color_weight: 0.15
    - color_hex: '#e879f9'
      color_weight: 0.1
    - color_hex: '#e2e8f0'
      color_weight: 0.1
  style_reference:
    path: public/ogimage__Lossless-Agent-Skills--Default.png
    mime: image/png
  aspect_ratios:
    banner_image: 16x9
    banner_image_tall: 4x5
    portrait_image: 9x16
    square_image: 1x1
  prompt:
    pattern: Top 1/3 of frame is empty negative space, {empty_region_content}. Bottom
      2/3 contains {subject}.
    max_chars_recommended: 220
    empty_region_content: dark gradient sky with faint teal glint at the horizon
    subject_themes:
    - a few humanoid teenager robots at a gym, pumping iron
    - three humanoid teenager robots overhead-pressing barbells in a row
    - humanoid teenager robots squatting and bench-pressing on yellow gym tile
    - humanoid teenager robots warming up with dumbbells along a magenta gym wall
    - a row of humanoid teenager robots spotting each other at a bench-press rig
    forbid:
    - brand names (Lossless, lossless-agent-skills, skill names)
    - color names (teal, amber, magenta, dark)
    - aesthetic adjectives (operator, handbook, brutalist, blueprint)
    - composition cues encoded by the style_reference (yellow tile floor, magenta
      gym wall, teal horizon band) — repeating them in the prompt dilutes attention
      from the actual subject variation
  output:
    public_dir: public
    naming: ogimage__Lossless-Agent-Skills--{Format}.jpg
    formats:
    - BannerImage
    - BannerImageTall
    - PortraitImage
    - SquareImage
    archive_dir: .ogimage-archive
    candidates_dir: .ideogram-candidates
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/splash/DESIGN.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/splash/DESIGN.md"
---

# Lossless Agent Skills — Design System

> The runtime source of truth is `src/styles/theme.css`'s `:root` and
> `:root[data-mode='...']` blocks; long-form prose styling lives in
> `src/styles/prose.css`. This document is the human- and agent-readable
> contract that explains intent. Keep them in sync when any of them
> changes.

## Brand & Style

The lossless-agent-skills splash reads as an **operator's manual rendered on
a high-end terminal** — `$_` prompt in the brand mark, `#01 · Featured`
folios at every section, a `skills/` tree-panel readout in the hero, brutalist
hairline cards with sharp corners, a faint blueprint grid running underneath
everything. Not "AI startup with neon gradients", not "build-in-public emoji
sprawl", not "marketing-deck dark theme." Closer to a `man` page printed on a
high-DPI display: dense, instrumented, deliberate.

The defining typographic move is **mono-as-display**. JetBrains Mono is the
headline AND the meta — section folios, status pills, status indicators,
chips, identifiers, AND every `<h1>` / `<h2>` / `<h3>`. Inter carries body
prose. There is no third family. Sibling Lossless splashes lean *editorial*
(memopop sans, lfm serif) or *instrumented-but-display-sans* (ai-labs Space
Grotesk display + JetBrains meta); this one collapses display into mono and
treats that collapse as the brand.

Three modes are first-class: **dark** ("operator") is the default — this is a
developer surface first; **light** ("daylight inspection") inherits the paper
axis but keeps the mono-forward type and brutalist hairlines; **vibrant**
("demo") is dark-based, pushes neon hues, and adds amber-tinted shadow
contour for demo-room presentations.

The voice is **handbook / datasheet**: short, declarative, prefers `$ ./sync-skills.sh`
to "Let's get started!", prefers `load lossless-agent-skills` (a command) to
"Welcome to..." Words like *catalog*, *roster*, *sync*, *load*, *prompt*,
*manual*, *ship*, *active* are preferred over *vibrant*, *amazing*, *unleash*,
*empower*. Hero h1 is literally a shell command.

## Colors

Two tiers. **Named tokens** are raw values, mode-invariant — the inputs.
**Semantic tokens** are what components consume — `bg`, `text`, `accent`,
`thread`, `border`, etc. — and get rebound per `<html data-mode>`. Components
must read semantic tokens only; hard-coded hex values break mode switching
silently.

The **brand spine** is three terminal hues:

- **`teal`** (#5eead4) — the primary accent. Terminal-prompt color, OK-signal,
  cursor block. Drives all calls-to-act, the hero `$` prompt, the brand mark
  glyph, the eyebrow underline, the hover-state on cards (`title` shifts to
  teal). Sparing use; every appearance should read as meaningful.
- **`amber`** (#fbbf24) — the warm accent. Highlight / careful / draft. Used
  for the "Draft" pill state, the leftmost terminal-window dot, the major
  blueprint-grid line. Reserved for "this needs attention but isn't a stop."
- **`magenta`** (#e879f9) — the thread. Signal-state, featured, version
  callouts. The middle terminal-window dot. Used sparingly; the vibrant
  mode pushes it to neon-pink for demo presence.

The **console neutrals** are the dark axis: `console-bg` (#0a0e14) →
`console-soft` → `console-card` → `console-line` → `console-rule`. Harder-
edged than ai-labs's `ink-bench` and considerably darker than memopop's deep
ink — closer to a literal terminal background.

The **paper neutrals** are the light axis: `paper` (#f5f4f0) → `paper-soft` →
`paper-deep`. Slightly warmer than pure white; reads as printed-datasheet
paper, not as glare.

Mode bindings:

| Semantic | Dark (operator) | Light (daylight) | Vibrant (demo) |
|---|---|---|---|
| `bg` | `console-bg` | `paper` | `#050810` |
| `text` | `#e6edf3` | `ink` | `#f0f9ff` |
| `accent` | `teal` | `teal-deep` | `neon-teal` |
| `accent-warm` | `amber` | `amber-deep` | `neon-amber` |
| `thread` | `magenta` | `magenta-deep` | `neon-pink` |

Borders are rendered from a single hex (`#e6edf3` in dark, `#0a0e14` in light)
at varying alpha levels (8% / 18% for the strong / 45% for the accent-tinted) —
the alpha *is* the strength signal. Status-indicating pills tint the same
border at 55% with the relevant accent color and fill the surface at 10%.

## Typography

Two families. The split is intentional and unusual:

- **JetBrains Mono** (display AND mono — the dominant family) — `h1`/`h2`/
  `h3`, card titles, folios, eyebrows, status pills, chips, code, identifiers,
  every number, every shell-prompt glyph. **This is the defining type move.**
  Where memopop reaches for sans, lfm reaches for serif, and ai-labs splits
  display (Space Grotesk) from meta (JetBrains Mono), this splash collapses
  display *into* mono. Headlines are commands; commands look like commands.
- **Inter** (body grotesque) — long-form prose paragraphs and reading text.
  Optimized for short-to-medium paragraphs at 1rem with the slashed-zero
  feature on (`'cv11' on`). Never used in headlines, eyebrows, or chips.

Single mono family is also intentional — fewer font weights to load, more
visual coherence between heading and inline-code, and the headline shares the
exact glyph shapes with the `$ ./sync-skills.sh` install line directly below
it. That visual rhyme is the whole point.

Conventions:

- **Folios** (`#01 · Featured`) lead every section. JetBrains Mono `0.74rem`
  at `0.18em` letter-spacing, uppercase, with the leading `#XX` rendered in
  `--color-accent` (teal) via the `data-num` attribute and a `::before`
  pseudo-element. The chapter-style numbering is the manual voice expressed
  at the section level — sections without a folio don't read as part of the
  manual.
- **Hero h1** is `clamp(1.8rem, 4.6vw, 2.9rem)` JetBrains Mono `700` with the
  shell `$` glyph as a separate span in `--color-accent`. The h1 is literally
  a shell command (`load lossless-agent-skills`) with one gradient-text word.
- **Body paragraphs** stay Inter; never use mono for paragraph prose. Mono in
  paragraphs reads as code; we want long-form prose to read as prose so
  that mono in headings reads as command.

Never introduce a third family. Two is the contract — and one of those two
gets used twice.

## Layout & Spacing

Container model: `--container-max` of `1200px` (and `--container-narrow-max`
of `820px` for prose-heavy pages) centered with `var(--space-6)` (24px) inline
padding. Sections add vertical rhythm via `padding: var(--space-12) 0` (48px)
with a `1px solid var(--color-border)` top border that signals section change
without weight. The hero drops the top border (it's the first thing).

Spacing scale is a power-of-1.25 progression mostly aligned to rem multiples:
`0.25rem`, `0.5rem`, `0.75rem`, `1rem`, `1.25rem`, `1.5rem`, `2rem`, `2.5rem`,
`3rem`, `4rem`, `5rem`, `6rem`. Components reach for the scale tokens, never
raw `px` values; spot-tuning lives only where the scale is the wrong instrument
(e.g. the 30px mode-toggle button size, the 10px header backdrop blur, the
60px sticky-header height).

The hero uses an asymmetric two-column split at `≥980px`:
`grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr)`. The left column
carries the manual copy (folio + h1 command + tagline + philosophy + CTAs +
install line); the right column carries the **terminal-panel readout** — a
fake `skills/` directory tree showing the first 8 featured skills as
`└─ skill-name`. Below `980px`, both columns stack.

Other grids use `repeat(auto-fill, minmax(<min>, 1fr))`:

- Featured skill grid: `minmax(290px, 1fr)`.

The featured grid uses `auto-fill` (not `auto-fit`) on purpose — empty cells
preserve the column rhythm at wide widths instead of letting cards stretch
unevenly.

## Elevation & Depth

Flat. The blueprint grid is the *only* ambient lighting.

The blueprint grid runs as a fixed `.bg-mesh` element behind every page:
two layered grid systems (32px fine teal lines + 128px major amber lines)
at very low alpha (4.5% / 3.5%), masked to a radial-gradient ellipse that
fades to transparent at ~92% radius. That's the entire ambient lighting
layer; no glow, no other gradient washes, no noise.

Cards earn a hairline `1px solid var(--color-border)` and **no shadow at
all** in dark mode (`--shadow-card: 0 0 0 transparent`). Hover thickens the
border to `--color-border-strong` and shifts the title to `--color-accent`,
nothing else. No lift, no glow, no scale. The brutalism is non-negotiable.

`--color-bg-elevated` (the slightly-lighter tier) signals elevation without
shadow — the hero terminal panel, the mode toggle, ghost-rect buttons, and
the search popover all use it. Vibrant mode is the sole exception: cards
gain a faint amber-tinted 1px shadow contour for room-scale demo presence.
Light mode drops shadow intensity proportionally; ink-on-paper doesn't want
the same depth signal as a glowing console.

The header is sticky (`top: 0`) with a 10px `backdrop-filter: blur(10px)`
and `background: color-mix(... 90% --color-bg ...)` so the brand mark and
mode toggle stay reachable while scrolling, without breaking the console
surface beneath.

## Shapes

Cut, not poured. The radius scale is deliberately small and brutalist:

- `sm: 2px` — chips, inline kbd, status pills, ghost-rect buttons.
- `md: 3px` — used internally for the search popover panel.
- `lg: 4px` — reserved; not currently consumed.
- `xl: 6px` — reserved; not currently consumed.
- `full: 999px` — pills only when the `.pill-round` modifier is applied
  (the default `.pill` is square — square pills are part of the brutalist
  brand).

This is squarer than ai-labs (which uses 2/3/5), much squarer than lfm
(2/4/8/12), and another universe from memopop's glass shapes (8/16/24).
The skill-card itself uses **zero radius** — that's the strongest
brand-defining shape decision.

Borders are 1px hairlines everywhere. Two-pixel borders only appear as the
left-rail on `.hero__philosophy` and `blockquote` (a teal accent rail), and
as the prose `.prose blockquote` left-rail.

## Components

### SkillCard (the defining card chrome)

A **zero-radius hairline-bordered card** with the skill's directory path in
mono `0.74rem` as the meta-line, a status pill on the same row, a JetBrains
Mono `1.04rem` title, a body lede capped at 220 chars (truncated with `…`),
and up to four chip tags in the footer above a dashed top border.

Hover thickens the border (`-strong`) and shifts the title to teal. No lift,
no shadow change, no scale. The whole card is a single anchor.

This is THE defining card affordance. Cards on this splash do not have
rounded corners. Period.

### Pill (status indicator)

Square corners (`rounded.sm`), JetBrains Mono `0.68rem` at `0.08em`
letter-spacing, uppercase. Tinted by `[data-status]` attribute so frontmatter
status values flow through directly:

- `data-status='Active' | 'Stable' | 'live'` — teal border + teal text + 10%
  teal fill. Primary status indicator; "this works."
- `data-status='Beta' | 'Iterating'` — magenta border + magenta text + 10%
  magenta fill. "Shipped but moving."
- `data-status='Alpha' | 'Experiment' | 'planned' | 'Draft'` — amber border +
  amber text + 10% amber fill. "Work in progress / be careful."
- (default — no `data-status`) — neutral hairline border + soft text + 4%
  text fill. Used for low-key meta or legacy status values.

Never put more than one status pill on a single card; the cross-product
signal collapses otherwise.

### Chip (tag indicator)

Used inside SkillCards for tag rows. `0.68rem` JetBrains Mono, dim color,
hairline border, `rounded.sm`. Wraps freely; capped at 4 visible tags per
card (overflow is silent — fewer is fine, more isn't shown). The chip
divider above is a `1px dashed var(--color-border)` — the only dashed border
in the whole design.

### Folio (section marker)

The `#01 · Featured`, `#02 · Recent` chapter mark that leads every section.
JetBrains Mono `0.74rem` at `0.18em` letter-spacing, uppercase, color
`--color-text-dim`. The leading `#XX` is supplied via `data-num="#01"` and
rendered with `::before { content: attr(data-num); color: var(--color-accent); }`.
The teal-tinted number is what makes a folio read as a folio rather than a
plain eyebrow — it's the manual's table-of-contents reference.

### Hero terminal panel

A right-column aside on the hero showing a fake `skills/` directory tree
listing the first 8 featured skills. Frame chrome:

- `--color-bg-elevated` background, `--color-border-strong` 1px border,
  `rounded.sm`, overflow hidden.
- Header strip with three colored dots (amber / magenta / teal — the brand
  spine in left-to-right order, mimicking macOS traffic-light buttons) and a
  `skills/` title in mono.
- List body with `└─ <skill-name>  <STATUS>` rows in JetBrains Mono `0.82rem`,
  `line-height: 1.9` for readable density.

Demonstrates the rollup mechanism above the fold and doubles as a
proof-of-life signal. Hidden from screen readers (`aria-hidden="true"`) — it's
illustrative, not the primary content.

### Hero install line

A small mono chip showing `$ ./sync-skills.sh ~/.claude/skills`. Same code
surface (`--color-bg-code`) as inline `<code>`, hairline border, `rounded.sm`,
`max-width: max-content` so it sizes to its contents and doesn't stretch.
The leading `$` is in `--color-accent` (teal) like the hero `$` prompt and
the brand mark `$_` — three places where the same prompt glyph is the same
color, on purpose.

### Mode toggle (three-button segmented control)

Inline-flex group of three icon buttons (moon / sun / star). Pressed state
fills the button with `--color-accent` (teal) and inverts text to
`--color-bg`. Persists choice to `localStorage` under
`lossless-skills-splash-mode`. The pre-paint inline script in `BaseLayout`
reads the persisted value and writes `<html data-mode="...">` before first
paint, preventing FOUC on mode-switched visits.

### Brand mark (header)

`$_` prompt in mono `--color-accent` (teal) + "Lossless Agent Skills"
wordmark in mono `0.95rem` `font-weight: 600`. On viewports `≤720px` the
wordmark collapses to the short tag "LAS" in `--color-text-dim`. Never
substitute a glyph icon — the `$_` IS the logo.

### Gradient text

A single-word gradient applied sparingly — currently only on
`lossless-agent-skills` in the hero h1. Background-clipped gradient flows
teal → amber → magenta (the brand spine in left-to-right order, matching the
terminal-panel dots). Never apply to whole phrases; the move dilutes if
reused.

### Background — blueprint grid

A fixed `.bg-mesh` element renders four layered linear gradients: 32px-pitch
1px-line teal verticals + horizontals at 4.5% alpha, and 128px-pitch (×4)
1px-line amber verticals + horizontals at 3.5% alpha. The whole layer is
masked with a radial-gradient ellipse `(black 40%, transparent 92%)` so the
grid is brightest at the center of the viewport and fades outward. Pure CSS;
no images.

## Imagery

All splash imagery is generated via Ideogram's v3 generate endpoint. The
frontmatter's `imagery:` block is the **complete locked recipe** — every
field there stays constant across every request. The two things that vary
per call are `prompt` (subject + composition) and `aspect_ratio` (one entry
from the four-format enum). Everything else — style reference, color palette,
style type, magic-prompt flag, negative prompt, seed, rendering speed,
empty-region content — is identical request-to-request.

### The locked channels (don't touch per request)

- **`style_reference_images`** — `public/ogimage__Lossless-Agent-Skills--Default.png`,
  uploaded on every request. The canonical aesthetic anchor: humanoid
  teenager robots at a gym in Wall-E illustration style, yellow tile floor,
  magenta gym wall, teal-glint horizon band cresting under a dark sky. Wall-E
  proportions (chunky cartoon body, dark visor eye-band, exposed yellow
  torso). If this file doesn't exist yet (first generation), seed it by
  running once with only `color_palette` + `style_type: AUTO` and save the
  PNG output here.
- **`color_palette.members`** — five weighted members. `console-bg` (#0a0e14)
  dominates at 0.45 so the dark terminal surface is the ground. Teal at 0.20
  is the primary accent (the cursor / prompt color); amber at 0.15 is the
  warm highlight; magenta at 0.10 is the reserved signal; slate-200 at 0.10
  keeps the subject from going stark white.
- **`style_type: AUTO`** — required when `style_reference_images` is uploaded;
  the v3 API rejects `DESIGN` / `REALISTIC` / `FICTION` in that combination.
  AUTO lets the reference image carry the aesthetic.
- **`magic_prompt: OFF`** — non-negotiable. Magic-prompt rewrites the prompt
  before generation; rewriting is the largest source of drift across
  "identical" requests.
- **`negative_prompt`** — short on purpose:
  `text, typography, lettering, logos, watermarks, central subject filling
  frame, photorealistic human faces, saturated, rainbow, vibrant, oversized
  subject, subject in top half`. The trailing `oversized subject` /
  `subject in top half` exclusions defend the SVG-overlay zone in tall
  aspect ratios.
- **`seed: 2048`** — fixed canonical seed for the skills splash family. Bump
  only when the visual canon itself shifts (rebrand, new reference image,
  palette redo).
- **`rendering_speed: QUALITY`** — for production assets. `TURBO` / `FLASH`
  are for prompt iteration only.
- **`empty_region_content`** — locked at the project level (not per-request)
  to `"dark gradient sky with faint teal glint at the horizon"`. Same sky
  in all four crops; otherwise the family drifts even with everything else
  identical.

### The variable channels (the only things you change)

- **`prompt`** — one sentence, ≤220 characters, two clauses:
  1. **Empty region first** — declare the top region as empty negative space
     and give it the locked `empty_region_content` (the teal-glint sky).
  2. **Subject second** — what the bottom 2/3 contains. Skills-splash subjects
     lean on the **robot-gym canon**: humanoid teenager robots at a gym in
     Wall-E illustration style, working out with barbells, dumbbells, bench-
     press rigs. **Never humans, never logos, never literal product UI
     screenshots.** Humanoid robots (clearly mechanical, not biological) are
     the only character class.

  **Conceptual thread:** the imagery is a visual metaphor for what the splash
  catalogs — *agents developing skills*. Robots literally "develop skills"
  at the gym by lifting weights and getting stronger; the AI agents reading
  this catalog develop skills the same way, one rep at a time. The
  metaphor is the family glue.

  Canonical subject themes (rotate across generations, not within a single
  family-of-four — for one set of four, use the **same prompt** with only
  `aspect_ratio` varying so the style_reference can anchor all four crops):

  - *a few humanoid teenager robots at a gym, pumping iron*
  - *three humanoid teenager robots overhead-pressing barbells in a row*
  - *humanoid teenager robots squatting and bench-pressing on yellow gym tile*
  - *humanoid teenager robots warming up with dumbbells along a magenta gym wall*
  - *a row of humanoid teenager robots spotting each other at a bench-press rig*

  The "**teenager**" modifier matters — it pushes proportions taller and
  lankier than Wall-E's smol cousin defaults; without it the robots come
  back chibi-scale. The number is left soft (`a few`, `a row of`) — Ideogram
  consistently returns 3-5 robots which matches the "a few" framing.

- **`aspect_ratio`** — pick from `imagery.aspect_ratios`:

  | Format key | Ideogram value | Use for |
  |---|---|---|
  | `banner_image` | `16x9` | OG / Twitter / Slack / generalized share |
  | `banner_image_tall` | `4x5` | **WhatsApp / iMessage (primary)** — close to 1x1, slightly taller |
  | `portrait_image` | `9x16` | Stories, Reels, TikTok, vertical feed |
  | `square_image` | `1x1` | Avatars, square unfurls, Discord embeds |

### Naming + preservation

Save canonical deliverables to `public/` as:

```
public/ogimage__Lossless-Agent-Skills--BannerImage.jpg       # 16x9 — OG / Twitter / Slack
public/ogimage__Lossless-Agent-Skills--BannerImageTall.jpg   # 4x5 — WhatsApp / iMessage (primary)
public/ogimage__Lossless-Agent-Skills--PortraitImage.jpg     # 9x16 — Stories / Reels / TikTok
public/ogimage__Lossless-Agent-Skills--SquareImage.jpg       # 1x1 — Avatars / square unfurls
```

Plus the `.png` style reference at
`public/ogimage__Lossless-Agent-Skills--Default.png` (re-uploaded on every
request as `style_reference_images`). The reference is not a deliverable —
it's the aesthetic anchor that keeps the four JPEGs above looking like family.

Per the `generate-consistent-og-images` skill's **preservation discipline**:

- Raw candidates from each run land in `.ideogram-candidates/<subject>-<aspect>-<timestamp>/` (dot-prefixed, outside `public/` so the Pages workflow doesn't deploy them).
- When replacing a canonical JPEG, move the old one to `.ogimage-archive/ogimage__Lossless-Agent-Skills--{Format}--{YYYY-MM-DD}.jpg` *before* writing the new one. The unfurler URL stays stable; old bytes survive in archive with a date stamp.

## Do's and Don'ts

- **Do** lead every section with a folio (`#01 · Featured`, `#02 · Recent`).
  The chapter-style numbering with the teal `#XX` prefix is the manual voice;
  sections without it don't read as part of the manual.
- **Do** keep JetBrains Mono as the dominant family for headlines AND meta.
  That's the defining type move; weakening it (e.g. swapping h1 to a sans
  display) collapses the brand into "another dark startup splash."
- **Do** use the SkillCard chrome (zero-radius hairline border, no shadow,
  hover thickens) on every card. Cards with rounded corners or shadows don't
  belong to the system; if you need a different chrome, push back on the
  requirement first.
- **Do** keep imagery on the robot-gym canon. The conceptual thread —
  *robots developing skills at the gym = agents developing skills via the
  catalog* — is the family glue. Subject variation is fine within that
  canon (different exercises, different rigs); subject *class* should stay
  humanoid teenager robots in Wall-E illustration style.
- **Do** persist the mode choice and resolve it pre-paint. Mode toggling
  must never FOUC; the inline pre-paint script in `BaseLayout` is mandatory.
- **Do** keep the `.bg-mesh` blueprint grid as the *only* ambient lighting
  layer. No radial mesh, no gradient washes, no noise — those belong to
  sibling splashes.
- **Do** match the three terminal-panel dot colors (amber / magenta / teal,
  left-to-right) to the gradient-text sweep direction. The visual rhyme
  between the dots and the gradient is the whole point of having both.

- **Don't** introduce a third typeface. JetBrains Mono + Inter is the
  contract; a serif or second sans dilutes the mono-as-display signal.
- **Don't** use mono for paragraph prose. Mono in paragraphs reads as code;
  long-form prose is Inter. Mono in headlines reads as command precisely
  *because* prose is sans.
- **Don't** hard-code color hex values in components. Every value must come
  from a semantic token (`var(--color-*)`); hard-coding breaks mode
  switching silently.
- **Don't** apply the `gradient-text` move to more than one or two words at
  a time. It's a hero accent on a single word in the h1; reusing it on
  phrases dilutes the move.
- **Don't** soften the SkillCard corners past `0` (zero radius). The brutalism
  is the divergence from sibling splashes; rounding it up drifts the brand
  back toward generic dark-tech-startup territory.
- **Don't** add a shadow to any card in dark mode. `--shadow-card: 0 0 0
  transparent` is intentional — depth comes from the elevated surface tier,
  not from glow.
- **Don't** add a second background layer behind the blueprint grid. The grid
  is the ambient ground; a second layer (mesh, wash, noise) breaks the console
  feel.
- **Don't** put humans, logos, or product screenshots in OG imagery.
  Humanoid robots are the only character class — they read as agents
  (mechanical, learning, on-purpose), not as people. A photoreal human face
  in a share preview collapses the metaphor.
- **Don't** vary `seed`, `magic_prompt`, `style_type`, `color_palette`,
  `style_reference_images`, OR `empty_region_content` per Ideogram request.
  Two channels vary (`prompt` and `aspect_ratio`); the rest are locked at
  the project level exactly so that variation looks like family, not chaos.
- **Don't** overwrite a canonical OG JPEG in place when re-running. Archive
  the previous bytes to `.ogimage-archive/ogimage__Lossless-Agent-Skills--{Format}--{YYYY-MM-DD}.jpg`
  first, then write the new pick to the canonical path. The unfurler URL
  stays stable; byte history is preserved.
- **Don't** put raw Ideogram candidates inside `public/`. The Pages workflow
  ships everything under `public/` verbatim — ~1.4 MB per PNG ships otherwise.
  Candidates live in `.ideogram-candidates/`, dot-prefixed, outside `public/`.
- **Don't** rebrand the `$_` mark to a glyph icon. The shell prompt IS the
  logo; replacing it with a generic icon erases the operator-manual posture
  in one move.
