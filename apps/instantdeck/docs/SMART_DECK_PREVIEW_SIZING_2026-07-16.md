# Smart Deck Preview Sizing

Status: mounted and wired

## Contract

The generated deck preview must use the available width inside
`DeckDesignShellCard` while preserving the render schema's 16:9 aspect ratio.
Text uses `cqw` units derived from the rendered canvas width, so expanding the
canvas also produces readable proportional typography without changing persisted
font sizes or the backend render schema.

## Mounted Path

```text
/admin/decks/[deckId]/smart-deck
-> SmartDeckWorkspace.svelte
-> DeckDesignShellCard.svelte
-> DeckVisualizerSurface.svelte
-> GeneratedSlideRenderer.svelte
```

The canonical user route uses `SmartDeckCanvas.svelte`, which already forces the
same renderer to `width: 100%` and `height: 100%`. No alternate renderer or route
was introduced.

## Root Cause

`generated-slide-preview` used `place-items: center`. Its child visualizer was a
centered grid item with intrinsic width, so the panel and its 16:9 render stage
occupied only part of the available shell. Since render-schema font sizes are
container-width units, the undersized stage also produced undersized text.

## Solution

The generated-preview branch now stretches `DeckVisualizerSurface` to the full
available width. Source-slide and empty states keep their existing centered
behavior. The renderer's existing percentage geometry, 16:9 ratio, and `cqw`
typography remain authoritative.

Future LLM output is also protected in the backend generation path. The Smart
Deck generator, critique, and repair prompts require a presentation hierarchy of
44-72px headlines, 28-36px normal slide copy, and 20-24px supporting labels or
notes on the canonical 1920x1080 canvas. Runtime validation rejects smaller text
and sends the payload through the existing bounded repair pass, which must shorten
and reflow copy rather than preserve document-scale typography.

## Affected Files

- `src/lib/components/smart-deck/DeckDesignShellCard.svelte`: stretches the
  generated preview visualizer.
- `src/lib/components/smart-deck/DeckVisualizerSurface.svelte`: existing frame
  that passes full width to the renderer; unchanged.
- `src/lib/components/smart-deck/GeneratedSlideRenderer.svelte`: existing 16:9
  renderer and container-relative typography; unchanged.
- `scripts/verify-smart-deck-preview-sizing-contract.mjs`: guards this sizing
  chain.
- Backend `app/llm/prompt_packages/smart_deck/{generator,critique,repair}.md`:
  tells the LLM to produce concise, presentation-legible slides.
- Backend `app/services/llm/generation_service.py`: rejects undersized generated
  text before persistence so the existing repair pass can correct it.
- Backend `tests/test_smart_deck_typography_legibility.py`: verifies headline,
  body, supporting-text, and missing-size thresholds.

## Legacy Review

No duplicate renderer, route, or document needed absorption into `legacy/`.
