# Component Wiring Audit - 2026-07-19

## Durable Deck intelligence

### `app/api/routes/deck_map.py`

- Purpose: owns authenticated Deck Map and Market Research product commands.
- Entry points: `POST /deck-map/analyze` and `POST /market-research`.
- Inputs: user-owned deck ID.
- Outputs: HTTP 202 `WorkflowCommandAcceptedResponse` receipts.
- Coupling: `queue_deck_intelligence_job`; synchronous provider execution is
  preserved in comments and disabled at the HTTP boundary.

### `workflow_orchestration.py` and `deck_intelligence_runtime.py`

- Purpose: enqueue, deduplicate, execute, and persist the intelligence jobs.
- Inputs: completed Smart Deck context, deck ID, requesting user, job type.
- Outputs: workflow dependency, job output, persisted artifact correlation.
- Worker owner: the existing `llm_generation` worker claims generation, Deck Map,
  and Market Research command types.

## Deck media

### `app/api/routes/deck_media.py`

- Purpose: owns upload, list, content, thumbnail, patch, archive, and retry HTTP
  boundaries for deck-scoped media.
- Inputs: authenticated deck ownership, bounded raster upload, media role.
- Outputs: persisted `DeckMediaAsset` contracts and media-processing receipts.
- Coupling: media service, upload storage, workflow jobs.

### `DeckMediaAsset`, migrations, and `media_runtime.py`

- Purpose: persist media state and process uploads outside the request path.
- Inputs: storage path, checksum, MIME type, media ID.
- Outputs: validated dimensions, colors, ready/failure state, workflow output.
- Worker owner: the existing deployed generation worker also claims
  `media_processing`, preventing uploaded media from remaining permanently queued.

### Generation and Smart Edit services

- Purpose: add bounded ready-media context to generation and Smart Edit prompts.
- Inputs: ready, non-archived, LLM-enabled media for the current deck.
- Outputs: `deck-media-context.v1` in the provider context; failures degrade to an
  empty media context without blocking deck work.

## Supporting contracts

- Brand profile update creates a manual profile when extraction has not produced
  one yet.
- Explicit OpenAI environment routing is honored only when the selected generation
  mode is OpenAI; Qwen remains the default.
- Workflow schemas, job-type constraints, handlers, and migrations include Deck
  Map, Market Research, and media-processing identities.

## Verification

- Focused durable intelligence/media/brand/diligence/Smart Edit tests: passed.
- Production workflow contract: `READY`, no blockers or warnings.
- Alembic graph: one head at `20260717_0003_deck_media_library`.
- Full focused suite and production contract must be repeated after merging current
  main.
