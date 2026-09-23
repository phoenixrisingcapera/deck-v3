# Changelog

## 2026-07-14 — Deck Surface Wiring Completion

- Wired the mounted Due Diligence page to the canonical product due-diligence load and run endpoints.
- Added the missing frontend proxy route for `/api/products/deck-aistack-codes/decks/[deckId]/due-diligence/run`.
- Switched mounted Smart Edit accept/reject actions to the deck-scoped suggestion PATCH proxy.
- Updated the wiring audit to mark Smart Deck, Smart Edit, Due Diligence, and Export as completed and mounted.

## 2026-07-14 — Product Smart Edit Review Actions

- Removed the retired `/welcome-v2` and `/welcome_back` compatibility routes from the product tree.
- Switched Smart Edit accept/reject actions to dedicated suggestion decision endpoints instead of the deck-scoped compatibility patch route.
- Kept Smart Edit generation on the canonical classify + patch-run workflow.

## 2026-07-07 — LLM Workflows Release

- Added provider-backed Deck Map and Market Research product panels.
- Migrated Smart Edit to classify + reviewable patch workflow.
- Migrated Due Diligence UI to audience-conversion-backed workflow.
- Added shared artifact history/details UI and canonical deck intelligence inspector.
- Added admin workflow checks page and frontend LLM verification scripts.

## 2026-07-07 — Deck Map Tool & App Rail Switching (fix)

- **Fix:** Moved `{@const}` blocks outside `<aside>` to comply with Svelte 5 `{@const}` placement rules (must be immediate child of `{#if}` block).

## 2026-07-07 — Deck Map Tool & App Rail Switching

- **SmartDeckAppRail** — added `onToolChange` callback prop so clicking a rail button switches the active tool panel.
- **UserSmartDeckWorkspace** — wired `activeTool` state from the rail; added a "Deck Map" panel showing slide-role distribution; conditional rendering based on selected tool.
- **Redirect `/changes` → `/due-diligence`** — new route at `(product)/decks/[deckId]/changes` permanently redirects to the due-diligence page.
