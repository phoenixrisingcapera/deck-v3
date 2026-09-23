"""Workflow-state read model.

Owns the canonical frontend-facing readiness contract and workflow job detail
read surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, get_args

from sqlalchemy.orm import Session

from app.db.models import Deck, DeckFile, DeckSlide, DeckSlideAsset, DesignVersion, GeneratedSlide, SmartDeckWorkspace, WorkflowJob, WorkflowJobArtifact, WorkflowJobDependency, WorkflowJobEvent
from app.schemas.brand_profile import normalize_branding_json_payload
from app.schemas.deck_workflow import WorkflowBlockingReason
from app.services.admin.failure_tickets import list_smart_deck_failure_events
from app.services.llm.generation_service import (
    GenerationValidationError,
    get_generation_provider_config,
    get_smart_deck_workspace,
    require_publishable_instant_design_version,
)
from app.services.deck_processing.workflow_jobs import (
    CLAIMABLE_JOB_STATUSES,
    JOB_STATUS_BLOCKED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_TIMED_OUT,
    JOB_TYPE_DB_PUBLISHER,
    PUBLISHABLE_WORKFLOW_PHASES,
    get_workflow_job_by_id,
    latest_generation_root_and_chain,
    list_workflow_jobs_for_deck,
    workflow_job_dependencies_status,
    workflow_job_is_superseded_publisher_noop,
    workflow_job_phase,
    workflow_job_progress,
)
from app.services.admin.worker_health import get_latest_worker_heartbeat
from app.services.deck_processing.source_slide_payload import map_source_slide_payload
from app.services.ai_vc.advisory import investment_critique_status, source_summary
from app.services.ai_vc.runtime import strategy_status as ai_vc_strategy_status
from app.services.visual_intelligence.persistence import visual_intelligence_status
from app.services.visual_intelligence.review.deck_review import vision_review_status


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _coerce_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _titleize_workflow_token(value: str) -> str:
    return " ".join(part[:1].upper() + part[1:] for part in value.split("_") if part)


def _workflow_status_to_phase_status(status: str) -> str:
    if status == "completed":
        return "completed"
    if status == "running":
        return "active"
    if status == "blocked":
        # A dependency-blocked stage did not itself fail. Keep that distinction
        # in the canonical workflow payload so the processing UI identifies the
        # causal failed stage instead of presenting every downstream job as bad.
        return "blocked"
    if status in {"failed_retryable", "failed_final", "timed_out"}:
        return "failed"
    return "pending"


def _workflow_id(deck_id: str) -> str:
    return f"deckwf_{deck_id}"


def _workflow_job_design_version_id(job: WorkflowJob) -> str | None:
    output = _coerce_mapping(job.output_json)
    input_payload = _coerce_mapping(job.input_json)
    direct_id = output.get("designVersionId") or input_payload.get("designVersionId")
    if isinstance(direct_id, str) and direct_id.strip():
        return direct_id.strip()
    apply_result = _coerce_mapping(output.get("applyResult"))
    active_id = apply_result.get("activeDesignVersionId")
    if isinstance(active_id, str) and active_id.strip():
        return active_id.strip()
    return None


def _workflow_job_workspace_payload(db: Session, job: WorkflowJob) -> dict[str, Any] | None:
    if job.job_type not in {"llm_generation", "instant_deck_generation", "selected_slide_generation", "schema_validation", "preview_render", "apply_version"}:
        return None
    return get_smart_deck_workspace(db, job.deck_id)


def _workflow_job_design_version_payload(
    db: Session,
    job: WorkflowJob,
    workspace: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    design_version_id = _workflow_job_design_version_id(job)
    if not design_version_id:
        return None
    workspace = workspace if workspace is not None else _workflow_job_workspace_payload(db, job)
    versions = workspace.get("designVersions") if isinstance(workspace, dict) else []
    if isinstance(versions, list):
        version = next((item for item in versions if isinstance(item, dict) and item.get("id") == design_version_id), None)
        if version is not None:
            return version
    return None


def _error_payload(code: str, message: str, *, recoverable: bool = True, next_action: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "recoverable": recoverable,
        "nextAction": next_action,
    }


def _job_error(job: WorkflowJob) -> dict[str, Any] | None:
    if not job.error_message:
        return None
    recoverable = job.status == JOB_STATUS_FAILED_RETRYABLE
    next_action = "retry_job" if recoverable else "manual_review"
    return _error_payload(
        job.error_code or f"{job.job_type}_failed",
        job.error_message,
        recoverable=recoverable,
        next_action=next_action,
    )


_ALLOWED_WORKFLOW_BLOCKING_REASONS = frozenset(get_args(WorkflowBlockingReason))

_JOB_TYPE_FAILURE_BLOCKING_REASONS: dict[str, str] = {
    "source_ingestion": "source_extraction_failed",
    "source_extraction": "source_extraction_failed",
    "miniatures": "thumbnail_generation_failed",
    "brand_extraction": "brand_extraction_failed",
    "smart_deck_context": "smart_deck_context_failed",
    "llm_generation": "llm_generation_failed",
    "instant_deck_generation": "llm_generation_failed",
    "selected_slide_generation": "selected_slide_generation_failed",
    "schema_validation": "schema_validation_failed",
    "preview_render": "preview_render_failed",
    "db_publisher": "db_publisher_failed",
    "apply_version": "apply_version_failed",
    "compile_final_deck": "export_failed",
    "export": "export_failed",
    "due_diligence": "due_diligence_failed",
    "deck_map_analysis": "deck_map_analysis_failed",
    "market_research": "market_research_failed",
    "media_processing": "preview_render_failed",
    "smart_edit": "apply_version_failed",
}


def _workflow_blocking_reason(job: WorkflowJob) -> str:
    """Return a controlled public reason without discarding detailed job errors."""
    for candidate in (job.error_code, job.terminal_reason):
        if candidate in _ALLOWED_WORKFLOW_BLOCKING_REASONS:
            return str(candidate)
    return _JOB_TYPE_FAILURE_BLOCKING_REASONS.get(job.job_type, "dependency_failed")


def _job_retry_eligible(job: WorkflowJob) -> bool:
    return job.status == JOB_STATUS_FAILED_RETRYABLE and int(job.attempt_count or 0) < int(job.max_attempts or 0)


def _job_terminal(job: WorkflowJob) -> bool:
    return job.status in {
        JOB_STATUS_COMPLETED,
        JOB_STATUS_FAILED_FINAL,
        JOB_STATUS_BLOCKED,
        JOB_STATUS_TIMED_OUT,
    }


def _workflow_job_liveness(job: WorkflowJob, *, now: datetime | None = None) -> dict[str, Any]:
    """Return backend-owned liveness without treating heartbeat age alone as terminal."""
    now = now or datetime.utcnow()
    heartbeat_at = job.heartbeat_at or job.started_at or job.queued_at or job.created_at
    heartbeat_age_seconds = max(0, int((now - heartbeat_at).total_seconds())) if heartbeat_at else None
    lease_active = bool(job.locked_until and job.locked_until > now)

    if _job_terminal(job):
        liveness_status = "terminal"
        recoverable = _job_retry_eligible(job)
        next_action = "retry_job" if recoverable else "manual_review"
    elif job.status == JOB_STATUS_QUEUED:
        liveness_status = "queued"
        recoverable = False
        next_action = "view_processing"
    elif job.status == JOB_STATUS_RUNNING and lease_active:
        # A valid backend lease remains authoritative even when a synchronous
        # provider call has not emitted a recent progress heartbeat.
        liveness_status = "active"
        recoverable = False
        next_action = "view_processing"
    elif job.status == JOB_STATUS_RUNNING:
        liveness_status = "stalled"
        recoverable = True
        next_action = "retry_job"
    else:
        liveness_status = "recovering" if int(job.recovery_count or 0) > 0 else "queued"
        recoverable = False
        next_action = "view_processing"

    return {
        "livenessStatus": liveness_status,
        "heartbeatAgeSeconds": heartbeat_age_seconds,
        "leaseExpiresAt": _iso(job.locked_until),
        "operationDeadlineAt": _iso(job.locked_until),
        "recoverable": recoverable,
        "nextAction": next_action,
    }


GENERATION_DESCENDANT_PARENT_FIELDS = {
    "schema_validation": "generationWorkflowJobId",
    "preview_render": "schemaValidationWorkflowJobId",
    "db_publisher": "previewRenderWorkflowJobId",
}


def _nonempty_string(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _workflow_job_lineage(
    job: WorkflowJob,
    *,
    dependency_job_ids: list[str] | None = None,
    authoritative_job_ids: set[str] | None = None,
) -> dict[str, Any]:
    input_payload = _coerce_mapping(getattr(job, "input_json", None))
    output_payload = _coerce_mapping(getattr(job, "output_json", None))
    dependencies = list(dict.fromkeys(dependency_job_ids or []))
    root_job_types = {"llm_generation", "instant_deck_generation"}

    if job.job_type in root_job_types:
        lineage_valid = not dependencies if dependency_job_ids is not None else True
        generation_job_id = job.id if lineage_valid else None
        parent_job_id = None
    elif job.job_type in GENERATION_DESCENDANT_PARENT_FIELDS:
        input_generation_id = _nonempty_string(input_payload.get("generationWorkflowJobId"))
        output_generation_id = _nonempty_string(output_payload.get("generationWorkflowJobId"))
        generation_ids = {value for value in (input_generation_id, output_generation_id) if value}
        generation_job_id = next(iter(generation_ids)) if len(generation_ids) == 1 else None
        parent_field = GENERATION_DESCENDANT_PARENT_FIELDS[job.job_type]
        parent_job_id = _nonempty_string(input_payload.get(parent_field))
        if job.job_type == "schema_validation":
            parent_job_id = input_generation_id
        if job.job_type == JOB_TYPE_DB_PUBLISHER and input_payload.get("publishTarget") != "preview_ready":
            generation_job_id = None
            parent_job_id = None
        if dependency_job_ids is not None and (
            len(dependencies) != 1 or parent_job_id is None or dependencies[0] != parent_job_id
        ):
            generation_job_id = None
            parent_job_id = None
        if generation_job_id is None or parent_job_id is None:
            generation_job_id = None
            parent_job_id = None
    else:
        generation_job_id = None
        parent_job_id = None

    lineage = {
        "rootJobId": generation_job_id,
        "generationJobId": generation_job_id,
        "parentJobId": parent_job_id,
        "dependencyJobIds": dependencies,
        "authoritative": bool(authoritative_job_ids and job.id in authoritative_job_ids),
    }
    if getattr(job, "deck_id", None):
        lineage["workflowId"] = _workflow_id(job.deck_id)
    return lineage


def _workflow_dependency_ids(db: Session, jobs: list[WorkflowJob]) -> dict[str, list[str]]:
    job_ids = [job.id for job in jobs]
    if not job_ids:
        return {}
    dependencies = (
        db.query(WorkflowJobDependency)
        .filter(WorkflowJobDependency.job_id.in_(job_ids))
        .order_by(WorkflowJobDependency.created_at.asc(), WorkflowJobDependency.id.asc())
        .all()
    )
    dependency_ids: dict[str, list[str]] = {job_id: [] for job_id in job_ids}
    for dependency in dependencies:
        dependency_ids.setdefault(dependency.job_id, []).append(dependency.depends_on_job_id)
    return dependency_ids


def _authoritative_instant_chain_identity(
    jobs: list[WorkflowJob],
    dependency_ids: dict[str, list[str]],
) -> tuple[dict[str, Any] | None, set[str]]:
    generation_root, generation_chain = latest_generation_root_and_chain(
        jobs,
        generation_root_job_type="instant_deck_generation",
    )
    if generation_root is None or generation_root.job_type != "instant_deck_generation":
        return None, set()
    root_lineage = _workflow_job_lineage(
        generation_root,
        dependency_job_ids=dependency_ids.get(generation_root.id, []),
    )
    if root_lineage["generationJobId"] != generation_root.id:
        return None, set()

    for job in jobs:
        if job.job_type not in GENERATION_DESCENDANT_PARENT_FIELDS:
            continue
        input_payload = _coerce_mapping(job.input_json)
        output_payload = _coerce_mapping(job.output_json)
        input_generation_id = _nonempty_string(input_payload.get("generationWorkflowJobId"))
        output_generation_id = _nonempty_string(output_payload.get("generationWorkflowJobId"))
        if (
            input_generation_id
            and output_generation_id
            and input_generation_id != output_generation_id
            and generation_root.id in {input_generation_id, output_generation_id}
        ):
            return None, set()

    stage_types = ("schema_validation", "preview_render", JOB_TYPE_DB_PUBLISHER)
    stage_jobs: dict[str, WorkflowJob | None] = {}
    for job_type in stage_types:
        candidates = [
            job
            for job in generation_chain
            if job.job_type == job_type
            and not (
                job_type == JOB_TYPE_DB_PUBLISHER
                and (
                    _coerce_mapping(job.input_json).get("publishTarget") != "preview_ready"
                    or workflow_job_is_superseded_publisher_noop(job)
                )
            )
        ]
        if len(candidates) > 1:
            return None, set()
        stage_jobs[job_type] = candidates[0] if candidates else None

    ordered_jobs = [generation_root]
    expected_parent_id = generation_root.id
    for job_type in stage_types:
        stage_job = stage_jobs[job_type]
        if stage_job is None:
            if any(stage_jobs[later_type] is not None for later_type in stage_types[stage_types.index(job_type) + 1 :]):
                return None, set()
            continue
        lineage = _workflow_job_lineage(
            stage_job,
            dependency_job_ids=dependency_ids.get(stage_job.id, []),
        )
        if lineage["generationJobId"] != generation_root.id or lineage["parentJobId"] != expected_parent_id:
            return None, set()
        ordered_jobs.append(stage_job)
        expected_parent_id = stage_job.id

    authoritative_ids = {job.id for job in ordered_jobs}
    return {
        "workflowId": _workflow_id(generation_root.deck_id),
        "rootJobId": generation_root.id,
        "generationJobId": generation_root.id,
        "chainJobIds": [job.id for job in ordered_jobs],
        "schemaValidationJobId": stage_jobs["schema_validation"].id if stage_jobs["schema_validation"] else None,
        "previewRenderJobId": stage_jobs["preview_render"].id if stage_jobs["preview_render"] else None,
        "publisherJobId": stage_jobs[JOB_TYPE_DB_PUBLISHER].id if stage_jobs[JOB_TYPE_DB_PUBLISHER] else None,
    }, authoritative_ids


def _map_workflow_job_summary(
    job: WorkflowJob,
    *,
    dependency_job_ids: list[str] | None = None,
    authoritative_job_ids: set[str] | None = None,
) -> dict[str, Any]:
    output = _coerce_mapping(job.output_json)
    # DISABLED: phase = job.published_phase or workflow_job_phase(...) trusted invalid legacy values.
    published_phase = job.published_phase if job.published_phase in PUBLISHABLE_WORKFLOW_PHASES else None
    phase = published_phase or workflow_job_phase(job.job_type, job.status, output_payload=output)
    return {
        "jobId": job.id,
        **_workflow_job_lineage(
            job,
            dependency_job_ids=dependency_job_ids,
            authoritative_job_ids=authoritative_job_ids,
        ),
        "jobType": job.job_type,
        "status": job.status,
        "phase": phase,
        "attemptCount": int(job.attempt_count or 0),
        "maxAttempts": int(job.max_attempts or 0),
        "recoveryCount": int(job.recovery_count or 0),
        "progress": workflow_job_progress(job.status),
        "queuedAt": _iso(job.queued_at or job.created_at),
        "startedAt": _iso(job.started_at),
        "heartbeatAt": _iso(job.heartbeat_at),
        "updatedAt": _iso(job.updated_at),
        "lockedUntil": _iso(job.locked_until),
        "lastRecoveredAt": _iso(job.last_recovered_at),
        "lastRecoveredBy": job.last_recovered_by,
        "completedAt": _iso(job.completed_at),
        "failedAt": _iso(job.failed_at),
        # DISABLED: "publishedPhase": job.published_phase exposed invalid legacy publication markers.
        "publishedPhase": published_phase,
        "publishedAt": _iso(job.published_at),
        "workerId": job.locked_by,
        "terminal": _job_terminal(job),
        "terminalReason": job.terminal_reason,
        "retryEligible": _job_retry_eligible(job),
        "error": _job_error(job),
        **_workflow_job_liveness(job),
    }


def _map_workflow_job_artifact(artifact: WorkflowJobArtifact) -> dict[str, Any]:
    return {
        "artifactType": artifact.artifact_type,
        "artifactId": artifact.id,
        "storageKey": artifact.storage_key,
        "metadata": dict(artifact.metadata_json or {}),
    }


def _map_workflow_job_event(event: WorkflowJobEvent) -> dict[str, Any]:
    return {
        "eventType": event.event_type,
        "fromStatus": event.from_status,
        "toStatus": event.to_status or event.event_type,
        "message": event.message,
        "createdAt": _iso(event.created_at),
    }


def _latest_active_design_version(db: Session, deck_id: str) -> DesignVersion | None:
    return (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.is_active.is_(True))
        .order_by(DesignVersion.updated_at.desc())
        .first()
    )


def _latest_completed_publisher(jobs: list[WorkflowJob]) -> WorkflowJob | None:
    for job in jobs:
        if (
            job.job_type == JOB_TYPE_DB_PUBLISHER
            and job.status == JOB_STATUS_COMPLETED
            and job.published_phase
            and not workflow_job_is_superseded_publisher_noop(job)
        ):
            return job
    return None


def _latest_terminal_failure(jobs: list[WorkflowJob]) -> WorkflowJob | None:
    for job in jobs:
        if job.status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT}:
            return job
    return None


def _root_terminal_failure(jobs: list[WorkflowJob]) -> WorkflowJob | None:
    """Prefer the causal failed stage over dependency-blocked descendants."""
    for job in reversed(jobs):
        if job.status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_TIMED_OUT}:
            return job
    return _latest_terminal_failure(jobs)


def _latest_generation_chain(jobs: list[WorkflowJob]) -> tuple[WorkflowJob | None, list[WorkflowJob]]:
    generation_root, chain = latest_generation_root_and_chain(jobs)
    return generation_root, chain if generation_root is not None else jobs


SOURCE_PIPELINE_STAGE_JOB_TYPES = {
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "smart_deck_context",
    "brand_extraction",
}


def _authoritative_phase_jobs(
    jobs: list[WorkflowJob],
    generation_root: WorkflowJob | None,
    generation_chain: list[WorkflowJob],
) -> list[WorkflowJob]:
    if generation_root is None:
        return jobs

    selected: list[WorkflowJob] = []
    selected_ids: set[str] = set()
    for job in jobs:
        input_payload = _coerce_mapping(job.input_json)
        is_source_publisher = (
            job.job_type == JOB_TYPE_DB_PUBLISHER
            and not input_payload.get("generationWorkflowJobId")
            and str(input_payload.get("publishTarget") or "smart_deck_ready") == "smart_deck_ready"
        )
        if job.job_type in SOURCE_PIPELINE_STAGE_JOB_TYPES or is_source_publisher:
            selected.append(job)
            selected_ids.add(job.id)
    for job in generation_chain:
        if job.id not in selected_ids:
            selected.append(job)
            selected_ids.add(job.id)
    return selected


def _latest_completed_jobs_by_type(jobs: list[WorkflowJob]) -> dict[str, WorkflowJob]:
    latest: dict[str, WorkflowJob] = {}
    for job in jobs:
        if (
            job.status == JOB_STATUS_COMPLETED
            and job.job_type not in latest
            and not workflow_job_is_superseded_publisher_noop(job)
        ):
            latest[job.job_type] = job
    return latest


def _source_enrichment_payload(completed_jobs_by_type: dict[str, WorkflowJob]) -> dict[str, Any] | None:
    def _source_enrichment_message(source: str | None, provider: str | None, llm_status: str | None) -> str:
        normalized_source = str(source or "").strip().lower()
        normalized_llm_status = str(llm_status or "").strip().lower()
        if normalized_source == "llm":
            return f"Validated source labels are attached{f' via {provider}' if provider else ''}."
        if normalized_source == "deterministic":
            return "Deterministic source labels are attached."
        if normalized_llm_status == "disabled":
            return "Source enrichment is disabled; deterministic labels are attached."
        if normalized_llm_status == "missing_provider":
            return "No enrichment provider was available; deterministic labels are attached."
        if normalized_llm_status == "invalid_llm_output":
            return "The enrichment output was rejected; deterministic labels are attached."
        if normalized_llm_status == "llm_failed":
            return "The enrichment step fell back to deterministic labels."
        return "Source-label readiness has not been reported yet."

    def _source_enrichment_badge(source: str | None, llm_status: str | None) -> str:
        normalized_source = str(source or "").strip().lower()
        normalized_llm_status = str(llm_status or "").strip().lower()
        if normalized_source == "llm" or normalized_llm_status == "llm_enriched":
            return "LLM-enriched source labels"
        if normalized_source == "deterministic":
            return "Deterministic source labels"
        if normalized_llm_status == "disabled":
            return "LLM enrichment disabled"
        if normalized_llm_status == "missing_provider":
            return "LLM provider missing"
        if normalized_llm_status == "invalid_llm_output":
            return "LLM output rejected"
        if normalized_llm_status == "llm_failed":
            return "LLM enrichment fallback"
        return "Source labels pending"

    for job_type in ("smart_deck_context", "source_extraction"):
        job = completed_jobs_by_type.get(job_type)
        if job is None:
            continue
        output = _coerce_mapping(job.output_json)
        source_enrichment = _coerce_mapping(output.get("sourceEnrichment"))
        if source_enrichment:
            source = source_enrichment.get("source")
            llm_status = source_enrichment.get("llmStatus")
            provider = source_enrichment.get("provider")
            return {
                "source": source,
                "llmStatus": llm_status,
                "provider": provider,
                "model": source_enrichment.get("model"),
                "badge": source_enrichment.get("badge") or _source_enrichment_badge(source, llm_status),
                "message": source_enrichment.get("message") or _source_enrichment_message(source, provider, llm_status),
            }
        source = output.get("enrichmentSource")
        llm_status = output.get("llmStatus")
        provider = output.get("llmProvider") or output.get("provider")
        model = output.get("llmModel") or output.get("model")
        if any(value not in {None, ""} for value in (source, llm_status, provider, model)):
            return {
                "source": source,
                "llmStatus": llm_status,
                "provider": provider,
                "model": model,
                "badge": _source_enrichment_badge(source, llm_status),
                "message": _source_enrichment_message(source, provider, llm_status),
            }
    return None


def _source_preview_payload(db: Session, deck_id: str) -> list[dict[str, Any]]:
    slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck_id)
        .order_by(DeckSlide.slide_index.asc())
        .limit(4)
        .all()
    )

    # DISABLED: This function previously hand-built a second slide dictionary
    # without slide IDs or authenticated preview proxy URLs.
    # Reason: The duplicate mapper drifted from the canonical visualizer payload.
    # Difference: map_source_slide_payload supplies the same text/block/asset data
    # plus id, thumbnailUrl, previewImageUrl, and previewUrl.
    # preview = []
    # for slide in slides:
    #     preview.append({"slideIndex": slide.slide_index, "thumbnailPath": slide.thumbnail_path, ...})
    # return preview
    return [map_source_slide_payload(slide) for slide in slides]


def _brand_state_payload(deck: Deck) -> dict[str, Any]:
    profile = deck.brand_profile
    if profile is None:
        return {
            "profileId": None,
            "status": "idle",
            "ready": False,
            "sourceMode": None,
            "profile": None,
        }

    status = profile.processing_status or "idle"
    ready = bool(profile.logo_url or (profile.palette_json and len(profile.palette_json) > 0) or profile.primary_color)
    if ready:
        status = "ready"
    elif status == "ready":
        status = "idle"

    return {
        "profileId": profile.id,
        "status": status,
        "ready": ready,
        "sourceMode": profile.source_mode,
        "profile": {
            "id": profile.id,
            "status": status,
            "companyName": profile.company_name,
            "companyWebsiteUrl": profile.company_website_url,
            "logoUrl": profile.logo_url,
            "faviconUrl": profile.favicon_url,
            "primaryColor": profile.primary_color,
            "secondaryColor": profile.secondary_color,
            "accentColor": profile.accent_color,
            "backgroundColor": profile.background_color,
            "textColor": profile.text_color,
            "palette": list(profile.palette_json or []),
            "fontCandidates": list(profile.font_candidates_json or []),
            "confidenceScore": profile.confidence_score,
            "sourceMode": profile.source_mode,
            "brandingJson": normalize_branding_json_payload(profile.branding_json),
            "rawEvidence": dict(profile.raw_evidence_json or {}) if profile.raw_evidence_json else None,
            "warnings": list(profile.warnings_json or []),
            "updatedAt": profile.updated_at.isoformat() if profile.updated_at else None,
        },
    }


def _active_workflow_job(db: Session, jobs: list[WorkflowJob]) -> WorkflowJob | None:
    running_jobs = [job for job in jobs if job.status == JOB_STATUS_RUNNING]
    if running_jobs:
        running_jobs.sort(
            key=lambda job: (
                job.started_at or job.updated_at or job.created_at or datetime.min,
                job.created_at or datetime.min,
            ),
            reverse=True,
        )
        return running_jobs[0]

    queued_jobs = [job for job in jobs if job.status in CLAIMABLE_JOB_STATUSES]
    queued_jobs.sort(
        key=lambda job: (
            -(int(job.priority or 0)),
            job.created_at or datetime.min,
        ),
    )
    for job in queued_jobs:
        ready, blocked = workflow_job_dependencies_status(db, job)
        if ready and not blocked:
            return job
    return None


def _workflow_updated_at(
    *,
    jobs: list[WorkflowJob],
    deck_updated_at: datetime | None,
) -> str | None:
    candidates: list[datetime] = []
    for job in jobs[:25]:
        for value in (
            job.updated_at,
            job.completed_at,
            job.failed_at,
            job.heartbeat_at,
            job.started_at,
            job.queued_at,
            job.created_at,
        ):
            if value is not None:
                candidates.append(value)
                break
    if deck_updated_at is not None:
        candidates.append(deck_updated_at)
    if not candidates:
        return None
    return _iso(max(candidates))


def _provider_payload(db: Session, deck: Deck) -> dict[str, Any]:
    config = get_generation_provider_config(db, deck, None, strict=False, use_case="smart_deck")
    provider = str(config.get("provider") or "")
    api_key = config.get("apiKey")
    configured = provider not in {"", "missing", "missing_provider", "missing_openai", "missing_openrouter", "missing_claude", "fallback", "deterministic"} and bool(api_key)
    return {
        "configured": configured,
        "blockingReason": None if configured else "provider_not_configured",
        "provider": None if provider.startswith("missing") else provider,
        "model": config.get("model"),
    }


STAGE_BLOCKING_METADATA: dict[str, dict[str, bool]] = {
    "source_ingestion":      {"blocking_for_visualizer": True,  "blocking_for_export": True},
    "source_extraction":     {"blocking_for_visualizer": True,  "blocking_for_export": True},
    "miniatures":            {"blocking_for_visualizer": True,  "blocking_for_export": True},
    "brand_extraction":      {"blocking_for_visualizer": False, "blocking_for_export": True},
    "smart_deck_context":    {"blocking_for_visualizer": True,  "blocking_for_export": True},
    "db_publisher":          {"blocking_for_visualizer": True,  "blocking_for_export": True},
    "llm_generation":        {"blocking_for_visualizer": False, "blocking_for_export": True},
    "instant_deck_generation":{"blocking_for_visualizer": False, "blocking_for_export": True},
    "selected_slide_generation":   {"blocking_for_visualizer": False, "blocking_for_export": True},
    "schema_validation":     {"blocking_for_visualizer": False, "blocking_for_export": True},
    "preview_render":        {"blocking_for_visualizer": False, "blocking_for_export": True},
    "apply_version":         {"blocking_for_visualizer": False, "blocking_for_export": True},
    "export":                {"blocking_for_visualizer": False, "blocking_for_export": True},
    "compile_final_deck":    {"blocking_for_visualizer": False, "blocking_for_export": True},
}

ORDERED_STAGES = [
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "smart_deck_context",
    "db_publisher",
    "brand_extraction",
    "llm_generation",
    "instant_deck_generation",
    "selected_slide_generation",
    "schema_validation",
    "preview_render",
    "apply_version",
    "export",
    "compile_final_deck",
]


def _workflow_job_phases(jobs: list[WorkflowJob], active_job: WorkflowJob | None) -> list[dict[str, Any]]:
    latest_by_type: dict[str, WorkflowJob] = {}
    for job in jobs:
        if job.job_type not in latest_by_type:
            latest_by_type[job.job_type] = job

    active_job_type = active_job.job_type if active_job is not None else None
    phases: list[dict[str, Any]] = []
    for job_type in ORDERED_STAGES:
        job = latest_by_type.get(job_type)
        if job is None and active_job_type == job_type and active_job is not None:
            job = active_job
        workflow_status = job.status if job is not None else "pending"
        phase_description = (
            workflow_job_phase(
                job.job_type,
                job.status,
                output_payload=_coerce_mapping(job.output_json),
            )
            if job is not None
            else None
        )
        phase_status = _workflow_status_to_phase_status(str(workflow_status))
        phase_error = _job_error(job) if job is not None and phase_status == "failed" else None
        stage_meta = STAGE_BLOCKING_METADATA.get(job_type, {"blocking_for_visualizer": False, "blocking_for_export": True})
        phases.append(
            {
                "key": job_type,
                "label": _titleize_workflow_token(job_type),
                "description": phase_description,
                "status": phase_status,
                "active": phase_status == "active",
                "completed": phase_status == "completed",
                "started_at": _iso(job.started_at) if job is not None and job.started_at is not None else None,
                "completed_at": _iso(job.completed_at) if job is not None and job.completed_at is not None else None,
                "error": phase_error,
                "blocking_for_visualizer": stage_meta["blocking_for_visualizer"],
                "blocking_for_export": stage_meta["blocking_for_export"],
            }
        )
    return phases


def _workflow_missing_artifacts(
    *,
    source_file_saved: bool,
    source_extraction_ready: bool,
    thumbnail_count: int,
    generated_slide_count: int,
    renderable_schema_ready: bool,
    smart_deck_ready: bool,
    thumbnails_required: bool = True,
) -> list[str]:
    missing: list[str] = []
    if not source_file_saved:
        missing.append("source_file")
    if source_file_saved and not source_extraction_ready:
        missing.append("extracted_structure")
    if thumbnails_required and source_extraction_ready and thumbnail_count <= 0:
        missing.append("slide_thumbnails")
    if smart_deck_ready and generated_slide_count <= 0:
        missing.append("generated_slides")
    if smart_deck_ready and not renderable_schema_ready:
        missing.append("renderable_schema")
    return missing


def _lifecycle_status_from_phase(phase: str, workflow_status: str) -> str:
    if phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready", "source_ready", "selected_slide_generation_ready"}:
        return "ready"
    if workflow_status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT} or phase in {
        "failed_retryable",
        "failed_final",
        "needs_manual_review",
    }:
        return "failed"
    if phase in {
        "source_extraction_queued",
        "source_extraction_running",
        "miniatures_queued",
        "miniatures_running",
        "brand_extraction_queued",
        "brand_extraction_running",
        "smart_deck_context_queued",
        "smart_deck_context_running",
        "generation_queued",
        "generation_running",
        "selected_slide_generation_queued",
        "selected_slide_generation_running",
        "apply_queued",
        "apply_running",
        "export_queued",
        "export_running",
    } or workflow_status in {JOB_STATUS_QUEUED, JOB_STATUS_RUNNING}:
        return "processing"
    if phase in {"upload_accepted", "source_file_saved"}:
        return "queued"
    return "idle"


def _deck_extraction_status_from_phase(phase: str, workflow_status: str, source_file_saved: bool) -> str:
    if phase in {"source_ready", "smart_deck_ready", "preview_ready", "applied", "export_ready"}:
        return "ready"
    if phase in {
        "source_extraction_queued",
        "source_extraction_running",
        "miniatures_queued",
        "miniatures_running",
        "brand_extraction_queued",
        "brand_extraction_running",
        "smart_deck_context_queued",
        "smart_deck_context_running",
    } or workflow_status == JOB_STATUS_RUNNING:
        return "processing"
    if phase in {"upload_accepted"}:
        return "queued" if source_file_saved else "idle"
    if workflow_status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT} or phase in {
        "failed_retryable",
        "failed_final",
        "needs_manual_review",
    }:
        return "failed"
    return "queued" if source_file_saved else "idle"


def get_deck_workflow_state(db: Session, deck_id: str) -> dict[str, Any] | None:
    from app.services.llm.investor_public_research import public_research_status
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None

    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck_id).one_or_none()
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).one_or_none()
    active_version = _latest_active_design_version(db, deck_id)
    jobs = list_workflow_jobs_for_deck(db, deck_id)
    instant_upload = bool(deck_file and (deck_file.metadata_json or {}).get("preferredWorkspace") == "instant_deck")
    if instant_upload:
        # Optional/historical thumbnail work cannot own processing, failure, or
        # completion state for the canonical Instant Deck chain.
        jobs = [job for job in jobs if job.job_type != "miniatures"]
    dependency_ids = _workflow_dependency_ids(db, jobs)
    authoritative_instant_chain, authoritative_job_ids = _authoritative_instant_chain_identity(jobs, dependency_ids)
    latest_jobs = [
        _map_workflow_job_summary(
            job,
            dependency_job_ids=dependency_ids.get(job.id, []),
            authoritative_job_ids=authoritative_job_ids,
        )
        for job in jobs[:10]
    ]
    latest_jobs.sort(key=lambda item: item.get("queuedAt") or "", reverse=True)
    generation_root, authoritative_jobs = _latest_generation_chain(jobs)
    from app.services.llm.instant_factual_review import workflow_review
    factual_review = workflow_review(db, deck_id, generation_root.id if generation_root else None)
    active_job_model = _active_workflow_job(db, authoritative_jobs)
    active_job = (
        _map_workflow_job_summary(
            active_job_model,
            dependency_job_ids=dependency_ids.get(active_job_model.id, []),
            authoritative_job_ids=authoritative_job_ids,
        )
        if active_job_model is not None
        else None
    )

    published_job = _latest_completed_publisher(authoritative_jobs)
    readiness_publisher_job = _latest_completed_publisher(jobs)
    failed_job = _root_terminal_failure(authoritative_jobs)
    published_phase = (
        published_job.published_phase
        or workflow_job_phase(
            published_job.job_type,
            published_job.status,
            output_payload=_coerce_mapping(published_job.output_json),
        )
        if published_job is not None
        else None
    )
    completed_jobs_by_type = _latest_completed_jobs_by_type(jobs)
    authoritative_completed_jobs_by_type = _latest_completed_jobs_by_type(authoritative_jobs)
    strict_authoritative_jobs = [job for job in jobs if job.id in authoritative_job_ids]
    strict_authoritative_completed_jobs_by_type = _latest_completed_jobs_by_type(strict_authoritative_jobs)
    completed_job_types = set(completed_jobs_by_type)
    source_file_saved = deck_file is not None or "source_ingestion" in completed_job_types
    source_extraction_ready = bool({"source_extraction", "miniatures", "brand_extraction", "smart_deck_context", "db_publisher"} & completed_job_types)
    brand_extraction_ready = "brand_extraction" in completed_job_types
    source_context_ready = bool({"smart_deck_context", "db_publisher"} & completed_job_types)
    readiness_completed_jobs_by_type = (
        strict_authoritative_completed_jobs_by_type
        if generation_root is not None and generation_root.job_type == "instant_deck_generation"
        else authoritative_completed_jobs_by_type
    )
    renderable_schema_ready = bool(
        {"schema_validation", "preview_render", "apply_version", "export"}
        & set(readiness_completed_jobs_by_type)
    )

    phase = "upload_accepted"
    workflow_status = JOB_STATUS_QUEUED
    if active_job is not None:
        phase = str(active_job["phase"])
        workflow_status = str(active_job.get("status") or JOB_STATUS_RUNNING)
    elif published_job is not None:
        phase = str(published_phase or "upload_accepted")
        workflow_status = published_job.status
    elif failed_job is not None:
        phase = workflow_job_phase(failed_job.job_type, failed_job.status, output_payload=_coerce_mapping(failed_job.output_json))
        workflow_status = failed_job.status
    elif source_file_saved:
        phase = "source_file_saved"
        workflow_status = JOB_STATUS_COMPLETED

    provider = _provider_payload(db, deck)
    readiness_published_phase = (
        readiness_publisher_job.published_phase
        or workflow_job_phase(
            readiness_publisher_job.job_type,
            readiness_publisher_job.status,
            output_payload=_coerce_mapping(readiness_publisher_job.output_json),
        )
        if readiness_publisher_job is not None
        else None
    )
    published_ready_phase = str(readiness_published_phase or "")
    smart_deck_ready = published_ready_phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready"}
    blocking_reason = None
    if phase in {"smart_deck_ready", "source_ready"} and not provider["configured"]:
        blocking_reason = "provider_not_configured"
    elif (
        failed_job is not None
        and (active_job_model is None or active_job_model.id == failed_job.id)
        and (generation_root is not None or not smart_deck_ready)
    ):
        blocking_reason = _workflow_blocking_reason(failed_job)

    if phase in {"source_extraction_queued", "source_extraction_running", "miniatures_queued", "miniatures_running", "brand_extraction_queued", "brand_extraction_running", "smart_deck_context_queued", "smart_deck_context_running", "generation_queued", "generation_running", "selected_slide_generation_queued", "selected_slide_generation_running", "apply_queued", "apply_running"}:
        next_action = "view_processing"
    elif phase == "preview_ready":
        next_action = "apply_preview"
    elif phase == "applied":
        next_action = "open_smart_deck"
    elif phase == "smart_deck_ready" and not provider["configured"]:
        next_action = "configure_provider"
    elif phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready"}:
        next_action = "open_smart_deck"
    elif failed_job is not None and failed_job.status == JOB_STATUS_FAILED_RETRYABLE:
        next_action = "retry_job"
    elif failed_job is not None:
        next_action = "manual_review"
    elif deck_file is None:
        next_action = "continue_upload"
    else:
        next_action = "view_processing"

    slide_count = db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id).count()
    asset_count = db.query(DeckSlideAsset).filter(DeckSlideAsset.deck_id == deck_id).count()
    thumbnail_count = db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id, DeckSlide.thumbnail_path.isnot(None)).count()
    instant_generation_job = strict_authoritative_completed_jobs_by_type.get("instant_deck_generation")
    preview_render_job = strict_authoritative_completed_jobs_by_type.get("preview_render")
    instant_publisher_job = _latest_completed_publisher(strict_authoritative_jobs)
    generation_output = _coerce_mapping(generation_root.output_json) if generation_root is not None else {}
    instant_generation_output = _coerce_mapping(instant_generation_job.output_json) if instant_generation_job is not None else {}
    preview_render_output = _coerce_mapping(preview_render_job.output_json) if preview_render_job is not None else {}
    instant_publisher_output = _coerce_mapping(instant_publisher_job.output_json) if instant_publisher_job is not None else {}
    generation_design_version_id = generation_output.get("designVersionId")
    instant_design_version_id = instant_generation_output.get("designVersionId")
    generated_slide_count = 0
    if generation_root is None:
        generated_slide_count = db.query(GeneratedSlide).filter(GeneratedSlide.deck_id == deck_id).count()
    elif generation_design_version_id:
        generated_slide_count = (
            db.query(GeneratedSlide)
            .filter(
                GeneratedSlide.deck_id == deck_id,
                GeneratedSlide.design_version_id == generation_design_version_id,
                GeneratedSlide.generation_job_id == generation_root.id,
            )
            .count()
        )
    instant_version_publishable = False
    if instant_design_version_id:
        instant_version = (
            db.query(DesignVersion)
            .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == instant_design_version_id)
            .one_or_none()
        )
        if instant_version is not None:
            try:
                require_publishable_instant_design_version(instant_version)
                instant_version_publishable = True
            except GenerationValidationError:
                instant_version_publishable = False
    can_open_instant_deck = bool(
        authoritative_instant_chain is not None
        and instant_design_version_id
        and instant_version_publishable
        and instant_generation_output.get("coverageComplete") is True
        and instant_generation_output.get("wholeDeckCoverageComplete") is True
        and preview_render_output.get("designVersionId") == instant_design_version_id
        and preview_render_output.get("previewRenderable") is True
        and instant_publisher_job is not None
        and instant_publisher_job.published_phase == "preview_ready"
        and instant_publisher_output.get("publishTarget") == "preview_ready"
        and instant_publisher_output.get("generationWorkflowJobId") == instant_generation_job.id
        and instant_publisher_output.get("designVersionId") == instant_design_version_id
        and authoritative_instant_chain.get("generationJobId") == instant_generation_job.id
        and authoritative_instant_chain.get("previewRenderJobId") == preview_render_job.id
        and authoritative_instant_chain.get("publisherJobId") == instant_publisher_job.id
    )
    source_enrichment = _source_enrichment_payload(completed_jobs_by_type)
    brand_state = _brand_state_payload(deck)
    worker_heartbeat = get_latest_worker_heartbeat(db)
    failure_tickets = list_smart_deck_failure_events(db, deck_id=deck_id)

    source_context_job = completed_jobs_by_type.get("smart_deck_context")
    can_open_smart_deck = smart_deck_ready
    can_generate = can_open_smart_deck and provider["configured"]
    can_retry = bool(
        failed_job is not None
        and failed_job.status == JOB_STATUS_FAILED_RETRYABLE
        and (generation_root is not None or not smart_deck_ready)
    )
    degraded_mode = bool(
        (failed_job is not None and (generation_root is not None or not smart_deck_ready))
        or not worker_heartbeat.get("ok", False)
        or not provider["configured"]
        or (not smart_deck_ready and not source_file_saved)
    )
    lifecycle_status = _lifecycle_status_from_phase(phase, workflow_status)
    deck_extraction_status = _deck_extraction_status_from_phase(phase, workflow_status, source_file_saved)
    phase_jobs = _authoritative_phase_jobs(jobs, generation_root, authoritative_jobs)
    phases = _workflow_job_phases(phase_jobs, active_job_model)
    if instant_upload:
        phases = [stage for stage in phases if stage["key"] != "miniatures"]
    missing_artifacts = _workflow_missing_artifacts(
        source_file_saved=source_file_saved,
        source_extraction_ready=source_extraction_ready,
        thumbnail_count=thumbnail_count,
        generated_slide_count=generated_slide_count,
        renderable_schema_ready=renderable_schema_ready,
        smart_deck_ready=smart_deck_ready,
        thumbnails_required=not instant_upload,
    )
    failures = list(failure_tickets.get("tickets") or [])
    root_failure_visible = bool(
        failed_job is not None
        and (active_job_model is None or active_job_model.id == failed_job.id)
    )

    source_version_id = None
    if source_context_job is not None:
        source_output = _coerce_mapping(source_context_job.output_json)
        source_version_id = source_output.get("sourceRunId")

    return {
        "deckId": deck.id,
        "workflowId": _workflow_id(deck.id),
        "publicResearch": public_research_status(db, deck.id),
        "aiVcStrategy": ai_vc_strategy_status(db, deck_id=deck.id),
        "investmentCritique": investment_critique_status(db, deck.id),
        "sourceSummary": source_summary(db, deck.id),
        "visualIntelligence": visual_intelligence_status(db, deck.id),
        "visionReview": vision_review_status(db, deck.id),
        "authoritativeInstantChain": authoritative_instant_chain,
        "phase": phase,
        "activeStage": phase,
        "status": workflow_status,
        "lifecycleStatus": lifecycle_status,
        "nextAction": next_action,
        "blockingReason": blocking_reason,
        "message": failed_job.error_message if root_failure_visible else None,
        "sourceFileStatus": "saved" if source_file_saved else "missing",
        "sourceFileSaved": source_file_saved,
        "deckExtractionStatus": deck_extraction_status,
        "processingStage": phase,
        "processingStageLabel": _titleize_workflow_token(phase),
        "workerState": active_job["status"] if active_job is not None else workflow_status,
        "workerMessage": failed_job.error_message if root_failure_visible else None,
        "retryUrl": f"/api/products/deck-aistack-codes/decks/{deck.id}/retry",
        "canRemove": False,
        "canOpenSmartDeck": can_open_smart_deck,
        "canOpenInstantDeck": can_open_instant_deck,
        "canGenerate": can_generate,
        "canRetry": can_retry,
        "degradedMode": degraded_mode,
        "missingArtifacts": missing_artifacts,
        "failures": failures,
        "factualReview": factual_review,
        "workerHeartbeat": worker_heartbeat,
        "updatedAt": _workflow_updated_at(jobs=jobs, deck_updated_at=deck.updated_at),
        "activeJob": active_job,
        "failedJob": (
            _map_workflow_job_summary(
                failed_job,
                dependency_job_ids=dependency_ids.get(failed_job.id, []),
                authoritative_job_ids=authoritative_job_ids,
            )
            if failed_job is not None
            else None
        ),
        "latestJobs": latest_jobs[:5],
        "stages": phases,
        "phases": phases,
        "source": {
            "inputSourceId": deck_file.id if deck_file is not None else None,
            "sourceVersionId": source_version_id,
            "fileSaved": source_file_saved,
            "extractionReady": source_extraction_ready,
            "slideCount": slide_count,
            "assetCount": asset_count,
            "thumbnailCount": thumbnail_count,
            "thumbnailsRequired": not instant_upload,
            "brandExtractionReady": brand_extraction_ready,
            "sourceEnrichment": source_enrichment,
            "slides": _source_preview_payload(db, deck_id),
        },
        "smartDeck": {
            "workspaceId": workspace.id if workspace is not None else None,
            "ready": smart_deck_ready,
            "sourceSlideCount": slide_count,
            "generatedSlideCount": generated_slide_count,
            "activeDesignVersionId": active_version.id if active_version is not None else None,
            "hasRenderableSchema": renderable_schema_ready,
            "sourceContextReady": source_context_ready,
        },
        "provider": provider,
        "brand": brand_state,
        "links": {
            "processingUrl": f"/decks/{deck.id}/processing",
            "smartDeckUrl": f"/decks/{deck.id}/smart-deck",
        },
    }


def get_workflow_job(db: Session, job_id: str) -> dict[str, Any] | None:
    job = get_workflow_job_by_id(db, job_id)
    if job is None:
        return None

    deck_jobs = list_workflow_jobs_for_deck(db, job.deck_id)
    dependency_ids = _workflow_dependency_ids(db, deck_jobs)
    _authoritative_chain, authoritative_job_ids = _authoritative_instant_chain_identity(deck_jobs, dependency_ids)
    summary = _map_workflow_job_summary(
        job,
        dependency_job_ids=dependency_ids.get(job.id, []),
        authoritative_job_ids=authoritative_job_ids,
    )
    events = db.query(WorkflowJobEvent).filter(WorkflowJobEvent.job_id == job.id).order_by(WorkflowJobEvent.created_at.asc()).all()
    artifacts = db.query(WorkflowJobArtifact).filter(WorkflowJobArtifact.job_id == job.id).order_by(WorkflowJobArtifact.created_at.asc()).all()
    workspace = _workflow_job_workspace_payload(db, job)
    return {
        "jobId": summary["jobId"],
        "deckId": job.deck_id,
        "workflowId": _workflow_id(job.deck_id),
        "rootJobId": summary["rootJobId"],
        "generationJobId": summary["generationJobId"],
        "parentJobId": summary["parentJobId"],
        "dependencyJobIds": summary["dependencyJobIds"],
        "authoritative": summary["authoritative"],
        "jobType": summary["jobType"],
        "status": summary["status"],
        "phase": summary["phase"],
        "attemptCount": summary["attemptCount"],
        "maxAttempts": summary["maxAttempts"],
        "recoveryCount": summary["recoveryCount"],
        "priority": int(job.priority or 0),
        "idempotencyKey": job.idempotency_key,
        "workerId": summary["workerId"],
        "progress": summary["progress"],
        "input": _coerce_mapping(job.input_json) or None,
        "output": _coerce_mapping(job.output_json) or None,
        "artifacts": [_map_workflow_job_artifact(artifact) for artifact in artifacts],
        "error": summary["error"],
        "queuedAt": summary["queuedAt"],
        "startedAt": summary["startedAt"],
        "heartbeatAt": summary["heartbeatAt"],
        "updatedAt": summary["updatedAt"],
        "lockedUntil": summary["lockedUntil"],
        "lastRecoveredAt": summary["lastRecoveredAt"],
        "lastRecoveredBy": summary["lastRecoveredBy"],
        "completedAt": summary["completedAt"],
        "failedAt": summary["failedAt"],
        "publishedPhase": summary["publishedPhase"],
        "publishedAt": summary["publishedAt"],
        "terminal": summary["terminal"],
        "terminalReason": summary["terminalReason"],
        "retryEligible": summary["retryEligible"],
        "livenessStatus": summary["livenessStatus"],
        "heartbeatAgeSeconds": summary["heartbeatAgeSeconds"],
        "leaseExpiresAt": summary["leaseExpiresAt"],
        "operationDeadlineAt": summary["operationDeadlineAt"],
        "recoverable": summary["recoverable"],
        "nextAction": summary["nextAction"],
        "designVersion": _workflow_job_design_version_payload(db, job, workspace),
        "workspace": workspace,
        "events": [_map_workflow_job_event(event) for event in events],
    }


__all__ = ["get_deck_workflow_state", "get_workflow_job"]
