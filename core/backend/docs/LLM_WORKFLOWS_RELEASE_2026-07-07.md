# LLM Workflows Release 2026-07-07

## Scope

This release turns DeckAiStack into a real multi-workflow LLM product rather than a prompt-only or placeholder UI layer.

## Included

- Provider-backed Deck Map analysis
- Provider-backed Market Research analysis
- First-class Smart Edit classify and patch workflows
- Audience Conversion workflow as the real backend identity behind the Due Diligence product surface
- Prompt package loader and prompt package directory structure
- Pgvector-backed `vector_chunks` memory layer
- Canonical deck intelligence aggregation and persistence
- Post-deploy verification and smoke scripts
- Route-level tests for Smart Edit, Due Diligence, and Audience Conversion workflows

## Backend Highlights

- `app/services/llm/prompt_package_loader.py`
- `app/services/llm/embedding_service.py`
- `app/services/llm/deck_chunking_service.py`
- `app/services/llm/vector_retrieval_service.py`
- `app/services/llm/audience_conversion_service.py`
- `app/services/llm/canonical_deck_intelligence_service.py`
- `app/api/routes/decks.py` audience-conversion and workflow endpoints
- `app/api/routes/deck_map.py` canonical-deck-intelligence endpoints
- `alembic/versions/0038_vector_chunks_pgvector.py`

## Canonical Flow

1. Deck Map produces canonical deck understanding.
2. Audience Conversion adapts the deck for a diligence audience.
3. Market Research grounds or challenges market claims.
4. Canonical Deck Intelligence aggregates the latest upstream artifacts.
5. Smart Deck and Smart Edit consume that canonical object.

## Operational Notes

- Production still fails clearly when provider credentials are missing.
- Embeddings degrade clearly when unavailable.
- LangChain is still intentionally not part of the product architecture.

## Verification

- Python syntax checks across new services and route tests
- Prompt package verification
- Embedding pipeline verification
- Workflow route tests
- Post-deploy workflow verifier script

## Durable evidence contract

- Due Diligence chat POSTs require a stable `clientExchangeKey`; retries replay
  the persisted assistant message rather than creating another exchange.
- Conversations are bound to deck, authenticated user, and normalized audience;
  the Due Diligence workspace returns at most 40 persisted messages.
- Market Research v2 exposes `sources`, claim-level `citationIds`, and
  `citationStatus`. Source URLs must be absolute HTTP(S), contain no credentials
  or control characters, and persisted v1 reports read as explicit no-source
  reports rather than receiving invented citations.
# Due Diligence chat exchange reservation

Due Diligence chat now commits an exchange reservation before provider work.
Core PostgreSQL uniquely identifies keyed exchanges by deck, artifact type,
user, audience, and client exchange key. Completed requests replay the stored
reply/provider/model; concurrent pending requests wait briefly; stale pending
owners can be recovered. Nullable identity columns preserve legacy artifacts
and requests without a client-supplied key receive a server-generated key.
