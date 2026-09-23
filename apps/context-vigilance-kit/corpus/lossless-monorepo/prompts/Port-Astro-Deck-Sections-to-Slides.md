---
title: Port Astro Deck Sections to Slides
lede: Porting a scroll-deck section to a 16:9 slide is a copy/paste adaptation into
  an independent file, never a wrapper around the original.
date_created: 2026-05-10
date_modified: 2026-05-10
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 4.7
semantic_version: 0.0.0.1
status: Draft
tags:
- Scroll-to-Slide-Adaptation
- Slide-Tier
- Slide-Canvas
- Keynote-Style-Playback
- Fixed-Aspect-16-9
- Wrapper-Trap-Documented
- Copy-Paste-Adaptation
- Section-by-Section-Workflow
- Decision-Rules
- Astro-Sections
- Deck-Iteration-Workflow
related:
- '[[deck-iteration-workflow]]'
- '[[High-Resolution-High-Fidelity-Deck-Exports-from-Code-to-Images-&-PDFs]]'
- '[[2026-05-10_02]]'
site_uuid: dab15f7b-e90e-4988-9187-4c9cad4cee06
hex_code: 2nuzun
date_authored_initial_draft: 2026-05-10
date_authored_current_draft: 2026-05-10
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: prompts/Port-Astro-Deck-Sections-to-Slides.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/prompts/Port-Astro-Deck-Sections-to-Slides.md"
---

# Note to Agents:

We have a working scroll deck (calmstorm-decks: `/thesis`, `/thesis/version-2`, `/thesis/version-3`) where each "slide" is an Astro section component composed into a single scrolling page. The scroll-deck approach is intentional and valuable — agents reasoning about a whole-deck narrative produce more coherent design than agents reasoning slide-by-slide. That motion is documented in the existing `deck-iteration-workflow` skill at `~/.claude/skills/deck-iteration-workflow/SKILL.md`.

**The motion this prompt covers:** taking those scroll-deck sections and producing **independent, fixed-aspect 16:9 slide files** that play left/right like Keynote/PPT, **without changing the existing scroll-deck sections** and as **a new tier alongside** the existing wireframe variants on the `/{slug}` chooser pages.

**Core constraint we keep getting wrong:** the act of "porting" a scroll-deck section to a slide is **not a wrapper around the original**. It's a **copy/paste adaptation** into a new file that lives independently and can be tuned for the 16:9 canvas without leaking edits back into the scroll deck. We have learned this the hard way. If a future agent thinks "I'll just import the existing section into a SlideCanvas wrapper," that agent is about to repeat a mistake we've made and noticed.

---

## Why scroll → slide is genuinely hard (the lived experience)

When you design a scroll deck end-to-end you get **visual coherence for free** — the agent reasons about the whole arc, every section knows it's in conversation with the others, color and rhythm and density harmonize because one mind held the whole thing at once.

When you split that into individual slides played left-to-right at a fixed aspect ratio:

1. **Some sections fit the canvas naturally.** The cover, the vision/mission slide, the simple stat slides — these were always single-screen-ish in design intent.
2. **Some sections don't fit at all.** Sections written with multiple stat panels, dense person grids, or tall text columns assume vertical breathing room that a fixed 16:9 box doesn't have.
3. **Some sections fit but lose rhythm** — they were authored with the section above and below in mind. Played alone in a fullscreen canvas, the framing reads weird.
4. **You can't tell which is which from a `curl` response.** Visual inspection in the browser at fullscreen is the only honest measurement. This is why the workflow is iterative: generate, inspect, fix, move on.

Knowing **when to do this adaptation work** is part of the value of having a skill at all. Don't trigger it during initial design. Don't trigger it before the scroll deck feels done. Trigger it when there's a real need to play the deck Keynote-style or export to PPT/Reveal/PDF for an audience that expects fixed-aspect playback.

---

## Naming convention: not yet final, evolving

Where adapted slide files live:

```
src/slides/by-title/{NN}-{slug}-v{N}.astro
```

- `NN` is the slide number (`01` through `17`), zero-padded for filesystem sort.
- `slug` is the kebab-case slug from `src/lib/slides.ts` (lowercase only — `investment-team-lpac` not `investment-team-LPAC`, even though the registry keeps the latter for display).
- `v{N}` is the variant — currently `v1` / `v2` / `v3` mapping to which scroll-deck source inspired it (teaser / teaser-v2 / teaser-v3). This may evolve as new variants are generated independently of the scroll decks.

The folder choice is `src/slides/`, not `src/layouts/slides/` or `src/components/slides/`. Astro treats anything outside `src/pages/` and `src/content/` identically — the folder name signals semantics for humans, not Astro. `slides/` says "these are slide files." `by-title/` leaves room for future organization axes (`by-theme/`, `by-audience/`, `by-stage/`) as the deck-builder shopping experience matures.

**Open question, not yet answered:** there is also a "theme" axis lurking. The scroll decks v1/v2/v3 each have a coherent visual treatment because they were designed in one go (warm/light, dark/inverted, magazine-editorial respectively). When new variants are generated outside that initial coherence, tracking which theme they belong to gets harder. The naming may eventually need a theme tag (e.g. `01-disclaimer-confidential-warm-v1.astro`, `01-disclaimer-confidential-magazine-v2.astro`). Flagging for later — go with what feels natural for now.

---

## The workflow (section-by-section, iterative)

Do **one section title at a time**. For each section, produce 3 adaptations (one per scroll-deck variant), have the user inspect them in the player, get feedback, iterate. Do not speculatively generate all 17 × 3 = 51 files in a single pass — you cannot tell from a `curl` whether they look right, the user has to see each one, and bulk-generating without inspection burns iterations.

For each section:

1. **Read the three source files** in `src/layouts/sections/teaser/`, `teaser-v2/`, `teaser-v3/`.
2. **Copy the content into three new files** at `src/slides/by-title/{NN}-{slug}-v{1,2,3}.astro`.
3. **Wrap each in `SlideCanvas`** (the canvas component handles the 16:9 aspect ratio + scale-to-fit transform).
4. **Adapt the styles** for the 16:9 canvas: smaller fonts, tighter spacing, restructured layout where needed. Be conservative on the first pass — the user is going to tell you which ones need more aggressive adaptation.
5. **Tell the user which section is ready** for inspection. Provide the link to the per-section player.
6. **Wait for feedback.** Statuses to expect: `urgent-redo`, `non-urgent-could-be-better`, `passable`, `perfect`.
7. **Move to the next section** based on user direction.

What you must NOT do:

- Edit any file under `src/layouts/sections/teaser{,-v2,-v3}/`. Those are scroll-deck source. Untouchable.
- Generate all 17 sections in one pass without user inspection.
- Treat the new slide files as wrappers that import the originals. They are independent copies. Per-slide adaptations live in the slide file itself.

---

## The infrastructure (already built, don't redo)

The first iteration produced these pieces. They're correct and stay; only the slide files themselves change.

- **`src/components/slides/SlideCanvas.astro`** — the fixed-aspect 16:9 wrapper. Design size 1920×1080 by default, scale-to-fit container via JS ResizeObserver. Force-resolves `[data-reveal]` animations and resets `.slide` height inside the canvas.
- **`src/pages/play/index.astro`** — the keyboard-driven player. Cross-fades between slides via `aria-hidden` toggling. Bindings: ←/→/Space navigate, F fullscreen, C toggle chrome, Esc exits fullscreen. URL hash updates so `/play#7` jumps to slide 7.
- **`src/pages/index.astro`** — the deck index has a "▶ Play (next-gen slide tier)" tile linking to `/play`.

What still needs to be built once the per-section workflow takes shape:

- **`src/pages/play/section/[slot]/index.astro`** — dynamic route that walks just one section's 3 variants. So `/play/section/01` plays slides 01-v1 → 01-v2 → 01-v3. This is what the per-section inspection workflow points at.
- **`src/pages/data-assets/slides.astro`** — audit surface listing all 17 sections, each with a "Play 3 variants" link and a status pill (`urgent-redo` / `non-urgent-could-be-better` / `passable` / `perfect`). Same shape as the existing `/data-assets/companies` and `/data-assets/people` pages. Status persistence TBD — could be a sibling status registry file, or a top-of-file frontmatter comment in each slide.
- **A way to declare which variant is preferred per slot.** Once a section is reviewed and one variant is "perfect," the player should walk that variant for that slot. Implementation candidates: a `src/decks/canonical.ts` registry, or a "canonical" symlink/copy convention.

---

## What we got wrong in the first iteration (preserved as a warning)

The first attempt at this prompt produced 51 wrapper files at `src/slides/by-title/{NN}-{slug}-v{1,2,3}.astro` that imported the corresponding scroll-deck section directly:

```astro
---
import SlideCanvas from "../../components/slides/SlideCanvas.astro";
import Section from "../../layouts/sections/teaser/T01-DisclaimerCover.astro";
---
<SlideCanvas><Section /></SlideCanvas>
```

This LOOKS clever — minimal duplication, single source of truth. But it's wrong because:

1. **Per-slide adaptations leak.** Any CSS tweak you add to make the slide fit the canvas modifies the rendering of the imported section, which renders inside the scroll deck too. You can't constrain to "only when in slide mode" without flag-passing through the section, which defeats the simplicity.
2. **The slide file doesn't have its own DNA.** The file is just an import statement; you can't quickly read what's on the slide without opening the source section. This becomes painful when a human is "shopping through 100 slides" picking 12 for a meeting — they want to scan the slide files themselves.
3. **It conflates source and presentation.** The scroll-deck section is the agent's coherent design moment. The slide file is the presentation moment. Different concerns; should be different files.

The fix: replace each wrapper with a copy/paste of the source section's content, then adapt the copy for the canvas. The wrappers can be bulk-deleted once the copies exist.

---

## Worked example: T01 (Disclaimer / Confidential)

The first section to actually adapt this way. Three source files exist:

- `src/layouts/sections/teaser/T01-DisclaimerCover.astro` (warm/light, full-bleed cover)
- `src/layouts/sections/teaser-v2/T01-DisclaimerCover.astro` (dark/inverted, vertical wordmark on the left)
- `src/layouts/sections/teaser-v3/T01-DisclaimerCover.astro` (magazine-editorial, with plate marks top/bottom and 2-column justified disclaimer)

The pilot produces:

- `src/slides/by-title/01-disclaimer-confidential-v1.astro` — adaptation of the warm cover for 16:9
- `src/slides/by-title/01-disclaimer-confidential-v2.astro` — adaptation of the dark cover (already mostly fixed-height in design, since the v2 wordmark is rotated and the body is a fixed grid; should adapt cleanly)
- `src/slides/by-title/01-disclaimer-confidential-v3.astro` — adaptation of the magazine cover (already authored against absolute-positioned plate marks; should adapt cleanly)

Probable adaptation needs per variant for T01 specifically:
- **v1:** the disclaimer text at the bottom is 0.65rem and may need to shrink or wrap differently inside the canvas. The hero wordmark uses `clamp()` which the canvas's transform handles — should rescale fine.
- **v2:** the rotated wordmark on the left edge fits only because the section assumes `height: 100vh` with a fixed grid. Inside the canvas, height becomes the canvas height (fine) and the rotation still works.
- **v3:** the plate marks are `position: absolute` with explicit `top`/`bottom`. Inside the canvas they'll position relative to the canvas, which is what we want. The 2-column disclaimer at the bottom uses `position: absolute; bottom: 3rem` — should work.

After producing T01 v1/v2/v3, expect the user to play `/play/section/01` and report which of the three variants is `perfect` / `passable` / etc.

---

## See also

- `~/.claude/skills/deck-iteration-workflow/SKILL.md` — the original forward-arc skill that builds the scroll deck. This prompt picks up after that motion, when scroll mode is "done" and a slide tier is needed.
- `sites/calmstorm-decks/src/components/slides/SlideCanvas.astro` — the canvas primitive. Read this before adapting any slide.
- `sites/calmstorm-decks/src/pages/play/index.astro` — the player. Currently hardcoded to walk v1 of each slot; per-section route is the natural next.
- `sites/calmstorm-decks/scripts/export-decks.ts` — the existing exporter. Once enough slides are `perfect`, the slide tier can have its own exporter that's much simpler than the scroll-deck DOM-walker (just iterate the slide files at native 1920×1080 and screenshot).
- `sites/calmstorm-decks/context-v/changelogs/2026-05-07_01.md` — the export-pipeline changelog where Path 3 ("strict 16:9 canvas baked in from day one") is the architectural precondition this work operationalizes.
- `sites/calmstorm-decks/src/pages/data-assets/{companies,people}.astro` — pattern for the slides-audit page when it gets built.
