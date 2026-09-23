# DeckAiStack LLM Product Diagnosis

## Current State

### Real provider-backed workflows
- Smart Deck generation uses real provider calls through OpenAI, OpenRouter, and Anthropic.
- Smart Edit patch workflow is exposed and persists reviewable artifacts.
- Deck Map analysis is exposed and persists structured artifacts.
- Market Research is exposed and persists structured artifacts.
- Due Diligence currently exists as a workflow report surface, but the intended product direction is audience conversion.

### Persistence
- LLM outputs persist through `DeckLlmArtifact`.
- Smart Edit patches, Deck Map analyses, Market Research reports, and Due Diligence workflow outputs are persisted.
- Artifact history is now visible in the frontend and reusable through shared artifact UI.

### Retrieval and memory
- The product now has explicit vector memory via `vector_chunks` and pgvector.
- Chunking currently covers deck summary, slide text, slide block, brand profile, accepted edits, deck-map analysis, market research, and diligence claims.
- Vector retrieval is used in Deck Map, Smart Edit, Market Research, and Due Diligence workflow services.

## Missing Pieces

- Due Diligence is still modeled primarily as a report workflow instead of a first-class audience-conversion workflow.
- `audience_conversion_service.py` and `/audience-conversion/*` routes are not yet the canonical backend path.
- Market Research is still mainly deck-based interpretation. It does not yet use trusted external market sources or citations.
- Deck Map is conceptually canonical, but downstream workflows do not yet uniformly consume one shared canonical deck intelligence artifact contract.

## Why Due Diligence Should Be Audience Conversion

In DeckAiStack, the user goal is not only to generate a static diligence report. The product goal is to convert the uploaded deck for a specific audience's diligence expectations.

That means the workflow should answer:
- what this audience cares about
- what objections they will raise
- what evidence is missing for this audience
- how the deck should change slide-by-slide
- whether a new deck version should be generated from that conversion plan

The correct backend mental model is:

`uploaded deck -> canonical deck understanding -> audience conversion analysis -> Smart Deck generation / Smart Edit patching`

## LangChain Recommendation

LangChain is not required as the product architecture.

Recommended position:
- LangChain may be used narrowly for internal chunking/retrieval helpers if it materially reduces code.
- DeckAiStack services should remain the product architecture.

The product architecture should stay:

`workflow service -> retrieve context -> load prompt package -> call provider -> validate schema -> persist artifact -> return UI-ready object`

## Embeddings Recommendation

Embeddings are the correct next memory layer for DeckAiStack.

Why:
- prompt-only context assembly sends too much or the wrong context
- keyword matching is brittle
- accepted edits, audience lenses, and prior analyses need semantic reuse

Recommended embedded chunk types:
- `deck_summary`
- `slide_raw_text`
- `slide_block`
- `deck_map_analysis`
- `market_research`
- `audience_profile`
- `diligence_lens`
- `accepted_edit`
- `generated_version`
- `brand_profile`

## LoRA / Fine-Tuning Recommendation

Do not start with LoRA or model fine-tuning yet.

The immediate gains are more likely to come from:
- better prompt packages
- stronger retrieval
- stronger schema validation
- critique and repair
- artifact reuse

LoRA or fine-tuning becomes useful only after:
- enough accepted Smart Edit patches exist
- enough Smart Deck generations can be scored
- enough audience-conversion examples are curated

## Encoder / Decoder / Transformer in DeckAiStack

Practical explanation for this app:

- Encoder:
  turns deck text, slides, audience lenses, and accepted edits into embeddings
- Decoder:
  the LLM generates structured JSON, slide patches, market analysis, and conversion plans
- Transformer:
  the underlying model architecture behind both embeddings and generation
- Embeddings:
  the semantic memory/search layer
- Prompt packages:
  the instruction layer
- Schemas:
  the control layer
- Critique / repair:
  the quality layer

DeckAiStack should use existing models, not build its own transformer.

## Implementation Plan

1. Keep provider orchestration custom.
2. Keep prompt packages in `app/llm/prompt_packages/`.
3. Keep vector memory explicit via pgvector and `vector_chunks`.
4. Make Deck Map the canonical deck understanding artifact.
5. Replace the Due Diligence backend identity with Audience Conversion.
6. Feed Smart Deck from Deck Map + Audience Conversion plan.
7. Keep Smart Edit reviewable and never silently apply AI changes.
8. Keep all workflows schema-valid and artifact-persisted.

## Acceptance Criteria

1. A deck upload can produce canonical deck understanding.
2. Deck Map persists reusable deck intelligence.
3. Smart Edit produces reviewable patches.
4. Market Research produces structured market output with clear confidence limits.
5. Due Diligence evolves into audience conversion rather than static reporting.
6. Vector retrieval is used in at least Deck Map, Smart Edit, and audience-facing conversion workflows.
7. All outputs are persisted and reloadable in the frontend.
8. Missing provider credentials fail clearly in production.

## Current Recommendation

The next major architecture correction should be:

`due_diligence_service.py -> audience_conversion_service.py`

while keeping the current frontend label if needed for user familiarity.
