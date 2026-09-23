# Smart Deck, Smart Edit, Due Diligence, And Export Wiring Audit

Date: 2026-07-14

This audit verifies the mounted product surfaces for Smart Deck, Smart Edit,
Due Diligence, and Export. It is not a design note. It traces the real route,
proxy, backend contract, and DB-backed state used by the site.

## Audit result

Smart Deck, Smart Edit, Due Diligence, and Export are wired to real backend and
DB contracts.

They are not dummy pages.

The main risk is contract drift across:

- frontend fallback payloads
- compatibility routes
- duplicate admin or diagnostic copies of product components

Status: Completed on 2026-07-14

## Canonical product routes

- `/decks/[deckId]/smart-deck`
- `/decks/[deckId]/smart-edit`
- `/decks/[deckId]/due-diligence`
- `/decks/[deckId]/export`

These are the mounted product pages that must remain authoritative.

## Smart Deck route chain

### Mounted frontend page

- `src/routes/(product)/decks/[deckId]/smart-deck/+page.server.ts`
- `src/routes/(product)/decks/[deckId]/smart-deck/+page.svelte`
- `src/lib/server/load-smart-deck-page.ts`
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`

### Frontend proxies actually used

- `src/routes/api/decks/[deckId]/smart-deck/+server.ts`
- `src/routes/api/decks/[deckId]/generated-slides/[generatedSlideId]/code/+server.ts`
- `src/routes/api/decks/[deckId]/generated-slides/[generatedSlideId]/elements/[elementId]/variation-jobs/+server.ts`
- `src/routes/api/decks/[deckId]/smart-deck/preferences/+server.ts`
- `src/routes/api/decks/[deckId]/smart-deck/selection/+server.ts`

### Backend endpoints actually used

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck`
- `GET /api/decks/{deck_id}/generated-slides/{generated_slide_id}/code`
- `POST /api/decks/{deck_id}/generated-slides/{generated_slide_id}/elements/{element_id}/variation-jobs`
- `PATCH /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/preferences`
- `PATCH /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/selection`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/apply-design-version`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`

### DB-backed models feeding Smart Deck

- `smart_deck_workspaces`
- `smart_deck_preferences`
- `smart_deck_messages`
- `generation_jobs`
- `design_versions`
- `generated_slides`
- `generated_slide_code_versions`
- `generated_slide_elements`
- `generated_slide_element_versions`
- `design_tokens`

## Smart Edit route chain

### Mounted frontend page

- `src/routes/(product)/decks/[deckId]/smart-edit/+page.server.ts`
- `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte`

### Frontend proxies actually used

- `src/routes/api/decks/[deckId]/smart-edit/+server.ts`
- `src/routes/api/decks/[deckId]/slides/[slideId]/smart-edit/classify/+server.ts`
- `src/routes/api/decks/[deckId]/slides/[slideId]/smart-edit/patch/+server.ts`
- `src/routes/api/decks/[deckId]/slides/[slideId]/smart-edit/runs/[runId]/+server.ts`
- `src/routes/api/decks/[deckId]/smart-edit/suggestions/[suggestionId]/+server.ts`

### Product API endpoints used by page load

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields/{field_key}`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`

### Backend endpoints actually used

- `POST /api/decks/{deck_id}/smart-edit`
- `POST /api/decks/{deck_id}/slides/{slide_id}/smart-edit/classify`
- `POST /api/decks/{deck_id}/slides/{slide_id}/smart-edit/patch`
- `GET /api/decks/{deck_id}/slides/{slide_id}/smart-edit/runs/{run_id}`
- `PATCH /api/decks/{deck_id}/smart-edit/suggestions/{suggestion_id}`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/changes/preview`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/changes/apply`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields/{field_key}/preview`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields/{field_key}/save`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields/{field_key}/apply`

### DB-backed models feeding Smart Edit

- `smart_edit_runs`
- `smart_edit_suggestions`
- `decks`
- `deck_slides`
- `deck_blocks`

## Mounted cards verified

### Smart Deck

- `DeckDesignShellCard.svelte`
- `GeneratedBatchSaveCard.svelte`
- `LlmParallelizationCard.svelte`
- `LlmChatCard.svelte`
- `PdfSlideMiniaturesCard.svelte`
- `SmartDeckFloatingAIButton.svelte`

These are mounted from `SmartDeckWorkspace.svelte`, which is mounted from the
canonical product route.

### Smart Edit

- `DeckVisualizerSurface.svelte`
- `ChangeReviewPanel.svelte`
- `BlockClassificationBadge.svelte`

These are mounted from the canonical Smart Edit page.

## Due Diligence route chain

### Mounted frontend page

- `src/routes/(product)/decks/[deckId]/due-diligence/+page.server.ts`
- `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte`

### Frontend proxies actually used

- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/due-diligence/+server.ts`
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/due-diligence/run/+server.ts`

### Backend endpoints actually used

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence/run`
- `GET /api/decks/{deck_id}/graph`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/versions`

### DB-backed models feeding Due Diligence

- `decks`
- `deck_slides`
- `deck_blocks`
- due-diligence workspace payloads returned by `deck_intake.py`

## Export route chain

### Mounted frontend page

- `src/routes/(product)/decks/[deckId]/export/+page.server.ts`
- `src/routes/(product)/decks/[deckId]/export/+page.svelte`
- `src/lib/components/ExportPanel.svelte`

### Frontend proxies actually used

- `src/routes/api/decks/[deckId]/exports/+server.ts`
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/workflows/export/+server.ts`
- `src/routes/api/decks/[deckId]/exports/[exportId]/download/+server.ts`

### Backend endpoints actually used

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/exports`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/export`
- `GET /api/decks/{deck_id}/exports/{export_id}/download`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`

### DB-backed models feeding Export

- `deck_exports`
- `workflow_jobs`

## Important findings

### 1. Smart Deck is gated correctly

`load-smart-deck-page.ts` checks `workflow-state` first and only mounts the
workspace when `canOpenSmartDeck === true`.

This is correct.

It prevents half-built generated slides from being presented as final.

### 2. Smart Deck cards are backed by persisted workspace payloads

`SmartDeckWorkspace.svelte` does not invent local-only card data.

It reads from:

- `workspace`
- `preferences`
- `designVersions`
- `generatedSlides`
- generated slide code lookup

Those shapes come from `SmartDeckWorkspaceResponse`.

### 3. Smart Edit review actions are now canonical at the frontend boundary

The mounted Smart Edit page uses the newer canonical slide-scoped routes for:

- classify
- patch
- run lookup

The review action button path now calls the deck-scoped suggestion proxy:

- `PATCH /api/decks/{deck_id}/smart-edit/suggestions/{suggestion_id}`

The older global accept/reject compatibility routes still exist, but the mounted
product page no longer depends on them.

### 4. Persistent fields are the current Smart Edit source of truth

The page loader reads:

- `persistent-fields`
- one selected `persistent-field`
- `workflow-state`

That means the Smart Edit cards are currently anchored to persistent-field
contracts, not to a separate temporary in-browser model.

### 5. Due Diligence now hits the canonical product contract

The mounted Due Diligence page now loads and runs against:

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence/run`

It no longer depends on the audience-conversion translation shim at the
frontend boundary.

### 6. Export is mounted and workflow-backed

The mounted Export page loads persisted export history and submits generation
through the export workflow command path. User-file release is still
admin-controlled, but generation, polling, persisted history, and download
handoff are wired.

### 7. Contract drift is the biggest current weakness

The code still carries multiple tolerated shapes such as:

- camelCase and snake_case variants
- workspace fallback payloads
- compatibility route responses
- diagnostics-only fallback workspace models

This keeps the UI alive, but it also makes it easier for a broken contract to
look superficially mounted.

## Production judgment

### Verified as real product wiring

- mounted Smart Deck route
- mounted Smart Edit route
- mounted Due Diligence route
- mounted Export route
- authenticated frontend proxy layer
- backend product and `/api/decks/*` endpoints
- DB-backed workspace, version, slide, run, and export tables

### Still needs discipline

- do not judge success only from render
- do not create alternate product copies in admin
- keep diagnostics on product pages, but keep operator controls outside product
- reduce fallback response shapes over time

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

## File ownership references

Frontend route owner:

- `src/lib/server/load-smart-deck-page.ts`

Frontend Smart Deck runtime:

- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`

Frontend Smart Edit runtime:

- `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte`
- `src/routes/(product)/decks/[deckId]/smart-edit/+page.server.ts`

Backend Smart Deck route owner:

- `app/api/routes/smart_deck.py`

Backend Smart Edit route owner:

- `app/api/routes/decks.py`

Backend product field/workflow owner:

- `app/api/routes/deck_intake.py`
- `app/api/routes/deck_workflow.py`

Backend DB contract:

- `app/db/models/entities.py`
