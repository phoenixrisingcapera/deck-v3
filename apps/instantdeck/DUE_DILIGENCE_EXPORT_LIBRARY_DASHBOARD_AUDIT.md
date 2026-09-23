# Due Diligence, Export, Deck Library, And Dashboard Audit

Date: 2026-07-14

This audit verifies the mounted product surfaces for:

- `/decks/[deckId]/due-diligence`
- `/decks/[deckId]/export`
- `/decks`
- `/dashboard`

It distinguishes between:

- `mounted and wired`
- `mounted but degraded`
- `exists but not mounted`
- `legacy or concept component`

## Summary

### Due diligence

- Route status: `mounted but degraded`, then fixed in this pass
- Main issue found: the page tried to run diligence with `POST /due-diligence`
- Backend contract actually exposes `POST /due-diligence/run`
- Fix applied: the page now posts to the canonical run route

### Export

- Route status: `mounted and wired`
- Important limitation: generated exports remain release-locked for admin review
- User can generate export records, but direct product download remains intentionally blocked by backend policy

### Deck library

- Route status: `mounted and wired`, with one honest limitation
- Main issue found: status-filter buttons existed but had no real filter wiring
- Fix applied: those controls are now explicitly disabled until a real filter contract exists

### Dashboard

- Route status: `mounted and wired`
- Mounted dashboard card tree is real and backed by the backend workspace dashboard response
- One non-mounted component path exists: `FirstTimeDashboard.svelte` is effectively unreachable from `/dashboard` because the server redirects empty workspaces to `/welcome`

## Canonical route ownership

### Due diligence

- Route files:
  - `src/routes/(product)/decks/[deckId]/due-diligence/+page.server.ts`
  - `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte`

- Main mounted components:
  - `AppShell.svelte`
  - `AudienceSelector.svelte`
  - `FindingCard.svelte`
  - `RiskBadge.svelte`
  - `DeckVisualizerSurface.svelte`
  - `DeveloperVisibilityCard.svelte`

- Backend owners:
  - `app/api/routes/deck_intake.py`
  - `app/services/visualizer/generated_deck_read_model.py`

### Export

- Route files:
  - `src/routes/(product)/decks/[deckId]/export/+page.server.ts`
  - `src/routes/(product)/decks/[deckId]/export/+page.svelte`

- Main mounted component:
  - `ExportPanel.svelte`

- Backend owners:
  - `app/api/routes/exports.py`
  - `app/services/rendering/export_service.py`
  - `app/services/deck_processing/workflow_orchestration.py`

### Deck library

- Route files:
  - `src/routes/(product)/decks/+page.server.ts`
  - `src/routes/(product)/decks/+page.svelte`

- Main mounted component:
  - `src/lib/components/decks/DeckLibraryPage.svelte`

- Backend owners:
  - `app/api/routes/products.py`
  - `app/api/routes/workspace_dashboard.py`
  - `app/services/deck_processing/workspace_summary_service.py`

### Dashboard

- Route files:
  - `src/routes/(product)/dashboard/+page.server.ts`
  - `src/routes/(product)/dashboard/+page.svelte`

- Mounted dashboard components:
  - `DashboardWelcomeHero.svelte`
  - `ReturningUserDashboard.svelte`
  - `RecentSlidesPreview.svelte`
  - `UploadedDecksPanel.svelte`
  - `DashboardRightRail.svelte`
  - `CurrentDeckCard.svelte`
  - `WorkspaceStatsCard.svelte`
  - `LatestIterationsCard.svelte`
  - `DeveloperVisibilityCard.svelte`

- Backend owner:
  - `app/api/routes/workspace_dashboard.py`
  - `app/services/visualizer/workspace_dashboard_read_model.py`

## Per-surface verification

## 1. Due diligence

### Frontend contract

`+page.server.ts` loads:

- `/api/decks/{deckId}` for graph
- product `GET /decks/{deckId}/due-diligence`
- `/api/decks/{deckId}/iterations?limit=8`

`+page.svelte`:

- renders the diligence workspace
- reloads by audience
- runs diligence from the page
- links to Smart Edit and Export

### Backend contract

Verified backend routes:

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence/run`

### Concrete breakpoint found

Before this pass, the page called:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence`

That route did not exist as a POST handler.

### Fix completed

The mounted page now calls:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence/run`

### Current judgment

- Status: `mounted and wired`
- Residual risk: the page still performs browser-side product fetches directly instead of going through a local frontend proxy route family for every diligence mutation

## 2. Export

### Frontend contract

`+page.server.ts` loads:

- `/api/decks/{deckId}`
- `/api/decks/{deckId}/iterations?limit=8`
- `/api/decks/{deckId}/exports`
- product `GET /decks/{deckId}/workflow-state`

`ExportPanel.svelte`:

- calls product `POST /decks/{deckId}/workflows/export`
- waits for workflow completion
- refreshes export records
- shows release-lock state

### Backend contract

Verified backend routes:

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/exports`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/export`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}/download`

### Important truth

This page is not fake.

The export workflow is real, but the backend intentionally blocks product-file release with:

- `403 Export generated successfully. Contact admin to receive the released file.`

So the correct status is:

- generation: real
- artifact listing: real
- direct release/download: intentionally blocked by policy

### Current judgment

- Status: `mounted and wired`
- Product limitation: release remains admin-controlled

## 3. Deck library

### Frontend contract

`+page.server.ts` loads:

- product workspace summary
- AI provider summary
- deck summaries
- latest generated deck

`DeckLibraryPage.svelte` mounts:

- uploaded-deck list
- latest generated deck card
- upload-first-deck card for empty workspaces

### Concrete breakpoint found

The right-rail status buttons:

- `Under review`
- `Ready`
- `Failed`

were present but had no filter state, no query param, and no backend contract.

They looked real but did nothing.

### Fix completed

Those buttons are now explicitly disabled until a real filter path is wired.

### Current judgment

- Status: `mounted and wired`
- Honest limitation: status-filter controls are not implemented yet

## 4. Dashboard

### Frontend contract

`+page.server.ts` loads:

- `GET /api/workspace/dashboard`
- `GET /api/settings/workspace/ai-provider`

It validates the dashboard payload with `workspaceDashboardSchema`.

### Backend contract

Verified backend route:

- `GET /api/workspace/dashboard`

Verified backend service:

- `get_workspace_dashboard()` in `workspace_dashboard_read_model.py`

That service returns:

- user summary
- stats
- latest deck
- deck list
- recent slides
- latest iterations

### Mounted dashboard components verified

Mounted and receiving real page data:

- `DashboardWelcomeHero.svelte`
- `ReturningUserDashboard.svelte`
- `RecentSlidesPreview.svelte`
- `UploadedDecksPanel.svelte`
- `DashboardRightRail.svelte`
- `CurrentDeckCard.svelte`
- `WorkspaceStatsCard.svelte`
- `LatestIterationsCard.svelte`

### Important non-mounted finding

`FirstTimeDashboard.svelte` is imported by the page, but `/dashboard` server load redirects users with zero decks to `/welcome`.

That means:

- `FirstTimeDashboard.svelte` exists
- but in normal runtime it is effectively `exists but not mounted`

### Link verification

The mounted dashboard cards point to real routes:

- latest deck -> `/decks/{deckId}/smart-deck`
- recent slides -> `/decks/{deckId}/smart-deck`
- uploaded decks -> `/decks`
- current deck -> `/decks/{deckId}/smart-deck`
- latest iterations -> `/decks/{deckId}/iterations`

The iterations route family exists in the product tree.

### Current judgment

- Status: `mounted and wired`
- Clarification: `FirstTimeDashboard.svelte` should not be treated as active dashboard product truth

## Code changes made in this pass

- Fixed Due Diligence run action in:
  - `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte`

- Disabled non-functional deck-library filter controls in:
  - `src/lib/components/decks/DeckLibraryPage.svelte`

## Verification commands

Frontend:

```bash
cd deck-frontend-rescue
npm run check
```

Backend:

```bash
cd deck-backend-rescue
python3 -m compileall app
```
