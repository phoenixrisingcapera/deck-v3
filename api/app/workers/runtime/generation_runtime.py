"""Generation-side workflow job handlers.

Owns the post-source pipeline: LLM generation, schema validation, preview
renderability, applying a design version, and final deck compilation.

Audit note: `handle_llm_generation` currently delegates to the existing
generation service. The generation service must treat Smart Deck context/source
facts as required inputs before producing VC-style recommendations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from cryptography.fernet import InvalidToken
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Deck, DeckBrandProfile, DeckExtractionRun, DeckFile, DeckSlide, DesignVersion, GenerationJob, InstantDeckOperation, User, WorkflowJob
from app.schemas.smart_deck import CreateSmartDeckGenerationJobInput
from app.workers.dispatch.worker_runtime_service import _dependency_output, _job_payload
from app.services.rendering.final_deck_service import prepare_full_deck
from app.services.rendering.schema_validation import validate_design_version_slides
from app.services.llm.generation_service import (
    SmartDeckProviderUnavailableError,
    apply_design_version,
    create_generation_job,
    generation_job_is_instant_deck,
    get_generation_provider_config,
    require_publishable_instant_design_version,
)
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_TIMED_OUT,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_SCHEMA_VALIDATION,
    record_workflow_artifact,
    set_workflow_job_status,
)
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded
from app.services.platform.billing.ai_usage_quota_service import actual_tokens_from_usage, reconcile_ai_operation_budget, reserve_ai_operation_budget
from app.core.config import settings
from app.services.llm.generation_provenance_service import validate_generation_provenance


logger = logging.getLogger(__name__)


class _InstantLockedPrechargeValidationFailure(Exception):
    def __init__(self, original: Exception):
        super().__init__("locked precharge validation failed")
        self.original = original


def _safe_instant_context_failure_class(exc: Exception) -> str:
    """Return only a bounded class label suitable for internal logs."""
    if isinstance(exc, InvalidToken):
        return "InvalidToken"
    if isinstance(exc, OSError):
        return "OSError"
    if isinstance(exc, SQLAlchemyError):
        return "DatabaseError"
    if isinstance(exc, ValueError):
        return "ValueError"
    if isinstance(exc, TypeError):
        return "TypeError"
    if isinstance(exc, LookupError):
        return "LookupError"
    if isinstance(exc, RuntimeError):
        return "RuntimeError"
    return "UnexpectedError"


def _log_instant_context_failure(*, stage: str, code: str, exc: Exception) -> None:
    error_class = _safe_instant_context_failure_class(exc)
    logger.error(
        "instant_deck_pre_provider_context_failed stage=%s code=%s error_class=%s",
        stage,
        code,
        error_class,
        extra={
            "generationStage": stage,
            "failureCode": code,
            "errorClass": error_class,
        },
    )


def _designer_observability_binding(
    generation_job: GenerationJob,
) -> tuple[dict[str, Any], str]:
    """Return the immutable provider envelope only after it actually exists.

    Initial Instant Deck commands persist the encrypted request context before
    the provider binding is created.  Observability at that boundary must
    describe the truthful pre-binding state; it must not assume an envelope,
    create a provider attempt, or invent request/usage identities.
    """
    metadata = (
        generation_job.llm_context_json
        if isinstance(generation_job.llm_context_json, dict)
        else {}
    )
    binding = metadata.get("fullHtmlProviderBinding")
    if not isinstance(binding, dict):
        return {}, "not_created"
    envelope = binding.get("requestEnvelope")
    if not isinstance(envelope, dict):
        return {}, "binding_without_envelope"
    return envelope, "bound"


def _build_designer_observability_manifest(
    *,
    generation_job: GenerationJob,
    operation_id: str,
    provider_runtime_context: dict[str, Any],
    retrieval_trace: dict[str, Any] | None,
    fallback_model: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build the content-minimizing designer trace before provider binding.

    This function is intentionally pure with respect to durable/provider state:
    it neither creates a provider binding nor starts a provider request.  The
    returned status distinguishes an exact bound envelope from the normal
    pre-binding state so unknown usage and cost remain unknown.
    """
    from app.services.ai_vc.observability import build_provider_context_manifest

    envelope, provider_binding_status = _designer_observability_binding(
        generation_job
    )
    if isinstance(retrieval_trace, dict):
        provider_context_text = json.dumps(
            provider_runtime_context, separators=(",", ":"), default=str,
        )
        for record in retrieval_trace.get("retrievalRecords", []):
            if not isinstance(record, dict):
                continue
            chunk_id = str(record.get("chunkId") or "")
            stages = list(record.get("injectedStages") or [])
            if chunk_id and chunk_id in provider_context_text and "designer" not in stages:
                record["injectedStages"] = [*stages, "designer"]
    manifest = build_provider_context_manifest(
        operation_id=operation_id,
        stage="designer",
        provider=str(envelope.get("provider") or "openai"),
        model=str(envelope.get("model") or fallback_model),
        system="",
        system_hash=envelope.get("systemPromptHash"),
        payload=provider_runtime_context,
        retrieval_trace=retrieval_trace,
        prompt_version=envelope.get("systemPromptVersion"),
    )
    manifest.update({
        "providerBindingStatus": provider_binding_status,
        "requestEnvelopeHash": envelope.get("envelopeHash"),
        "boundUserPromptHash": envelope.get("userPromptHash"),
        "maxOutputTokens": envelope.get("maxOutputTokens"),
    })
    return manifest, retrieval_trace


def _terminalize_instant_context_failure(
    db: Session,
    *,
    workflow_job_id: str,
    operation_id: str | None,
    reason: str,
) -> None:
    from app.services.llm.instant_html_operation_service import terminalize_generation_failure

    try:
        db.rollback()
    except Exception:
        pass
    try:
        terminalize_generation_failure(
            db,
            operation_id=operation_id,
            workflow_job_id=None if operation_id else workflow_job_id,
            reason=reason,
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def handle_llm_generation(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Run the configured LLM provider against the prepared Smart Deck workspace."""
    from app.services.llm.instant_html_operation_service import terminalize_generation_failure

    workflow_job_id = job.id
    workflow_deck_id = job.deck_id
    workflow_user_id = job.user_id
    instant_html_operation = False
    try:
        raw_payload = _job_payload(job)
        instant_html_operation = raw_payload.get("outputContract") == "full_html_deck.v1"
        payload = CreateSmartDeckGenerationJobInput(**raw_payload)
        validate_generation_provenance(db, workflow_deck_id, payload.provenance)
        user = db.get(User, workflow_user_id) if workflow_user_id else None
        if user is None:
            raise ValueError("Smart Deck generation job requires an owning user")
        retry_of = str((raw_payload.get("retryOfGenerationJobId") or "")).strip()
        operation = "smart_deck_retry" if retry_of else "smart_deck_generation"
        estimated_tokens = 80_000 if retry_of else 200_000
        reservation_key = f"{operation}:{workflow_job_id}"
        if not instant_html_operation:
            reserve_ai_operation_budget(db, user, operation=operation, reservation_key=reservation_key, estimated_tokens=estimated_tokens, daily_limit=settings.ai_daily_generation_quota)
    except Exception:
        terminalize_generation_failure(db, workflow_job_id=workflow_job_id, reason="generation_setup_failed")
        raise
    usage: dict = {}
    try:
        result = create_generation_job(
            db,
            workflow_deck_id,
            payload,
            run_id=workflow_job_id,
            deadline=OperationDeadline.after(settings.instant_deck_generation_deadline_seconds),
            usage_sink=usage,
        )
    except OperationDeadlineExceeded:
        if instant_html_operation:
            terminalize_generation_failure(db, workflow_job_id=workflow_job_id, reason="operation_deadline_exceeded")
        else:
            reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_TIMED_OUT,
            worker_id=worker_id,
            message="Smart Deck generation exceeded its operation deadline.",
            output_payload={"phase": "timed_out", "errorCode": "operation_deadline_exceeded"},
        )
        db.commit()
        return
    except Exception as exc:
        if instant_html_operation:
            from app.services.llm.full_html_generation_service import ALLOWED_CHECKPOINT_RECOVERY_REASONS

            failure_code = str(getattr(exc, "code", "") or "")
            terminalize_generation_failure(
                db,
                workflow_job_id=workflow_job_id,
                reason=(
                    failure_code
                    if failure_code in ALLOWED_CHECKPOINT_RECOVERY_REASONS
                    else "generation_processing_failed"
                ),
            )
        else:
            reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
        raise
    if result is None:
        terminalize_generation_failure(db, workflow_job_id=workflow_job_id, reason="generation_deck_missing")
        raise ValueError("Deck not found")
    generation_job, design_version, workspace = result
    if not instant_html_operation:
        reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
    coverage_complete = generation_job.get("coverageComplete") is True
    failed_slide_ids = list(generation_job.get("failedSlideIds") or [])
    try:
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            message=(
                "LLM generation completed."
                if coverage_complete
                else f"LLM generation completed partially; {len(failed_slide_ids)} slide(s) require retry."
            ),
            output_payload={
            # DISABLED: "phase": "saving_design_version" exposed an internal stage as an invalid WorkflowPhase.
            "phase": "schema_validation_queued",
            "generationStage": "saving_design_version",
            "generationJob": generation_job,
            "designVersionId": design_version.get("id"),
            "generatedVersionCount": len(design_version.get("generatedSlides", [])),
            "workspaceId": workspace.get("workspace", {}).get("id") if isinstance(workspace.get("workspace"), dict) else None,
            "generationStatus": "completed" if coverage_complete else "partial",
            "coverageComplete": coverage_complete,
            "wholeDeckCoverageComplete": generation_job.get("wholeDeckCoverageComplete") is True,
            "partialSuccess": bool(generation_job.get("partialSuccess")),
            "failedSlideIds": failed_slide_ids,
            "failedSlides": list(generation_job.get("failedSlides") or []),
            "timings": generation_job.get("timings") if isinstance(generation_job, dict) else {},
            "progress": generation_job.get("progress") if isinstance(generation_job, dict) else {},
            "provenance": payload.provenance,
            "visionExecution": generation_job.get("visionExecution") if isinstance(generation_job, dict) else None,
            },
        )
        db.commit()
    except Exception:
        terminalize_generation_failure(db, workflow_job_id=workflow_job_id, reason="generation_artifact_recording_failed")
        raise


def handle_instant_deck_generation(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Run the dedicated Instant Deck whole-deck generation workflow."""
    payload = _job_payload(job)
    from app.services.llm.instant_factual_review import REVIEW_RESUME_WAIVER, require_review_resume_lineage
    resumed_operation = db.query(InstantDeckOperation).filter_by(workflow_job_id=job.id, deck_id=job.deck_id).one_or_none()
    if resumed_operation is not None and resumed_operation.charge_status == REVIEW_RESUME_WAIVER:
        require_review_resume_lineage(db, resumed_operation)
        handle_llm_generation(db, job, worker_id=worker_id)
        return
    if payload.get("outputContract") == "full_html_deck.v1":
        from app.services.llm.instant_html_operation_service import (
            INSTANT_HTML_UNAVAILABLE_REASON,
            INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE,
            MAX_PROVIDER_REQUEST_STARTS,
            InstantOperationConflict,
            InstantProviderAttestationUnavailable,
            validate_output_feasibility,
        )

        operation_id = str(payload.get("instantOperationId") or "").strip()
        if not operation_id:
            raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
        operation: InstantDeckOperation | None = None
        owned_operation_id: str | None = None
        owner: User | None = None
        deck: Deck | None = None
        # Provider configuration and paid release intentionally live in the
        # provider-capable Instant worker, never in the source publisher.
        from app.core.openai_full_html_policy import FULL_HTML_MAX_OUTPUT_TOKENS, require_full_html_openai_model
        from app.services.llm.full_html_generation_service import (
            _require_request_context_ownership,
            _validated_follow_up_baseline,
            build_full_html_provider_runtime_context,
            persist_full_html_request_context,
            resolve_full_html_request_context,
            validate_full_html_request_feasibility,
        )
        from app.schemas.smart_deck import CreateSmartDeckGenerationJobInput

        failure_stage = "context_ownership"
        failure_code = "instant_context_ownership_failed"
        try:
            operation = (
                db.query(InstantDeckOperation)
                .filter(InstantDeckOperation.id == operation_id)
                .one_or_none()
            )
            owner = db.query(User).filter(User.id == job.user_id).one_or_none() if job.user_id else None
            deck = db.query(Deck).filter(Deck.id == job.deck_id, Deck.user_id == job.user_id).one_or_none()
            if operation is None or operation.workflow_job_id != job.id or owner is None or deck is None:
                raise ValueError("Instant HTML durable owner binding is unavailable.")
            if operation.deck_id != deck.id or operation.user_id != owner.id or operation.output_contract != "full_html_deck.v1":
                raise ValueError("Instant HTML durable owner binding is unavailable.")
            owned_operation_id = operation.id
            failure_stage = "request_context_feasibility"
            failure_code = "instant_request_context_feasibility_failed"
            try:
                validate_output_feasibility(
                    selected_slide_count=len(set(payload.get("selectedSourceSlideIds") or []))
                )
            except InstantOperationConflict as exc:
                # Renderer/provider capability is mutable deployment state.
                # No durable context, provider attempt, or charge has started
                # yet, so preserve this same operation for a later worker
                # cycle after configuration is repaired.
                raise InstantProviderAttestationUnavailable(
                    INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
                ) from exc
            require_full_html_openai_model(settings.openai_model)
            if not settings.openai_api_key:
                raise SmartDeckProviderUnavailableError("OpenAI environment credentials are missing.")
            from app.services.llm.openai_provider import instant_openai_model_access_attested
            from app.services.brand.brand_extraction import confirmed_website_brand_ready, website_brand_binding

            if not instant_openai_model_access_attested(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            ):
                raise InstantProviderAttestationUnavailable(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            generation_payload = CreateSmartDeckGenerationJobInput(**payload)
            slide_lookup = {slide.id: slide for slide in deck.slides}
            selected_ids = list(generation_payload.selectedSourceSlideIds)
            if any(slide_id not in slide_lookup for slide_id in selected_ids):
                raise InstantOperationConflict("One or more selected source slides do not belong to this deck.")
            if set(selected_ids) != set(slide_lookup) or len(selected_ids) != len(slide_lookup):
                raise InstantOperationConflict("Instant Deck generation requires every source slide in the deck.")
            selected_slides = [slide_lookup[slide_id] for slide_id in selected_ids]
            selected_slides.sort(key=lambda item: (item.slide_index, item.id))
            generation_job = db.query(GenerationJob).filter(
                GenerationJob.id == job.id, GenerationJob.deck_id == deck.id
            ).one_or_none()
            if generation_job is None:
                generation_job = GenerationJob(
                    id=job.id,
                    deck_id=deck.id,
                    status="queued",
                    provider="openai",
                    model=settings.openai_model,
                    prompt=generation_payload.prompt,
                    selected_source_slide_ids_json=selected_ids,
                    llm_context_json={},
                )
                db.add(generation_job)
                db.flush()
            has_request_context = isinstance(generation_job.llm_context_json, dict) and (
                "fullHtmlRequestContextArtifactId" in generation_job.llm_context_json
                or "fullHtmlRequestContext" in generation_job.llm_context_json
            )
            if has_request_context and "fullHtmlRequestContextArtifactId" not in generation_job.llm_context_json:
                # Legacy migration owns a durable commit. Run it before any
                # owner row is locked, then reacquire every authority below.
                failure_stage = "request_context_persistence"
                failure_code = "instant_request_context_persistence_failed"
                resolve_full_html_request_context(
                    generation_job=generation_job,
                    operation_id=operation.id,
                    require_existing=True,
                    require_encrypted=True,
                )
            operation = db.query(InstantDeckOperation).filter(
                InstantDeckOperation.id == operation_id,
            ).with_for_update().one_or_none()
            generation_job = db.query(GenerationJob).filter(
                GenerationJob.id == job.id,
                GenerationJob.deck_id == deck.id,
            ).with_for_update().one_or_none()
            if (
                operation is None
                or generation_job is None
                or operation.workflow_job_id != job.id
                or operation.deck_id != deck.id
                or operation.user_id != owner.id
                or operation.output_contract != "full_html_deck.v1"
            ):
                raise ValueError("Instant HTML durable owner binding is unavailable.")
            failure_stage = "context_ownership"
            failure_code = "instant_context_ownership_failed"
            operation, deck, owner, _locked_workflow = _require_request_context_ownership(
                db,
                generation_job=generation_job,
                operation_id=operation.id,
                lock_for_update=True,
            )
            if has_request_context:
                failure_stage = "request_context_persistence"
                failure_code = "instant_request_context_persistence_failed"
                context_pack = resolve_full_html_request_context(
                    generation_job=generation_job,
                    operation_id=operation.id,
                    require_existing=True,
                    lock_owners=True,
                    require_encrypted=True,
                )
            else:
                # Canonical typed context path: build typed context from DB
                # objects, then bridge to the grounded dict contract for LLM
                # consumption.  This replaces the ad-hoc dict assembly that
                # previously happened in _build_llm_context + build_grounded_context_pack.
                from app.schemas.instant_deck_context import InstantDeckGenerationContext
                from app.services.llm.instant_deck_context_builder import (
                    build_bounded_retrieved_guidance,
                    build_compact_instant_deck_agent_context,
                    build_instant_deck_generation_context,
                    context_to_grounded_pack,
                    resolve_instant_deck_intent,
                )

                failure_stage = "baseline_validation"
                failure_code = "instant_baseline_validation_failed"
                validated_baseline = _validated_follow_up_baseline(
                    db,
                    deck.id,
                    generation_payload.baseDesignVersionId,
                    user_id=owner.id,
                )
                effective_base_version_id = (
                    generation_payload.baseDesignVersionId
                    if validated_baseline is not None
                    else None
                )
                failure_stage = "typed_context_build"
                failure_code = "instant_typed_context_build_failed"
                inferred_audience, inferred_deck_type = resolve_instant_deck_intent(
                    deck=deck,
                    selected_slides=selected_slides,
                    audience=generation_payload.audience,
                    deck_type=generation_payload.deckType,
                )
                agent_context = build_compact_instant_deck_agent_context()
                retrieved_guidance = build_bounded_retrieved_guidance(
                    db,
                    deck=deck,
                    objective=generation_payload.prompt or "",
                    audience=inferred_audience,
                    deck_type=inferred_deck_type,
                )
                typed_ctx: InstantDeckGenerationContext = build_instant_deck_generation_context(
                    db=db,
                    deck=deck,
                    selected_slides=selected_slides,
                    user_goal=generation_payload.prompt or "",
                    audience=inferred_audience,
                    deck_type=inferred_deck_type,
                    base_design_version_id=effective_base_version_id,
                    validated_baseline=validated_baseline,
                    agent_context=agent_context,
                    retrieved_guidance=retrieved_guidance,
                )
                if payload.get("publicResearchPolicy") in {
                    "bounded-ai-vc-research.v2",
                    # Persisted v1 jobs remain executable; v2 no longer
                    # requires a confirmed website.
                    "confirmed-public-website.v1",
                }:
                    from app.services.llm.instant_vc_strategy import (
                        build_company_intelligence,
                        ensure_vc_strategy,
                    )
                    from app.services.ai_vc.runtime import ensure_model_research_plan
                    from app.services.llm.investor_public_research import (
                        ensure_generation_public_research,
                        research_for_generation,
                    )
                    job.output_json = {**(job.output_json or {}), "publishedPhase": "ai_vc_understanding"}
                    db.commit()
                    preliminary_pack = context_to_grounded_pack(typed_ctx)
                    company = build_company_intelligence(
                        preliminary_pack["sourceFacts"], preliminary_pack["sourceSlides"]
                    )
                    model_research_plan = ensure_model_research_plan(
                        db, deck=deck, operation_id=operation.id, company=company,
                        source_facts=preliminary_pack["sourceFacts"],
                    )
                    from app.services.ai_vc.skills.resolver import (
                        resolve_core_skill_plan,
                        resolve_model_skill_plan,
                        stage_skill_context,
                    )

                    research_skill_context = stage_skill_context(
                        (
                            resolve_model_skill_plan(model_research_plan)
                            if model_research_plan.get("status") == "model_authored"
                            else resolve_core_skill_plan()
                        ),
                        "research",
                    )
                    # Research has its own durable prestart record and is never
                    # retried automatically after an unknown billing outcome.
                    job.output_json = {**(job.output_json or {}), "publishedPhase": "ai_vc_research"}
                    db.commit()
                    ensure_generation_public_research(
                        db, deck, operation.id,
                        public_brief="Research the model-authored public category questions using current authoritative evidence.",
                        company_descriptor={
                            "schema_version":"model-authored-public-research-context.v1",
                            "category":"model-authored; see each bounded task context",
                            "customer_type":"model-authored; see each bounded task context",
                            "product_type":"model-authored; see each bounded task context",
                            "industry_context":"model-authored; see each bounded task context",
                        },
                        research_tasks=model_research_plan.get("researchTasks") or [],
                        research_guidance=research_skill_context,
                        model_research_plan=model_research_plan,
                    )
                    external_research = research_for_generation(db, deck.id)
                    job.output_json = {**(job.output_json or {}), "publishedPhase": "ai_vc_analysis"}
                    db.commit()
                    vc_strategy = ensure_vc_strategy(
                        db, deck=deck, operation_id=operation.id,
                        source_facts=preliminary_pack["sourceFacts"],
                        source_slides=preliminary_pack["sourceSlides"],
                        external_research=external_research,
                        design_guidance=retrieved_guidance,
                    )
                    visual_intelligence_payload: dict = {}
                    if vc_strategy.get("analysisStatus") == "source_only_fallback":
                        vc_strategy = vc_strategy | {"visual_intelligence_always_built": True}
                    from app.services.visual_intelligence import build_visual_intelligence
                    from app.services.visual_intelligence.persistence import persist_visual_intelligence

                    job.output_json = {**(job.output_json or {}), "publishedPhase": "visual_direction"}
                    db.commit()
                    visual_intelligence = build_visual_intelligence(
                        vc_strategy=vc_strategy,
                        brand=preliminary_pack.get("brand") or {},
                        approved_assets=preliminary_pack.get("approvedAssets") or [],
                        metrics=preliminary_pack.get("metrics") or [],
                        metric_sets=preliminary_pack.get("metricSets") or [],
                        input_artifact_ids=[f"vc-strategy:{operation.id}"],
                    )
                    job.output_json = {**(job.output_json or {}), "publishedPhase": "visual_asset_planning"}
                    db.commit()
                    persist_visual_intelligence(
                        db,
                        deck_id=deck.id,
                        operation_id=operation.id,
                        bundle=visual_intelligence,
                    )
                    visual_intelligence_payload = visual_intelligence.model_dump(mode="json")
                    typed_ctx = typed_ctx.model_copy(update={
                        "external_research": external_research,
                        "vc_strategy": vc_strategy,
                        "visual_intelligence": visual_intelligence_payload,
                    })
                    job.output_json = {**(job.output_json or {}), "publishedPhase": "narrative_reconstruction"}
                    db.commit()
                llm_context = context_to_grounded_pack(typed_ctx)
                exact_provider_request_body = json.dumps(
                    build_full_html_provider_runtime_context(llm_context),
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
                failure_stage = "request_context_persistence"
                failure_code = "instant_request_context_persistence_failed"
                context_pack = persist_full_html_request_context(
                    db,
                    generation_job_id=generation_job.id,
                    operation_id=operation.id,
                    context_pack=llm_context,
                    llm_context_snapshot={"generationMode": "instant_deck", "canonicalContext": True},
                    exact_provider_request_body=exact_provider_request_body,
                )
                # The encrypted request bundle is the transport authority. Add
                # a safe operation-level manifest proving which retrieved IDs
                # are present in the exact logical designer context, without
                # duplicating confidential source prose in diagnostics.
                from app.services.ai_vc.observability import (
                    MANIFEST_SCHEMA,
                    MANIFEST_TYPE,
                    persist_internal_artifact,
                )
                from app.db.models import DeckLlmArtifact

                db.refresh(generation_job)
                trace_row = db.query(DeckLlmArtifact).filter_by(
                    deck_id=deck.id,
                    artifact_key=f"ai-vc-trace:{operation.id}",
                ).one_or_none()
                retrieval_trace = (
                    (trace_row.payload_json or {}).get("retrieval")
                    if trace_row is not None and isinstance(trace_row.payload_json, dict)
                    else None
                )
                provider_runtime_context = build_full_html_provider_runtime_context(context_pack)
                designer_manifest, retrieval_trace = _build_designer_observability_manifest(
                    generation_job=generation_job,
                    operation_id=operation.id,
                    provider_runtime_context=provider_runtime_context,
                    retrieval_trace=retrieval_trace,
                    fallback_model=settings.openai_model,
                )
                designer_manifest_row = persist_internal_artifact(
                    db, deck_id=deck.id, artifact_type=MANIFEST_TYPE,
                    artifact_key=f"ai-vc-context:{operation.id}:designer:primary",
                    schema_version=MANIFEST_SCHEMA,
                    summary=(
                        "Whole-deck designer context manifest with explicit provider-binding state; "
                        "hashes and IDs only."
                    ),
                    payload=designer_manifest,
                    metrics={"approximateInputTokens": designer_manifest["approximateInputTokens"]},
                )
                if trace_row is not None:
                    trace_row.payload_json = {
                        **(trace_row.payload_json or {}),
                        "retrieval": retrieval_trace,
                        "designerContextManifestId": designer_manifest_row.id,
                    }
                db.commit()
            failure_stage = "request_context_feasibility"
            failure_code = "instant_request_context_feasibility_failed"
            from app.services.llm.generation_service import (
                _historical_augmented_full_html_provider_context,
            )
            from app.services.llm.full_html_generation_service import (
                _validated_encrypted_exact_request_body,
            )

            provider_binding = (
                generation_job.llm_context_json.get("fullHtmlProviderBinding")
                if isinstance(generation_job.llm_context_json, dict)
                and isinstance(generation_job.llm_context_json.get("fullHtmlProviderBinding"), dict)
                else None
            )
            exact_user_prompt_bytes = None
            if provider_binding is not None and isinstance(provider_binding.get("requestEnvelope"), dict):
                exact_user_prompt_bytes = _validated_encrypted_exact_request_body(
                    generation_job=generation_job,
                    operation_id=operation.id,
                    context_pack=context_pack,
                    request_envelope=provider_binding["requestEnvelope"],
                )
            validate_full_html_request_feasibility(
                context_pack,
                model=settings.openai_model,
                max_output_tokens=settings.instant_html_max_output_tokens,
                provider_context_pack=build_full_html_provider_runtime_context(context_pack),
                provider_binding=provider_binding,
                historical_provider_context_pack=(
                    _historical_augmented_full_html_provider_context(context_pack, selected_slides)
                    if provider_binding is not None
                    else None
                ),
                exact_user_prompt_bytes=exact_user_prompt_bytes,
            )
            # Match the generation service's initial request plus one bounded
            # validation retry. The operation's cumulative cost cap still applies.
            operation.max_provider_request_starts = MAX_PROVIDER_REQUEST_STARTS
            operation.max_input_tokens = min(operation.max_input_tokens, 272_000)
            operation.max_output_tokens = min(settings.instant_html_max_output_tokens, FULL_HTML_MAX_OUTPUT_TOKENS)
            db.commit()
        except InstantProviderAttestationUnavailable:
            db.rollback()
            raise
        except SmartDeckProviderUnavailableError:
            _terminalize_instant_context_failure(
                db,
                workflow_job_id=job.id,
                operation_id=owned_operation_id,
                reason="provider_not_configured",
            )
            raise
        except Exception as exc:
            _log_instant_context_failure(stage=failure_stage, code=failure_code, exc=exc)
            _terminalize_instant_context_failure(
                db,
                workflow_job_id=job.id,
                operation_id=owned_operation_id,
                reason=failure_code,
            )
            raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE) from None
        from app.services.llm.instant_html_operation_service import charge_new_operation, confirm_operation_enqueued

        # ``charge_status=charged`` denotes an internal product-quota
        # reservation. Provider spend remains zero until a provider attempt is
        # started and its usage is reconciled by the operation service.
        def validate_locked_charge_eligibility(
            locked_db: Session, locked_operation: InstantDeckOperation, locked_owner: User,
        ) -> None:
            from app.core.openai_full_html_policy import FULL_HTML_MAX_INPUT_TOKENS
            from app.services.llm.full_html_generation_service import (
                FULL_SOURCE_TEXT_HASH_VERSION,
                LEGACY_SOURCE_TEXT_HASH_VERSION,
                canonical_full_source_text,
                build_full_html_provider_runtime_context,
                resolve_full_html_request_context,
                resolve_full_html_request_source_binding,
                validated_normalized_source_text_hash,
            )
            from app.services.llm.openai_provider import instant_openai_model_access_attested

            locked_job = locked_db.query(WorkflowJob).filter(
                WorkflowJob.id == job.id,
                WorkflowJob.deck_id == deck.id,
                WorkflowJob.user_id == locked_owner.id,
            ).with_for_update().one_or_none()
            locked_generation = locked_db.query(GenerationJob).filter(
                GenerationJob.id == job.id,
                GenerationJob.deck_id == deck.id,
            ).with_for_update().one_or_none()
            locked_deck = locked_db.query(Deck).filter(
                Deck.id == deck.id,
                Deck.user_id == locked_owner.id,
            ).with_for_update().one_or_none()
            if (
                locked_job is None
                or locked_generation is None
                or locked_deck is None
                or locked_operation.workflow_job_id != locked_job.id
                or locked_operation.user_id != locked_owner.id
                or locked_operation.deck_id != locked_deck.id
                or locked_operation.output_contract != "full_html_deck.v1"
                or locked_operation.max_provider_request_starts != MAX_PROVIDER_REQUEST_STARTS
                or locked_operation.max_input_tokens > FULL_HTML_MAX_INPUT_TOKENS
            ):
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            locked_brand = locked_db.query(DeckBrandProfile).filter(
                DeckBrandProfile.deck_id == locked_deck.id
            ).with_for_update().one_or_none()
            if not confirmed_website_brand_ready(locked_brand):
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            locked_selected = list(locked_generation.selected_source_slide_ids_json or [])
            current_ids = [row[0] for row in locked_db.query(DeckSlide.id).filter(
                DeckSlide.deck_id == locked_deck.id
            ).order_by(DeckSlide.slide_index.asc(), DeckSlide.id.asc()).all()]
            if locked_selected != current_ids or list(payload.get("selectedSourceSlideIds") or []) != current_ids:
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            context = resolve_full_html_request_context(
                generation_job=locked_generation,
                operation_id=locked_operation.id,
                require_existing=True,
                lock_owners=True,
                require_encrypted=True,
            )
            persisted_brand = context.get("brand") if isinstance(context.get("brand"), dict) else {}
            current_brand_binding = website_brand_binding(locked_brand)
            if current_brand_binding.get("sourceUrl") and (
                persisted_brand.get("websiteSourceUrl") != current_brand_binding.get("sourceUrl")
                or persisted_brand.get("websiteEvidenceSha256") != current_brand_binding.get("evidenceSha256")
                or persisted_brand.get("palette") != current_brand_binding.get("palette")
                or persisted_brand.get("colors") != current_brand_binding.get("colors")
            ):
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            source_binding = resolve_full_html_request_source_binding(
                generation_job=locked_generation,
                operation_id=locked_operation.id,
            )
            current_slides = locked_db.query(DeckSlide).filter(
                DeckSlide.deck_id == locked_deck.id,
                DeckSlide.id.in_(current_ids),
            ).order_by(DeckSlide.slide_index.asc(), DeckSlide.id.asc()).with_for_update().all()
            current_file_ids = {slide.source_file_id for slide in current_slides}
            current_extraction_ids = {slide.extraction_run_id for slide in current_slides}
            if len(current_file_ids) != 1 or len(current_extraction_ids) != 1:
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            current_file_id = next(iter(current_file_ids))
            current_extraction_id = next(iter(current_extraction_ids))
            source_file = locked_db.query(DeckFile).filter(
                DeckFile.id == current_file_id,
                DeckFile.deck_id == locked_deck.id,
            ).with_for_update().one_or_none()
            extraction = locked_db.query(DeckExtractionRun).filter(
                DeckExtractionRun.id == current_extraction_id,
                DeckExtractionRun.deck_id == locked_deck.id,
                DeckExtractionRun.source_file_id == current_file_id,
            ).with_for_update().one_or_none()
            binding_version = source_binding.get("contractVersion")
            if (
                binding_version == "full-html-source-binding.v2"
                and source_binding.get("sourceTextHashVersion") == FULL_SOURCE_TEXT_HASH_VERSION
            ):
                source_text_hash_version = FULL_SOURCE_TEXT_HASH_VERSION
            elif binding_version == "full-html-source-binding.v1":
                # Legacy hashes are truncated, so compatibility is allowed only
                # with an additional complete canonical text comparison.
                source_text_hash_version = LEGACY_SOURCE_TEXT_HASH_VERSION
            else:
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            context_source_text = {
                str(item.get("sourceSlideId")): item.get("text")
                for item in context.get("sourceSlides", [])
                if isinstance(item, dict) and item.get("sourceSlideId")
            }
            try:
                if any(
                    canonical_full_source_text(context_source_text.get(slide.id))
                    != canonical_full_source_text(slide.raw_text)
                    for slide in current_slides
                ):
                    raise ValueError("Source context text no longer matches current source text.")
                current_source_slides = [
                    {
                        "sourceSlideId": slide.id,
                        "textHash": validated_normalized_source_text_hash(
                            slide,
                            hash_version=source_text_hash_version,
                        ),
                    }
                    for slide in current_slides
                ]
            except ValueError:
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE) from None
            current_source_binding = {
                "contractVersion": binding_version,
                "sourceFileId": current_file_id,
                "sourceFileChecksum": source_file.checksum_sha256 if source_file is not None else None,
                "extractionRunId": current_extraction_id,
                "extractorName": extraction.extractor_name if extraction is not None else None,
                "extractorVersion": extraction.extractor_version if extraction is not None else None,
                "sourceSlides": current_source_slides,
            }
            if binding_version == "full-html-source-binding.v2":
                current_source_binding["sourceTextHashVersion"] = FULL_SOURCE_TEXT_HASH_VERSION
            if (
                source_binding != current_source_binding
                or extraction is None
                or extraction.status != "completed"
            ):
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            validate_output_feasibility(selected_slide_count=len(current_ids))
            feasibility = validate_full_html_request_feasibility(
                context,
                model=settings.openai_model,
                max_output_tokens=settings.instant_html_max_output_tokens,
                provider_context_pack=build_full_html_provider_runtime_context(context),
                provider_binding=(
                    locked_generation.llm_context_json.get("fullHtmlProviderBinding")
                    if isinstance(locked_generation.llm_context_json, dict)
                    and isinstance(locked_generation.llm_context_json.get("fullHtmlProviderBinding"), dict)
                    else None
                ),
                historical_provider_context_pack=(
                    _historical_augmented_full_html_provider_context(context, current_slides)
                    if isinstance(locked_generation.llm_context_json, dict)
                    and isinstance(locked_generation.llm_context_json.get("fullHtmlProviderBinding"), dict)
                    else None
                ),
                exact_user_prompt_bytes=(
                    _validated_encrypted_exact_request_body(
                        generation_job=locked_generation,
                        operation_id=locked_operation.id,
                        context_pack=context,
                        request_envelope=locked_generation.llm_context_json["fullHtmlProviderBinding"]["requestEnvelope"],
                    )
                    if isinstance(locked_generation.llm_context_json, dict)
                    and isinstance(locked_generation.llm_context_json.get("fullHtmlProviderBinding"), dict)
                    and isinstance(
                        locked_generation.llm_context_json["fullHtmlProviderBinding"].get("requestEnvelope"),
                        dict,
                    )
                    else None
                ),
            )
            if feasibility["inputTokens"] > locked_operation.max_input_tokens:
                raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)
            if not instant_openai_model_access_attested(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            ):
                raise InstantProviderAttestationUnavailable(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE)

        def guarded_locked_charge_eligibility(
            locked_db: Session, locked_operation: InstantDeckOperation, locked_owner: User,
        ) -> None:
            try:
                validate_locked_charge_eligibility(locked_db, locked_operation, locked_owner)
            except InstantProviderAttestationUnavailable:
                raise
            except Exception as exc:
                raise _InstantLockedPrechargeValidationFailure(exc) from None

        try:
            charge_new_operation(
                db,
                operation.id,
                owner,
                locked_eligibility_validator=guarded_locked_charge_eligibility,
            )
            confirm_operation_enqueued(db, operation.id, job.id)
        except InstantProviderAttestationUnavailable:
            db.rollback()
            raise
        except _InstantLockedPrechargeValidationFailure as exc:
            _log_instant_context_failure(
                stage="locked_precharge_validation",
                code="instant_locked_precharge_validation_failed",
                exc=exc.original,
            )
            _terminalize_instant_context_failure(
                db,
                workflow_job_id=job.id,
                operation_id=operation.id,
                reason=INSTANT_HTML_UNAVAILABLE_REASON,
            )
            raise InstantOperationConflict(INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE) from None
    handle_llm_generation(db, job, worker_id=worker_id)


def _generation_dependency_output(db: Session, job: WorkflowJob) -> dict:
    generation_output = _dependency_output(db, job, JOB_TYPE_INSTANT_DECK_GENERATION)
    if generation_output:
        return generation_output
    return _dependency_output(db, job, JOB_TYPE_LLM_GENERATION)


def handle_schema_validation(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Validate generated slides before they become renderable previews."""
    generation_output = _generation_dependency_output(db, job)
    design_version_id = generation_output.get("designVersionId")
    generation_workflow_job_id = str(_job_payload(job).get("generationWorkflowJobId") or "").strip()
    if not design_version_id:
        raise ValueError("Schema validation cannot run without a generated designVersionId.")
    if not generation_workflow_job_id:
        raise ValueError("Schema validation cannot run without its generation workflow identity.")
    slides = validate_design_version_slides(db, job.deck_id, design_version_id)
    version = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == job.deck_id, DesignVersion.id == design_version_id)
        .one()
    )
    if version.generation_job_id != generation_workflow_job_id:
        raise ValueError("Schema validation design version does not match its generation workflow.")
    if generation_job_is_instant_deck(version.generation_job) and getattr(version, "render_mode", "scene_graph.v1") != "html_compiled.v1":
        require_publishable_instant_design_version(version)
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Schema validation stage completed.",
        output_payload={
            "phase": "generation_running",
            "designVersionId": design_version_id,
            "generationWorkflowJobId": generation_workflow_job_id,
            "workspaceId": generation_output.get("workspaceId"),
            "generationJob": generation_output.get("generationJob"),
            "validationStatus": "passed",
            "validatedSlideCount": len(slides),
        },
    )
    db.commit()


def handle_preview_render(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Record the manifest that tells the UI a design version can be previewed."""
    schema_output = _dependency_output(db, job, JOB_TYPE_SCHEMA_VALIDATION)
    design_version_id = schema_output.get("designVersionId")
    generation_workflow_job_id = str(_job_payload(job).get("generationWorkflowJobId") or "").strip()
    workspace_id = schema_output.get("workspaceId")
    if not design_version_id:
        raise ValueError("Preview render cannot run without a generated designVersionId.")
    if (
        not generation_workflow_job_id
        or schema_output.get("generationWorkflowJobId") != generation_workflow_job_id
    ):
        raise ValueError("Preview render dependencies do not identify the same generated design version.")
    version = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == job.deck_id, DesignVersion.id == design_version_id)
        .one_or_none()
    )
    if version is None:
        raise ValueError("Preview render cannot find the generated design version.")
    if version.generation_job_id != generation_workflow_job_id:
        raise ValueError("Preview render design version does not match its generation workflow.")
    if generation_job_is_instant_deck(version.generation_job):
        if getattr(version, "render_mode", "scene_graph.v1") == "html_compiled.v1":
            from app.services.rendering.render_proof_service import create_complete_render_proofs
            try:
                create_complete_render_proofs(db, version)
                from app.services.llm.instant_html_operation_service import mark_render_recovery_proven

                mark_render_recovery_proven(db, version.id)
            except Exception:
                from app.services.llm.instant_html_operation_service import terminalize_operation_for_design_version

                db.rollback()
                terminalize_operation_for_design_version(
                    db,
                    version.id,
                    reason="render_proof_failed",
                    defer_release=True,
                )
                raise
        require_publishable_instant_design_version(version)
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    if not slides:
        raise ValueError("Preview render cannot run without generated slides.")
    manifest_key = version.bucket_manifest_key or f"workflow/design-version-manifests/{design_version_id}.json"
    record_workflow_artifact(
        db,
        job=job,
        artifact_type="design_version_manifest",
        storage_key=manifest_key,
        metadata={
            "designVersionId": design_version_id,
            "generationWorkflowJobId": generation_workflow_job_id,
            "generatedSlideCount": len(slides),
            "hasStoredManifest": bool(version.bucket_manifest_key),
        },
    )
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Preview render stage completed.",
        output_payload={
            "phase": "preview_ready",
            "designVersionId": design_version_id,
            "generationWorkflowJobId": generation_workflow_job_id,
            "workspaceId": workspace_id,
            "renderStatus": "completed",
            "previewRenderable": bool(design_version_id),
            "generatedSlideCount": len(slides),
            "manifestKey": manifest_key,
        },
    )
    db.commit()


def handle_apply_version(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Apply a generated design version as the active deck version."""
    payload = _job_payload(job)
    design_version_id = str(payload.get("designVersionId") or "").strip()
    if not design_version_id:
        raise ValueError("Workflow apply-version job is missing designVersionId.")
    result = apply_design_version(db, job.deck_id, design_version_id)
    if result is None:
        raise ValueError("Design version not found")
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Apply version completed.",
        output_payload={
            "phase": "apply_running",
            "designVersionId": design_version_id,
            "applyResult": result,
        },
    )
    db.commit()


def handle_compile_final_deck(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Compile a generated batch into the final downloadable deck artifact."""
    payload = _job_payload(job)
    batch_id = str(payload.get("batchId") or "").strip()
    if not batch_id:
        raise ValueError("Workflow compile-final job is missing batchId.")

    # Reuse the existing synchronous compiler here; the worker wrapper turns it
    # into a durable job and publishes the resulting deck ids back to the UI.
    compiled = prepare_full_deck(
        db,
        job.deck_id,
        batch_id,
        title=payload.get("title"),
        latest_slide_version_id=payload.get("latestSlideVersionId"),
    )
    if compiled is None:
        raise ValueError("Deck or batch not found")

    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Final deck compilation completed.",
        output_payload={
            "phase": "compiled_deck_ready",
            "batchId": batch_id,
            "deckId": compiled.get("deckId"),
            "compiledDeckId": compiled.get("compiledDeckId"),
            "finalDeckId": compiled.get("finalDeckId"),
            "latestBatchId": compiled.get("latestBatchId"),
            "status": compiled.get("status"),
        },
    )
    db.commit()
