# Product Spine Cleanup Plan

## Stage 1 — Audit: Current Reality

### TL;DR for the Product Owner

The backend has a working product spine but it is obscured by heavyweight services that do too many things. `smart_deck_llm_service.py` (4400+ lines) mixes AI provider config, workspace CRUD, source fact building, LLM context assembly, design version management, assistant runs, and design tokens. `brand_extraction_service.py` (1400 lines) mixes its own HTTP fetching, HTML parsing, color science, and persistence. Processing routes are duplicated across 3+ files. LLM provider calls are scattered across 12 files with two incompatible abstraction layers. The plan below prunes, splits, and merges until each spine stage has exactly one owner.

---

### 1. Current Files Used by Each Product Spine Stage

#### PHASE A — Source Readiness Spine

| Stage | Primary File(s) | Spine Wrapper | Handler | Notes |
|-------|----------------|---------------|---------|-------|
| **1. Source Ingestion** | `app/workers/source_pipeline_runtime.py` (line 17: `handle_source_ingestion`) | `app/services/deck_processing/source_ingestion.py` | `source_pipeline_runtime.handle_source_ingestion` | Thin — just marks file saved |
| **2. Source Extraction** | `app/services/pdf_deck_extraction_service.py` + `app/services/deck_extractors/*` (5 files) | `app/services/deck_processing/source_extraction.py` | `source_pipeline_runtime.handle_source_extraction` | Extraction is cleanly separated; persistence is in `source_structure_persistence.py` |
| **3. Miniatures** | `app/services/deck_processing/source_preview_renderer.py` + `source_preview_persistence.py` | `app/services/visualizer/miniature_service.py` | `source_pipeline_runtime.handle_miniatures` | Also: `deck_preview_service.py` (overlaps), `slide_thumbnail_service.py` (pdftoppm variant) |
| **4. Brand Extraction** | `app/services/brand_extraction_service.py` (1406 lines) | `app/services/deck_processing/brand_extraction.py` | `source_pipeline_runtime.handle_brand_extraction` | Self-contained mini-system with own HTTP, HTML, color science |
| **5. Smart Deck Context** | `app/services/smart_deck_job_service.py` + `smart_deck_source_enrichment_service.py` + `smart_deck_artifact_writer.py` + `smart_deck_output_validation.py` + `smart_deck_prompt_builder.py` | `app/services/deck_processing/smart_deck_context.py` | `source_pipeline_runtime.handle_smart_deck_context` | Splits across 5 files — can merge into one context service |
| **6. DB Publisher** | `app/workers/publisher_runtime.py` | `app/services/deck_processing/readiness_publisher.py` | `publisher_runtime.handle_db_publisher` | Clean, thin |
| **7. Workflow-state** | `app/services/deck_processing/workflow_state_read_model.py` (761 lines) | N/A (read model, not a stage) | N/A | Returns 12 stages, but `compile_final_deck` is missing; `llm_parallelization` is missing from DB constraint |
| **8. Visualizer** | `app/services/visualizer/slide_read_model.py` (397 lines) | N/A (read model) | N/A | Loads source slides, previews, assets for frontend display |

#### PHASE B — Generation Spine

| Stage | Primary File(s) | Spine Wrapper | Handler | Notes |
|-------|----------------|---------------|---------|-------|
| **9. LLM Generation** | `app/services/smart_deck_llm_service.py` (4400+ lines) | `app/services/llm/generation_service.py` | `generation_runtime.handle_llm_generation` | Massively overloaded service; mixes config, context, CRUD, generation |
| **10. LLM Parallelization** | `app/services/llm_parallelization_service.py` + `app/workers/llm_parallelization_runtime.py` | N/A | `llm_parallelization_runtime.handle_llm_parallelization` | Standalone; DB constraint missing for `llm_parallelization` job type |
| **11. Schema Validation** | `app/services/generation/validate_generated_deck.py` + `generated_deck_schema.py` | N/A | `generation_runtime.handle_schema_validation` | Minimal validation — needs to be more robust |
| **12. Preview Render** | Embedded in `generation_runtime` | N/A | `generation_runtime.handle_preview_render` | Handled by generation runtime; no dedicated service |
| **13. Apply Version** | `app/services/smart_deck_llm_service.py` (scattered) | N/A | `generation_runtime.handle_apply_version` | Mixed into large service |
| **14. Export** | `app/services/export_service.py` (143 lines) | N/A | `publisher_runtime.handle_export` | Clean, thin — good |

---

### 2. Duplicate Services / Workers / Routes Per Stage

**Miniatures duplication:**
- `deck_preview_service.extract_source_previews()` — orchestrates rendering + persistence (154 lines)
- `slide_thumbnail_service.render_pdf_page_thumbnail()` — pdftoppm variant (83 lines)
- `source_preview_renderer.render_source_preview_page()` — PyMuPDF variant (82 lines)
- `source_preview_persistence.persist_source_preview()` — DB persistence
- `visualizer/miniature_service.py` — spine wrapper re-exporting `extract_source_previews`

**Brand extraction — two code paths exist:**
- `brand_extraction_service.py` (1406 lines) — full brand extraction with URL scraping, logo upload, palette generation
- `deck_processing/brand_extraction.py` (51 lines) — pipeline wrapper that calls `brand_extraction_service`
- `brand_loader_service.py` (161 lines) — creates fallback profile (separate entry point)
- `brand_enrichment_service.py` (246 lines) — post-extraction enrichment

**Processing routes (3+ duplicates for `/processing`):**
- `deck_intake.py` line 44: GET `/products/deck-aistack-codes/decks/{deck_id}/processing`
- `products.py` line 298: GET `/products/deck-aistack-codes/decks/{deck_id}/processing`
- `product_runtime_hardening.py` line 209: GET `/products/deck-aistack-codes/decks/{deck_id}/processing`
- `admin_operations.py` line 476: GET `/admin/decks/{deck_id}/processing`

**Smart Deck start routes (2 duplicates):**
- `products.py` line 311: POST `/products/deck-aistack-codes/decks/{deck_id}/smart-deck/start`
- `upload_rescue.py` line 186: POST `/products/deck-aistack-codes/decks/{deck_id}/smart-deck/start`

**Export routes (2 duplicates):**
- `decks.py` lines 779, 822, 836: POST/GET `/decks/{deck_id}/export(s)(/{export_id}/download)`
- `exports.py` lines 18, 28, 125: POST/GET `/decks/{deck_id}/export(s)(/{export_id}/download)`

**Smart Deck assistant runs (2 paths):**
- `assistant.py` line 234: POST `/assistant/runs` (generic assistant)
- `smart_deck.py` line 712: POST `/decks/{deck_id}/smart-deck/assistant-runs` (deck-scoped)

**LLM provider code duplicated across:**
- `app/ai/llm_provider.py` — canonical Anthropic implementation
- `app/ai/anthropic_provider.py` — backward-compat re-export shim
- `app/ai/openai_provider.py` — OpenAI implementation
- `app/ai/openrouter_provider.py` — OpenRouter implementation
- `app/ai_orchestration/providers/base.py` — BaseLlmProvider protocol
- `app/ai_orchestration/providers/anthropic_provider.py` — AnthropicLlmProvider
- `app/ai_orchestration/providers/openai_provider.py` — OpenAiLlmProvider
- (NO OpenRouterLlmProvider at orchestration layer)

**Functions duplicated across files:**
- `load_deck_llm_artifact_payload` — in both `slide_read_model.py` and `smart_deck_llm_service.py` (resolved via lazy import)
- `list_design_tokens` — in both `slide_read_model.py` and `smart_deck_llm_service.py` (resolved via lazy import)
- `_map_design_token` — in both `slide_read_model.py` and `smart_deck_llm_service.py` (still duplicated)

---

### 3. File Classification: KEEP / SPLIT / MERGE / PRUNE LATER

#### KEEP (clean, single-ownership, stays as-is)

| File | Reason |
|------|--------|
| `deck_processing/workflow_state_read_model.py` | Core frontend contract for processing state |
| `deck_processing/source_structure_read_model.py` | Frontend-facing deck structure read surface |
| `deck_processing/source_structure_persistence.py` | Single owner for extracted structure persistence |
| `deck_processing/source_preview_renderer.py` | Single owner for PDF->PNG rendering |
| `deck_processing/source_preview_persistence.py` | Single owner for preview DB persistence |
| `deck_processing/source_ingestion.py` | Clean spine wrapper |
| `deck_processing/source_pipeline.py` | Clean spine wrapper for queueing |
| `deck_processing/readiness_publisher.py` | Clean spine wrapper |
| `visualizer/slide_read_model.py` | Read-only frontend contract for deck/slide/preview data |
| `visualizer/preview_asset_service.py` | Clean spine wrapper for signed URLs |
| `workers/worker_entrypoint.py` | Clean dispatch |
| `workers/deck_queue_worker.py` | Core worker loop |
| `workers/source_pipeline_runtime.py` | Handler runtime for source pipeline |
| `workers/publisher_runtime.py` | Handler runtime for publish/export |
| `workers/generation_runtime.py` | Handler runtime for generation pipeline |
| `workers/stale_job_rescuer_worker.py` | Recovery-only worker |
| `workflow_job_service.py` | Job type constants, dependency wiring |
| `export_service.py` | Clean export service |
| `bucket_artifact_service.py` | Storage abstraction |
| `upload_service.py` | Clean upload service |
| `upload_storage.py` | Storage abstraction |

#### SPLIT (one file has multiple concerns)

| File | Concern 1 | Concern 2 | Plan |
|------|-----------|-----------|------|
| `smart_deck_llm_service.py` (4400+ lines) | Provider config, workspace CRUD, source facts | Design versions, assistant runs, element variations, design tokens | Split generation/assistant/config concerns into separate files under `llm/` |
| `brand_extraction_service.py` (1406 lines) | Brand extraction logic | HTTP fetching, HTML parsing, color science, persistence | Split: keep extraction in `services/brand_extraction.py`; move HTTP/HTML/color helpers |
| `deck_mutation_service.py` (345 lines) | Deck CRUD | Block patching, suggestion patching, analysis pipeline | Keep CRUD; move analysis pipeline to its own service |

#### MERGE (multiple files doing the same thing)

| Files | Merge into | Reason |
|-------|-----------|--------|
| `slide_thumbnail_service.py` + `source_preview_renderer.py` + `deck_preview_service.py` | `rendering/source_preview_renderer.py` | All render PDF page previews; three implementations doing the same job |
| `visualizer/miniature_service.py` + `deck_preview_service.py` | `visualizer/miniature_service.py` `->` re-export from `source_preview_renderer` | Spine wrapper + orchestrator — merge into one |
| `app/ai/*` + `app/ai_orchestration/providers/*` | `llm/provider_registry.py` + `llm/provider_base.py` | Two incompatible abstraction layers; merge into one provider-neutral interface |
| `smart_deck_source_enrichment_service.py` + `smart_deck_artifact_writer.py` + `smart_deck_output_validation.py` + `smart_deck_prompt_builder.py` | `llm/context_service.py` or keep in `services/smart_deck_context_service.py` | All serve Smart Deck context preparation — split from LLM service |
| `llm_parallelization_service.py` + `llm_parallelization_runtime.py` | `workers/llm_parallelization_runtime.py` | Runtime handler + service — merge |

#### PRUNE LATER (after verification)

| File | Reason |
|------|--------|
| `deck_processing_queue_service.py` (503 lines) | Legacy compatibility — delegates to `workflow_orchestration` |
| `deck_processing_worker_service.py` (475 lines) | Worker runtime — much of this should move into `workflow_job_service.py` or `workers/deck_queue_worker.py` |
| `deck_processing/deck_mutation_service.py` analysis function | Analysis pipeline duplicated in `agents/*` |
| `deck_retention_service.py` | Check if still needed by product |
| `deck_intake_service.py` | Overlaps with `workflow_state_read_model` + `orchestration` |
| `deck_preview_service.py` | Merged into miniatures |
| `slide_thumbnail_service.py` | Merged into miniatures |

#### LEGACY UNKNOWN (needs product owner decision)

| File | Question |
|------|----------|
| `app/services/generation/claude/claude_generate_slides.py` | Is `claude_generate_slides.py` actively used or replaced by orchestrator? |
| `app/services/generation/openai/openai_generate_slides.py` | Is `openai_generate_slides.py` actively used or replaced by orchestrator? |
| `app/services/smart_edit_service.py` | Is Smart Edit still a product feature or legacy? |
| `app/services/smart_deck_retriever_service.py` | Is retriever used directly or only via `smart_deck_llm_service`? |
| `app/services/company_profile_service.py` | Used by brand extraction — check if needed independently |
| `app/services/deck_iteration_service.py` | Check if still needed |

---

### 4. Which Stage Currently Marks Readiness

**DB Publisher stage** (`JOB_TYPE_DB_PUBLISHER = "db_publisher"`) is the **sole** stage that marks readiness. It is the only job type allowed to set `published_phase` on a `WorkflowJob` record.

The `published_phase` values and their meanings:
- `smart_deck_ready` — all source pipeline complete; Smart Deck can open
- `preview_ready` — generation + schema validation + preview render complete
- `applied` — design version applied
- `export_ready` — export complete

`canOpenSmartDeck` becomes `True` only when `published_phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready"}`.

**Flow:** `source_ingestion → source_extraction → miniatures → smart_deck_context → db_publisher (smart_deck_ready) → brand_extraction` (runs in parallel after db_publisher)

---

### 5. Which Stage Currently Renders Source Previews

**Miniatures stage** (`JOB_TYPE_MINIATURES = "miniatures"`) renders source previews. But there are 3 implementations:

| Implementation | Tool | Used By | Status |
|---------------|------|---------|--------|
| `source_preview_renderer.py` | PyMuPDF (`fitz`) | Primary — called from `source_pipeline_runtime.handle_miniatures` | ACTIVE |
| `slide_thumbnail_service.py` | `pdftoppm` | Called from `source_extraction_runtime` for thumbnail generation | LEGACY |
| `deck_preview_service.py` | PyMuPDF | Called from `extract_source_previews()` via `/decks/{deck_id}/process` or standalone | DUPLICATE of `source_preview_renderer` |

**Recommendation:** Keep `source_preview_renderer.py` as the canonical implementation; remove `slide_thumbnail_service.py` and `deck_preview_service.py` after verifying no callers depend on them.

---

### 6. Which Stage Currently Renders Generated Previews

**Preview Render stage** (`JOB_TYPE_PREVIEW_RENDER = "preview_render"`) renders generated slide previews. 

The handler is `generation_runtime.handle_preview_render`. It runs after `schema_validation` completes and before `db_publisher (preview_ready)`.

Generated preview assets are stored in the bucket artifact service and served via signed URLs from `visualizer/slide_read_model.py` `_map_slide()`.

---

### 7. Which Stage Currently Prepares Smart Deck Context

**Smart Deck Context stage** (`JOB_TYPE_SMART_DECK_CONTEXT = "smart_deck_context"`) prepares the Smart Deck workspace.

The handler `source_pipeline_runtime.handle_smart_deck_context` calls:
1. `smart_deck_job_service.prepare_smart_deck_source_workspace()` — creates workspace, slides, LLM enrichment
2. `smart_deck_source_enrichment_service.enrich_source_labels_with_llm()` — LLM enrichment of labels
3. `smart_deck_artifact_writer.write_source_v1_artifacts()` — writes context artifacts
4. `smart_deck_prompt_builder` — builds prompt context

This is the most fragmented stage — 5 files serve one purpose. They should be merged into a single `llm/context_service.py`.

---

### 8. LLM Code: Provider-Specific Scatter

**Provider-specific calls are scattered across 12 files** with two incompatible abstraction layers:

**Abstraction Layer 1: `app/ai/provider.py` (`AIProvider` Protocol)**
- `complete(system, user) -> dict[str, str]` method
- Implementations: `AnthropicProvider`, `OpenAIProvider`, `OpenRouterProvider`
- **Not used anywhere** outside `app/ai/` — dead code at application level

**Abstraction Layer 2: `app/ai_orchestration/providers/base.py` (`BaseLlmProvider` Protocol)**
- `generate_slide_versions(context) -> LlmGenerationOutput` method
- Implementations: `AnthropicLlmProvider`, `OpenAiLlmProvider`
- NO `OpenRouterLlmProvider` implementation
- Used by `provider_resolver.py` and `orchestrator.py`

**Direct provider calls (not through any abstraction):**

| Location | What It Does | Provider |
|----------|-------------|----------|
| `smart_deck_llm_service.py:_call_anthropic_render_payload` | Calls Anthropic for slide render | Anthropic |
| `smart_deck_llm_service.py:_call_openai_render_payload` | Calls OpenAI for slide render | OpenAI |
| `smart_deck_llm_service.py:_call_openrouter_render_payload` | Calls OpenRouter for slide render | OpenRouter |
| `smart_deck_llm_service.py:_call_anthropic_assistant_insight` | Calls Anthropic for assistant insight | Anthropic |
| `smart_deck_llm_service.py:_call_openai_assistant_insight` | Calls OpenAI for assistant insight | OpenAI |
| `smart_deck_llm_service.py:_call_openrouter_assistant_insight` | Calls OpenRouter for assistant insight | OpenRouter |
| `smart_deck_source_enrichment_service.py:_call_provider` | Calls LLM for source label enrichment | All 3 |
| `llm_agent_utils.py:complete_json_with_ai_provider` | Calls LLM for structured JSON | All 3 |
| `workspace_ai_provider_service.py:_validate_*_connection` | Validates provider credentials | All 3 |
| `claude/claude_generate_slides.py:generate_slides_with_claude` | Claude-specific slide generation | Anthropic |
| `openai/openai_generate_slides.py:generate_slides_with_openai` | OpenAI-specific slide generation | OpenAI |

**Key issues:**
1. No single `LLMProvider.generate()` abstraction used across the codebase
2. Anthropic has retry logic; OpenAI and OpenRouter do not
3. No `OpenRouterLlmProvider` in `ai_orchestration` layer
4. `app/ai/anthropic_provider.py` is a redundant re-export shim for `app/ai/llm_provider.py`

---

### 9. Frontend Endpoints That Depend on Backend Contracts

| Endpoint | Response Key | Used For |
|----------|-------------|----------|
| `GET /products/deck-aistack-codes/decks/{deck_id}/workflow-state` | `canOpenSmartDeck`, `phases`/`stages`, `blockingReason`, `nextAction` | Processing page, Smart Deck enable gate |
| `GET /products/deck-aistack-codes/decks/{deck_id}/processing` | `canOpenSmartDeck`, `state`, `nextAction` | Processing page visibility |
| `GET /decks/{deck_id}` | Full deck with slides, blocks, assets, artifacts | Smart Deck visualizer |
| `GET /decks/{deck_id}/slides/{slide_id}/preview` | Image (preview) | Source slide previews in visualizer |
| `GET /decks/{deck_id}/smart-deck` | `workspace`, `preferences`, `selection` | Smart Deck page |
| `POST /decks/{deck_id}/smart-deck/generation-jobs` | `jobId` | Generate slides |
| `GET /decks/{deck_id}/smart-deck/generation-jobs/{job_id}` | `status`, `generatedSlides`, `renderableSchemas` | Poll generation |
| `POST /decks/{deck_id}/design-versions/{version_id}/apply` | `status` | Apply version |
| `POST /decks/{deck_id}/export` | `exportId` | Export deck |
| `GET /decks/{deck_id}/exports/{export_id}/download` | File | Download export |
| `GET /decks/{deck_id}/design-tokens` | `designTokens` | Visualizer styling |
| `GET /decks/{deck_id}/design-versions` | `designVersions` | Version history |

---

### 10. Exact Verification Commands

```bash
# Full test suite (pre-existing failures are known and tracked)
cd /home/phoenix/Documents/andrea-projects-workspace/rescue-DECK/deck-backend-rescue
/tmp/venv-deck/bin/python -m pytest tests/ -q 2>&1 | tail -5

# Compile check for all modified files
/tmp/venv-deck/bin/python -m py_compile app/services/deck_processing/workflow_state_read_model.py

# Check for any import errors
/tmp/venv-deck/bin/python -c "from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state; print('workflow_state OK')"

# Verify canOpenSmartDeck contract
/tmp/venv-deck/bin/python -m pytest tests/test_smart_deck_readiness_contract.py -v -q 2>&1 | tail -5

# Verify source extraction pipeline
/tmp/venv-deck/bin/python -m pytest tests/test_source_extraction_pipeline_contract.py -v -q 2>&1 | tail -5

# Verify LLM provider resolution
/tmp/venv-deck/bin/python -c "from app.services.smart_deck_llm_service import get_generation_provider_config; print('provider config OK')"

# Verify visualizer loads
/tmp/venv-deck/bin/python -c "from app.services.visualizer.slide_read_model import get_deck; print('visualizer OK')"

# Verify all workers compile
/tmp/venv-deck/bin/python -c "from app.workers.worker_entrypoint import main; print('worker_entrypoint OK')"

# Check git status is clean of unintended changes
git status --short
```

---

## Stage 2 — Plan: Make workflow-state Match the Product Spine

### Current state
`workflow_state_read_model.py` returns 12 stages in `stages`/`phases` array, but each stage has only `{key, label, description, status, active, completed}` — no `started_at`, `completed_at`, `error`, `blocking_for_visualizer`, `blocking_for_export`.

### Target state
Each stage must have:
```python
{
    "key": "source_ingestion",
    "status": "completed",       # pending / active / completed / failed
    "started_at": "2024-01-01...",  # ISO timestamp or None
    "completed_at": "2024-01-01...",  # ISO timestamp or None
    "error": None,                # {code, message, recoverable, nextAction} or None
    "blocking_for_visualizer": False,  # True if this stage blocks frontend visualizer
    "blocking_for_export": False,      # True if this stage blocks export
}
```

### Changes needed
1. Modify `_workflow_job_phases()` to return enriched stage objects
2. Add `blocking_for_visualizer` and `blocking_for_export` logic
3. Brand extraction: `blocking_for_visualizer = False` (unless explicitly configured)
4. Ensure `llm_parallelization` is added to DB check constraint
5. Ensure `compile_final_deck` is added to `ordered_job_types` or documented as UI-only

---

## Stage 3 — Plan: Source Readiness Cleanup

### Single ownership rules
| Responsibility | Current owner(s) | Target owner |
|---------------|-----------------|--------------|
| Extract structure | `pdf_deck_extraction_service`, `deck_extractors/*` | `deck_processing/source_extraction.py` -> `pdf_deck_extraction_service` |
| Render source previews | `source_preview_renderer`, `slide_thumbnail_service`, `deck_preview_service` | `deck_processing/source_preview_renderer.py` |
| Persist source previews | `source_preview_persistence` | `deck_processing/source_preview_persistence.py` |
| Extract brand profile | `brand_extraction_service`, `brand_loader_service`, `brand_enrichment_service` | `services/brand_extraction_service.py` (trimmed) |
| Prepare Smart Deck context | `smart_deck_job_service`, `smart_deck_source_enrichment`, `smart_deck_artifact_writer`, `smart_deck_output_validation`, `smart_deck_prompt_builder` | `services/smart_deck_context_service.py` (merged) |
| Mark source readiness | `readiness_publisher` -> `publisher_runtime` | `deck_processing/readiness_publisher.py` |
| Tell frontend canOpenSmartDeck | `workflow_state_read_model` | `deck_processing/workflow_state_read_model.py` |

### Non-blocking brand extraction
Currently `brand_extraction` is AFTER `db_publisher` in `SOURCE_PIPELINE_JOB_SEQUENCE` — it already does not block `canOpenSmartDeck`. However, the visualizer should open even if brand extraction is pending or failed.

### Cleanup actions
1. Keep `source_preview_renderer.py` as canonical; deprecate `slide_thumbnail_service.py` and `deck_preview_service.py`
2. Ensure `brand_extraction` stage has `blocking_for_visualizer=false` in workflow-state
3. Ensure `canOpenSmartDeck` is controlled ONLY by db_publisher (already is)
4. Remove duplicate `/processing` routes (prune `product_runtime_hardening.py` and `deck_intake.py` versions)

---

## Stage 4 — Plan: LLM Provider Harmonisation

### Target architecture
```
app/services/llm/
  provider_base.py          - LLMProvider abstract base class/Protocol
  provider_registry.py      - ProviderFactory registry
  openai_provider.py        - OpenAI implementation
  anthropic_provider.py     - Anthropic implementation  
  openrouter_provider.py    - OpenRouter implementation
  local_provider.py         - Local (testing) implementation
  generation_service.py     - Spine wrapper that delegates to registry
  response_models.py        - Standardized response types
```

### Migration
1. Create `LLMProvider` abstract base with `generate(system_prompt, user_prompt, model) -> LlmResponse`
2. Move existing provider implementations behind this interface
3. Create `provider_registry` with dynamic registration
4. Replace all `if provider == "anthropic"/"openai"/"openrouter"` chains with `provider_registry.get(provider).generate()`
5. Create `OpenRouterLlmProvider` in orchestration layer
6. Remove `app/ai/anthropic_provider.py` (re-export shim)
7. Remove `app/ai_orchestration/providers/` (replaced by `llm/`)

---

## Stage 5 — Plan: Generation Spine Cleanup

### Single ownership rules
| Responsibility | Current owner(s) | Target owner |
|---------------|-----------------|--------------|
| LLM generation | `smart_deck_llm_service.py` (4400 lines) | `services/llm/generation_service.py` |
| LLM parallelization | `llm_parallelization_service.py` + `llm_parallelization_runtime.py` | `workers/llm_parallelization_runtime.py` |
| Schema validation | `generation/validate_generated_deck.py` + handler | `services/rendering/schema_validation.py` |
| Preview render | generation_runtime handler | `services/rendering/generated_preview_renderer.py` |
| Apply version | smart_deck_llm service (scattered) | `services/rendering/version_apply_service.py` |
| Export | `export_service.py` | `services/rendering/export_service.py` |

### Cleanup actions
1. Extract generation logic from `smart_deck_llm_service.py` into `services/llm/generation_service.py`
2. Extract assistant run logic into `services/llm/assistant_service.py`
3. Extract design version logic into `services/rendering/version_apply_service.py`
4. Keep `smart_deck_llm_service.py` as a backward-compat re-export layer (then remove)
5. Add `llm_parallelization` to DB check constraint
6. Add `compile_final_deck` to ordered_job_types in workflow-state

---

## Stage 6 — Plan: Worker Pruning

### Pruning rules
A worker can be deleted only if ALL conditions are met:
1. No active workflow queues its job type
2. No Railway service uses its WORKER_KIND
3. No route depends on it
4. No visualizer output depends on it
5. No LLM/render/export path depends on it
6. Replacement owner exists and is verified

### Candidate for consolidation
All 13 per-kind wrapper workers follow the same 6-line pattern. They could be consolidated into a single `main.py` that accepts `WORKER_KIND` from environment, but they provide explicit entrypoints for Railway deployment configuration — so keep them unless Railway config is updated.

### Actual pruning candidates
After stages 2-5 are complete:
- `miniatures_worker.py` — if merged with source extraction
- `compile_final_deck_worker.py` — if `compile_final_deck` is not a product requirement
- `stale_job_rescuer_worker.py` — review if still needed (recovery may be handled by main workers)

---

## Stage 7 — Plan: Final Verification

### Full path verification
```bash
# 1. Upload deck
# (manual via frontend or test)

# 2. Processing page shows canonical stages
/tmp/venv-deck/bin/python -c "
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.db.session import SessionLocal
db = SessionLocal()
state = get_deck_workflow_state(db, '<deck_id>')
stages = [s['key'] for s in state['stages']]
assert stages == ['source_ingestion', 'source_extraction', 'miniatures',
                  'brand_extraction', 'smart_deck_context', 'db_publisher',
                  'llm_generation', 'llm_parallelization', 'schema_validation',
                  'preview_render', 'apply_version', 'export']
db.close()
print('Stages match product spine')
"

# 3. Verify canOpenSmartDeck after db_publisher
# (checked by test_smart_deck_readiness_contract.py)

# 4. Verify brand extraction doesn't block visualizer
/tmp/venv-deck/bin/python -c "
state = get_deck_workflow_state(db, '<deck_id>')
brand_stage = [s for s in state['stages'] if s['key'] == 'brand_extraction'][0]
assert brand_stage['blocking_for_visualizer'] == False
print('Brand extraction does not block visualizer')
db.close()
"

# 5. Verify source slides appear in visualizer
# (checked by visualizer contract)

# 6. Run full test suite
/tmp/venv-deck/bin/python -m pytest tests/ -q 2>&1 | tail -5
```
