# Smart Deck Generation Product Contract

## Goal

Backend generation should support a user-facing Smart Deck product flow, not expose infrastructure as the primary UX.

## Contract

- Smart Deck generation persists a canonical `design_version`
- Generated slide render schema is persisted on:
  - `generated_slides.render_schema_json`
  - `generated_slide_code_versions.render_schema_json`
- Workflow job detail for generation-related jobs returns hydrated:
  - `designVersion`
  - `workspace`
- Due Diligence full-deck generation reuses this endpoint with typed `provenance`:
  `mode=due_diligence_full_deck`, `audience`, optional `audienceArtifactId`, and
  `diligenceArtifactIds`. Every referenced artifact is validated as deck-owned.
- Selected-slide redesign includes `taskContext` in its idempotency identity and
  validates selected slides and returned design versions against the deck.
- `visionExecution.executed` is true only when the generation worker records a
  real vision call; generic workflow completion never implies vision execution.
- `background_vision` is rejected before queueing unless the selected source has
  a readable image and the configured provider has an explicit vision path.
- Due Diligence provenance is revalidated at route, durable queue, and worker
  boundaries for deck ownership, expected artifact type, ready status, and
  audience consistency.

## Non-Blocking Design Context

- Brand extraction is optional for Smart Deck generation. It must not block source processing, miniature readiness, Smart Deck activation, or LLM generation.
- Generation requests may include `designContext`. The backend preserves this field from route input through workflow job input into the LLM context.
- `designContext` is visual guidance only. It is not factual evidence and must not override `sourceFactPackage` claim rules.
- Visual guidance fallback order is:
  - `brand_profile`
  - `logo`
  - `company_url`
  - `presentation`
  - `default_presentation`
- The durable workflow queue owns Smart Deck readiness conflicts. Route-level compatibility seams must not add duplicate pre-queue readiness gates.

## Iteration history

- The backend mirrors each generated `design_version` into iteration history (`design_batch`) so existing iteration surfaces work.
- Iteration history is trimmed to the latest 3 records per deck.

## Parallelization rule

- `LLM_PARALLELIZATION_MODE=python|pyspark`
- Default is `python`
- PySpark is optional and internal
- LLM parallelization endpoints are super-admin only
