# Frontend Feature Audit — July 7, 2026

## Smart Deck

### Status
Functionally complete for the user flow: select slides, configure audience/deck-type/goal, enter prompt, generate, preview, apply, discard.

### Issues
- **Two diverging workspace implementations**: `UserSmartDeckWorkspace` (product route) is simplified vs `SmartDeckWorkspace` (admin route). Admin has element variation, compare mode, version restore, regeneration — user route lacks these.
- **Placeholder tabs**: Animation, Data, and Design tabs in `SmartDeckInspectorPanel` show placeholder content.
- **New slide creation**: Disabled with "later pass" message.
- **Export**: Linked but not wired in Smart Deck.

### Key Files
- `src/routes/(product)/decks/[deckId]/smart-deck/+page.svelte` — User workspace
- `src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte` — Main orchestrator
- `src/lib/features/smart-deck/user/SmartDeckAIAssistantPanel.svelte` — AI generation UI
- `src/lib/api/smartDeckWorkspace.ts` — API layer
- `src/lib/server/load-smart-deck-page.ts` — Server loader (1034 lines)

---

## Smart Edit

### Status
Active flow works. Redesigned in commit `8f2a8a5` (July 5).

### Issues
- **5 orphaned legacy component files** left from previous implementation:
  - `src/lib/components/SmartEditPanel.svelte` (dead, broken form POST to JSON endpoint)
  - `src/lib/components/SmartEditCommandBox.svelte` (dead, broken form POST)
  - `src/lib/components/SmartEditSuggestionCard.svelte` (dead, POST to PATCH-only endpoint)
  - `src/lib/components/ChangeReviewPanel.svelte` (dead, not imported)
  - `src/lib/components/ChangeReviewCard.svelte` (dead, not imported)
- Audience type hardcoded to `investment_committee` in both product and admin pages.
- Affected slides always shows first 4 slides (`graph.slides.slice(0, 4)`) instead of actual affected slides.
- Redundant `+page.ts` coexists with `+page.server.ts`.
- Type casting (`data as PageData & ...`) bypasses generated types.

### Key Files
- `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte` — Product page (redesign)
- `src/routes/(admin)/super-admin/decks/[deckId]/smart-edit/+page.svelte` — Admin page (old design)
- `src/routes/api/decks/[deckId]/smart-edit/+server.ts` — POST proxy
- `src/routes/api/decks/[deckId]/smart-edit/suggestions/[suggestionId]/+server.ts` — PATCH proxy

---

## Due Diligence ("Smart Audit")

### Status
User-facing and admin routes work. Legacy redirects from `diligence/` and `audience/` are in place.

### Issues
- **Missing `changes/` redirect**: `/decks/:deckId/changes` returns 404. Documented in `fornten.md` but route does not exist. **(FIXED July 7)**
- **No backend key normalization**: Product page casts API response directly as `DueDiligenceWorkspace` without camelCase/snake_case handling (admim page has `normalize*()` functions).
- Stale `(app)` route group references in `fornten.md` and contract verification script (route group renamed to `(product)` / `(admin)` in commit `9627430`).
- Redundant `+page.ts` in product route.

### Key Files
- `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte` — Product page ("Smart Audit")
- `src/routes/(admin)/super-admin/decks/[deckId]/due-diligence/+page.svelte` — Admin page
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/due-diligence/+server.ts` — API proxy
- `src/routes/(product)/decks/[deckId]/changes/+page.server.ts` — Redirect route **(added July 7)**

---

## Deck Map

### Status
**Stub/placeholder only.** No actual map visualization. Shows static text and slide role count pills (data already visible elsewhere).

### Issues
- **No interactive map**: Just a text paragraph + tag list of slide roles by count.
- **Default active tool is the stub**: `load-smart-deck-page.ts` sets `activeTool: 'deck_map'` as default, so users see the placeholder first.
- **App rail buttons had no click handlers in user workspace**: `SmartDeckAppRail.svelte` buttons were decorative (no `onclick`). **(FIXED July 7)** — Added `onToolChange` callback.
- Two shell systems: `DeckWorkspaceShell` (admin, working tool switching) vs `UserSmartDeckWorkspace` (product, was hardcoded to slides).
- No dedicated API endpoint — deck map data is derived client-side from `DeckGraph`.

### Key Files
- `src/lib/features/smart-deck/user/SmartDeckAppRail.svelte` — Tool rail (now wired)
- `src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte` — Now renders deck map panel conditionally
- `src/lib/features/smart-deck/user/smartDeckUserStore.ts` — `SMART_DECK_APP_RAIL_ITEMS` includes `deck_map`

---

## Fixes Applied July 7

1. **Created `/decks/[deckId]/changes` redirect route** (`+page.server.ts`): 308 redirect to `/decks/${deckId}/due-diligence`.
2. **Wired Deck Map app rail buttons**: Added `onToolChange` prop to `SmartDeckAppRail`, added `activeTool` state to `UserSmartDeckWorkspace`, conditionally renders slide navigator or deck map panel with role counts.
