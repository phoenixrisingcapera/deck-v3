---
version: alpha
name: Context Vigilance — Engineer's Clipboard, with the Information Just Out of Reach
description: A dark-default, mono-display "engineer's clipboard" aesthetic for the context-vigilance-kit splash. JetBrains Mono as the display face on Inter body, amber + sodium + lime brand spine, asymmetric hero with a Google/OpenAI-style "what context do you need?" search prompt as the primary action, hairline borders and a slowly drifting dot-grid background. Deliberately distinct from sibling Lossless splashes — operator-toned where lfm is bookish, datasheet where memopop is editorial, embodied-by-metaphor (a brain hovering above a Fallout-style delivery bot, surrounded by binary digits just out of reach) rather than abstract gradient-mesh AI-startup art.
colors:
  # Tier 1 — named, mode-invariant brand spine
  amber: "#fbbf24"
  amber-deep: "#b45309"
  amber-soft: "#fde68a"
  sodium: "#f97316"
  sodium-deep: "#9a3412"
  sodium-soft: "#fed7aa"
  lime: "#a3e635"
  lime-deep: "#4d7c0f"
  lime-soft: "#d9f99d"
  neon-amber: "#ffd60a"
  neon-sodium: "#ff7a1a"
  iris: "#818cf8"
  paper: "#f7f6f1"
  paper-soft: "#efece2"
  paper-deep: "#e2dfd1"
  ink: "#0a0c10"
  ink-soft: "#11141b"
  ink-deep: "#060709"
  charcoal: "#161a23"
  slate-700: "#2a2f3a"
  slate-600: "#3b414f"
  slate-500: "#5b6273"
  slate-400: "#8b91a3"
  slate-300: "#b4b9c7"
  slate-200: "#d4d8e0"
  slate-100: "#e8eaef"

  # Tier 2 semantic — DARK mode (default; "operator" / engineer's clipboard)
  dark-bg: "{colors.ink}"
  dark-bg-soft: "{colors.ink-soft}"
  dark-bg-elevated: "{colors.charcoal}"
  dark-bg-code: "{colors.ink-deep}"
  dark-text: "#e8eaef"
  dark-text-soft: "{colors.slate-200}"
  dark-text-dim: "{colors.slate-400}"
  dark-accent: "{colors.amber}"
  dark-accent-warm: "{colors.sodium}"
  dark-thread: "{colors.lime}"

  # Tier 2 semantic — LIGHT mode ("daylight")
  light-bg: "{colors.paper}"
  light-bg-soft: "{colors.paper-soft}"
  light-bg-elevated: "#fffefa"
  light-bg-code: "{colors.paper-deep}"
  light-text: "{colors.ink}"
  light-text-soft: "{colors.slate-700}"
  light-text-dim: "{colors.slate-500}"
  light-accent: "{colors.amber-deep}"
  light-accent-warm: "{colors.sodium-deep}"
  light-thread: "{colors.lime-deep}"

  # Tier 2 semantic — VIBRANT mode ("demo")
  vibrant-bg: "{colors.ink-deep}"
  vibrant-bg-soft: "#0a0a14"
  vibrant-bg-elevated: "#14122a"
  vibrant-text: "#fff8e8"
  vibrant-accent: "{colors.neon-amber}"
  vibrant-accent-warm: "{colors.neon-sodium}"
  vibrant-accent-hot: "{colors.iris}"
typography:
  hero-headline:
    fontFamily: JetBrains Mono
    fontSize: 3.4rem
    fontWeight: "600"
    lineHeight: "1.08"
    letterSpacing: "-0.035em"
  display-h1:
    fontFamily: JetBrains Mono
    fontSize: 2.6rem
    fontWeight: "600"
    lineHeight: "1.1"
    letterSpacing: "-0.03em"
  display-h2:
    fontFamily: JetBrains Mono
    fontSize: 1.85rem
    fontWeight: "500"
    lineHeight: "1.12"
    letterSpacing: "-0.025em"
  display-h3:
    fontFamily: JetBrains Mono
    fontSize: 1.15rem
    fontWeight: "600"
    lineHeight: "1.3"
    letterSpacing: "-0.015em"
  body-lg:
    fontFamily: Inter
    fontSize: 1.08rem
    fontWeight: "400"
    lineHeight: "1.65"
  body-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: "400"
    lineHeight: "1.6"
  body-sm:
    fontFamily: Inter
    fontSize: 0.92rem
    fontWeight: "400"
    lineHeight: "1.55"
  mono-md:
    fontFamily: JetBrains Mono
    fontSize: 0.92rem
    fontWeight: "400"
    lineHeight: "1.55"
  mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.78rem
    fontWeight: "500"
    letterSpacing: "0.04em"
  eyebrow-folio:
    fontFamily: JetBrains Mono
    fontSize: 0.72rem
    fontWeight: "500"
    letterSpacing: "0.18em"
rounded:
  sm: 2px
  md: 3px
  lg: 6px
  xl: 10px
  pill: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
  4xl: 96px
  container-padding: 24px
  section-margin: 64px
  card-gap: 16px
  grid-pitch: 28px
components:
  button-primary:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.ink}"
    typography: "{typography.mono-md}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  button-ghost:
    backgroundColor: "{colors.dark-bg-elevated}"
    textColor: "{colors.dark-text}"
    typography: "{typography.mono-md}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  matrix-cell:
    backgroundColor: "{colors.dark-bg-elevated}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
    accentRule: "2px solid {colors.dark-accent}"
  teaser-card:
    backgroundColor: "{colors.dark-bg-elevated}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  invite-card:
    backgroundColor: "{colors.dark-bg-elevated}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  pill:
    backgroundColor: "{colors.dark-bg-soft}"
    textColor: "{colors.dark-text-soft}"
    typography: "{typography.mono-sm}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  chip:
    backgroundColor: "{colors.dark-bg-code}"
    textColor: "{colors.dark-text-soft}"
    typography: "{typography.mono-sm}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  search-trigger:
    backgroundColor: "{colors.dark-bg-soft}"
    textColor: "{colors.dark-text-soft}"
    rounded: "{rounded.md}"
    padding: "5px 10px 5px 9px"
  search-hero:
    backgroundColor: "{colors.dark-bg-elevated}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "20px 16px 20px 32px"
    placeholder: "What context do you need?"
    placeholderFont: JetBrains Mono
    accentOnFocus: "{colors.dark-accent}"
---

## Overview

**Engineer's clipboard, with the information just out of reach.** Context Vigilance is a tool for engineers who have lived through coding agents that "almost" work — they've watched the agent guess because it didn't know the conventions, the prior decisions, the mistakes from last quarter. The splash needs to feel like *their tool*, not yet another AI-startup splash with neon gradients and floating UI screenshots.

The aesthetic resolves a tension at the heart of the practice: **the agent has the capability to act, but it lacks the context to act well.** Visually, that's our central metaphor — a brain hovering above a Fallout-style delivery bot, with binary digits floating around but out of reach. The bot has the body to do the work; it's missing the data it needs to do the work *right*. Context vigilance puts the data within reach.

Three deliberate moves separate this splash from its siblings:

- **Dark mode is the default ("operator" / "worked-in-the-night").** Light mode and vibrant mode are first-class, but the canonical entry point is near-black ink with amber highlighter accents. The way you encounter the kit matches the time of night you'd actually be wrestling with an agent's failures.
- **JetBrains Mono is the display face, not just the chip face.** The headlines themselves are monospaced. This is the move that most loudly signals "for engineers" before any copy is read. lfm/splash uses a serif (Newsreader); memopop and content-farm use a humanist sans (Inter). cvk goes the other direction: mono-as-display.
- **The hero search input is the primary CTA, styled as a prompt.** Instead of "Sign Up" or even a low-commitment CTA pair, the centerpiece of Act 1 is a Google/OpenAI-homepage-sized search input with placeholder text "What context do you need?", a blinking caret, and example chips below. The search is not a utility tucked into the header — it's the first thing the page asks you.

## Colors

The palette is rooted in a three-color *highlighter ink* spine: **amber for highlight/insight, sodium-orange for warm signal, lime-green for "live / stable / worked-on."** The neutrals are a slightly cool ink axis — near-black with a subtle blue cast — so dark mode reads like a terminal in a dim room rather than a marketing surface.

- **Amber (`#fbbf24`)** — the primary accent. Headlines emphasis, links, primary CTAs, the highlighter underlay (`.highlight`). In light mode this deepens to amber-deep (`#b45309`) for legibility against paper.
- **Sodium (`#f97316`)** — the warm secondary. Beta/Draft/idea-started status pills, the strikethrough mark on "code" in the hero claim, the warm accent slot.
- **Lime (`#a3e635`)** — the live / stable / worked-on signal. "From `<repo>`" tags use it; status pills for `worked-on` corpus entries use it; the moss equivalent in lfm's vocabulary.
- **Ink (`#0a0c10`)** — the canonical background in dark mode. Near-black with a faint blue cast, not pure black. Pure black flattens; this preserves a sense of depth.
- **Slate-100 / `#e8eaef`** — the canonical foreground in dark mode. Slightly warm off-white, not pure white.
- **Paper (`#f7f6f1`)** — the canonical background in light mode. Warm off-white that pairs with the amber accent without going antiseptic.

The three-mode contract:

- **Dark mode** — ink background + slate-100 text + amber accent + sodium warm + lime thread. The default.
- **Light mode** — paper background + ink text + amber-deep accent + sodium-deep warm + lime-deep thread. "Daylight."
- **Vibrant mode** — ink-deep background + cream text + neon-amber accent + neon-sodium warm + iris hot. Demo mode for screenshots and conferences.

All three modes use the same semantic-token names (`--color-bg`, `--color-text`, `--color-accent`, `--color-thread`); only the Tier-1 values rebound under `[data-mode='...']`. A pre-paint inline script in `BaseLayout` resolves the persisted choice from `localStorage.cvk-splash-mode` before any paint, eliminating FOUC.

## Typography

Two faces. Each does one job — and one of them does two.

- **JetBrains Mono (display + mono)** — the brand-defining move. Used for *all* headings (h1 through h4), the hero brand-line, the section folio numbering, the search input, code/path chips, status pills, eyebrows, and inline mono. Tracking is tightened progressively at larger sizes (`-0.035em` at h1, easing toward neutral by inline mono). Weight is held at 500–600 for headlines so mono-as-display reads as "engineered" rather than "brutalist." The contrast inside the same family — mono headlines, mono chips — is the voice.
- **Inter (sans body)** — geometric sans for body copy and UI labels. Stylistic sets `cv11` and `ss01` enabled site-wide for the humanist single-story `a` and tighter punctuation. Inter pairs with mono headlines without competing — when both faces share a similar geometric substrate, they read as a system rather than a clash.

The `folio` numbering primitive is the only typographic ornament: a small mono `§ 01` / `§ 02` / `§ 03` / `§ 04` marking the four narrative acts (Hook → Practice → Proof → Invitation). The number is rendered via `::before` on `data-num`, so the markup stays semantic.

## Layout

**Asymmetric hero.** Two columns at desktop widths: copy + the prominent hero search + CTAs in the left column (1.5fr), the live stats card in the right column (1fr, min 280px). At narrow widths the columns stack; the search input remains the visual anchor.

**Container widths:**

- `.container` — `max-width: 1180px`, the standard width for index, list pages, the hero
- `.container-narrow` — `max-width: 760px`, used on `/search`, `/corpus/<slug>`, and the 404 page

**The dot-grid background ornament** — a fixed-position `.bg-grid` element layers three soft radial-gradient mesh hues (amber + sodium + lime, at 6–10% opacity in dark mode) under a 28px-pitch dot grid drawn as a CSS `radial-gradient` pattern. The grid drifts one full pitch over 80 seconds via `@keyframes grid-drift`, animating only `background-position`. The drift is below the noticeable threshold for any individual second of viewing, but a returning reader senses the surface has shifted. Disabled under `prefers-reduced-motion`.

**Section rhythm** — sections are separated by `border-bottom: 1px solid var(--color-border)` and `padding: var(--space-16) 0`. The four narrative acts on the homepage each get their own `<section>` with this rhythm, which produces the "vertical scroll = vertical narrative" cadence the brief asks for.

## Elevation & Depth

**Hairline borders, restrained shadows.** No glassmorphism (except the sticky header's `backdrop-filter: blur(10px)`, which is a legibility need, not an aesthetic one). No glow shadows on cards. No floating Z-axis tricks.

- `--shadow-card: 0 18px 36px -22px rgba(0, 0, 0, 0.72)` — a tight diffused shadow well below the card. Reads as "clipboard on a desk," not "floating in space."
- `--shadow-elevated` — a slightly stronger version of the same shape for popovers (the search panel, mode toggle in pressed state).
- `--shadow-glow` — used only on the hero stats card edge and on focus rings of the hero search input. Soft amber wash, never neon.

The background's subtle drift is the only ambient motion. Hover states are restrained — color shifts and border-color shifts, occasionally a 1px Y-translate on cards, never scale transforms or shadow blooms.

## Shapes

**Squarer than typical.** The radius scale is the tightest of any Lossless splash — datasheet, not magazine.

- `--radius-sm: 2px` — chips, status pills' inner rectangles, hidden filter spans
- `--radius-md: 3px` — buttons, sort controls, search trigger, matrix cells, all card-class containers
- `--radius-lg: 6px` — used sparingly, reserved for the search popover and elevated panels
- `--radius-xl: 10px` — almost never used; held in reserve
- `--radius-pill: 9999px` — pills, the `from-tag` ribbon

Pills stay round (signaling "named state"); everything else stays squarer (signaling "this is a working surface").

**Hairlines do most of the boundary work.** Lists use `border-bottom: 1px dashed var(--color-border)` between items (the "manual punch-card" feel). Section dividers use solid 1px hairlines. The matrix cells get a 2px accent rule across their top edge, color-coded to the cognitive mode (`prep` → amber, `reflection` → sodium, `journey` → lime).

**The blinking caret.** The hero search input and the 404 page both render a `▎` glyph that pulses at 1.1s steps. The cadence is slow enough to read as "thoughtful" rather than "anxious." Only two surfaces use it; both are moments where the page is asking a question of the reader.

## Components

The component primitives shared across all Lossless splashes (`.pill`, `.eyebrow`, `.gradient-text`, `.from-tag`, `.chip`) take on the engineer's-clipboard treatment here:

- **`.folio`** — same numbering primitive as lfm, used on each of the four homepage acts and on the corpus / search pages. Renders as `<p class="folio" data-num="§ 01">…</p>` with the number as `::before`.
- **`.highlight`** — a brand-specific addition: `background-image: linear-gradient(180deg, transparent 58%, color-mix(in oklab, var(--color-accent) 38%, transparent) 58%)`. Wrap a phrase to give it the marker-through-the-line effect. Used sparingly on key claim phrases ("context is missing," "actual mess," "open specification").
- **Matrix cells** — the Act 2 6-cell grid uses `.matrix__cell--prep`, `.matrix__cell--reflection`, `.matrix__cell--journey` modifier classes. Each carries a 2px top accent rule in the mode color, the cognitive-mode label in the upper-right of the header, the kind name (`specs/`) as the cell title, a short blurb, and a real example pulled from the corpus at build time.
- **Long-tail row** — under the canonical six matrix cells, a dashed-bordered row counts the *non*-canonical kind folders actually present in the corpus (habits/, workflow/, plans/, journals/, etc.). Renders honestly — "in isolation each makes sense; we just haven't fit them all into the matrix yet" — with live counts.
- **Stats card** — the hero's right column. Lead stat (total files) at 2.6rem in mono, four secondary stats in a 2×2 grid below, color-coded: thread for `worked-on`, accent for `idea-started`, warm for `stub`. A 16px-pitch dot-grid texture is scoped to the card itself for visual rhyme with the page background.
- **SearchBox (three variants)** — `compact` for the header popover (icon trigger + `/` keycap), `full` for the `/search` page (autoFocus, full-width panel), and the cvk-specific **`hero` variant**: a tall mono-styled prompt input with a blinking amber caret, the placeholder "What context do you need?", and clickable example chips below ("splash", "agent context", "frontmatter", "search-by-default").
- **Sort controls** — chip group + direction toggle, mono-font, mode-aware. Direction label adapts: dates show "Newest first / Oldest first", titles show "A → Z / Z → A", repo names use the alpha labels.
- **Mode toggle** — three sun/moon/star buttons in a 3-segment pill group; pressed state gets the amber fill against ink text.

Variants follow the standard pattern (hover, focus-visible, pressed). Hover changes are restrained.

## Open Graph Imagery — Ideogram Brief

Four pieces our tool exposes: **Style notes** (prefix), **Body** (per-image "what"), **Brand alignment** (suffix), **Negative prompt**. Prefix, suffix, and negative are reused across every image; body changes per file.

### Style notes

```text
Right half of the canvas empty — uniform background, nothing on it. All subjects on the left half only. Mood: Fallout retro-mechanical, hand-crafted toy charm.
```

### Body

```text
A yellow Fallout-style delivery bot reaches toward a cluster of out-of-reach floating fragments (binary digits, document scraps, file tags). A glass dome above its head holds a small calm brain. Bot, dome, and fragments all on the left half. Right half stays empty.
```

### Brand alignment

```text
Accents: amber #fbbf24, sodium-orange #f97316, lime #a3e635. Background: warm cream with faint dots. Figures in deep ink #0a0c10.
```

### Negative prompt

```text
edge-to-edge composition, subject filling whole canvas, photorealistic human face, neon, glassmorphism.
```

## Do's and Don'ts

**Do:**

- Default to dark mode. Light mode is first-class; it isn't the default here.
- Use JetBrains Mono for headlines. The mono-as-display move is the single loudest brand signal.
- Use hairlines instead of shadows for boundaries. Hairlines + the dot-grid drift do most of the work shadows would in a glassy aesthetic.
- Keep card corners squarer than your instinct suggests. The datasheet feel comes from radii at 2–3px, not 6px+.
- Render the dot-grid background ornament on every page; let it drift slowly.
- Use the `folio` primitive for section numbering (`§ 01`, `§ 02`) to mark the four-act narrative.
- Use the `highlight` primitive on key claim phrases — not more than once or twice per section.
- Limit accent colors to the three-color spine: amber, sodium, lime.
- Pair mono headlines with sans body. The contrast inside-the-system is the voice.
- For OG imagery, lead with the **embodied metaphor** (bot + brain + out-of-reach context). Avoid abstract gradient-mesh art.

**Don't:**

- Don't add glassmorphism. No `backdrop-filter: blur` on cards. The sticky header is the only exception (legibility need).
- Don't add glow shadows on cards. The hero stats card has a *very* subtle amber wash; nothing else does.
- Don't introduce a fourth accent color. If a new signal needs distinction, use a Tier-1 hue from the existing palette (e.g., `slate-500` for muted secondary states).
- Don't center hero compositions or OG illustrations. The asymmetric layout is the splash's visual signature; the off-center OG composition is required for mobile-share legibility.
- Don't use `border-radius` greater than 6px on most surfaces. The datasheet feel breaks at 8px+.
- Don't use the cyan / electric-blue / royal-purple palette of competing context-engineering products. Even as accent. The whole point of this aesthetic is immediate differentiation in a noisy landscape.
- Don't use Newsreader or any serif. The serif slot belongs to lfm/splash; this splash deliberately doesn't use serif headlines.
- Don't generate OG images that look like generic AI-startup card art. The negative prompt above is opinionated for a reason; honor it.
- Don't render the agent figure in chrome or photorealistic 3D. The Fallout / Mr. Handy / hand-drawn lineage is the aesthetic, not "Boston Dynamics PR shoot."

---

**See also:**

- `splash/README.md` — implementation overview, local dev, deploy
- `splash/src/styles/theme.css` — the canonical Tier-1 + Tier-2 token implementation this DESIGN.md describes
- `lossless-monorepo/context-v/skills/maintain-splash-pages/SKILL.md` — the skill that codifies splash-page conventions across all Lossless repos, including the "diverge in shape, not just in hue" directive that produced this aesthetic
- `ai-labs/context-v/plans/Context-Vigilance-Splash-Page-Narrative.md` — the four-act narrative brief this splash implements
