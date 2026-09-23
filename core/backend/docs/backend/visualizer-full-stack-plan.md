# Smart Deck visualizer full-stack plan

Status: completed

This document defines the full-stack plan for making the Smart Deck visualizer load slides reliably.
The renderer itself is not the main problem. The main problem is the contract that feeds the renderer:

- backend must publish a valid visualizer payload
- frontend must consume that payload from one source of truth
- asset URLs must resolve through the app, not through ad hoc direct paths
- slide loading must be coordinated with workflow readiness

## What the product needs from the visualizer

The visualizer should load these surfaces in Smart Deck:

- source slides from the uploaded deck
- miniature/thumbnail previews for those source slides
- generated slides for the current design version
- selected element highlighting
- brand tokens and brand asset previews when available

The renderer should not guess where data comes from.
It should receive a backend-published payload and draw from it.

## What the current visualizer is doing wrong

The current setup is fragile because the data flow is split across multiple assumptions:

- the frontend renderer only works when `renderSchema` is already present
- image assets only render when their URLs are already valid and routable
- Smart Deck readiness is inferred from several fields instead of one canonical payload
- source slides, generated slides, and brand assets are loaded from different paths
- the app can end up rendering a shell before the backend has published all visualizer inputs

In practice, this means the visualizer can fail even when the deck itself exists.
The fix is to make the backend publish a single visualizer contract and make the frontend consume that contract only.

## RAG layer output for this product

The RAG layer should not return raw unstructured text as the final product output.
Its output should be a grounded retrieval package that can feed Smart Deck and the visualizer.

Expected RAG output:

- answer text
- source citations
- retrieval trace
- confidence or fallback reason
- deck-scoped metadata
- source version references

That output is useful for Smart Deck context and slide generation, but the visualizer still needs a separate rendering contract.

## Backend responsibilities

### 1. Publish a canonical visualizer payload

The backend should publish one payload that contains:

- deck readiness state
- source slides
- generated slides
- render schemas
- asset references
- brand references
- selected slide IDs
- selected generated slide IDs
- active design version ID

Suggested shape:

- `workflow-state`
- `smart-deck-workspace`
- `visualizer-state`

### 2. Guarantee asset resolution

Every asset the visualizer uses must be accessible through a stable backend route.

Required routes:

- deck source preview assets
- brand asset binary downloads
- generated slide thumbnails
- rendered preview assets

No visualizer component should rely on opaque local paths or inconsistent frontend-only path guessing.

### 3. Produce render schema after validation

The backend must only publish render schemas after they are validated.

That means:

- schema generation
- schema validation
- preview rendering
- publisher state update

If validation fails, the visualizer should receive a failure state with a clear reason instead of partial data.

### 4. Keep slide loading versioned

The backend should attach version metadata to all visualizer data:

- source deck version
- design version
- generated slide version
- preview render version

This prevents the visualizer from mixing stale source slides with newer generated slides.

## Frontend responsibilities

### 1. Use one source of truth

The frontend should stop inferring readiness from scattered fields.
It should read one backend payload and decide:

- can the visualizer mount
- should it show source slides
- should it show generated slides
- should it show a fallback state

### 2. Make the renderer resilient

The renderer should:

- show an empty state when `renderSchema` is missing
- show a broken-asset fallback when an image URL fails
- not crash if a single image cannot load
- keep text, shapes, and background layers renderable independently

### 3. Load assets through backend routes

The frontend should use backend-backed routes for:

- source thumbnails
- brand assets
- rendered previews
- generated slide imagery

That keeps the browser from depending on a direct file path that may not exist in production.

### 4. Remove redundant local inference

The frontend should not:

- infer visualizer readiness from 3 different endpoints
- recompute source slide readiness on its own
- guess whether a deck is ready based on partial data

## Backend service map

### Existing services that matter

- `app/services/deck_workflow_service.py`
- `app/services/smart_deck_llm_service.py`
- `app/services/smart_deck_prompt_builder.py`
- `app/services/smart_deck_retriever_service.py`
- `app/services/deck_preview_service.py`
- `app/services/brand_extraction_service.py`
- `app/services/deck_processing_visibility_service.py`

### Services to extend

- `app/services/smart_deck_llm_service.py`
  - publish render schema and generated slide payloads
- `app/services/deck_workflow_service.py`
  - expose visualizer readiness in one place
- `app/services/deck_preview_service.py`
  - make preview assets canonical and idempotent
- `app/services/brand_extraction_service.py`
  - make brand asset URLs and fallbacks reliable

### Backend API surfaces to keep aligned

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`
- `GET /api/workflow-jobs/{job_id}`
- smart deck workspace payload routes
- brand asset proxy routes
- source preview / thumbnail routes

## Frontend file map

### Visualizer component layer

- `src/lib/components/smart-deck/DeckVisualizerSurface.svelte`
- `src/lib/components/smart-deck/GeneratedSlideRenderer.svelte`
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`
- `src/lib/components/smart-deck/DeckDesignShellCard.svelte`
- `src/lib/components/smart-deck/SourceEnrichmentStatusCard.svelte`

### Smart Deck page layer

- `src/routes/(app)/decks/[deckId]/smart-deck/+page.svelte`
- `src/routes/(app)/decks/[deckId]/smart-deck/+page.server.ts`

### Data contract layer

- `src/lib/api/smartDeckWorkspace.ts`
- `src/lib/contracts/constants.ts`
- `src/lib/server/backendApi.ts`

## Full-stack load flow

1. upload deck
2. run source extraction
3. generate miniatures
4. extract brand context
5. build Smart Deck context
6. publish workflow state
7. validate render schema
8. publish visualizer-ready slide payload
9. mount Smart Deck
10. render source slides and generated slides
11. load asset URLs through backend routes
12. allow selection and editing

## Failure modes to eliminate

- missing `renderSchema`
- image URLs that point to local or invalid paths
- source slides that are present but not mounted
- generated slides that exist but are not published
- deck ready state that is inferred from stale fields
- visualizer component errors caused by a single bad asset

## Fix plan

### Phase 1

- make the backend publish one visualizer-ready payload
- make asset routes canonical
- make render schema validation explicit

### Phase 2

- make the frontend read only the canonical payload
- add graceful fallbacks for missing schema or missing assets
- remove redundant readiness inference

### Phase 3

- wire source slides and generated slides into the same visualizer surface
- verify that Smart Deck opens only after the backend says the payload is ready
- add logs and observability for every missing asset or failed schema

## Acceptance criteria

- source slides load in Smart Deck
- generated slides load in Smart Deck
- missing assets do not crash the visualizer
- brand assets resolve through backend routes
- the page opens only after the backend publishes readiness
- the renderer receives a valid schema or a clear fallback state

## Bottom line

The visualizer is not a frontend-only bug.
It is a contract problem between:

- the workflow state
- the generated render schema
- the asset routes
- the frontend mount logic

Fix the contract first, then the renderer becomes straightforward.

## Completion note

This plan is complete as the reusable visualizer contract for Smart Deck.
The shared surface is now the expected path for Smart Deck, Smart Edit, and Due Diligence.
Use `DeckVisualizerSurface` as the canonical wrapper around the existing Smart Deck renderer layer.

The implementation surface should stay shared across Smart Deck, Smart Edit, and Due Diligence:

- `src/lib/components/smart-deck/GeneratedSlideRenderer.svelte`
- `src/lib/components/smart-deck/DeckDesignShellCard.svelte`
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`

The rule is simple:

- one backend-published payload
- one backend-backed asset path
- one frontend rendering surface
- no duplicated slide-loading logic in feature pages

If a page cannot load slides, fix the contract or the backend asset route first.
Do not fork a second renderer surface for the same deck data.
