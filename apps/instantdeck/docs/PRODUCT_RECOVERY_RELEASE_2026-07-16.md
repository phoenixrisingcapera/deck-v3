# Product Recovery Release 2026-07-16

Tag: `v2026.07.16-production-reconciliation`

## Scope

This release repairs the mounted canonical product routes without introducing
alternate welcome, dashboard, deck, Smart Edit, or Due Diligence surfaces.

## Product Changes

- Restores the original Deck AIStack navy, cyan, violet, and magenta design
  tokens that were removed during the July 11 frontend cleanup.
- Restores token aliases still consumed by mounted welcome, dashboard, intake,
  Smart Deck, Smart Edit, and brand components.
- Labels canonical sidebar destinations as `Smart Edit` and `Due Diligence`.
- Makes dashboard Home active and keeps returning-user navigation on
  `/dashboard`.
- Accepts canonical failed deck state and valid empty intake metadata without
  replacing persisted dashboard data with the global error page.
- Degrades optional AI-provider summary failures without hiding the dashboard.
- Fixes the Due Diligence run proxy to send one validated `runMode` alias rather
  than the duplicate payload rejected by the backend.
- Wires Smart Edit slide search and suggestion status/risk filters.
- Disables Add Slide explicitly until a canonical persisted command exists.
- Keeps Smart Edit mounted when iteration history or persistent fields are
  temporarily unavailable, while preserving dependency diagnostics.
- Improves authentication, mobile route handling, CSP behavior, route errors,
  processing handoff, and canonical product navigation.

## Canonical Routes

- `/welcome`
- `/dashboard`
- `/decks`
- `/decks/new`
- `/decks/[deckId]/processing`
- `/decks/[deckId]/smart-deck`
- `/decks/[deckId]/smart-edit`
- `/decks/[deckId]/due-diligence`
- `/decks/[deckId]/export`

## Verification

- `npm run check`: passed with zero errors and zero warnings.
- `npm run build`: passed using the Node adapter.
- `npm run test:dashboard-contract`: passed.
- `git diff --check`: passed.

## Production Boundary

The frontend fixes require deployment with the matching backend tag. A healthy
page load alone does not prove Smart Deck, Smart Edit, or Due Diligence runtime
completion; use the Railway authenticated product smoke after deployment.
