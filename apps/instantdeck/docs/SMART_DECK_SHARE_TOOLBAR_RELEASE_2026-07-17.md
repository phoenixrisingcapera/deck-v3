# Smart Deck Share And Toolbar Release

## Scope

This release improves the canonical `/decks/[deckId]/smart-deck` workspace without adding another route or component tree.

## Changes

- The mounted Share control now uses the browser's native share capability when available and falls back to copying the canonical Smart Deck URL.
- The Share control displays visible success or unavailable feedback instead of silently ignoring clipboard failures.
- Unsupported element-format controls are represented by one explanatory status instead of a row of disabled buttons that imply unavailable editing actions.

## Contracts Preserved

- Smart Deck route ownership remains with `UserSmartDeckWorkspace` and its mounted user components.
- The shared URL remains `/decks/[deckId]/smart-deck` and continues through normal authentication protection.
- No backend API, persistence schema, workflow job, or compatibility route changed.

## Verification

- `node scripts/verify-smart-deck-share-toolbar-contract.mjs`
- `node scripts/verify-smart-deck-tool-wiring-contract.mjs`
- `node scripts/verify-smart-deck-route-smoke.mjs`
- `npm run check`
- `npm run build`
- Railway deployment and production HTTP health smoke after publishing
