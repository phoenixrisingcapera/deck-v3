# Backend Code Explainer — Spine Owner Files

## app/schemas/deck_workflow.py

- **Owns:** Canonical workflow job type/status, workflow phase/action/blocking literals, and workflow command/state response schemas.
- **Must not own:** Worker execution logic or DB persistence.
- **Spine stage:** Product workflow contract across upload, source extraction, generation, render, apply, and export.
- **Breaks:** Processing page, Smart Deck workflow-state, worker/admin orchestration responses, and workflow command routes drift from one contract.
- **Verify:** `python3 -c "from app.schemas.deck_workflow import WorkflowJobType, DeckWorkflowStateResponse; print('OK')"`

## app/schemas/deck.py

- **Owns:** Legacy deck route request/patch/export contracts, deck summary schema, Smart Edit create request, and deck status canonicalization for response payloads.
- **Must not own:** Workflow job phase/status vocabulary or generated Smart Deck schema validation.
- **Spine stage:** Legacy deck API compatibility and shared deck mutation inputs.
- **Breaks:** `/api/decks/*` create/upload/edit/export compatibility routes and deck summaries fail validation.
- **Verify:** `python3 -c "from app.schemas.deck import DeckCreate, ExportCreate, SmartEditCreate; print('OK')"`

## app/schemas/analysis.py

- **Owns:** Analysis findings and adaptation suggestion response schemas.
- **Must not own:** Suggestion mutation service logic or deck status vocabulary.
- **Spine stage:** Analysis/adaptation read contracts.
- **Breaks:** Findings and suggestions routes lose response validation.
- **Verify:** `python3 -c "from app.schemas.analysis import AdaptationSuggestionsRouteResponse; print('OK')"`

## app/schemas/smart_edit.py

- **Owns:** Smart Edit run/suggestion response schemas; reuses `SmartEditCreate` from `deck.py`.
- **Must not own:** Smart Edit generation, quota, guardrail, or suggestion persistence logic.
- **Spine stage:** Smart Edit route response contract.
- **Breaks:** Smart Edit create/read routes lose response validation.
- **Verify:** `python3 -c "from app.schemas.smart_edit import SmartEditResponse; print('OK')"`

## app/schemas/block.py, slide.py, export.py, suggestion.py, deck_processing.py

- **Owns:** Nothing active after prune.
- **Must not own:** New compatibility contracts unless an active route imports them and route-order tests prove they are reachable.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; import scans found no direct importers for `block.py`, `slide.py`, or `deck_processing.py`, and the two wrapper importers were updated to canonical owners.
- **Disposition:** PRUNED. `deck_processing.py` was a stale duplicate of workflow concepts now owned by `deck_workflow.py`.

## app/db/base.py

- **Owns:** Shared SQLAlchemy declarative `Base` for all mapped models and Alembic metadata discovery.
- **Must not own:** Engine/session creation or model class definitions.
- **Spine stage:** Persistence foundation across all stages.
- **Breaks:** ORM mappings, test metadata creation, and Alembic metadata loading fail.
- **Verify:** `python3 -c "from app.db.base import Base; print('OK')"`

## app/db/session.py

- **Owns:** Runtime SQLAlchemy engine and `SessionLocal` factory configured from `settings.database_url`.
- **Must not own:** Request-scoped dependency lifecycle or model definitions.
- **Spine stage:** Persistence runtime across API, workers, and scripts.
- **Breaks:** API dependencies, workers, scripts, and health checks cannot open DB sessions.
- **Verify:** `python3 -c "from app.db.session import SessionLocal, engine; print('OK')"`

## app/db/models/entities.py

- **Owns:** SQLAlchemy mapped classes and table metadata for runtime models.
- **Must not own:** Query/business logic, route handlers, or DB session lifecycle.
- **Spine stage:** Persistence schema across all product/platform stages.
- **Breaks:** ORM queries, migrations metadata, table creation in tests, and relationship loading fail.
- **Verify:** `python3 -c "from app.db.models.entities import Deck, User, InterestLead; print('OK')"`

## app/db/models/__init__.py

- **Owns:** Public model import surface used by app code: `from app.db.models import Deck, User, ...`.
- **Must not own:** Separate model definitions beyond re-exporting real mapped classes from `entities.py`.
- **Spine stage:** Persistence import boundary across all stages.
- **Breaks:** Most services, routes, tests, and scripts cannot import model classes.
- **Verify:** `python3 -c "from app.db.models import Deck, User, InterestLead; print('OK')"`

## app/db/models/* one-class shim files

- **Owns:** Nothing active after prune. These files only re-exported classes already defined in `entities.py` and had no direct importers.
- **Must not own:** New SQLAlchemy model definitions; use `entities.py` plus `models/__init__.py` export unless the DB layer is deliberately split again.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; stale direct import scan found no importers before deletion.
- **Disposition:** PRUNED. `InterestLead` was absorbed into `entities.py`; all other deleted model files were re-export shims.

## app/api/deps.py

- **Owns:** FastAPI DB session dependency, bearer-token user resolution, role guards, workspace/deck ownership checks, and resource-access audit hooks.
- **Must not own:** Route business logic or domain service mutations.
- **Spine stage:** API security boundary across all authenticated routes.
- **Breaks:** Authenticated API routes cannot resolve users, enforce resource access, or audit super-admin cross-resource access.
- **Verify:** `python3 -c "from app.api.deps import get_current_user, require_resource_access; print('OK')"`

## app/api/routes/decks.py

- **Owns:** Legacy `/api/decks/*` route surface and the first-registered runtime handlers for upload, analysis, blocks, suggestions, Smart Edit, finalization, status, slides, and export compatibility endpoints.
- **Must not own:** Product workflow routes under `/api/products/deck-aistack-codes/*` except where an older `/api/decks/*` compatibility surface still exists.
- **Spine stage:** Legacy deck API surface and compatibility owner.
- **Breaks:** Older frontend/API clients lose deck CRUD, upload, analysis, block/suggestion mutation, Smart Edit, and export endpoints.
- **Verify:** `python3 -c "from app.api.routes.decks import router, decks_upload, decks_smart_edit; print('OK')"`

## app/api/routes/product/__init__.py

- **Owns:** Product router registry and registration order for `/api/products/deck-aistack-codes/*` routes.
- **Must not own:** Route handlers themselves or admin/public router registration.
- **Spine stage:** Product route composition across upload, processing, Smart Deck, generation, export, and workspace surfaces.
- **Breaks:** Product routes can be omitted or registered in the wrong order, changing which duplicate/hardening handler wins.
- **Verify:** `python3 -c "from app.api.routes.product import PRODUCT_ROUTERS; print(len(PRODUCT_ROUTERS))"`

## app/api/routes/admin/__init__.py

- **Owns:** Admin router registry split between protected admin routers and public failure-ticket reporting.
- **Must not own:** Admin operation implementations or auth dependency logic.
- **Spine stage:** Admin/control-plane route composition.
- **Breaks:** Admin diagnostics/users/readiness/LLM health routes or public failure-ticket report route are not mounted correctly.
- **Verify:** `python3 -c "from app.api.routes.admin import ADMIN_PROTECTED_ROUTERS, ADMIN_PUBLIC_ROUTERS; print('OK')"`

## app/api/routes/analysis.py, blocks.py, smart_edit.py, suggestions.py, uploads.py

- **Owns:** Nothing active after prune. These split route modules were fully shadowed by earlier `app/api/routes/decks.py` registrations for identical method/path pairs.
- **Must not own:** New runtime endpoints unless deliberately reintroduced with unique paths and route-order tests.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; app route introspection showed 0 unique reachable endpoints for each module.
- **Disposition:** PRUNED. Tests that imported these modules now import the actual runtime owner in `app/api/routes/decks.py`.

## app/core/config.py

- **Owns:** Runtime settings, environment-derived defaults, Railway env alias application, DB/auth/storage/provider configuration, and config constants used by app startup, scripts, routes, services, and tests.
- **Must not own:** Business workflow state transitions, worker execution logic, or route-specific response formatting.
- **Spine stage:** Runtime configuration across all stages.
- **Breaks:** API, workers, DB sessions, storage, auth, and provider setup can fail at import/startup time.
- **Verify:** `python3 -c "from app.core.config import settings; print('OK')"`

## app/core/security.py

- **Owns:** Application ID generation, password hashing/verification, JWT creation/decoding, and token constants.
- **Must not own:** Authorization policy, workspace permission checks, or domain-specific IDs beyond prefix generation.
- **Spine stage:** Platform/security support across all stages.
- **Breaks:** Auth, user bootstrap, workflow/job row creation, artifact IDs, and many service mutations fail.
- **Verify:** `python3 -c "from app.core.security import generate_id, create_access_token; print(generate_id('chk'))"`

## app/core/railway_env.py

- **Owns:** Railway/environment variable alias normalization used before settings are loaded by startup scripts, config, checks, and tests.
- **Must not own:** Service-role inference, worker job routing, or deployment command selection.
- **Spine stage:** Railway/runtime startup support.
- **Breaks:** Railway API/worker startup and required-env checks can miss valid aliased variables.
- **Verify:** `python3 -c "from app.core.railway_env import apply_railway_env_aliases; apply_railway_env_aliases(); print('OK')"`

## app/core/workspace_ai_crypto.py

- **Owns:** Deriving the Fernet helper used to encrypt/decrypt workspace AI provider credentials.
- **Must not own:** Provider resolution, workspace provider CRUD, or generation-provider policy.
- **Spine stage:** Platform shell/provider credential support for LLM stages.
- **Breaks:** Workspace-scoped provider credentials cannot be stored/read securely.
- **Verify:** `python3 -c "from app.core.workspace_ai_crypto import get_workspace_ai_fernet; print('OK')"`

## app/core/errors.py

- **Owns:** Nothing active. Pruned after verification; previously defined unused legacy `DeckBackendError` and `NotFoundError` classes.
- **Must not own:** New route/service exception policy unless deliberately revived.
- **Spine stage:** None.
- **Breaks:** No known runtime path; grep found no importers.
- **Disposition:** PRUNED. `python3 -m compileall app scripts tests` passed after deletion.

## app/core/statuses.py

- **Owns:** Nothing active. Pruned after verification; previously defined unused legacy status lists.
- **Must not own:** Current deck lifecycle or workflow job status vocabulary.
- **Spine stage:** None.
- **Breaks:** No known runtime path; grep found no importers.
- **Disposition:** PRUNED. Current deck states are owned by `app/services/deck_processing/state_machine.py`; workflow job statuses by `app/services/deck_processing/workflow_jobs.py`; suggestion statuses by route schema/model vocabulary.

## app/services/platform/auth/*

- **Owns:** Authentication sessions, users, profiles, connected accounts, and workspace bootstrap attached to account identity.
- **Must not own:** Product/deck processing, LLM generation, billing plans, or shell/dashboard read models.
- **Spine stage:** Platform auth outside the 12-stage deck spine.
- **Breaks:** Login/logout, profile, account connection, and admin user management fail.
- **Verify:** `python3 -c "from app.services.platform.auth.user_service import authenticate_user; from app.services.platform.auth.auth_session_service import is_auth_session_active; print('OK')"`

## app/services/platform/billing/*

- **Owns:** Billing plan/subscription read models, AI usage quota enforcement, and route rate limiting.
- **Must not own:** Auth/session identity, provider credential storage, or deck generation logic.
- **Spine stage:** Platform billing/quota outside the 12-stage deck spine.
- **Breaks:** Billing page, quota gates, and route throttling fail.
- **Verify:** `python3 -c "from app.services.platform.billing.billing_service import get_workspace_subscription; from app.services.platform.billing.rate_limit_service import enforce_rate_limit; print('OK')"`

## app/services/platform/shell/*

- **Owns:** Application shell/dashboard data, workspace shell mutations, workspace AI provider settings, Turnstile verification, and public-interest lead capture.
- **Must not own:** Auth token creation, subscription switching, or deck pipeline execution.
- **Spine stage:** Platform shell outside the 12-stage deck spine.
- **Breaks:** Shell/workspace pages, provider settings, Turnstile checks, and public-interest form submission fail.
- **Verify:** `python3 -c "from app.services.platform.shell.shell_service import get_deck_graph; from app.services.platform.shell.workspace_ai_provider_service import get_workspace_ai_provider_summary; print('OK')"`

## app/services/platform/admin/superadmin_client.py

- **Owns:** Superadmin AI stack snapshot client integration used by admin operations.
- **Must not own:** Admin operation orchestration or product-spine diagnostics.
- **Spine stage:** Platform admin outside the 12-stage deck spine.
- **Breaks:** Superadmin-backed AI stack admin snapshot fails.
- **Verify:** `python3 -c "from app.services.platform.admin.superadmin_client import get_superadmin_aistack_snapshot; print('OK')"`

## app/services/brand/brand_extraction.py

- **Owns:** Brand extraction from deck content, company URL, logo, and brand guideline uploads.
- **Must not own:** Workflow readiness, LLM generation, or visualizer rendering.
- **Spine stage:** 6. Brand Extraction.
- **Inputs:** Deck ID, DB session, optional company URL/logo/guidelines.
- **Outputs:** Brand profile payloads and brand asset files.
- **DB/artifacts:** `DeckBrandProfile`, `DeckBrandAsset`, `DeckInputSource`, upload storage.
- **Breaks:** Brand page/status and non-blocking brand context disappear.
- **Verify:** `python3 -c "from app.services.brand.brand_extraction import extract_deck_brand; print('OK')"`

## app/services/brand/brand_profile_persistence.py

- **Owns:** Creating/updating persisted brand profile rows from deck/company inputs.
- **Must not own:** HTTP upload parsing or frontend status projection.
- **Spine stage:** 6. Brand Extraction.
- **Inputs:** Deck, company profile, input sources, brand assets.
- **Outputs:** Persisted `DeckBrandProfile`.
- **DB/artifacts:** `DeckBrandProfile`, `CompanyProfile`, `DeckBrandAsset`.
- **Breaks:** Brand extraction can run but profile save/fallback palette fails.
- **Verify:** `python3 -c "from app.services.brand.brand_profile_persistence import upsert_brand_profile; print('OK')"`

## app/services/brand/brand_read_model.py

- **Owns:** Brand extraction status/read payload for the frontend.
- **Must not own:** Brand mutation or asset upload.
- **Spine stage:** 6. Brand Extraction.
- **Inputs:** Deck ID and DB session.
- **Outputs:** `BrandExtractionStatusResponse`.
- **DB/artifacts:** `Deck`, `DeckBrandProfile`, `DeckBrandAsset`, `DeckInputSource`.
- **Breaks:** Brand extraction progress/status UI fails.
- **Verify:** `python3 -c "from app.services.brand.brand_read_model import get_deck_brand_status; print('OK')"`

## app/services/rendering/schema_validation.py

- **Owns:** Generated-deck schema loading, generated payload validation, and Smart Deck source-label validation.
- **Must not own:** Provider calls or DB persistence.
- **Spine stage:** 9. Schema Validation.
- **Inputs:** Generated JSON or source-label payloads.
- **Outputs:** Validated `GeneratedDeckPayload` or normalized label payload.
- **DB/artifacts:** None.
- **Breaks:** Generated preview/apply pipeline can accept invalid generated payloads or reject valid labels.
- **Verify:** `python3 -c "from app.services.rendering.schema_validation import validate_generated_deck, validate_source_labels; print('OK')"`

## app/services/rendering/render_schema_service.py

- **Owns:** Runtime Smart Deck table repair/bootstrap used by API and workers at startup.
- **Must not own:** Generated deck validation or render image creation.
- **Spine stage:** 9-10 support, Railway runtime safety.
- **Inputs:** DB session/engine via startup bootstrap.
- **Outputs:** Required runtime tables/columns exist.
- **DB/artifacts:** Smart Deck generation/version/feedback tables.
- **Breaks:** Railway API/worker startup can fail against partially migrated production DBs.
- **Verify:** `python3 -c "from app.services.rendering.render_schema_service import ensure_smart_deck_runtime_schema; print('OK')"`

## app/services/rendering/export_service.py

- **Owns:** Export creation, listing, and download payloads.
- **Must not own:** LLM generation or source extraction.
- **Spine stage:** 12. Export.
- **Inputs:** Deck ID, export type, DB session.
- **Outputs:** `DeckExport` rows and downloadable content payloads.
- **DB/artifacts:** `DeckExport`, `CompiledDeck`, `DeckSlide`, `AnalysisFinding`.
- **Breaks:** Export panel cannot create/list/download exports.
- **Verify:** `python3 -c "from app.services.rendering.export_service import create_export; print('OK')"`

## app/services/storage/artifact_storage.py

- **Owns:** Upload/object storage adapter, temp upload handling, local/S3 implementations, and promotion.
- **Must not own:** Route validation, workflow jobs, or preview rendering.
- **Spine stage:** Storage support across Source Ingestion, Miniatures, Preview Render, Export.
- **Inputs:** Relative storage paths and file bytes/paths.
- **Outputs:** `StoredUpload`, signed URLs, object metadata.
- **DB/artifacts:** Filesystem/S3 objects only.
- **Breaks:** Upload, preview persistence, brand assets, and visualizer signed assets fail.
- **Verify:** `python3 -c "from app.services.storage.artifact_storage import get_upload_storage; print('OK')"`

## app/services/storage/signed_urls.py

- **Owns:** Bucket artifact key generation, JSON/blob persistence, deletes, and signed URLs for generated assets.
- **Must not own:** Upload route parsing or DB read models.
- **Spine stage:** Storage support across LLM Generation, Preview Render, Export, Visualizer.
- **Inputs:** User/deck/version/slide IDs, artifact keys, content bytes/JSON.
- **Outputs:** Storage keys, persisted blobs, signed URL strings.
- **DB/artifacts:** Filesystem/S3 objects.
- **Breaks:** Generated previews, LLM artifacts, manifests, and signed visualizer assets fail.
- **Verify:** `python3 -c "from app.services.storage.signed_urls import get_bucket_artifact_service; print('OK')"`

## app/services/storage/bucket_health.py

- **Owns:** Storage pipeline health probe.
- **Must not own:** Admin route formatting or object inventory cleanup.
- **Spine stage:** Storage/admin health.
- **Inputs:** Runtime storage settings.
- **Outputs:** Health dict with config/object/signed-url checks.
- **DB/artifacts:** Temporary health object in configured storage.
- **Breaks:** Admin/deployment readiness cannot diagnose storage failures.
- **Verify:** `python3 -c "from app.services.storage.bucket_health import storage_pipeline_health_check; print('OK')"`

## app/services/admin/diagnostics.py

- **Owns:** Admin storage inventory and stale/orphan storage cleanup diagnostics.
- **Must not own:** User-facing upload or storage adapter implementation.
- **Spine stage:** Admin diagnostics.
- **Inputs:** DB session, storage adapter listing.
- **Outputs:** Inventory/cleanup reports.
- **DB/artifacts:** Reads deck/file/asset tables; may delete stale storage objects when called.
- **Breaks:** Admin storage cleanup and visibility endpoints fail.
- **Verify:** `python3 -c "from app.services.admin.diagnostics import build_storage_inventory; print('OK')"`

## app/services/admin/worker_health.py

- **Owns:** Worker heartbeat write/read model.
- **Must not own:** Worker job execution or queue claiming.
- **Spine stage:** Admin/worker health across all stages.
- **Inputs:** Worker ID/status and DB session.
- **Outputs:** Heartbeat telemetry rows and latest heartbeat projection.
- **DB/artifacts:** `AgentTelemetryEvent`.
- **Breaks:** Processing/workflow-state/admin pages lose worker liveness signals.
- **Verify:** `python3 -c "from app.services.admin.worker_health import record_worker_heartbeat; print('OK')"`

## app/services/admin/product_spine_health.py

- **Owns:** Deployment/product-spine readiness checks.
- **Must not own:** Actual workflow transitions or storage implementation.
- **Spine stage:** Admin health across all product-spine stages.
- **Inputs:** DB session and runtime settings.
- **Outputs:** Readiness report for DB, storage, workers, upload, env, AI provider.
- **DB/artifacts:** `WorkflowJob`, worker heartbeat telemetry.
- **Breaks:** Deployment readiness route and smoke script fail.
- **Verify:** `python3 -c "from app.services.admin.product_spine_health import get_deployment_readiness; print('OK')"`

## app/services/llm/parallelization_service.py

- **Owns:** Splitting selected source slides into LLM parallelization batches.
- **Must not own:** Provider calls, Spark runtime, or workflow job execution.
- **Spine stage:** 8. LLM Parallelization.
- **Inputs:** Deck, selected source slide IDs, prompt, partition count, batch size.
- **Outputs:** Batch plan dict consumed by the parallelization worker.
- **DB/artifacts:** Reads `DeckSlide` and blocks.
- **Breaks:** LLM parallelization worker cannot partition selected source slides.
- **Verify:** `python3 -c "from app.services.llm.parallelization_service import build_llm_parallelization_batches; print('OK')"`

## app/services/deck_processing/workflow_jobs.py

- **Owns:** Workflow job type/status constants, dependency wiring, artifacts, events, and source pipeline ordering.
- **Must not own:** Worker execution loops or frontend workflow-state formatting.
- **Spine stage:** All stages, orchestration contract.
- **Inputs:** Deck/run/job IDs, DB session, payload/artifact dicts.
- **Outputs:** `WorkflowJob`, dependency, event, and artifact rows.
- **DB/artifacts:** `WorkflowJob`, `WorkflowJobDependency`, `WorkflowJobEvent`, `WorkflowJobArtifact`.
- **Breaks:** Workers cannot claim/order/complete canonical product-spine jobs.
- **Verify:** `python3 -c "from app.services.deck_processing.workflow_jobs import SOURCE_PIPELINE_JOB_SEQUENCE; print('OK')"`

## app/services/llm/generation_service.py

- **Owns:** Active Smart Deck LLM generation, assistant runs/messages, provider resolution, design version apply/discard/restore/list, and generated slide persistence.
- **Must not own:** Source extraction, source preview rendering, or worker job claiming.
- **Spine stage:** 7. LLM Generation and 11. Apply Version.
- **Inputs:** Deck ID, generation/apply/assistant payloads, DB session, provider credentials/settings.
- **Outputs:** Generation jobs, design versions, assistant messages/runs, generated slide artifacts.
- **DB/artifacts:** `GenerationJob`, `DesignVersion`, `GeneratedSlide`, `DeckLlmArtifact`, `SmartDeckWorkspace`, bucket artifacts.
- **Breaks:** Smart Deck generation, assistant, generated preview/apply flow, and provider readiness checks fail.
- **Verify:** `python3 -c "from app.services.llm.generation_service import create_generation_job, apply_design_version; print('OK')"`

## app/services/llm/deck_generation_service.py

- **Owns:** Legacy deck-generation workspace/run API service used by the `deck_generation` route.
- **Must not own:** New Smart Deck source pipeline or provider registry internals.
- **Spine stage:** 7. LLM Generation.
- **Inputs:** Deck ID, generation request, feedback request, DB session.
- **Outputs:** Deck generation workspaces/runs/slide versions/feedback events.
- **DB/artifacts:** `DeckGenerationWorkspace`, `DeckGenerationRun`, `DeckSlideVersion`, `DeckFeedbackEvent`.
- **Breaks:** Legacy generation route and slide feedback route fail.
- **Verify:** `python3 -c "from app.services.llm.deck_generation_service import get_deck_generation_workspace; print('OK')"`

## app/services/llm/knowledge_service.py

- **Owns:** LLM knowledge package metadata, task contracts, and health summaries.
- **Must not own:** Route authorization or generation execution.
- **Spine stage:** 7. LLM Generation support/admin health.
- **Inputs:** Local knowledge package loaders.
- **Outputs:** Health/metadata/task contract dicts.
- **DB/artifacts:** None.
- **Breaks:** LLM knowledge admin health checks and metadata attached to generation artifacts fail.
- **Verify:** `python3 -c "from app.services.llm.knowledge_service import get_llm_knowledge_health; print('OK')"`

## app/services/llm/source_enrichment.py

- **Owns:** Optional provider-backed source slide/block semantic label enrichment.
- **Must not own:** DB writes or Smart Deck context persistence.
- **Spine stage:** 4. Smart Deck Context and 7. LLM Generation support.
- **Inputs:** Prompt bundle and known slide/block IDs.
- **Outputs:** Validated enrichment payload or disabled/error status.
- **DB/artifacts:** None.
- **Breaks:** Smart Deck source context falls back to deterministic labels only.
- **Verify:** `python3 -c "from app.services.llm.source_enrichment import enrich_source_labels_with_llm; print('OK')"`

## app/services/deck_processing/smart_deck_context.py

- **Owns:** Preparing the source V1 Smart Deck workspace and artifacts from extracted slides/blocks.
- **Must not own:** LLM generation jobs, DB Publisher readiness, or PDF extraction.
- **Spine stage:** 4. Smart Deck Context.
- **Inputs:** Deck ID, DB session.
- **Outputs:** Smart Deck workspace/source versions/artifacts.
- **DB/artifacts:** `DeckGenerationWorkspace`, `DeckGenerationRun`, `DeckSlideVersion`, `DeckLlmArtifact`.
- **Breaks:** Smart Deck opens without source context/source versions.
- **Verify:** `python3 -c "from app.services.deck_processing.smart_deck_context import prepare_smart_deck_source_workspace; print('OK')"`

## app/services/visualizer/generated_deck_read_model.py

- **Owns:** Frontend-facing generated deck/runtime read model and deck runtime surface helpers.
- **Must not own:** LLM provider calls or workflow job dispatch.
- **Spine stage:** Visualizer/Smart Deck read surface.
- **Inputs:** Deck ID, DB session, mutation payloads for runtime surface actions.
- **Outputs:** Deck graph/runtime payloads and patched block responses.
- **DB/artifacts:** `Deck`, `DeckSlide`, `DeckSlideBlock`, `AnalysisRun`, `AudienceProfile`.
- **Breaks:** Intake/runtime surface pages cannot load or patch generated/source deck data.
- **Verify:** `python3 -c "from app.services.visualizer.generated_deck_read_model import *; print('OK')"`

## app/services/visualizer/workspace_dashboard_read_model.py

- **Owns:** Workspace dashboard cards, recent slides, latest iterations, and deck thumbnail/readiness projections.
- **Must not own:** Canonical deck lifecycle normalization; it should defer to the deck state machine for status interpretation.
- **Spine stage:** Visualizer/dashboard read surface.
- **Breaks:** Dashboard deck cards drift from workflow/deck status truth or lose preview thumbnails.
- **Verify:** `python3 -c "from app.services.visualizer.workspace_dashboard_read_model import get_workspace_dashboard; print('OK')"`

Visualizer note:

- Local legacy deck-status mapping was removed from dashboard status projection in favor of `app.services.deck_processing.state_machine.canonical_deck_state`.

## app/services/rendering/final_deck_service.py

- **Owns:** Final deck compilation, compiled deck read model, and batch slide decisions.
- **Must not own:** LLM provider calls or export download formatting.
- **Spine stage:** 11. Apply Version and 12. Export support.
- **Inputs:** Deck/batch IDs, selected slide decisions, DB session.
- **Outputs:** `CompiledDeck` and `CompiledDeckSlide` rows/read payloads.
- **DB/artifacts:** `CompiledDeck`, `CompiledDeckSlide`, `DesignBatch`, `BatchSlideDecision`.
- **Breaks:** Final deck/compiled deck/export-ready paths fail.
- **Verify:** `python3 -c "from app.services.rendering.final_deck_service import prepare_full_deck; print('OK')"`

## app/services/deck_processing/state_machine.py

- **Owns:** Canonical deck lifecycle states and state transitions.
- **Must not own:** Job dispatch, extraction, or UI projections.
- **Spine stage:** Source ingestion through DB Publisher readiness.
- **Inputs:** Deck row, target state, optional reason/metadata.
- **Outputs:** Updated deck status/state fields and save confirmation side effects.
- **DB/artifacts:** `Deck`, save confirmation records.
- **Breaks:** Upload/readiness gates drift from canonical lifecycle states.
- **Verify:** `python3 -c "from app.services.deck_processing.state_machine import DeckState; print('OK')"`

## app/services/deck_processing/source_extraction.py

- **Owns:** Deterministic PDF structure extraction: page metadata, text, OCR fallback, and embedded images.
- **Must not own:** DB persistence or Smart Deck readiness publication.
- **Spine stage:** 2. Source Extraction.
- **Inputs:** Local PDF path.
- **Outputs:** Extracted deck structure dict.
- **DB/artifacts:** Reads PDF only.
- **Breaks:** No source slides/blocks/assets can be persisted.
- **Verify:** `python3 -c "from app.services.deck_processing.source_extraction import extract_pdf_deck_structure; print('OK')"`

## app/services/deck_processing/source_pipeline.py, readiness_publisher.py, source_ingestion.py

- **Owns:** Nothing active after prune.
- **Must not own:** Re-export seams for queueing or worker stage handlers now that direct owners are stable and imported directly.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; import scan found no importers.
- **Disposition:** PRUNED. Direct owners are `workflow_orchestration.py`, `workers/runtime/source_pipeline_runtime.py`, and `workers/runtime/publisher_runtime.py`.

## app/services/deck_processing/source_preview_service.py

- **Owns:** Miniatures orchestration that renders source previews and persists preview assets.
- **Must not own:** Source slide creation or DB Publisher readiness.
- **Spine stage:** 3. Miniatures.
- **Inputs:** Deck ID and DB session.
- **Outputs:** Preview counts and persisted source preview assets.
- **DB/artifacts:** `DeckSlide`, `DeckSlideAsset`, `DeckExtractionRun`, upload storage.
- **Breaks:** Visualizer source previews/miniatures are missing.
- **Verify:** `python3 -c "from app.services.deck_processing.source_preview_service import extract_source_previews; print('OK')"`

Miniatures runtime note:

- `app/services/visualizer/miniature_service.py` was pruned after call-site proof.
- The source worker now imports this owner directly.
- Source extraction no longer has an optional thumbnail branch; miniatures is the only source preview/thumbnail producer.

## app/services/deck_processing/processing_queue.py

- **Owns:** Legacy processing run enqueue/process helpers around durable workflow jobs.
- **Must not own:** Worker process boot or Railway service inference.
- **Spine stage:** Source pipeline support.
- **Inputs:** Deck/run IDs and DB session.
- **Outputs:** Processing run status changes and job dispatch calls.
- **DB/artifacts:** `DeckExtractionRun`, `WorkflowJob`.
- **Breaks:** Legacy processing queue/retry paths fail.
- **Verify:** `python3 -c "from app.services.deck_processing.processing_queue import enqueue_deck_processing; print('OK')"`

## app/services/deck_processing/processing_visibility.py

- **Owns:** Processing-page projection built from workflow state, source assets, and worker heartbeat.
- **Must not own:** Job mutation or worker dispatch.
- **Spine stage:** Frontend processing read model across stages 1-6.
- **Inputs:** Deck ID and DB session.
- **Outputs:** Processing visibility payload.
- **DB/artifacts:** `Deck`, `DeckFile`, `DeckSlide`, `DeckSlideAsset`, worker heartbeat telemetry.
- **Breaks:** Processing page loses stage/progress/failure visibility.
- **Verify:** `python3 -c "from app.services.deck_processing.processing_visibility import get_deck_processing_visibility; print('OK')"`

## app/workers/dispatch/worker_runtime_service.py

- **Owns:** Durable worker runtime helpers: kind inference, job claiming, stale recovery, handler dispatch.
- **Must not own:** Individual source/LLM/render/export business logic.
- **Spine stage:** Worker execution across all stages.
- **Inputs:** Worker env vars, DB session, job kinds.
- **Outputs:** Claimed/completed/failed workflow jobs and worker metadata.
- **DB/artifacts:** `WorkflowJob`, `WorkflowJobDependency`, `DeckExtractionRun`, `Deck`.
- **Breaks:** Railway workers start but cannot claim/process durable jobs.
- **Verify:** `python3 -c "from app.workers.dispatch.worker_runtime_service import process_next_durable_deck; print('OK')"`

## app/services/storage/upload_security.py

- **Owns:** Upload MIME/extension validation and streaming size-limited uploads.
- **Must not own:** Route authorization or persistence decisions.
- **Spine stage:** 1. Source Ingestion.
- **Inputs:** FastAPI `UploadFile`, filename, content type.
- **Outputs:** `LimitedUpload` temp file or upload validation error.
- **DB/artifacts:** Temporary local upload file.
- **Breaks:** Upload route accepts bad files or rejects valid PDF/PPT/PPTX files.
- **Verify:** `python3 -c "from app.services.storage.upload_security import stream_limited_upload; print('OK')"`

## app/services/storage/deck_file_service.py

- **Owns:** Stored deck file path resolution, hashing, and local conversion output paths.
- **Must not own:** Upload route contracts or extraction logic.
- **Spine stage:** Source Ingestion/Extraction support.
- **Inputs:** `DeckFile` rows and storage paths.
- **Outputs:** Local paths, hashes, converted PDF source path.
- **DB/artifacts:** Reads `DeckFile`, upload storage objects.
- **Breaks:** Extraction/preview cannot resolve uploaded deck source files.
- **Verify:** `python3 -c "from app.services.storage.deck_file_service import ensure_pdf_source; print('OK')"`

## app/services/admin/security_audit.py

- **Owns:** Persisting redacted security audit events for auth/admin/product routes.
- **Must not own:** Authorization decisions or user session creation.
- **Spine stage:** Admin/security cross-cutting.
- **Inputs:** DB session, action/result, request/user metadata.
- **Outputs:** `SecurityAuditEvent` rows.
- **DB/artifacts:** `SecurityAuditEvent`.
- **Breaks:** Security-sensitive route activity loses audit trail.
- **Verify:** `python3 -c "from app.services.admin.security_audit import record_security_event; print('OK')"`

## app/services/admin/failure_tickets.py

- **Owns:** Failure ticket creation/listing and exception promotion.
- **Must not own:** Business retries or route-specific error policy.
- **Spine stage:** Admin diagnostics across all stages.
- **Inputs:** Error metadata, request context, optional deck/user IDs.
- **Outputs:** `FailureTicket` rows and failure event lists.
- **DB/artifacts:** `FailureTicket`.
- **Breaks:** Upload/Smart Deck/admin failures are no longer diagnosable from failure tickets.
- **Verify:** `python3 -c "from app.services.admin.failure_tickets import create_failure_ticket; print('OK')"`

## app/services/deck_processing/workflow_state_read_model.py

- **Owns:** The canonical frontend-facing workflow state response (`GET /workflow-state`).
- **Must not own:** Job queueing, worker dispatch, DB mutation.
- **Spine stage:** Read model across all stages — reflects current state of stages 1-12.
- **Input:** `deck_id`, database session.
- **Output:** Dict with `phases`, `stages`, `canOpenSmartDeck`, `nextAction`, `sourceSlideCount`, `previewCount`, `failures`, `providerState`.
- **DB tables:** `Deck`, `WorkflowJob`, `WorkflowJobArtifact`, `WorkflowJobDependency`, `DeckSlide`.
- **Breaks:** Frontend processing page and Smart Deck open gate (`canOpenSmartDeck`).
- **Verify:** `python -c "from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state; print('OK')"`

## app/services/deck_processing/source_structure_persistence.py

- **Owns:** Persisting extracted deck structure (slides, blocks, assets) to DB.
- **Must not own:** PDF parsing, preview rendering, Smart Deck workspace prep.
- **Spine stage:** 2. Source Extraction.
- **Input:** `deck_id`, extraction run, extracted structure dict from `pdf_deck_extraction_service`.
- **Output:** Persisted `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset` rows.
- **DB tables:** `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset`.
- **Breaks:** Source slides missing from visualizer; Smart Deck context has no source data.
- **Verify:** `python -c "from app.services.deck_processing.source_structure_persistence import extract_and_persist_deck_structure; print('OK')"`

## app/services/deck_processing/source_preview_renderer.py

- **Owns:** Rendering PDF page preview images via PyMuPDF and tagging the preview with the active upload storage provider before promotion.
- **Must not own:** DB persistence, readiness publication.
- **Spine stage:** 3. Miniatures.
- **Input:** Source PDF file path, slide page numbers.
- **Output:** Promotable preview artifact metadata for one source slide image.
- **DB tables:** None (raw bytes output).
- **Breaks:** No preview images for source slides in visualizer.
- **Verify:** `python -c "from app.services.deck_processing.source_preview_renderer import render_source_preview_page; print('OK')"`

## app/services/deck_processing/source_preview_persistence.py

- **Owns:** Persisting source preview assets to DB + storage.
- **Must not own:** Rendering, readiness.
- **Spine stage:** 3. Miniatures.
- **Input:** Deck ID, slide ID, preview image bytes.
- **Output:** Persisted `DeckSlideAsset(asset_type='source_preview')`, updated `thumbnail_path`.
- **DB tables:** `DeckSlideAsset`, `DeckSlide.thumbnail_path`.
- **Breaks:** Preview images missing; thumbnails not updated.
- **Verify:** `python -c "from app.services.deck_processing.source_preview_persistence import persist_source_preview; print('OK')"`

## app/services/rendering/slide_thumbnail.py

- **Owns:** Nothing active after prune.
- **Must not own:** Source preview rendering; miniatures now owns the only source preview/thumbnail path.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; source extraction no longer called this optional helper and no other importers remained.
- **Disposition:** PRUNED.

## app/services/visualizer/preview_asset_service.py

- **Owns:** Nothing active after prune.
- **Must not own:** Signed URL access helpers; use `app.services.storage.signed_urls` directly.
- **Spine stage:** None after prune.
- **Breaks:** No known runtime path; import scan found no importers.
- **Disposition:** PRUNED.

## app/services/deck_processing/smart_deck_context.py

- **Owns:** Preparing Smart Deck source workspace (spine wrapper — delegates to `smart_deck_job_service`).
- **Must not own:** Source extraction, preview rendering.
- **Spine stage:** 4. Smart Deck Context.
- **Input:** Deck ID, database session.
- **Output:** Smart Deck source workspace, source versions, artifacts.
- **DB tables:** `SmartDeckWorkspace`, `DesignVersion`, `DeckLlmArtifact`.
- **Breaks:** Smart Deck opens empty (no source slides, no workspace).
- **Verify:** `python -c "from app.services.deck_processing.smart_deck_context import prepare_smart_deck_source_workspace; print('OK')"`

## app/services/deck_processing/readiness_publisher.py

- **Owns:** Publishing Smart Deck readiness (spine wrapper — delegates to `publisher_runtime`).
- **Must not own:** Any other stage's status.
- **Spine stage:** 5. DB Publisher.
- **Input:** Workflow job for `db_publisher`.
- **Output:** Deck state transitioned to `READY`; `published_phase` set to `smart_deck_ready`.
- **DB tables:** `WorkflowJob`, `Deck.state`.
- **Breaks:** `canOpenSmartDeck` stays false even after all stages complete.
- **Verify:** `python -c "from app.services.deck_processing.readiness_publisher import handle_db_publisher; print('OK')"`

## app/services/deck_processing/brand_extraction.py

- **Owns:** Running brand extraction during source pipeline (delegates to `brand_extraction_service`).
- **Must not own:** Readiness, preview, extraction.
- **Spine stage:** 6. Brand Extraction.
- **Input:** Deck ID, database session.
- **Output:** Brand profile with colors, typography, logo URLs.
- **DB tables:** `BrandProfile`, `CompanyProfile`.
- **Breaks:** Brand profile missing; visualizer shows no brand context (non-blocking).
- **Verify:** `python -c "from app.services.deck_processing.brand_extraction import run_brand_extraction_for_deck; print('OK')"`

## app/services/deck_processing/workflow_orchestration.py

- **Owns:** Coordinating workflow job creation and pipeline orchestration.
- **Must not own:** Individual stage business logic.
- **Spine stage:** All stages (orchestration layer).
- **Input:** Deck ID, job types, dependencies.
- **Output:** Created `WorkflowJob` rows with correct dependencies.
- **DB tables:** `WorkflowJob`, `WorkflowJobDependency`.
- **Breaks:** Pipeline jobs not created; stages don't execute in order.
- **Verify:** `python -c "from app.services.deck_processing.workflow_orchestration import *; print('OK')"`

## app/services/deck_processing/deck_mutation_service.py

- **Owns:** Deck CRUD operations (block patching, suggestion patching).
- **Must not own:** Analysis pipeline, Smart Deck context.
- **Spine stage:** Post-extraction edit surface.
- **Input:** Deck ID, slide/block mutations.
- **Output:** Updated `DeckSlideBlock` content, `DeckSlide` structure.
- **DB tables:** `DeckSlide`, `DeckSlideBlock`.
- **Breaks:** Suggestion apply fails; block content not saved.
- **Verify:** `python -c "from app.services.deck_processing.deck_mutation_service import *; print('OK')"`

## app/services/deck_processing/source_structure_read_model.py

- **Owns:** Read-only structure queries for frontend.
- **Must not own:** Persistence, mutation.
- **Spine stage:** Read model across stages 2-3.
- **Input:** Deck ID, database session.
- **Output:** Deck structure with slides, blocks, assets.
- **DB tables:** `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset`.
- **Breaks:** Visualizer can't load source structure.
- **Verify:** `python -c "from app.services.deck_processing.source_structure_read_model import *; print('OK')"`

## app/services/visualizer/slide_read_model.py

- **Owns:** Full deck read model for frontend visualizer (slides, previews, blocks, artifacts, signed URLs).
- **Must not own:** Mutation, generation, worker dispatch.
- **Spine stage:** Visualizer (post-pipeline read).
- **Input:** Deck ID, database session.
- **Output:** Full deck payload with slides, blocks, preview assets, signed URLs, design tokens, versions.
- **DB tables:** `Deck`, `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset`, `DeckLlmArtifact`, `DesignVersion`.
- **Breaks:** Frontend visualizer fails to load; slides missing; previews don't load.
- **Verify:** `python -c "from app.services.visualizer.slide_read_model import get_deck; print('OK')"`

## app/services/visualizer/preview_asset_service.py

- **Owns:** Signed URL generation for preview assets.
- **Must not own:** Rendering, persistence.
- **Spine stage:** Visualizer.
- **Input:** Asset storage key.
- **Output:** Signed URL string for frontend.
- **DB tables:** None (reads from `DeckSlideAsset.storage_key`).
- **Breaks:** Preview images don't load in frontend.
- **Verify:** `python -c "from app.services.visualizer.preview_asset_service import *; print('OK')"`

## app/services/llm/provider_base.py

- **Owns:** `LLMProvider` abstract base class with `generate_text()` and `validate_connection()`.
- **Must not own:** Prompt construction, response parsing, artifact saving.
- **Spine stage:** 7. LLM Generation (provider abstraction).
- **Input:** System prompt, user prompt, generation config (model, temperature, max_tokens).
- **Output:** `LlmResponse` with text and usage metadata.
- **DB tables:** None.
- **Breaks:** All LLM generation fails (no provider to call).
- **Verify:** `python -c "from app.services.llm.provider_base import LLMProvider; print('OK')"`

## app/services/llm/provider_registry.py

- **Owns:** Provider registration and lookup (`register()`, `get()`, `available_providers()`).
- **Must not own:** Provider configuration (keys, models), API transport.
- **Spine stage:** 7. LLM Generation (provider resolution).
- **Input:** Provider name string.
- **Output:** `LLMProvider` instance.
- **DB tables:** None.
- **Breaks:** Provider lookup fails; `provider_registry.get(name)` raises `KeyError`.
- **Verify:** `python -c "from app.services.llm import default_registry; print(default_registry.available_providers())"`

## app/services/llm/generation_service.py

- **Owns:** LLM generation orchestration (spine wrapper — re-exports from `smart_deck_llm_service`).
- **Must not own:** Provider API transport.
- **Spine stage:** 7. LLM Generation.
- **Input:** Delegates to `smart_deck_llm_service`.
- **Output:** Generation result dict.
- **DB tables:** `DeckLlmArtifact`, `DesignVersion`.
- **Breaks:** Generation jobs fail to create.
- **Verify:** `python -c "from app.services.llm.generation_service import create_generation_job; print('OK')"`

## app/services/storage/artifact_storage.py

- **Owns:** Bucket artifact storage key construction, CRUD, and signed URLs.
- **Must not own:** Upload flow, workflow logic.
- **Spine stage:** Storage (cross-cutting).
- **Input:** Deck ID, artifact type, file bytes.
- **Output:** Storage key, signed URL.
- **DB tables:** None (filesystem/S3 only).
- **Breaks:** No preview images or artifacts stored.
- **Verify:** `python -c "from app.services.storage.artifact_storage import BucketArtifactService; print('OK')"`

## app/services/storage/signed_urls.py

- **Owns:** Signed URL generation for asset retrieval.
- **Must not own:** Upload, artifact storage.
- **Spine stage:** Storage.
- **Input:** Storage key.
- **Output:** Signed URL string.
- **DB tables:** None.
- **Breaks:** Frontend can't load preview images.
- **Verify:** `python -c "from app.services.storage.signed_urls import *; print('OK')"`

## app/services/rendering/version_apply_service.py

- **Owns:** Design version CRUD (apply, discard, list, restore).
- **Must not own:** Generation, provider calls.
- **Spine stage:** 11. Apply Version.
- **Input:** Deck ID, version ID, database session.
- **Output:** Updated `DesignVersion` status.
- **DB tables:** `DesignVersion`.
- **Breaks:** Version apply/discard fails.
- **Verify:** `python -c "from app.services.rendering.version_apply_service import apply_design_version; print('OK')"`

## app/workers/dispatch/job_handlers.py

- **Owns:** Dispatch table mapping job types to handler functions.
- **Must not own:** Any business logic.
- **Spine stage:** All stages (dispatch seam).
- **Input:** Job type string, workflow job.
- **Output:** Dispatched handler function.
- **DB tables:** None.
- **Breaks:** Workers can't find handler for job type.
- **Verify:** `python -c "from app.workers.dispatch.job_handlers import get_workflow_job_handler; print('OK')"`

## app/workers/runtime/source_pipeline_runtime.py

- **Owns:** Source-pipeline job handlers (source_ingestion, source_extraction, miniatures, brand_extraction, smart_deck_context).
- **Must not own:** Generation, export, version apply.
- **Spine stage:** Stages 1-4, 6.
- **Input:** Workflow job, database session.
- **Output:** Completed job with phase output.
- **DB tables:** `WorkflowJob` (status updates), `DeckSlide`, `DeckSlideAsset`, `SmartDeckWorkspace`.
- **Breaks:** Source pipeline stages don't execute.
- **Verify:** `python -c "from app.workers.runtime.source_pipeline_runtime import handle_source_extraction; print('OK')"`

## app/workers/runtime/publisher_runtime.py

- **Owns:** Publisher job handlers (db_publisher, export).
- **Must not own:** Source pipeline stages.
- **Spine stage:** 5. DB Publisher, 12. Export.
- **Input:** Workflow job, database session.
- **Output:** Deck state transitioned; export created.
- **DB tables:** `Deck` (state), `DeckExport`.
- **Breaks:** `canOpenSmartDeck` stays false; exports fail.
- **Verify:** `python -c "from app.workers.runtime.publisher_runtime import handle_db_publisher; print('OK')"`

## app/workers/runtime/generation_runtime.py

- **Owns:** Generation-pipeline job handlers (llm_generation, schema_validation, preview_render, apply_version, compile_final_deck).
- **Must not own:** Source pipeline stages.
- **Spine stage:** Stages 7-11.
- **Input:** Workflow job, database session.
- **Output:** Generated slides, validated schema, rendered previews, applied versions.
- **DB tables:** `DesignVersion`, `DeckLlmArtifact`, `DeckSlide`.
- **Breaks:** Generation pipeline stalls; no generated slides.
- **Verify:** `python -c "from app.workers.runtime.generation_runtime import handle_llm_generation; print('OK')"`
