# Smart Deck Workflow Rail Navigation

## Scope

This release restores direct Smart Edit and Due Diligence links in the canonical Smart Deck app rail without creating new product surfaces or backend contracts.

## Canonical Routes

- Smart Deck: `/decks/[deckId]/smart-deck`
- Smart Edit: `/decks/[deckId]/smart-edit`
- Due Diligence: `/decks/[deckId]/due-diligence`

The app rail is mounted by `UserSmartDeckWorkspace.svelte`. Selecting either workflow link uses the active deck ID and navigates to the existing canonical route.

## Wiring

### Smart Edit

The Smart Edit page loads the deck graph, persisted editable fields, workflow state, and iteration history. Its actions use authenticated frontend proxies for intent classification, patch generation, run retrieval, and suggestion decisions. Those proxies forward to the existing `/api/decks/{deck_id}/slides/{slide_id}/smart-edit/...` backend routes.

### Due Diligence

The Due Diligence page loads the deck graph and product-scoped diligence workspace. Its run and audience actions use authenticated product proxies under `/api/products/deck-aistack-codes/decks/[deckId]/due-diligence`. Those proxies forward to the existing product and deck diligence backend routes and services.

## Font CSP

No external Google Fonts request is enabled. `src/app.html` retains the disabled historical links, and the production CSP remains self-hosted for styles and fonts. This preserves the previously released CSP correction.

## Verification

- Smart Deck rail contract checks
- Font CSP contract checks
- Svelte type checking
- Production frontend build
- Relevant backend Smart Edit and Due Diligence route tests
