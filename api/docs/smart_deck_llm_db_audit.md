# Smart Deck LLM DB audit

## What already works

- Deck upload saves the source file before Smart Deck processing starts.
- Deterministic extraction creates source slides, source blocks, assets, thumbnails, and `DeckExtractionRun` rows.
- `original_source_v1` source versions are written with existing tables: `DeckGenerationWorkspace`, `DeckGenerationRun`, and `DeckSlideVersion`.
- LLM-ready artifacts are already persisted in `DeckLlmArtifact`.
- No new database columns are required for source semantic enrichment because the existing schema already has:
  - `DeckSlide.semantic_slide_type`
  - `DeckSlide.summary`
  - `DeckSlide.metadata_json`
  - `DeckSlideBlock.block_kind`
  - `DeckSlideBlock.semantic_role`
  - `DeckSlideBlock.text`
  - `DeckSlideBlock.content_hash`
  - `DeckSlideBlock.metadata_json`
  - `DeckGenerationRun.generated_deck_json`
  - `DeckLlmArtifact.payload_json`

## Weakness fixed in this PR

Before this PR, the source V1 baseline was deterministic only. The LLM prompt/context artifact existed, but the source-ingestion path did not call the configured provider or persist validated LLM semantic labels into the DB.

This PR adds a controlled LLM enrichment step:

1. Build deterministic source context.
2. Build the source-enrichment prompt.
3. Call the configured provider when enabled and available.
4. Parse the provider JSON response.
5. Validate slide and block ids against the extracted source DB records.
6. Persist only validated labels to the existing DB columns.
7. Save the provider/model/status and validated output into `DeckGenerationRun.generated_deck_json` and `DeckLlmArtifact`.
8. Fall back to deterministic labels if no provider is available, enrichment is disabled, the provider fails, or the output fails validation.

## Safety boundary

The LLM does not write directly to the database. It returns JSON only. The backend validates and persists the normalized result.

## Runtime controls

- `SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED=false` disables the LLM source-enrichment call.
- `SMART_DECK_SOURCE_LLM_MAX_TOKENS` controls the enrichment response budget.
- Provider selection follows `DECK_GENERATION_MODE` and the existing provider keys:
  - `OPENROUTER_API_KEY`
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`

## No migration required

This PR does not add DB columns or migrations. It uses existing schema capacity for semantic labels, metadata, run output, and artifacts.
