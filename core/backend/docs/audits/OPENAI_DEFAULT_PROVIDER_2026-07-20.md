# OpenAI Default Provider Wiring Audit

Date: 2026-07-20
Decision: OpenAI is the default production generation and embedding provider.

## End-To-End Ownership

| File | Ownership | Inputs | Outputs / next hop |
|---|---|---|---|
| `app/core/config.py` | owns behavior | Railway `OPENAI_API_KEY`, `OPENAI_MODEL`, `DECK_GENERATION_MODE`, `EMBEDDING_PROVIDER`, and `EMBEDDING_MODEL` | validated runtime settings for API and LLM-capable workers |
| `app/services/llm/generation_service.py` | owns behavior | deck/workspace settings plus default provider settings | resolved OpenAI provider/model/key source for Smart Deck, Smart Edit, and diligence services |
| `app/services/llm/source_enrichment.py` | owns behavior | selected generation mode | OpenAI-backed source-label enrichment request |
| `app/ai_orchestration/provider_resolver.py` | translates contract | platform mode or same-provider workspace credential | concrete OpenAI provider adapter; legacy orchestration route remains compatibility-only |
| `app/services/llm/openai_provider.py` | owns behavior | resolved model, prompts, and API key | OpenAI Responses API payload and extracted text |
| `app/services/llm/embedding_service.py` | owns behavior and persists derived data through callers | OpenAI embedding model and key | 1024-dimensional vectors compatible with the existing AI database |
| `app/api/routes/health.py` | translates contract | selected provider configuration | redacted product-readiness provider/model status |

The canonical user action still enters through the mounted frontend product route,
passes through the product-scoped SvelteKit proxy and FastAPI workflow command, is
claimed by the existing durable worker, resolves OpenAI in the backend service, and
persists the resulting workflow/design artifacts before the frontend renders them.
No alternate product route or worker was added.

## Concrete Breakpoints Found

1. Railway initially had `OPENAI_API_KEY` only on `deck-backend-api`. The same
   existing secret is now attached through stdin to generation, Due Diligence,
   source-pipeline, and DB-publisher workers; no secret value was printed.
2. A bounded OpenAI Responses API probe authenticated but returned HTTP 429 with
   provider type/code `insufficient_quota`. Billing/quota must be enabled before live
   generation can succeed.
3. `WORKSPACE_AI_FERNET_KEY` on `deck-backend-api` was configured with length 29 and
   failed Fernet validation. All LLM workers shared one valid established key and
   version, so those existing values were restored to the API through stdin. A
   Railway-backed application settings load now passes startup validation.
4. The code previously allowed an existing Qwen key to override OpenAI for source
   enrichment and reported Qwen as the fixed product-readiness dependency. Those
   boundaries now follow the selected default provider.

## Verification

- expanded OpenAI/model/vision/embedding/workflow suite: 81 passed
- production contract verifier: passed
- production workflow contract: `READY`, no blockers or warnings
- Python compileall: passed
- `git diff --check`: passed
- bounded provider probe: reached OpenAI and returned HTTP 429
  `insufficient_quota`; credential content was never printed

## Runtime Completion Gates

- Enable OpenAI account/project billing or quota for the configured key.
- OpenAI secret coverage and non-secret provider settings are aligned across the API
  and LLM-capable workers.
- The API now shares the established worker Fernet key/version and passes settings
  startup validation.
- Deploy current backend `main`, verify OpenAI in `/api/health/product-ready`, and run
  one authenticated workflow through generation, persistence, and rendered reload.
