# Smart Deck source LLM enrichment runtime

## Purpose

This document records how source-level LLM enrichment runs after `original_source_v1` extraction.

The pipeline has two layers:

1. Deterministic extraction creates source slides, blocks, thumbnails, and a safe baseline.
2. Optional LLM enrichment classifies those existing records and writes only validated labels through backend services.

## Runtime controls

```bash
SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED=true
SMART_DECK_SOURCE_LLM_MAX_TOKENS=2048
```

If `SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED=false`, the system keeps deterministic labels only.

If no configured provider key is available, the system keeps deterministic labels only and records the missing-provider status in the source run/artifacts.

## Provider selection

The source enrichment service follows the existing backend provider settings:

```bash
DECK_GENERATION_MODE=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
```

Supported modes:

- `openrouter`
- `openai`
- `claude` / `anthropic`

## Persistence contract

The LLM never writes directly to the database.

The backend:

1. calls the provider;
2. parses JSON;
3. validates slide and block ids against DB records;
4. writes validated labels to existing columns;
5. writes provider/model/status into `DeckGenerationRun.generated_deck_json`;
6. writes the normalized payload into `DeckLlmArtifact`.

## Existing DB fields used

- `DeckSlide.semantic_slide_type`
- `DeckSlide.summary`
- `DeckSlide.metadata_json`
- `DeckSlideBlock.block_kind`
- `DeckSlideBlock.semantic_role`
- `DeckSlideBlock.text`
- `DeckSlideBlock.content_hash`
- `DeckSlideBlock.metadata_json`
- `DeckGenerationRun.provider`
- `DeckGenerationRun.model`
- `DeckGenerationRun.generated_deck_json`
- `DeckLlmArtifact.payload_json`

No migration is required.
