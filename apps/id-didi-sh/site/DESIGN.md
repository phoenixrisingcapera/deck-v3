---
version: alpha
name: didi.sh — Site
description: >-
  Design system for didi.sh — the public landing page, served by Vercel
  at the apex domain. Shares one design system with splash/ (the developer
  surface on GitHub Pages) by deliberate intent, currently by file copy
  rather than shared import. Three-mode contract
  (dark-default / light / vibrant) with a verdigris-copper-teal brand
  spine — the currency-engraving palette — over a green-black vault
  axis, Space Grotesk display over IBM Plex Sans and Mono, and a
  credential posture: the identity service dresses like an identity
  document. Guilloche rosette ornament, stamp chrome for statuses,
  mono-forward data fields, terse datasheet voice. Tokens mirror the
  CSS custom properties in src/styles/theme.css — that file remains
  the runtime source of truth; this DESIGN.md is the human- and
  agent-readable contract.

# ── Tier-1 raw values — mode-invariant ─────────────────────────────────
# These are the primitives, declared once on :root. Semantic tokens
# (below) map onto these and rebind per <html data-mode="...">. The
# DARK bindings are the defaults — dark is the vault, and the vault is
# where this service lives. Light and vibrant live under modes: below.
colors:
  # ── Brand spine — the intaglio inks ─────────────────────────────────
  # Currency engraving, not a wordmark gradient. Verdigris is the
  # oxidized-copper green of banknote ink; copper is the plate it was
  # struck from; teal carries the security thread.
  verdigris: "#4ecf95"
  verdigris-deep: "#1f9a63"
  verdigris-soft: "#b5eed3"
  copper: "#d29a62"
  copper-deep: "#a86f3d"
  copper-soft: "#eed3b2"
  teal: "#4fbfae"
  teal-deep: "#2a7f74"
  teal-soft: "#b8e8e1"

  # ── Signal hues — off-spine, status and mode-specific roles ─────────
  thread: "#55e0d2"        # the security thread woven through the note
  uv: "#9d7bff"            # fluoresces under the vibrant lamp
  uv-soft: "#c9b3ff"
  amber: "#ffb547"         # warm warning

  # ── Editorial neutrals — the vault-ink axis ─────────────────────────
  # Green-black, not blue-black. This is the single most load-bearing
  # decision separating didi.sh from its sibling splashes.
  vault-deep: "#060a08"
  vault: "#0b110e"
  vault-soft: "#121a16"
  moss-800: "#1a2620"
  sage-700: "#33443c"
  sage-500: "#5c7268"
  sage-400: "#7a9186"
  sage-300: "#9db1a7"
  sage-200: "#c2d2c9"
  sage-100: "#e0eae4"
  paper: "#f3f6f2"
  paper-soft: "#e9efe8"
  paper-deep: "#dbe5da"

  # ── Semantic — DARK-mode bindings (the defaults) ────────────────────
  # When data-mode="dark" (or unset), these are the active values.
  # See modes: below for light / vibrant overrides.
  bg: "{colors.vault-deep}"
  bg-soft: "{colors.vault}"
  bg-elevated: "{colors.moss-800}"
  bg-card: "rgba(18, 26, 22, 0.82)"
  bg-code: "#040705"

  text: "#ecf3ee"
  text-soft: "{colors.sage-200}"
  text-dim: "{colors.sage-400}"
  text-dimmer: "#64796e"
  text-faint: "#465850"

  accent: "{colors.verdigris}"
  accent-soft: "{colors.verdigris-soft}"
  accent-warm: "{colors.copper}"
  accent-hot: "{colors.verdigris-deep}"

  thread-semantic: "{colors.thread}"
  thread-soft: "#aef0e9"

  border: "rgba(78, 207, 149, 0.14)"
  border-strong: "rgba(78, 207, 149, 0.32)"
  border-accent: "rgba(78, 207, 149, 0.58)"

typography:
  # Three families. Space Grotesk does engraved-caps headline duty,
  # IBM Plex Sans is the institutional document body, and IBM Plex Mono
  # is the data field on the credential. The mono is not decorative —
  # it is what makes key IDs, JWKS paths, and cascade records legible.
  display:
    fontFamily: Space Grotesk
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.015em"
  sans:
    fontFamily: IBM Plex Sans
    fontWeight: 400
    fontSize: 16px
    lineHeight: 1.6
  mono:
    fontFamily: IBM Plex Mono
  label-eyebrow:
    fontFamily: IBM Plex Mono
    fontSize: 0.72rem
    letterSpacing: "0.22em"
    textTransform: uppercase
  label-folio:
    fontFamily: IBM Plex Mono
    fontSize: 0.72rem
    letterSpacing: "0.18em"
    textTransform: uppercase
  label-pill:
    fontFamily: IBM Plex Mono
    fontSize: 0.7rem
    letterSpacing: "0.06em"
  label-stamp:
    fontFamily: IBM Plex Mono
    fontSize: 0.66rem
    fontWeight: 600
    letterSpacing: "0.16em"
    textTransform: uppercase
  label-version:
    fontFamily: IBM Plex Mono
    fontSize: 0.66rem
    letterSpacing: "0.04em"

rounded:
  # Documents are square. Passports, banknotes, and ID cards have
  # hard corners; only the stamps and status pills are round.
  sm: 2px      # chip, ver-chip, from-tag, stamp, folio chip
  md: 3px      # btn
  lg: 5px
  xl: 8px
  pill: 999px  # status pills

spacing:
  base: 1rem
  "1": 0.25rem
  "2": 0.5rem
  "3": 0.75rem
  "4": 1rem
  "5": 1.25rem
  "6": 1.5rem      # container gutter
  "8": 2rem
  "10": 2.5rem
  "12": 3rem
  "16": 4rem
  "20": 5rem
  "24": 6rem

  # Layout-named tokens
  container-max: 1180px
  container-narrow-max: 760px
  container-padding: 24px        # {spacing.6}
  guilloche-pitch: 11px          # engraved ring spacing (--guilloche-pitch)

motion:
  transition-fast: "160ms ease"
  transition-mid: "320ms ease"
  reduced-motion: "all transitions and animations disabled under prefers-reduced-motion"

components:
  # ── Pill (status indicator) ───────────────────────────────────────────
  pill:
    backgroundColor: "color-mix(in oklab, {colors.text} 4%, transparent)"
    textColor: "{colors.text-soft}"
    typography: "{typography.label-pill}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
    border: "1px solid {colors.border-strong}"
  pill-live:
    # data-status: Active | Stable | live | Implementing
    textColor: "{colors.thread-semantic}"
    backgroundColor: "color-mix(in oklab, {colors.thread-semantic} 12%, transparent)"
    border: "1px solid color-mix(in oklab, {colors.thread-semantic} 50%, transparent)"
  pill-beta:
    textColor: "{colors.accent}"
    backgroundColor: "color-mix(in oklab, {colors.accent} 12%, transparent)"
    border: "1px solid color-mix(in oklab, {colors.accent} 50%, transparent)"
  pill-alpha:
    # data-status: Alpha | Experiment | planned | Draft
    textColor: "{colors.accent-warm}"
    backgroundColor: "color-mix(in oklab, {colors.accent-warm} 12%, transparent)"
    border: "1px solid color-mix(in oklab, {colors.accent-warm} 50%, transparent)"

  # ── Stamp — the credential posture's signature chrome ─────────────────
  stamp:
    border: "2px double currentColor"
    rounded: "{rounded.sm}"
    typography: "{typography.label-stamp}"
    padding: "3px 10px"
    textColor: "{colors.thread-semantic}"
    backgroundColor: "color-mix(in oklab, currentColor 6%, transparent)"
    transform: "rotate(-2deg)"
    inks: "data-ink=copper | accent | dim rebind currentColor"

  # ── from-tag (provenance marker, with a filled dot) ───────────────────
  from-tag:
    textColor: "{colors.thread-semantic}"
    backgroundColor: "color-mix(in oklab, {colors.thread-semantic} 12%, transparent)"
    border: "1px solid color-mix(in oklab, {colors.thread-semantic} 35%, transparent)"
    rounded: "{rounded.sm}"
    padding: "3px 9px"
    ornament: "6px filled circle in thread, via ::before"

  # ── chip (inline code / literal) ──────────────────────────────────────
  chip:
    backgroundColor: "{colors.bg-code}"
    border: "1px solid {colors.border}"
    textColor: "{colors.text-soft}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
    fontSize: "0.82em"

  # ── ver-chip (semver badge) ───────────────────────────────────────────
  ver-chip:
    textColor: "{colors.accent}"
    border: "1px solid color-mix(in oklab, {colors.accent} 36%, transparent)"
    backgroundColor: "color-mix(in oklab, {colors.accent} 8%, transparent)"
    typography: "{typography.label-version}"
    rounded: "{rounded.sm}"
    padding: "1px 6px"

  # ── folio (section marker: "SEC.02 · THE SERVICES") ───────────────────
  folio:
    typography: "{typography.label-folio}"
    textColor: "{colors.text-dim}"
    numberChip:
      content: "attr(data-num)"
      textColor: "{colors.accent}"
      border: "1px solid {colors.border-accent}"
      backgroundColor: "color-mix(in oklab, {colors.accent} 8%, transparent)"
      rounded: "{rounded.sm}"
      padding: "1px 6px"

  # ── btn ───────────────────────────────────────────────────────────────
  btn:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text}"
    border: "1px solid {colors.border-strong}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
    fontFamily: IBM Plex Sans
    fontSize: 0.92rem
    fontWeight: 600
    hover: "border-color -> {colors.accent}"
  btn-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    border: "1px solid {colors.accent}"
    hover: "background + border -> {colors.accent-soft}"

  # ── gradient-text ─────────────────────────────────────────────────────
  gradient-text:
    background: "{gradients.thread}"
    clip: text

gradients:
  # The security thread, rendered as a 110-degree sweep. Rebinds per mode.
  thread: "linear-gradient(110deg, {colors.verdigris} 0%, {colors.teal} 48%, {colors.copper} 100%)"

# ─── modes: extension ──────────────────────────────────────────────────
# Off-spec extension (Stitch spec accepts unknown top-level keys). Each
# mode rebinds the semantic tokens above; tier-1 values stay constant.
# The data-mode attribute on <html> drives this. BaseLayout.astro ships
# data-mode="dark" in the markup and its pre-paint inline script reads
# `id-didi-sh-splash-mode` from localStorage, applying the stored choice
# before first paint to avoid FOUC.
modes:
  dark:
    # Default. The semantic bindings in colors: above ARE the dark
    # bindings. Listed here for completeness.
    label: "the vault"
    posture: "engraved verdigris + copper on deep green-black; banknote intaglio"
    color-scheme: dark
    bg: "{colors.vault-deep}"
    bg-soft: "{colors.vault}"
    bg-elevated: "{colors.moss-800}"
    bg-card: "rgba(18, 26, 22, 0.82)"
    text: "#ecf3ee"
    accent: "{colors.verdigris}"
    accent-warm: "{colors.copper}"
    thread-semantic: "{colors.thread}"
    gradient-thread: "linear-gradient(110deg, {colors.verdigris} 0%, {colors.teal} 48%, {colors.copper} 100%)"
  light:
    label: "security paper"
    posture: "pale green-white stock, engraved ink"
    color-scheme: light
    bg: "{colors.paper}"
    bg-soft: "{colors.paper-soft}"
    bg-elevated: "#ffffff"
    bg-card: "rgba(255, 255, 255, 0.92)"
    text: "#14201a"
    text-soft: "{colors.sage-700}"
    text-dim: "{colors.sage-500}"
    accent: "{colors.verdigris-deep}"
    accent-soft: "#167a4d"
    accent-warm: "{colors.copper-deep}"
    accent-hot: "{colors.verdigris}"
    thread-semantic: "{colors.teal-deep}"
    thread-soft: "#58a89d"
    border: "rgba(20, 32, 26, 0.12)"
    border-strong: "rgba(20, 32, 26, 0.24)"
    border-accent: "rgba(31, 154, 99, 0.42)"
    gradient-thread: "linear-gradient(110deg, {colors.verdigris-deep} 0%, {colors.teal-deep} 48%, {colors.copper-deep} 100%)"
  vibrant:
    label: "UV lamp"
    posture: >-
      the blacklight check — hidden security features fluoresce violet
      while the verdigris thread stays lit. DARK-BASED, per the
      three-mode contract: the surface is near-black violet, never paper.
    color-scheme: dark
    bg: "#07060f"
    bg-soft: "#0c0a17"
    bg-elevated: "#17132a"
    bg-card: "rgba(20, 16, 40, 0.80)"
    bg-code: "#050410"
    text: "#f0ecfb"
    text-soft: "#cfc6e8"
    text-dim: "#9187b3"
    text-dimmer: "#6d6390"
    text-faint: "#4e4570"
    accent: "{colors.uv}"
    accent-soft: "{colors.uv-soft}"
    accent-warm: "{colors.thread}"
    accent-hot: "#7e54f0"
    thread-semantic: "#55f0a6"
    thread-soft: "#b2f9d4"
    border: "rgba(157, 123, 255, 0.18)"
    border-strong: "rgba(157, 123, 255, 0.38)"
    border-accent: "rgba(157, 123, 255, 0.62)"
    gradient-thread: "linear-gradient(110deg, {colors.uv} 0%, #55f0a6 55%, {colors.thread} 100%)"

# ─── ornament: extension ───────────────────────────────────────────────
# The fixed `.bg-mesh` element painted behind every page. Three radial
# mesh gradients per mode, plus TWO guilloche rosettes — the engraved
# concentric rings that banknote and passport corners carry. Pure CSS:
# repeating-radial-gradient at hairline pitch, masked to fade out.
# This is the didi.sh signature ornament; it is not a dot grid.
ornament:
  mesh:
    type: triple-radial-gradient
    dark: "verdigris-deep 16% / teal-deep 16% / copper-deep 12%"
    light: "verdigris 7% / teal 7% / copper 6%"
    vibrant: "uv 22% / #55f0a6 14% / #7e54f0 22%"
  guilloche:
    type: repeating-radial-gradient
    pitch: "11px (--guilloche-pitch)"
    rosette-upper-right:
      origin: "86% 6%"
      ink: "{colors.accent} at 30%"
      pitch-multiplier: 1
      mask: "radial fade — opaque to 12%, transparent by 38%"
      opacity: { dark: 0.16, light: 0.12, vibrant: 0.24 }
    rosette-lower-left:
      origin: "6% 96%"
      ink: "{colors.accent-warm} at 30%"
      pitch-multiplier: 1.4
      mask: "radial fade — opaque to 10%, transparent by 34%"
      opacity: { dark: 0.13, light: 0.10, vibrant: 0.20 }
    note: >-
      The two rosettes use DIFFERENT pitches (1x and 1.4x) on purpose.
      Matched pitch reads as a tiled pattern; mismatched pitch reads as
      two separately engraved plates, which is the intended effect.

# ─── imagery: extension — Ideogram v3 generate recipe ──────────────────
# Project-specific extension (outside the Stitch standard groups). Spec-
# compliant consumers preserve unknown top-level keys, so this is safe
# to keep here as the single source of truth for image generation.
#
# The contract: every Ideogram request for an id-didi-sh OG asset uses
# the values below for ALL fields. The only per-request variables are:
#   - `prompt`           — subject + composition (see imagery.prompt + imagery.subject_canon)
#   - `aspect_ratio`     — one of imagery.aspect_ratios
#   - `num_images`       — optional, defaults to 4 (lets us pick a winner)
# Anything else is locked. This is what produces a coherent visual
# family across banner / banner_tall / portrait / square.
#
# Aesthetic family — deliberately related to the context-vigilance-kit
# splash but distinct: same comic-ink crosshatch language, but with
# copper/verdigris as the pop colors (vs. the context-vigilance sienna).
# This signals "same family of Lossless illustrative imagery" while
# preserving didi.sh's credential/vault brand spine.
imagery:
  provider: ideogram
  endpoint: POST https://api.ideogram.ai/v1/ideogram-v3/generate
  content_type: multipart/form-data

  # ── Locked defaults — DO NOT vary per request ───────────────────────
  defaults:
    style_type: AUTO              # required when style_reference_images is uploaded
                                  # (v3 API rejects DESIGN / REALISTIC / FICTION with
                                  # a style reference). AUTO lets the reference image
                                  # drive aesthetic, which is what we want.
    magic_prompt: OFF             # non-negotiable — prompt-rewriter is the #1
                                  # source of drift across "identical" requests.
    rendering_speed: QUALITY      # use TURBO only when iterating prompts.
    seed: 20260706                # canonical seed — reads as the ISO date of the
                                  # repo's first commit ("scaffold(id-didi-sh): the
                                  # identity plane gets its home").
                                  # Bump only when the visual canon itself shifts.
    num_images: 4                 # generate four candidates per run so we can pick
                                  # a winner without burning tokens on a retry.

  # ── Locked negative prompt — skill canonical (~12 tokens) ──────────
  # Per the generate-consistent-og-images skill: short on purpose,
  # each token competes with the positive prompt for attention. The
  # last block (saturated / rainbow / vibrant / oversized subject /
  # subject in top half) is anti-failure-mode — "subject in top half"
  # specifically defends the SVG overlay zone in tall aspect ratios,
  # paired with the positive-prompt empty-region declaration.
  negative_prompt: >-
    text, typography, lettering, sign, plaque, banner, poster, label,
    logos, watermarks, central subject filling frame, photorealistic
    human faces, saturated, rainbow, vibrant, oversized subject,
    subject in top half

  # ── Prompt convention — skill canonical empty-region-first pattern ──
  # Pattern: "Top 1/3 of frame is empty negative space, dark guilloche-
  # etched sky. Bottom 2/3 contains {short subject noun phrase}."
  #
  # Empty-region-first framing is the load-bearing rule. Without it,
  # the subject expands to fill the canvas. Per the skill: "empty space
  # won't be left as residue; it has to be declared, named, and given
  # content."
  #
  # Forbidden in prompts (already encoded via style_reference and
  # color_palette — repeating dilutes attention budget):
  #   - color words ("copper", "verdigris", brand colors)
  #   - texture descriptors ("guilloche", "engraved", "intaglio")
  #   - aesthetic adjectives
  #   - brand names
  #   - any mention of text, writing, labels (negation primes the
  #     concept — text encoders don't process "no X" correctly)
  prompt:
    pattern: "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains {subject}."
    max_chars_recommended: 220

  # ── Locked color palette — id-didi-sh credential brand, weighted ───
  # Weighted for a near-monochrome vault illustration with warm gold/
  # copper as the dominant pop (the safety-deposit contents) and cool
  # verdigris/teal as secondary accents (the aged-brass vault hardware,
  # the security thread). vault-deep dominates so the canvas defaults
  # to the dark void; paper carries linework highlights (diamond
  # sparkle, engraved detail). Sum of weights does not need to equal 1;
  # Ideogram interprets them as relative emphasis.
  color_palette:
    members:
      - { color_hex: "#060a08", color_weight: 0.40 }   # vault-deep (void background)
      - { color_hex: "#d29a62", color_weight: 0.25 }   # copper (gold/brass pop — coins, box, key)
      - { color_hex: "#f3f6f2", color_weight: 0.10 }   # paper (linework highlights, diamond sparkle)
      - { color_hex: "#4ecf95", color_weight: 0.15 }   # verdigris (aged-brass patina accent)
      - { color_hex: "#4fbfae", color_weight: 0.10 }   # teal (security-thread accent)

  # ── Locked style reference — uploaded as style_reference_images ─────
  # This is the strongest consistency signal in the v3 API. Every
  # request uploads this file; texture, lighting, ink density, and
  # crosshatch language are inherited from it.
  #
  # Bootstrapped 2026-07-07: the context-vigilance-kit reference image
  # (a text-heavy "Keep Calm" poster) contaminated every candidate with
  # garbled pseudo-text banners — style_reference_images is the
  # strongest signal in the v3 API and overpowered the negative_prompt.
  # Re-ran with NO style reference (color_palette + prompt only) and
  # picked the winner below as id-didi-sh's own self-anchored reference.
  style_reference:
    path: public/ogimage__Id-Didi-Sh--Default.jpg
    mime: image/jpeg

  # ── Aspect ratio enum — pick one per request ────────────────────────
  # Maps Lossless format names to Ideogram's allowed values. The
  # Lossless default tall (banner_tall = 3x4) is the most important
  # variant — iMessage / WhatsApp chat previews are the primary share
  # surface per the open-graph-share-seo-geo skill.
  aspect_ratios:
    banner: 16x9                  # OG / Twitter / Slack / generic share
    portrait: 4x5                 # LinkedIn portrait, Instagram feed
    portrait_tall: 9x16           # Stories, Reels, TikTok
    square: 1x1                   # avatars, square unfurls, fallbacks
    banner_tall: 3x4              # WhatsApp / iMessage previews (default tall)
    banner_tall_max: 2x3          # dramatic-tall variant; use sparingly

  # ── Subject canon — the agreed visual subject for id-didi-sh ─────
  # The "safety deposit box" metaphor for the didi.sh credential:
  #   - The vault = didi.sh, the identity service.
  #   - The safety deposit box = the didi_session credential.
  #   - The gold coins and diamonds = the identity/account being
  #     protected — the thing of value the vault safeguards.
  #   - The key still in the lock = the one credential that opens it,
  #     shared across all three consuming services.
  #
  # This is the *only* subject family used for id-didi-sh OG imagery
  # in the current canon. Per-format crops focus on different parts of
  # the same scene so the family reads as one visual story across
  # banner / banner_tall / portrait / square.
  subject_canon:
    metaphor: "Identity as the contents of a safety deposit box — the vault protects it, three consuming services borrow it."
    era: "Bank-vault aesthetic — brass safety deposit boxes, engraved vault door, banknote-intaglio linework."
    canonical_subject: "an open brass safety deposit box overflowing with gold coins and loose diamonds, set into a vault wall lined with rows of matching deposit boxes, a key in the lock"
    per_format_focus:
      banner: "Wide scene — vault wall with rows of deposit boxes, one open box in foreground spilling gold coins and diamonds, key in the lock."
      banner_tall: "Vertical focus — a single open deposit box dominates the bottom 2/3, gold coins and diamonds cascading out, a key hanging from the lock, vault wall implied at the edges."
      banner_tall_max: "Same as banner_tall but more dramatic vertical — a taller vault wall visible above, the single open box more centered."
      portrait: "Close-up on the open box — coins and diamonds in sharp detail, brass box edges, key still in the lock."
      portrait_tall: "Stacked composition — a row of vault boxes at top thinning down to one open box at the bottom with jewels."
      square: "Tight crop — one open deposit box with gold and diamonds, one neighboring box visible at the edge."

  # ── Prompt convention — the ONLY free-text per request ─────────────
  # Constraints documented in the Imagery prose section below. The
  # pattern follows the empirical empty-space-first structure from the
  # generate-consistent-og-images skill (subject-first prompts produce
  # subjects that swallow the overlay zone). Two clauses separated by
  # a period:
  #   1. Top region: declared as empty negative space with concrete
  #      content (a "dark guilloche-etched sky") — the model renders it.
  #   2. Bottom region: contains the actual subject from subject_canon.
  # Explicit numeric proportions ("1/3", "2/3"), never soft terms.
  prompt:
    pattern: "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains {subject_from_subject_canon}."
    example_banner_tall: "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains an open brass safety deposit box overflowing with gold coins and loose diamonds, a key hanging from the lock, a vault wall of matching boxes at the edges."
    example_banner: "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains a vault wall lined with rows of brass deposit boxes, one open box in the foreground spilling gold coins and diamonds, a key in the lock."
    example_square: "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains an open brass safety deposit box overflowing with gold coins and loose diamonds, one neighboring vault box visible at the edge."
    max_chars_recommended: 220
    forbid:
      # Vocabulary that belongs in tokens, NOT in the prompt:
      - brand names ("didi.sh", "Lossless")
      - color names ("copper", "verdigris", "teal", "dark", "warm")
      - aesthetic adjectives ("comic-style", "vibrant-minimal", "credential-posture")
      - texture descriptors ("crosshatch", "ink", "engraved", "guilloche", "monochrome")
      # All of the above are already locked via style_reference_images,
      # color_palette, and style_type. Repeating them in the prompt
      # only dilutes the model's attention budget for the actual subject.

  # ── Preservation discipline — paths the generation flow uses ───────
  candidate_archive: .ideogram-candidates/    # one timestamped subdir per run
  canonical_archive: .ogimage-archive/        # date-suffixed copies of replaced canonicals
  output_dir: public/                          # canonical JPEGs live here
  naming_convention: "ogimage__Id-Didi-Sh--{Format-Or-Variant}.{ext}"
---

# didi.sh — Design System

> The runtime source of truth is `src/styles/theme.css` (Tier-1 raw values + Tier-2 semantic bindings under each `:root[data-mode='...']`).
> The pre-paint resolver lives in `src/layouts/BaseLayout.astro`'s inline script (`localStorage.getItem('id-didi-sh-splash-mode')`).
> This document is the **human- and agent-readable** contract that explains the system's intent. Keep the two in sync when either changes.

## Brand & Style

didi.sh is the identity plane for the Lossless venture-tooling family — one credential across three consuming services: **MemoPop AI** (investment-memo orchestration), **DidiDecks AI** (code-first slide decks), and **Augment It** (AI data augmentation). The splash exists to make the credential-posture pitch — *one login, three doors, no passwords ever* — legible to an invited visitor before they open the repo, and to surface the changelog and `context-v/` alongside it.

The aesthetic is **the identity document itself.** Where memopop centers a headline and augment-it leads with a module-federation manifest grid, didi.sh dresses like the thing it issues: a banknote, a passport page, a specimen ID card. This is not decoration — it is the argument. A service whose entire value proposition is *trustworthy credentials* should look engraved, not launched.

Tone calibration:

- **Institutional, not startup.** Terse datasheet voice. Section markers render as document folios (`SEC.02 · THE SERVICES`). Data — key IDs, JWKS paths, API routes, cascade records — always sets in mono, because on a credential the data fields *are* the content.
- **Engraved, not glowing.** The brand spine is verdigris, copper, and security-teal: the currency-engraving palette, oxidized-copper green against the plate it was struck from. Surfaces sit on a **green-black vault axis**, not the blue-black most dark themes default to. That single choice does most of the work distinguishing didi.sh from its siblings.
- **Three modes, dark first.** The default is **dark** ("the vault") — engraved verdigris and copper on deep green-black, banknote intaglio. Light ("security paper") flips to pale green-white stock with engraved ink and verdigris-deep as primary. Vibrant ("UV lamp") is the blacklight check: hidden features fluoresce violet while the verdigris thread stays lit.

Where the splash departs from sibling Lossless splashes is **shape and ornament, not just hue.** Radii are near-square (2–8px) because documents have hard corners. Statuses wear **stamp chrome** — double-ruled borders, uppercase mono, a two-degree rotation, as if inked by hand. And the background ornament is a pair of **guilloche rosettes**: the fine concentric ring engravings that banknote corners carry, rendered in pure CSS at an 11px hairline pitch.

## Colors

The palette is rooted in two axes: a **brand spine** drawn from currency engraving, and a **vault-ink ladder** (vault-deep → sage → paper) the modes pivot through.

### Brand spine (mode-invariant)

Unlike its siblings, didi.sh's spine does not derive from a wordmark gradient — it derives from a *material*. Intaglio printing, oxidized copper plate, and the security thread woven through the paper.

- **Verdigris** — `verdigris-deep #1f9a63` / `verdigris #4ecf95` / `verdigris-soft #b5eed3`. The primary. `verdigris` is `--color-accent` in dark mode; `verdigris-deep` takes over in light mode, where the bright green would not hold contrast on paper.
- **Copper** — `copper-deep #a86f3d` / `copper #d29a62` / `copper-soft #eed3b2`. The `accent-warm` — the plate under the ink. Carries the lower-left guilloche rosette, the `Alpha`/`Draft` status pills, and the warm terminus of the thread gradient.
- **Teal** — `teal-deep #2a7f74` / `teal #4fbfae` / `teal-soft #b8e8e1`. The midpoint of `--gradient-thread`, and the light-mode thread color.

### Signal hues (off-spine; status and mode-specific roles)

- **Thread `#55e0d2`** — the security thread. Used on `pill[data-status='Active'|'Stable'|'live'|'Implementing']`, the `from-tag` provenance marker, and the default `.stamp` ink. Deliberately off-spine so it reads as "system-state" rather than "brand."
- **UV `#9d7bff`** / **UV-soft `#c9b3ff`** — the fluorescing inks. These appear **in vibrant mode only**, where they become `--color-accent`. This is the whole conceit of vibrant: under the lamp, the features you cannot normally see light up.
- **Amber `#ffb547`** — warm warning.

### Editorial neutrals (the vault-ink axis)

A thirteen-step ramp from `vault-deep #060a08` to `paper-deep #dbe5da`. Dark mode draws its surfaces from the bottom (vault-deep → vault → vault-soft → moss-800); light mode draws from the top (paper-deep → paper-soft → paper → white). The sage-700/500/400/300/200/100 mids serve as text colors across modes — sage-700 is soft text in light mode, sage-200 in dark.

**The green-black is load-bearing.** `#060a08` is not `#000000` and not a blue-tinted `#0a0712`. If a surface is ever hard-coded to a neutral black, it will read as a hole punched in the vault wall. Always reference `--color-bg`.

### Semantic bindings (the Tier-2 layer)

Every component references **semantic tokens** (`--color-bg`, `--color-text`, `--color-accent`, `--color-thread`), never Tier-1 raw values directly. The semantic-to-raw mapping rebinds when the user changes mode. The dark bindings are in the frontmatter's `colors:` block; light and vibrant overrides live in `modes:`. The single largest "do" of the system is **always reference the semantic token** — a component that hard-codes a hex will only look right in one of three modes.

### Status pills and stamps

- `Active` / `Stable` / `live` / `Implementing` → thread
- `Beta` → accent (verdigris / verdigris-deep / uv)
- `Alpha` / `Experiment` / `planned` / `Draft` → accent-warm (copper / copper-deep / thread)

Each pill is ~12% fill against a ~50%-alpha border in its own accent, so pills coexist with the vault surface without out-shouting primary CTAs.

The **stamp** is the posture's signature and is reserved for document surfaces — service cards, the specimen ID, "Stamped as it ships." It takes `data-ink="copper|accent|dim"` to rebind `currentColor`; the double rule and the `-2deg` rotation come along automatically.

## Typography

**Three families, mono-forward for data.**

- **Space Grotesk** — the display family. All `h1`–`h6` at weight 600, `line-height: 1.08`, `letter-spacing: -0.015em`. Geometric and slightly technical; does engraved-caps headline duty without tipping into novelty.
- **IBM Plex Sans** — body. 16px / 1.6. IBM Plex is an institutional typeface designed for a corporation's documentation, which is exactly the register a credential service wants.
- **IBM Plex Mono** — every data field, and every label. Eyebrows, folios, pills, stamps, version chips, code chips, `from-tag`. On a credential the mono fields are the content, so the mono is not an accent here — it is roughly half the type on the page.

Label scale (mode does not affect type size):

- **Eyebrow** — 0.72rem, `0.22em` letter-spacing, uppercase.
- **Folio** — 0.72rem, `0.18em`, uppercase. The `.folio` component's `data-num` renders as a small bordered chip in accent (e.g. `SEC.02`).
- **Pill** — 0.7rem, `0.06em`. Tighter than eyebrow because pills sit in tighter UI.
- **Stamp** — 0.66rem, weight 600, `0.16em`, uppercase.
- **Version** — 0.66rem, `0.04em`. Used by `.ver-chip`.

## Layout & Spacing

A **fixed-max-width** layout with two widths:

- **`.container` — 1180px** — full-width sections (the three-service grid, footer).
- **`.container-narrow` — 760px** — single-column long-form (changelog and context-v lists and detail pages, search).

Inside both, `padding-inline: var(--space-6)` (24px) reserves a consistent gutter to the viewport edge.

## Shapes

**Documents are square.** The radius ladder tops out at 8px and spends most of its time at 2–3px:

- `sm: 2px` — chip, ver-chip, from-tag, stamp, folio number chip
- `md: 3px` — buttons
- `lg: 5px` / `xl: 8px` — larger panels
- `pill: 999px` — status pills only

Status pills are the one deliberate exception. They are round because they are *stickers applied to* the document, not part of it.

## Ornament

`.bg-mesh` is a fixed, pointer-events-none layer at `z-index: 0`; every direct child of `body` that is not `.bg-mesh` gets `position: relative; z-index: 1`.

It carries two things: three soft radial **mesh gradients**, and two **guilloche rosettes** built from `repeating-radial-gradient` at the `--guilloche-pitch` hairline (11px), each masked by a radial fade so it dissolves before reaching the middle of the page.

The rosettes use **different pitches** — 1× upper-right in accent, 1.4× lower-left in accent-warm. This is intentional and worth preserving: matched pitch reads as a tiled background pattern, mismatched pitch reads as two separately engraved plates.

Opacities step up with mode intensity: light `0.12 / 0.10`, dark `0.16 / 0.13`, vibrant `0.24 / 0.20`.

## Modes

Three modes on `<html data-mode="...">`, resolved before first paint.

| Mode | Label | Surface | Accent | Thread |
|---|---|---|---|---|
| `dark` *(default)* | the vault | vault-deep `#060a08` | verdigris `#4ecf95` | `#55e0d2` |
| `light` | security paper | paper `#f3f6f2` | verdigris-deep `#1f9a63` | teal-deep `#2a7f74` |
| `vibrant` | UV lamp | `#07060f` | uv `#9d7bff` | `#55f0a6` |

**Vibrant is dark-based**, per the three-mode contract. It shifts the surface from green-black to violet-black and hands `--color-accent` to the UV inks, but it never inherits light mode's paper. The verdigris thread survives the shift as `#55f0a6` — under the lamp, the security thread is the one feature that stays lit.

`BaseLayout.astro` ships `data-mode="dark"` in the markup, and its inline pre-paint script reads `id-didi-sh-splash-mode` from `localStorage` and applies the stored choice before first render.

## Do / Don't

- **Do** reference semantic tokens (`--color-accent`, `--color-bg`, `--color-thread`) in every component. Three modes means a hard-coded hex is wrong in at least two of them.
- **Do** set data in `--font__mono`. Key IDs, JWKS paths, API routes, cascade records, timestamps.
- **Do** keep the green-black. `--color-bg` is `#060a08`, not black. A neutral-black surface reads as a hole in the vault.
- **Do** keep radii near-square. If something needs to look softer, it probably needs different spacing, not a bigger radius.
- **Don't** blanket-replace the string "Augment It." It is one of the three consuming services didi.sh issues credentials for, and it belongs on this site. What does *not* belong is augment-it's magenta-violet-iris palette, which this document previously carried wholesale.
- **Don't** let vibrant mode inherit a light background. It is the UV lamp — dark-based by definition.
- **Don't** match the two guilloche pitches. The 1× / 1.4× mismatch is what makes the pair read as engraving rather than wallpaper.
- **Don't** drop the `data-mode` attribute or the pre-paint resolver in `BaseLayout.astro`. Without it every reload flashes the default before settling to the user's chosen mode.

## Known drift

Tracked here so it does not get rediscovered:

- **`ModeToggle.astro` uses augment-it's mode vocabulary.** Its `aria-label`s read "Demo mode (vibrant)", "Operator mode (dark)", "Ledger mode (light)". The didi.sh vocabulary is **UV lamp / the vault / security paper**. The labels should be brought over.
- **`ModeToggle.astro` falls back to `'vibrant'`** when reading the current mode, while `BaseLayout.astro` ships `data-mode="dark"`. Dark is the default; the fallback should say so.
- **The token file is shared by copy, not by import.** `site/src/styles/theme.css`
  and `splash/src/styles/theme.css` are byte-identical, and this file's copy still
  carries a header comment reading `theme.css — id-didi-sh/splash`. Sharing the
  system is correct; sharing it by duplication is what will drift.
- **The Phoenix app does not use this system at all.** `assets/css/app.css` is stock Tailwind 4 + daisyUI with the generator's Phoenix-purple dark and Phoenix-orange light themes, and it drives `data-theme` (`light`/`dark`/`system`) rather than `data-mode` (`dark`/`light`/`vibrant`). See `context-v/plans/Bring-The-Spike-Under-The-Credential-Design-System.md`.
