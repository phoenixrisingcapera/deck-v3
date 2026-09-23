# Smart Deck Elements Release

Date: 2026-07-17

## Scope

The canonical mounted `/decks/[deckId]/smart-deck` workspace now includes an
Elements tool backed by the selected generated slide's render schema.

## Product Behavior

- Lists generated text, shape, image, and chart-placeholder elements.
- Shows content, position, dimensions, typography, asset, and data-key details.
- Keeps panel selection aligned with the selected canvas element and persisted
  Smart Deck selection state.
- Accepts a focused element-fitting instruction.
- Uses the existing authenticated element-variation endpoint.
- Returns the generated variation through the existing design-version preview,
  apply, keep, and discard flow.

## Canonical Contract

```text
Elements rail action
  -> UserSmartDeckWorkspace
  -> SmartDeckElementsPanel
  -> persisted selected element
  -> POST /api/decks/{deckId}/generated-slides/{generatedSlideId}/elements/{elementId}/variation-jobs
  -> reviewable design version
  -> apply or discard
```

No duplicate backend endpoint, alternate Smart Deck route, or parallel element
persistence model was introduced.

## Verification

- `node scripts/verify-smart-deck-elements-module.mjs`
- `node scripts/verify-smart-deck-tool-wiring-contract.mjs`
- `npm run check`
- Railway production deployment for code commit `9bfc0128958b4decec288742ae781c729ecb365c`
  completed successfully.

## Runtime Notes

- A generated render schema is required before the panel can list elements.
- Element variations require the configured provider to be available.
- Provider-capacity failures remain visible and do not silently create mock
  element results.
