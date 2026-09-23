# Deck AI Stack - Backend Agent Guide

## Project Overview
FastAPI backend for the Deck AI-powered pitch deck analysis platform. Processes PDF/PPTX uploads, extracts structure, generates AI-powered Smart Deck slides, and manages workspace-level LLM provider configuration.

## Stack
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL via SQLAlchemy ORM
- **LLM Providers**: OpenAI (primary), Qwen/DashScope, Anthropic, OpenRouter
- **Embeddings**: OpenAI text-embedding-3-small (primary), DashScope text-embedding-v3
- **Deployment**: Railway

## Architecture

### Core Directories
- `app/api/routes/` — FastAPI route handlers
- `app/services/` — Business logic layer
- `app/services/llm/` — LLM provider integrations
- `app/ai_orchestration/` — AI provider resolution and orchestration
- `app/core/config.py` — Settings and environment configuration
- `app/db/models.py` — SQLAlchemy ORM models
- `app/schemas/` — Pydantic request/response schemas
- `app/agents/` — Agent utilities (LLM agent utils, etc.)

### LLM Provider System

The backend supports 4 LLM providers. **OpenAI is the default production provider.**

Provider resolution order:
1. `OpenAiLlmProvider` — OpenAI direct (`gpt-5`, `gpt-4.1`)
2. `DashScopeLlmProvider` — Qwen/Alibaba DashScope (`qwen3.7-plus`, `qwen-plus`, `qwen-max`)
3. `OpenRouterLlmProvider` — OpenRouter routing
4. `AnthropicLlmProvider` — Anthropic direct (`claude-sonnet-4-5`, `claude-opus-4-1`)

**Important**: `"qwen"` and `"dashscope"` are interchangeable provider identifiers. Code that checks `provider in {"openai", "openrouter", "anthropic"}` MUST also include `"dashscope"` to avoid silent failures.

#### Qwen Strategy (v1.0.0+)

The Qwen strategy implements explicit model routing for each operation type:

| Operation | Model | Env Variable |
|-----------|-------|--------------|
| Generation | `qwen3.7-plus` | `QWEN_MODEL` |
| Critique | `qwen-plus` (fallback: generation model) | `QWEN_CRITIQUE_MODEL` |
| Repair | `qwen-turbo` (fallback: generation model) | `QWEN_REPAIR_MODEL` |
| Embedding | `text-embedding-v3` | `QWEN_EMBEDDING_MODEL` |
| Vision | (env-controlled) | `QWEN_VISION_MODEL` |

Key features:
- **Token accounting**: Per-request usage tracking (input/output tokens, latency, error category)
- **Quota limits**: `QWEN_MAX_TOKENS_PER_JOB`, `QWEN_MAX_TOKENS_PER_WORKSPACE_DAY`
- **Retry logic**: Exponential backoff with non-retryable error classification (auth/quota)
- **Fallback**: Disabled by default. Set `QWEN_FALLBACK_PROVIDER` and `QWEN_FALLBACK_MODEL` to enable
- **Health monitoring**: `/admin/llm/health` includes Qwen status with redacted secrets

Key files:
- `app/services/llm/dashscope_provider.py` — Chat completion + embedding calls to DashScope with token accounting
- `app/services/llm/qwen_strategy.py` — Canonical routing policy, token usage, quota, health
- `app/ai_orchestration/providers/dashscope_provider.py` — `DashScopeLlmProvider` class for orchestration
- `app/ai_orchestration/provider_resolver.py` — Provider resolution from workspace config or env
- `app/services/platform/shell/workspace_ai_provider_service.py` — User-facing provider config CRUD

### Environment Variables

```bash
# Primary LLM provider (OpenAI)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-2025-08-07

# Instant Deck whole-document HTML byte budget (separate from provider tokens)
INSTANT_HTML_WHOLE_DECK_MAX_BYTES=512000  # Canonical range: 64000-800000
# Optional deployment cap for NEW operations, in cents. Omit for no per-deck
# dollar cap. Existing explicit operation limits remain unchanged. Request-count,
# token, deadline, usage accounting, and product quota policies still apply.
# INSTANT_HTML_MAX_OPERATION_COST_CENTS=500
# One generation plus one validation repair. Any other value is invalid.
INSTANT_HTML_MAX_PROVIDER_STARTS=2
# Set by the release process to bake the reviewed commit into the image.
# DECK_BUILD_COMMIT=<full commit SHA>
# Legacy alias: INSTANT_HTML_MAX_OUTPUT_BYTES. Values through the former
# 1000000 maximum remain accepted and normalize to the safe 800000 ceiling;
# prefer INSTANT_HTML_WHOLE_DECK_MAX_BYTES for all new configuration.

# Explicitly selectable Qwen/DashScope provider and specialized vision settings
QWEN_API_KEY=                    # Primary API key
DASHSCOPE_API_KEY=               # Legacy alias
QWEN_MODEL=qwen3.7-plus          # Default generation model
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
DASHSCOPE_WORKSPACE_ID=          # Optional workspace ID

# Qwen strategy — separate model routing
DECK_LLM_PROVIDER=dashscope      # Provider identifier
DECK_LLM_STRATEGY=qwen_native    # Strategy name
QWEN_CRITIQUE_MODEL=             # Falls back to QWEN_MODEL
QWEN_REPAIR_MODEL=               # Falls back to QWEN_MODEL
QWEN_EMBEDDING_MODEL=text-embedding-v3
QWEN_VISION_MODEL=               # Optional vision model
QWEN_TEMPERATURE=0.3
QWEN_MAX_RETRIES=2
QWEN_MAX_OUTPUT_TOKENS=8192

# Quota limits
QWEN_MAX_TOKENS_PER_JOB=200000
QWEN_MAX_TOKENS_PER_WORKSPACE_DAY=2000000
QWEN_MAX_REPAIR_ATTEMPTS=1

# AI-VC cost caps are optional. Omit them for uncapped-but-metered execution.
# Zero from a legacy deployment normalizes to no cap; it is never a feature switch.
# INSTANT_HTML_VC_RESEARCH_MAX_COST_CENTS=500
# INSTANT_HTML_VC_MEMO_MAX_COST_CENTS=500
# AI_VC_MAX_TOTAL_COST_CENTS=1000
# INSTANT_HTML_FACTUAL_REVIEW_MAX_COST_CENTS=1000

# Paid visual-intelligence nodes are independently opt-in. A cap never enables one.
AI_VC_VISUAL_PLANNING_ENABLED=false
AI_VC_IMAGE_GENERATION_ENABLED=false
AI_VC_VISION_REVIEW_ENABLED=false
AI_VC_VISUAL_REPAIR_ENABLED=false
# AI_VC_VISUAL_PLANNING_MAX_COST_CENTS=500
# AI_VC_IMAGE_GENERATION_MAX_COST_CENTS=2000
# AI_VC_VISION_REVIEW_MAX_COST_CENTS=500
# AI_VC_VISUAL_REPAIR_MAX_COST_CENTS=500
AI_VC_MAX_VISUAL_REPAIR_PASSES=1

# Fallback (disabled by default)
QWEN_FALLBACK_PROVIDER=          # e.g., openrouter
QWEN_FALLBACK_MODEL=             # e.g., openai/gpt-4o

# Other LLM providers
OPENROUTER_API_KEY=              # OpenRouter (secondary)
ANTHROPIC_API_KEY=               # Anthropic direct (tertiary)

# Generation mode (defaults to OpenAI)
DECK_GENERATION_MODE=openai

# Embedding (OpenAI primary, stored at the existing vector dimension)
EMBEDDING_PROVIDER=openai        # or dashscope, openrouter
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1024

# Frontend
DECK_FRONTEND_URL=http://localhost:5173
DECK_JWT_SECRET=                 # Auth secret
```

### Existing Smart Deck pipeline (Instant Deck beta path below)

1. **Upload** → `create_first_deck_upload()` in `app/services/deck_workflow_service.py`
2. **Source extraction** → `queue_source_extraction()` → workflow job created
3. **Structure extraction** → `extract_and_persist_deck_structure()` (deterministic)
4. **Brand extraction** → `extract_brand_profile()`
5. **LLM generation** → `queue_smart_deck_generation()` → async workflow job
6. **Rendering** → `render_all_generated_slides()` (optional)
7. **Export** → PowerPoint/PDF export

### Key Service Files

- `app/services/llm/generation_service.py` — LLM slide generation (provider dispatch, prompt building, render schema validation)
- `app/services/llm/qwen_strategy.py` — Qwen routing policy, token accounting, quota limits, health
- `app/services/llm/embedding_service.py` — Embedding vector generation
- `app/services/llm/source_enrichment.py` — Source slide enrichment with LLM
- `app/services/llm/audience_diligence_service.py` — Audience analysis
- `app/services/deck_processing/workflow_orchestration.py` — Workflow job management
- `app/services/admin/operations.py` — Admin operations (retry, cancel, discard)
- `app/services/admin/product_spine_health.py` — Health checks

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/ -v

# Type check (if using mypy)
mypy app/
```

## Code Conventions

- Pydantic v2 for all schemas (`model_config = ConfigDict(extra="forbid")`)
- SQLAlchemy 2.0 style with `Mapped` type annotations
- All route handlers use `Depends()` for auth/db injection
- Provider errors are masked in production — never expose raw provider errors to frontend
- Security audit events recorded for all state-changing operations
- All LLM calls must use the existing provider transports and their durable request/cost accounting. The Instant Deck designer and factual reviewer use the canonical OpenAI transport; do not add ad hoc SDK calls or a new agent framework.
- The authorized AI-VC intelligence layer may use pinned LangGraph/LangChain infrastructure under `app/services/ai_vc/`. It is an internal coordinator/adapter only: all provider calls still use Deck V2 transports and durable accounting, and all product state remains application-owned.
- AI-VC/IC critique is advisory. Persist concerns, missing proof, objections, weak slides and recommended changes, but never use investment quality alone as a generation/publication/export gate. Factual, provenance, calculation, security, compilation and render validation remain blocking authorities.
- AI-VC owns the capital-raising thesis, investor questions, narrative architecture, output slide count and visual intent. Company evidence, current cited research, and semantically retrieved product knowledge inform that decision in separate lanes. Product knowledge and embeddings are advisory context, never a source-count formula, rigid template, company fact, or publication gate.
- Visual intelligence lives under `app/services/visual_intelligence/` as versioned, application-owned artifacts. The LLM may propose visual meaning and intent, but charts require finite validated values plus calculation IDs, diagrams use deterministic geometry, and generated images never establish evidence. Do not special-case an evaluation fixture or allow visual/vision review to bypass factual or render gates.
- Whole-deck design is an advisory-stack handoff, not a raw model response. The active designer prompt must consume the persisted investment memo, evidence-classed financial analysis, advisory IC findings, current research, product methodology, brand authority and visual briefs; it must privately audit and improve the complete draft before returning HTML. Persist final rendered-pixel investor-quality findings and repair recommendations as internal artifacts. They remain advisory and never block an otherwise factual, safe and technically valid export.

## Canonical Architecture Rules

### Render Contract
- The canonical render output is `html_compiled.v1` (full HTML slide).
- `DesignVersion` is the canonical product artifact; the backend must persist the truthful state of what was generated.
- Instant source publication validates extracted page records and contiguous source page numbers; source thumbnails are disabled and never gate canonical completion. Generated HTML browser validation remains a separate required publication check.
- Preview rendering and source-preview ownership are separate contracts; do not collapse without shared renderer + migration tests.
- Probabilistic reasoning lives in the LLM; reference resolution, identities, source bindings, accounting and state changes are application-owned and versioned.

### LLM / RAG Layer
- `ContextMode` enum (`retriever_service.py`) controls vector retrieval: `slide_generation` (mandatory) vs `full_deck` (optional/skipped).
- Instant Deck full-deck generation must NOT require vector retrieval; use `build_full_deck_generation_context()` instead of `build_slide_generation_retrieval_context()`.
- Vector retrieval remains mandatory for Smart Deck slide generation and element variation.
- Embeddings are search infrastructure, not deck generation transport.

### Config Consolidation
- S3/storage credentials: prefer `effective_s3_access_key` / `effective_s3_secret_key` properties over direct field access.
- Qwen/DashScope: use `effective_qwen_*` properties; legacy `dashscope_*` fields are retained for backward compatibility only.
- Never add new env var aliases without updating this file and the config consolidation properties.

### Provider Error Handling
- `OpenAIResponseMalformed` extends `ValueError` for backward compatibility.
- Use typed exceptions (`OpenAIResponseMalformed`, `OpenAIResponseFailed`, `OpenAIResponseRefusal`, `OpenAIResponseIncomplete`) instead of generic `ValueError`.
- `provider_errors.py` classifies errors for retry/durable-boundary decisions.

## Active Instant Deck beta path

- `INSTANT_HTML_LLM_FIRST_BETA=true` selects the whole-deck investor HTML designer and separate factual reviewer. `INSTANT_HTML_FACTUAL_REVIEW_ENABLED=true` remains mandatory for this safety path. Its cost cap is optional; omitted means uncapped but metered.
- The upload workflow supplies the VC/investor audience. New VC redesigns run bounded public research and persist an evidence-referenced AI-VC strategy before the immutable designer request is created. The recovered structured planner remains supported for historical versioned requests; do not silently substitute it for the AI-VC strategy contract.
- Real worker path: `handle_instant_deck_generation` → `create_generation_job` → `generate_instant_deck` → `_prepare_candidate` → factual review → full compilation → existing isolated proof/publication/export.
- `instant_html_review_candidate.prepare_candidate` produces an inert quarantined claim inventory, not a renderable or publishable deck. It may attach exact canonical matches and unambiguous source-cover identities, never unrelated facts. Preserve sanitizer allowlists and all final grounding/contrast gates.
- The reviewer compares generated text/claims against original PDF pages and evidence. It does not inspect rendered charts. Material factual findings block publication; minor presentation suggestions do not alone cause terminal failure. The UI must show review findings and a useful next action.
- Permit only the existing bounded correction and verification phases. Two designer starts are separate from up to two review/verification requests; report token and cost accounting accurately even when no dollar cap is configured. Never reset historical operations or modify saved provider responses to make a comparison pass.
- Persist retrieval/context/grounding diagnostics as internal `DeckLlmArtifact` records. Public workflow status may expose safe counts and state only; never copy source prose, provider bodies, or internal critique into public status.
- Preserve numerical value, currency, unit, period, qualifier, meaning and actual/projected status. Distinguish structural presentation counts from company metrics; digits appearing elsewhere are not supporting evidence. Synthetic fixture content must stay in tests.
- Source images may use bounded aspect-preserving derivatives; keep original bytes immutable and retain provenance. Compilation, HTTP success and synthetic rendering do not establish real-deck numerical or visual quality.

### Live MVP recovery and acceptance

- PDF extraction persists observed span-font usage separately from reconstructed
  text blocks. Canonical branding consumes that evidence before website font
  fallback; verify actual renderer fonts, not only candidate names.
- Keep the existing whole-deck context path for Instant Deck. AI-VC research is
  a separate verified evidence lane; do not activate vector retrieval or a
  recovered planner as a substitute for the persisted investment strategy.
- Review states distinguish reviewing, correcting, verifying and needs_review.
  Owner-visible draft text is inert and is not a publication/render artifact.
  Historical checkpoint text reads retain ownership validation and audit records.
- New versioned uncertainty handling may expose an exact source quotation with a
  visible clarification notice. It must not reconcile contradictory source facts,
  invent values, or bypass final factual verification, compilation and render proof.
- Acceptance means a real deployed upload, visible draft/review, useful redesign,
  reopening and product PDF export. Offline test success alone is insufficient.
