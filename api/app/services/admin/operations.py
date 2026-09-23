from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.utils import request_id
from app.db.models import (
    AiUsageBucket,
    AnalysisRun,
    AuthSession,
    CompiledDeck,
    Deck,
    DeckFile,
    DeckExtractionRun,
    DeckLlmArtifact,
    DeckExport,
    DeckSlide,
    DeckSlideAsset,
    DeckSlideBlock,
    DesignVersion,
    FailureTicket,
    ElementVariationJob,
    GeneratedSlide,
    GeneratedSlideCodeVersion,
    GeneratedSlideElement,
    GeneratedSlideElementVersion,
    GenerationJob,
    RateLimitBucket,
    SecurityAuditEvent,
    SmartDeckMessage,
    SmartEditRun,
    SmartEditSuggestion,
    User,
    WorkflowJob,
    WorkflowJobArtifact,
    WorkflowJobEvent,
    Workspace,
    WorkspaceAiProviderSetting,
)
from app.services.admin.security_audit import record_security_event
from app.services.admin.guardrail_client import get_guardrail_health_snapshot
from app.services.platform.admin.superadmin_client import get_superadmin_aistack_snapshot
from app.services.deck_processing.processing_visibility import get_deck_processing_visibility
from app.schemas.deck_workflow import WorkflowGenerationRequest
from app.services.admin.agent_learning_memory import record_generation_failure_memory
from app.services.admin.agent_telemetry import record_agent_event
from app.services.deck_processing.workflow_orchestration import queue_smart_deck_generation
from app.services.llm.generation_service import discard_design_version
from app.db.session import AiSessionLocal


logger = logging.getLogger(__name__)


SENSITIVE_RUN_FIELDS = [
    "prompt",
    "additional_context",
    "llm_context_json",
    "result_json",
    "payload_json",
    "error_message",
    "error_json",
    "content",
    "instruction",
    "original_text",
    "suggested_text",
]

ADMIN_ACTIVE_RUN_STATUSES = {"queued", "running", "pending", "processing"}
ADMIN_RETRYABLE_GENERATION_STATUSES = {"failed", "canceled"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None



def _deck_owner_context(db: Session, deck_id: str | None) -> tuple[str | None, str | None]:
    if not deck_id:
        return None, None
    deck = db.get(Deck, deck_id)
    if deck is None:
        return None, None
    return deck.workspace_id, deck.user_id


def _record_admin_agent_telemetry(
    db: Session,
    *,
    event_name: str,
    run_id: str,
    run_type: str,
    deck_id: str | None,
    actor: User,
    request: Any | None,
    status: str,
    previous_status: str | None,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    workspace_id, owner_user_id = _deck_owner_context(db, deck_id)
    record_agent_event(
        db,
        event_name=event_name,
        run_type=f"admin_{run_type}",
        workspace_id=workspace_id,
        deck_id=deck_id,
        user_id=owner_user_id,
        run_id=run_id,
        status=status,
        request_id=request_id(request),
        metadata={
            "actorUserId": actor.id,
            "adminAction": event_name,
            "targetRunType": run_type,
            "previousStatus": previous_status,
            "nextStatus": status,
            "reasonLength": len(reason),
            **(metadata or {}),
        },
        commit=True,
    )


def _preview(value: str | None, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _deck_context(db: Session) -> dict[str, dict[str, Any]]:
    rows = (
        db.query(
            Deck.id,
            Deck.title,
            Deck.user_id,
            Deck.workspace_id,
            User.email.label("user_email"),
            Workspace.name.label("workspace_name"),
        )
        .outerjoin(User, User.id == Deck.user_id)
        .outerjoin(Workspace, Workspace.id == Deck.workspace_id)
        .all()
    )
    return {
        row.id: {
            "deckTitle": row.title,
            "userId": row.user_id,
            "userEmail": row.user_email,
            "workspaceId": row.workspace_id,
            "workspaceName": row.workspace_name,
        }
        for row in rows
    }


def _run_base(
    *,
    id: str,
    run_type: str,
    status: str,
    deck_id: str | None,
    context: dict[str, Any] | None,
    provider: str | None = None,
    model: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    completed_at: datetime | None = None,
    selected_slide_count: int = 0,
    artifact_count: int = 0,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "runType": run_type,
        "status": status,
        "deckId": deck_id,
        "deckTitle": context.get("deckTitle") if context else None,
        "userId": context.get("userId") if context else None,
        "userEmail": context.get("userEmail") if context else None,
        "workspaceId": context.get("workspaceId") if context else None,
        "workspaceName": context.get("workspaceName") if context else None,
        "provider": provider,
        "model": model,
        "createdAt": _iso(created_at),
        "updatedAt": _iso(updated_at),
        "completedAt": _iso(completed_at),
        "selectedSlideCount": selected_slide_count,
        "artifactCount": artifact_count,
        "requestId": request_id,
        "metadata": metadata or {},
    }


def _slide_summary(slide: GeneratedSlide) -> dict[str, Any]:
    return {
        "id": slide.id,
        "sourceSlideId": slide.source_slide_id,
        "slideNumber": slide.slide_number,
        "title": slide.title,
        "status": slide.status,
        "validationStatus": slide.validation_status,
        "createdAt": _iso(slide.created_at),
        "updatedAt": _iso(slide.updated_at),
    }


def _design_version_summary(version: DesignVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "name": version.name,
        "status": version.status,
        "isActive": version.is_active,
        "summary": version.summary,
        "createdAt": _iso(version.created_at),
        "updatedAt": _iso(version.updated_at),
        "appliedAt": _iso(version.applied_at),
        "discardedAt": _iso(version.discarded_at),
    }


def _artifact_summary(artifact: DeckLlmArtifact) -> dict[str, Any]:
    metrics = artifact.metrics_json or {}
    provider = metrics.get("provider") if isinstance(metrics, dict) else None
    model = metrics.get("model") if isinstance(metrics, dict) else None
    return {
        "id": artifact.id,
        "artifactType": artifact.artifact_type,
        "artifactKey": artifact.artifact_key,
        "schemaVersion": artifact.schema_version,
        "status": artifact.status,
        "summary": artifact.summary,
        "provider": str(provider) if provider else None,
        "model": str(model) if model else None,
        "createdAt": _iso(artifact.created_at),
        "updatedAt": _iso(artifact.updated_at),
    }


def _extraction_run_summary(run: DeckExtractionRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "runType": run.run_type,
        "extractorName": run.extractor_name,
        "extractorVersion": run.extractor_version,
        "sourceFormat": run.source_format,
        "status": run.status,
        "slideCount": run.slide_count,
        "blockCount": run.block_count,
        "assetCount": run.asset_count,
        "hasError": bool(run.error_message or run.error_json),
        "errorCategory": "extraction" if run.error_message or run.error_json else None,
        "startedAt": _iso(run.started_at),
        "completedAt": _iso(run.completed_at),
        "createdAt": _iso(run.created_at),
        "updatedAt": _iso(run.updated_at),
    }


def _generation_job_summary(job: GenerationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "selectedSlideCount": len(job.selected_source_slide_ids_json or []),
        "styleId": job.style_id,
        "brandProductId": job.brand_product_id,
        "hasError": bool(job.error_message),
        "errorCategory": "provider_or_generation" if job.error_message else None,
        "createdAt": _iso(job.created_at),
        "updatedAt": _iso(job.updated_at),
        "completedAt": _iso(job.completed_at),
    }


def _source_file_summary(source_file: DeckFile | None) -> dict[str, Any] | None:
    if source_file is None:
        return None
    return {
        "id": source_file.id,
        "filename": source_file.filename,
        "originalFilename": source_file.original_filename,
        "fileRole": source_file.file_role,
        "mimeType": source_file.mime_type,
        "fileExtension": source_file.file_extension,
        "storageProvider": source_file.storage_provider,
        "size": source_file.size,
        "pageCount": source_file.page_count,
        "hasStoragePath": bool(source_file.storage_path),
        "uploadedAt": _iso(source_file.uploaded_at),
    }


def _workflow_job_refs_by_extraction_run(
    db: Session,
    extraction_run_ids: list[str],
) -> dict[str, dict[str, str | None]]:
    from app.db.models import WorkflowJob

    run_ids = [run_id for run_id in extraction_run_ids if isinstance(run_id, str) and run_id]
    if not run_ids:
        return {}

    mapping: dict[str, dict[str, str | None]] = {}
    jobs = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.extraction_run_id.in_(run_ids))
        .order_by(WorkflowJob.created_at.desc())
        .all()
    )
    for job in jobs:
        if job.extraction_run_id and job.extraction_run_id not in mapping:
            mapping[job.extraction_run_id] = {
                "workflowJobId": job.id,
                "workflowJobType": job.job_type,
            }
    return mapping


def _source_slide_summary(slide: DeckSlide, workflow_ref: dict[str, str | None] | None = None) -> dict[str, Any]:
    return {
        "id": slide.id,
        "extractionRunId": slide.extraction_run_id,
        "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
        "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
        "slideIndex": slide.slide_index,
        "slideNumber": slide.slide_number,
        "pageIndex": slide.page_index,
        "sourcePageNumber": slide.source_page_number,
        "title": slide.title,
        "role": slide.role,
        "semanticSlideType": slide.semantic_slide_type,
        "summary": slide.summary,
        "textPreview": _preview(slide.raw_text),
        "narrativeNotesPreview": _preview(slide.narrative_notes),
        "thumbnailMimeType": slide.thumbnail_mime_type,
        "hasThumbnail": bool(slide.thumbnail_path),
        "hasRenderedImage": bool(slide.rendered_image_path),
        "widthPoints": slide.width_points,
        "heightPoints": slide.height_points,
        "blockCount": slide.block_count,
        "assetCount": slide.asset_count,
        "createdAt": _iso(slide.created_at),
        "updatedAt": _iso(slide.updated_at),
    }


def _source_block_summary(block: DeckSlideBlock) -> dict[str, Any]:
    return {
        "id": block.id,
        "slideId": block.slide_id,
        "parentBlockId": block.parent_block_id,
        "blockIndex": block.block_index,
        "blockType": block.block_type,
        "blockKind": block.block_kind,
        "extractionStage": block.extraction_stage,
        "extractionSource": block.extraction_source,
        "semanticRole": block.semantic_role,
        "sourceKind": block.source_kind,
        "position": block.position,
        "textPreview": _preview(block.text or block.normalized_text or block.raw_text),
        "isVisible": block.is_visible,
        "confidence": block.confidence,
        "bbox": {
            "left": block.bbox_left,
            "top": block.bbox_top,
            "width": block.bbox_width,
            "height": block.bbox_height,
        },
        "createdAt": _iso(block.created_at),
        "updatedAt": _iso(block.updated_at),
    }


def _source_asset_summary(asset: DeckSlideAsset, workflow_ref: dict[str, str | None] | None = None) -> dict[str, Any]:
    return {
        "id": asset.id,
        "slideId": asset.slide_id,
        "extractionRunId": asset.extraction_run_id,
        "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
        "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
        "assetType": asset.asset_type,
        "assetKind": asset.asset_kind,
        "storageProvider": asset.storage_provider,
        "label": asset.label,
        "mimeType": asset.mime_type,
        "filename": asset.filename,
        "pageNumber": asset.page_number,
        "width": asset.width,
        "height": asset.height,
        "fileSizeBytes": asset.file_size_bytes,
        "hasStoragePath": bool(asset.storage_path),
        "createdAt": _iso(asset.created_at),
        "updatedAt": _iso(asset.updated_at),
    }


def _deck_structure_preview(db: Session, deck_id: str, *, slide_limit: int = 8, item_limit: int = 4) -> dict[str, Any]:
    slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck_id)
        .order_by(DeckSlide.slide_index.asc())
        .limit(slide_limit)
        .all()
    )
    slide_ids = [slide.id for slide in slides]
    blocks_by_slide: dict[str, list[DeckSlideBlock]] = {slide_id: [] for slide_id in slide_ids}
    assets_by_slide: dict[str, list[DeckSlideAsset]] = {slide_id: [] for slide_id in slide_ids}

    if slide_ids:
        for block in (
            db.query(DeckSlideBlock)
            .filter(DeckSlideBlock.slide_id.in_(slide_ids))
            .order_by(DeckSlideBlock.slide_id.asc(), DeckSlideBlock.block_index.asc())
            .all()
        ):
            bucket = blocks_by_slide.setdefault(block.slide_id, [])
            if len(bucket) < item_limit:
                bucket.append(block)

        for asset in (
            db.query(DeckSlideAsset)
            .filter(DeckSlideAsset.slide_id.in_(slide_ids))
            .order_by(DeckSlideAsset.slide_id.asc(), DeckSlideAsset.created_at.asc())
            .all()
        ):
            bucket = assets_by_slide.setdefault(asset.slide_id, [])
            if len(bucket) < item_limit:
                bucket.append(asset)

    extraction_warnings: list[dict[str, Any]] = []
    for slide in slides:
        metadata = slide.metadata_json if isinstance(slide.metadata_json, dict) else {}
        errors = metadata.get("extractionErrors")
        if not isinstance(errors, list):
            continue
        for error in errors:
            if not error:
                continue
            extraction_warnings.append(
                {
                    "slideId": slide.id,
                    "slideIndex": slide.slide_index,
                    "sourcePageNumber": slide.source_page_number,
                    "title": slide.title,
                    "message": str(error),
                }
            )

    extraction_run_ids = [
        run_id
        for run_id in {
            *[slide.extraction_run_id for slide in slides if slide.extraction_run_id],
            *[
                asset.extraction_run_id
                for assets in assets_by_slide.values()
                for asset in assets
                if asset.extraction_run_id
            ],
        }
    ]
    workflow_refs = _workflow_job_refs_by_extraction_run(db, extraction_run_ids)

    return {
        "slideLimit": slide_limit,
        "itemLimit": item_limit,
        "warningCount": len(extraction_warnings),
        "warnings": extraction_warnings[:25],
        "slides": [
            {
                **_source_slide_summary(slide, workflow_refs.get(slide.extraction_run_id or "")),
                "blocks": [_source_block_summary(block) for block in blocks_by_slide.get(slide.id, [])],
                "assets": [
                    _source_asset_summary(asset, workflow_refs.get(asset.extraction_run_id or ""))
                    for asset in assets_by_slide.get(slide.id, [])
                ],
            }
            for slide in slides
        ],
    }


def _generated_element_summary(element: GeneratedSlideElement) -> dict[str, Any]:
    return {
        "id": element.id,
        "generatedSlideId": element.generated_slide_id,
        "designVersionId": element.design_version_id,
        "sourceSlideId": element.source_slide_id,
        "elementKey": element.element_key,
        "elementType": element.element_type,
        "parentElementId": element.parent_element_id,
        "zIndex": element.z_index,
        "x": element.x,
        "y": element.y,
        "width": element.width,
        "height": element.height,
        "rotation": element.rotation,
        "locked": element.locked,
        "visible": element.visible,
        "versionCount": len(element.versions),
        "createdAt": _iso(element.created_at),
        "updatedAt": _iso(element.updated_at),
    }


def _element_version_summary(version: GeneratedSlideElementVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "elementId": version.element_id,
        "generatedSlideId": version.generated_slide_id,
        "designVersionId": version.design_version_id,
        "versionNumber": version.version_number,
        "source": version.source,
        "status": version.status,
        "changeSummary": version.change_summary,
        "hasStylePayload": bool(version.style_json),
        "hasContentPayload": bool(version.content_json),
        "styleKeys": sorted(version.style_json.keys()) if isinstance(version.style_json, dict) else [],
        "contentKeys": sorted(version.content_json.keys()) if isinstance(version.content_json, dict) else [],
        "createdAt": _iso(version.created_at),
    }


def _variation_job_summary(job: ElementVariationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "deckId": job.deck_id,
        "workspaceId": job.workspace_id,
        "generatedSlideId": job.generated_slide_id,
        "elementId": job.element_id,
        "baseElementVersionId": job.base_element_version_id,
        "userId": job.user_id,
        "instructionPreview": _preview(job.instruction),
        "variationCount": job.variation_count,
        "status": job.status,
        "outputElementVersionId": job.output_element_version_id,
        "hasError": bool(job.error_message),
        "errorCategory": "element_variation" if job.error_message else None,
        "createdAt": _iso(job.created_at),
        "startedAt": _iso(job.started_at),
        "completedAt": _iso(job.completed_at),
    }


def _admin_element_summary(
    element: GeneratedSlideElement,
    *,
    deck_context: dict[str, Any] | None,
    generated_slide: GeneratedSlide | None,
    source_slide: DeckSlide | None,
    design_version: DesignVersion | None,
    variation_jobs: list[ElementVariationJob],
) -> dict[str, Any]:
    content_keys = sorted(element.content_json.keys()) if isinstance(element.content_json, dict) else []
    style_keys = sorted(element.style_json.keys()) if isinstance(element.style_json, dict) else []
    return {
        "id": element.id,
        "deckId": element.deck_id,
        "deckTitle": deck_context.get("deckTitle") if deck_context else None,
        "userId": deck_context.get("userId") if deck_context else None,
        "userEmail": deck_context.get("userEmail") if deck_context else None,
        "workspaceId": deck_context.get("workspaceId") if deck_context else None,
        "workspaceName": deck_context.get("workspaceName") if deck_context else None,
        "generatedSlideId": element.generated_slide_id,
        "generatedSlideTitle": generated_slide.title if generated_slide else None,
        "generatedSlideNumber": generated_slide.slide_number if generated_slide else None,
        "sourceSlideId": element.source_slide_id,
        "sourceSlideTitle": source_slide.title if source_slide else None,
        "designVersionId": element.design_version_id,
        "designVersionName": design_version.name if design_version else None,
        "designVersionStatus": design_version.status if design_version else None,
        "elementKey": element.element_key,
        "elementType": element.element_type,
        "parentElementId": element.parent_element_id,
        "zIndex": element.z_index,
        "geometry": {
            "x": element.x,
            "y": element.y,
            "width": element.width,
            "height": element.height,
            "rotation": element.rotation,
        },
        "locked": element.locked,
        "visible": element.visible,
        "hasStylePayload": bool(element.style_json),
        "hasContentPayload": bool(element.content_json),
        "styleKeys": style_keys,
        "contentKeys": content_keys,
        "versionCount": len(element.versions),
        "variationJobCount": len(variation_jobs),
        "versions": [
            _element_version_summary(version)
            for version in sorted(element.versions, key=lambda item: item.version_number, reverse=True)
        ],
        "variationJobs": [_variation_job_summary(job) for job in variation_jobs],
        "createdAt": _iso(element.created_at),
        "updatedAt": _iso(element.updated_at),
    }


def _generated_code_summary(code_version: GeneratedSlideCodeVersion) -> dict[str, Any]:
    return {
        "id": code_version.id,
        "versionNumber": code_version.version_number,
        "codeKind": code_version.code_kind,
        "schemaVersion": code_version.schema_version,
        "status": code_version.status,
        "validationErrors": code_version.validation_errors_json or [],
        "createdAt": _iso(code_version.created_at),
    }


def _generated_slide_detail(slide: GeneratedSlide) -> dict[str, Any]:
    render_schema = slide.render_schema_json or {}
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "designVersionId": slide.design_version_id,
        "generationJobId": slide.generation_job_id,
        "sourceSlideId": slide.source_slide_id,
        "slideNumber": slide.slide_number,
        "title": slide.title,
        "status": slide.status,
        "validationStatus": slide.validation_status,
        "previewImageUrl": slide.preview_image_url,
        "renderSchema": render_schema,
        "renderSchemaSummary": {
            "schemaVersion": render_schema.get("schemaVersion") if isinstance(render_schema, dict) else None,
            "renderer": render_schema.get("renderer") if isinstance(render_schema, dict) else None,
            "width": render_schema.get("width") if isinstance(render_schema, dict) else None,
            "height": render_schema.get("height") if isinstance(render_schema, dict) else None,
            "elementCount": len(render_schema.get("elements", [])) if isinstance(render_schema, dict) else 0,
        },
        "designTokens": slide.design_tokens_json or {},
        "elementCount": len(slide.elements),
        "codeVersionCount": len(slide.code_versions),
        "elements": [_generated_element_summary(element) for element in sorted(slide.elements, key=lambda item: item.z_index)],
        "codeVersions": [
            _generated_code_summary(version)
            for version in sorted(slide.code_versions, key=lambda item: item.version_number, reverse=True)
        ],
        "createdAt": _iso(slide.created_at),
        "updatedAt": _iso(slide.updated_at),
    }


def _message_summary(message: SmartDeckMessage) -> dict[str, Any]:
    metadata = message.metadata_json or {}
    insight = metadata.get("insight") if isinstance(metadata, dict) else None
    return {
        "id": message.id,
        "role": message.role,
        "generationJobId": message.generation_job_id,
        "selectedSlideCount": len(message.selected_source_slide_ids_json or []),
        "intentType": metadata.get("intentType") if isinstance(metadata, dict) else None,
        "scope": metadata.get("scope") if isinstance(metadata, dict) else None,
        "summary": insight.get("summary") if isinstance(insight, dict) else None,
        "createdAt": _iso(message.created_at),
    }


def _suggestion_summary(suggestion: SmartEditSuggestion) -> dict[str, Any]:
    return {
        "id": suggestion.id,
        "slideId": suggestion.slide_id,
        "blockId": suggestion.block_id,
        "riskLevel": suggestion.risk_level,
        "status": suggestion.status,
        "reason": suggestion.reason,
    }


def _redaction_notice(extra: list[str] | None = None) -> dict[str, Any]:
    fields = [*SENSITIVE_RUN_FIELDS]
    if extra:
        fields.extend(extra)
    return {
        "sensitiveFieldsRedacted": sorted(set(fields)),
        "detailPolicy": "Admin run detail returns operational metadata and safe summaries only. Raw prompts, raw provider bodies, customer text payloads, and decrypted credentials are not returned.",
    }


def _admin_run_notes(db: Session, run_id: str, *, limit: int = 25) -> list[dict[str, Any]]:
    notes = (
        db.query(SecurityAuditEvent)
        .filter(
            SecurityAuditEvent.action == "admin.agent_run.note",
            SecurityAuditEvent.resource_type == "admin_agent_run",
            SecurityAuditEvent.resource_id == run_id,
        )
        .order_by(SecurityAuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": note.id,
            "actorUserId": note.actor_user_id,
            "actorEmail": note.actor_email,
            "note": note.details_json.get("note") if isinstance(note.details_json, dict) else None,
            "runType": note.details_json.get("runType") if isinstance(note.details_json, dict) else None,
            "requestId": note.request_id,
            "createdAt": _iso(note.created_at),
        }
        for note in notes
    ]


def _admin_run_detail_response(
    db: Session,
    run_id: str,
    *,
    run: dict[str, Any],
    related: dict[str, Any],
    redaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "run": run,
        "related": related,
        "redaction": redaction or _redaction_notice(),
        "notes": _admin_run_notes(db, run_id),
    }


def _clean_admin_action_reason(reason: str, *, field_name: str = "Reason", max_length: int = 500) -> str:
    clean_reason = " ".join(reason.split())
    if not clean_reason:
        raise ValueError(f"{field_name} is required.")
    if len(clean_reason) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return clean_reason


def _controlled_action_target(db: Session, run_id: str) -> tuple[Any, str, str | None] | None:
    from app.db.models import WorkflowJob

    for model, run_type in (
        (WorkflowJob, "workflow_job"),
        (GenerationJob, "generation_job"),
        (DeckLlmArtifact, "llm_artifact"),
        (AnalysisRun, "analysis_run"),
        (DeckExtractionRun, "deck_extraction"),
    ):
        record = db.get(model, run_id)
        if record is not None:
            return record, run_type, getattr(record, "deck_id", None)
    return None


def create_admin_agent_run_note(
    db: Session,
    *,
    run_id: str,
    note: str,
    actor: User,
    request: Any | None = None,
) -> dict[str, Any] | None:
    detail = get_admin_agent_run_detail(db, run_id)
    if detail is None:
        return None

    clean_note = " ".join(note.split())
    if not clean_note:
        raise ValueError("Note is required.")
    if len(clean_note) > 2000:
        raise ValueError("Note must be 2000 characters or fewer.")

    event = record_security_event(
        db,
        action="admin.agent_run.note",
        result="success",
        actor=actor,
        resource_type="admin_agent_run",
        resource_id=run_id,
        request=request,
        details={
            "note": clean_note,
            "runType": detail["run"].get("runType"),
            "deckId": detail["run"].get("deckId"),
        },
        commit=True,
    )
    return {
        "id": event.id,
        "actorUserId": event.actor_user_id,
        "actorEmail": event.actor_email,
        "note": clean_note,
        "runType": detail["run"].get("runType"),
        "requestId": event.request_id,
        "createdAt": _iso(event.created_at),
    }


def _record_generation_failure_memory_in_ai(
    core_db: Session,
    record: GenerationJob,
    actor: User,
    reason: str,
) -> None:
    ai_db = AiSessionLocal()
    try:
        record_generation_failure_memory(core_db, ai_db=ai_db, job=record, actor=actor, reason=reason)
        ai_db.commit()
    except Exception as exc:
        ai_db.rollback()
        logger.warning(
            "generation_failure_memory_persist_failed",
            extra={"runId": record.id, "errorType": exc.__class__.__name__},
        )
    finally:
        ai_db.close()


def mark_admin_agent_run_failed(
    db: Session,
    *,
    run_id: str,
    reason: str,
    actor: User,
    request: Any | None = None,
) -> dict[str, Any] | None:
    target = _controlled_action_target(db, run_id)
    if target is None:
        return None

    record, run_type, deck_id = target
    clean_reason = _clean_admin_action_reason(reason)
    previous_status = str(getattr(record, "status", "") or "")
    if previous_status.lower() not in ADMIN_ACTIVE_RUN_STATUSES:
        raise ValueError(f"Run status '{previous_status or 'unknown'}' cannot be marked failed by admin.")

    record.status = "failed"
    if hasattr(record, "completed_at"):
        record.completed_at = datetime.utcnow()
    if hasattr(record, "updated_at"):
        record.updated_at = datetime.utcnow()
    if hasattr(record, "error_message") and not getattr(record, "error_message", None):
        record.error_message = "Marked failed by admin."
    if isinstance(record, GenerationJob):
        if not settings.ai_database_url:
            record_generation_failure_memory(db, job=record, actor=actor, reason=clean_reason)
        else:
            _record_generation_failure_memory_in_ai(db, record, actor, clean_reason)

    event = record_security_event(
        db,
        action="admin.agent_run.mark_failed",
        result="success",
        actor=actor,
        resource_type="admin_agent_run",
        resource_id=run_id,
        request=request,
        details={
            "reason": clean_reason,
            "runType": run_type,
            "deckId": deck_id,
            "previousStatus": previous_status,
            "nextStatus": "failed",
        },
        commit=True,
    )
    _record_admin_agent_telemetry(
        db,
        event_name="admin.agent_run.mark_failed",
        run_id=run_id,
        run_type=run_type,
        deck_id=deck_id,
        actor=actor,
        request=request,
        status="failed",
        previous_status=previous_status,
        reason=clean_reason,
    )
    return {
        "run": get_admin_agent_run_detail(db, run_id)["run"],
        "auditEvent": {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        },
    }


def cancel_admin_agent_run(
    db: Session,
    *,
    run_id: str,
    reason: str,
    actor: User,
    request: Any | None = None,
) -> dict[str, Any] | None:
    target = _controlled_action_target(db, run_id)
    if target is None:
        return None

    record, run_type, deck_id = target
    clean_reason = _clean_admin_action_reason(reason)
    previous_status = str(getattr(record, "status", "") or "")
    if previous_status.lower() not in ADMIN_ACTIVE_RUN_STATUSES:
        raise ValueError(f"Run status '{previous_status or 'unknown'}' cannot be canceled by admin.")

    record.status = "canceled"
    if hasattr(record, "completed_at"):
        record.completed_at = datetime.utcnow()
    if hasattr(record, "updated_at"):
        record.updated_at = datetime.utcnow()

    event = record_security_event(
        db,
        action="admin.agent_run.cancel",
        result="success",
        actor=actor,
        resource_type="admin_agent_run",
        resource_id=run_id,
        request=request,
        details={
            "reason": clean_reason,
            "runType": run_type,
            "deckId": deck_id,
            "previousStatus": previous_status,
            "nextStatus": "canceled",
        },
        commit=True,
    )
    _record_admin_agent_telemetry(
        db,
        event_name="admin.agent_run.cancel",
        run_id=run_id,
        run_type=run_type,
        deck_id=deck_id,
        actor=actor,
        request=request,
        status="canceled",
        previous_status=previous_status,
        reason=clean_reason,
    )
    return {
        "run": get_admin_agent_run_detail(db, run_id)["run"],
        "auditEvent": {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        },
    }


def discard_admin_design_version(
    db: Session,
    *,
    run_id: str,
    reason: str,
    actor: User,
    request: Any | None = None,
) -> dict[str, Any] | None:
    version = db.get(DesignVersion, run_id)
    if version is None:
        return None

    clean_reason = _clean_admin_action_reason(reason)
    previous_status = version.status
    if version.status.lower() != "draft":
        raise ValueError(f"Design version status '{version.status or 'unknown'}' cannot be discarded by admin.")
    if version.is_active or version.applied_at is not None:
        raise ValueError("Active or applied design versions cannot be discarded by admin.")
    if version.discarded_at is not None:
        raise ValueError("Design version is already discarded.")

    payload = discard_design_version(db, version.deck_id, version.id)
    if payload is None:
        return None

    event = record_security_event(
        db,
        action="admin.design_version.discard",
        result="success",
        actor=actor,
        resource_type="design_version",
        resource_id=run_id,
        request=request,
        details={
            "reason": clean_reason,
            "deckId": version.deck_id,
            "generationJobId": version.generation_job_id,
            "previousStatus": previous_status,
            "nextStatus": "discarded",
        },
        commit=True,
    )
    _record_admin_agent_telemetry(
        db,
        event_name="admin.design_version.discard",
        run_id=run_id,
        run_type="design_version",
        deck_id=version.deck_id,
        actor=actor,
        request=request,
        status="discarded",
        previous_status=previous_status,
        reason=clean_reason,
        metadata={"generationJobId": version.generation_job_id},
    )
    return {
        "run": get_admin_agent_run_detail(db, run_id)["run"],
        "auditEvent": {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        },
    }


def retry_admin_agent_run(
    db: Session,
    *,
    run_id: str,
    reason: str,
    actor: User,
    request: Any | None = None,
) -> dict[str, Any] | None:
    original = db.get(GenerationJob, run_id)
    if original is None:
        return None

    clean_reason = _clean_admin_action_reason(reason)
    previous_status = original.status
    if previous_status.lower() not in ADMIN_RETRYABLE_GENERATION_STATUSES:
        raise ValueError(f"Generation job status '{previous_status or 'unknown'}' cannot be retried by admin.")

    retry_payload = WorkflowGenerationRequest(
        prompt=original.prompt,
        selectedSourceSlideIds=original.selected_source_slide_ids_json or [],
        idempotencyKey=f"{original.deck_id}:admin-retry:{original.id}",
        brandProductId=original.brand_product_id,
        additionalContext=original.additional_context,
        styleId=original.style_id,
        deckType=None,
        audience=None,
        preferredModel=original.model,
    )
    accepted = queue_smart_deck_generation(
        db,
        original.deck_id,
        current_user_id=actor.id,
        payload=retry_payload,
    )
    replacement_job = db.get(WorkflowJob, accepted["jobId"])
    if replacement_job is None:
        return None
    event = record_security_event(
        db,
        action="admin.agent_run.retry",
        result="success",
        actor=actor,
        resource_type="admin_agent_run",
        resource_id=run_id,
        request=request,
        details={
            "reason": clean_reason,
            "runType": "generation_job",
            "deckId": original.deck_id,
            "previousStatus": previous_status,
            "nextStatus": "retried",
            "replacementRunId": replacement_job.id,
            "replacementRunType": "workflow_job",
            "replacementWorkflowJobType": replacement_job.job_type,
        },
        commit=True,
    )
    _record_admin_agent_telemetry(
        db,
        event_name="admin.agent_run.retry",
        run_id=run_id,
        run_type="generation_job",
        deck_id=original.deck_id,
        actor=actor,
        request=request,
        status="retried",
        previous_status=previous_status,
        reason=clean_reason,
        metadata={
            "replacementRunId": replacement_job.id,
            "replacementRunType": "workflow_job",
            "replacementWorkflowJobType": replacement_job.job_type,
        },
    )
    return {
        "run": get_admin_agent_run_detail(db, replacement_job.id)["run"],
        "originalRun": get_admin_agent_run_detail(db, run_id)["run"],
        "auditEvent": {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        },
    }


def list_admin_agent_runs(db: Session, *, limit: int = 100) -> dict[str, Any]:
    deck_context = _deck_context(db)
    runs: list[dict[str, Any]] = []

    artifact_counts = dict(
        db.query(DeckLlmArtifact.artifact_key, func.count(DeckLlmArtifact.id)).group_by(DeckLlmArtifact.artifact_key).all()
    )

    for job in db.query(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(limit).all():
        selected = job.selected_source_slide_ids_json or []
        runs.append(
            _run_base(
                id=job.id,
                run_type="generation_job",
                status=job.status,
                deck_id=job.deck_id,
                context=deck_context.get(job.deck_id),
                provider=job.provider,
                model=job.model,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                selected_slide_count=len(selected),
                artifact_count=int(artifact_counts.get(job.id, 0)),
                metadata={
                    "styleId": job.style_id,
                    "brandProductId": job.brand_product_id,
                    "hasError": bool(job.error_message),
                    "errorCategory": "provider_or_generation" if job.error_message else None,
                },
            )
        )

    for version in db.query(DesignVersion).order_by(DesignVersion.created_at.desc()).limit(limit).all():
        runs.append(
            _run_base(
                id=version.id,
                run_type="design_version",
                status=version.status,
                deck_id=version.deck_id,
                context=deck_context.get(version.deck_id),
                created_at=version.created_at,
                updated_at=version.updated_at,
                completed_at=version.applied_at or version.discarded_at,
                artifact_count=len(version.generated_slides),
                metadata={
                    "generationJobId": version.generation_job_id,
                    "name": version.name,
                    "isActive": version.is_active,
                    "appliedAt": _iso(version.applied_at),
                    "discardedAt": _iso(version.discarded_at),
                },
            )
        )

    for artifact in db.query(DeckLlmArtifact).order_by(DeckLlmArtifact.created_at.desc()).limit(limit).all():
        metrics = artifact.metrics_json or {}
        provider = metrics.get("provider") if isinstance(metrics, dict) else None
        model = metrics.get("model") if isinstance(metrics, dict) else None
        runs.append(
            _run_base(
                id=artifact.id,
                run_type=f"llm_artifact:{artifact.artifact_type}",
                status=artifact.status,
                deck_id=artifact.deck_id,
                context=deck_context.get(artifact.deck_id),
                provider=str(provider) if provider else None,
                model=str(model) if model else None,
                created_at=artifact.created_at,
                updated_at=artifact.updated_at,
                selected_slide_count=int(metrics.get("selectedSlideCount", 0)) if isinstance(metrics, dict) else 0,
                artifact_count=1,
                metadata={
                    "artifactKey": artifact.artifact_key,
                    "schemaVersion": artifact.schema_version,
                    "summary": artifact.summary,
                },
            )
        )

    for run in db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).all():
        runs.append(
            _run_base(
                id=run.id,
                run_type="analysis_run",
                status=run.status,
                deck_id=run.deck_id,
                context=deck_context.get(run.deck_id),
                created_at=run.created_at,
            )
        )

    from app.db.models import WorkflowJob, WorkflowJobArtifact

    for run in db.query(WorkflowJob).order_by(WorkflowJob.created_at.desc()).limit(limit).all():
        artifact_count = db.query(WorkflowJobArtifact).filter(WorkflowJobArtifact.job_id == run.id).count()
        payload = run.output_json if isinstance(run.output_json, dict) else {}
        runs.append(
            _run_base(
                id=run.id,
                run_type=f"workflow_job:{run.job_type}",
                status=run.status,
                deck_id=run.deck_id,
                context=deck_context.get(run.deck_id),
                provider="deterministic",
                model=run.job_type,
                created_at=run.created_at,
                updated_at=run.updated_at,
                completed_at=run.completed_at or run.failed_at,
                selected_slide_count=int(payload.get("slideCount") or 0),
                artifact_count=artifact_count,
                metadata={
                    "jobType": run.job_type,
                    "attemptCount": int(run.attempt_count or 0),
                    "maxAttempts": int(run.max_attempts or 0),
                    "workerId": run.locked_by,
                    "hasError": bool(run.error_message),
                    "errorCategory": run.error_code,
                    "phase": payload.get("phase"),
                },
            )
        )

    for run in db.query(SmartEditRun).order_by(SmartEditRun.created_at.desc()).limit(limit).all():
        suggestion_count = db.query(SmartEditSuggestion).filter(SmartEditSuggestion.run_id == run.id).count()
        runs.append(
            _run_base(
                id=run.id,
                run_type="smart_edit_run",
                status="completed" if suggestion_count else "pending",
                deck_id=run.deck_id,
                context=deck_context.get(run.deck_id),
                provider="anthropic_or_deterministic",
                created_at=run.created_at,
                selected_slide_count=1,
                artifact_count=suggestion_count,
                metadata={
                    "slideId": run.slide_id,
                    "blockId": run.block_id,
                    "audienceType": run.audience_type,
                },
            )
        )

    assistant_messages = (
        db.query(SmartDeckMessage)
        .filter(SmartDeckMessage.role == "assistant")
        .order_by(SmartDeckMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    for message in assistant_messages:
        metadata = message.metadata_json or {}
        insight = metadata.get("insight") if isinstance(metadata, dict) else None
        runs.append(
            _run_base(
                id=str(metadata.get("assistantRunId") or message.id) if isinstance(metadata, dict) else message.id,
                run_type="assistant_message",
                status="completed",
                deck_id=message.deck_id,
                context=deck_context.get(message.deck_id),
                provider=str(metadata.get("provider")) if isinstance(metadata, dict) and metadata.get("provider") else None,
                model=str(metadata.get("model")) if isinstance(metadata, dict) and metadata.get("model") else None,
                created_at=message.created_at,
                selected_slide_count=len(message.selected_source_slide_ids_json or []),
                artifact_count=1,
                metadata={
                    "messageId": message.id,
                    "intentType": metadata.get("intentType") if isinstance(metadata, dict) else None,
                    "scope": metadata.get("scope") if isinstance(metadata, dict) else None,
                    "summary": insight.get("summary") if isinstance(insight, dict) else message.content[:240],
                },
            )
        )

    runs.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return {"runs": runs[:limit], "total": len(runs[:limit])}


def get_admin_agent_run_detail(db: Session, run_id: str) -> dict[str, Any] | None:
    deck_context = _deck_context(db)

    job = db.get(GenerationJob, run_id)
    if job:
        selected = job.selected_source_slide_ids_json or []
        run = _run_base(
            id=job.id,
            run_type="generation_job",
            status=job.status,
            deck_id=job.deck_id,
            context=deck_context.get(job.deck_id),
            provider=job.provider,
            model=job.model,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            selected_slide_count=len(selected),
            artifact_count=db.query(DeckLlmArtifact).filter(DeckLlmArtifact.artifact_key == job.id).count(),
            metadata={
                "styleId": job.style_id,
                "brandProductId": job.brand_product_id,
                "hasError": bool(job.error_message),
                "errorCategory": "provider_or_generation" if job.error_message else None,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "selectedSourceSlideIds": selected,
                "designVersions": [
                    _design_version_summary(version)
                    for version in db.query(DesignVersion)
                    .filter(DesignVersion.generation_job_id == job.id)
                    .order_by(DesignVersion.created_at.desc())
                    .limit(25)
                    .all()
                ],
                "generatedSlides": [
                    _slide_summary(slide)
                    for slide in db.query(GeneratedSlide)
                    .filter(GeneratedSlide.generation_job_id == job.id)
                    .order_by(GeneratedSlide.slide_number.asc())
                    .limit(100)
                    .all()
                ],
                "artifacts": [
                    _artifact_summary(artifact)
                    for artifact in db.query(DeckLlmArtifact)
                    .filter(DeckLlmArtifact.artifact_key == job.id)
                    .order_by(DeckLlmArtifact.created_at.desc())
                    .limit(25)
                    .all()
                ],
                "assistantMessages": [
                    _message_summary(message)
                    for message in db.query(SmartDeckMessage)
                    .filter(SmartDeckMessage.generation_job_id == job.id)
                    .order_by(SmartDeckMessage.created_at.desc())
                    .limit(25)
                    .all()
                ],
            },
        )

    workflow_job = db.get(WorkflowJob, run_id)
    if workflow_job:
        run = _run_base(
            id=workflow_job.id,
            run_type="workflow_job",
            status=workflow_job.status,
            deck_id=workflow_job.deck_id,
            context=deck_context.get(workflow_job.deck_id),
            created_at=workflow_job.created_at,
            updated_at=workflow_job.updated_at,
            completed_at=workflow_job.completed_at or workflow_job.failed_at,
            artifact_count=db.query(WorkflowJobArtifact).filter(WorkflowJobArtifact.job_id == workflow_job.id).count(),
            metadata={
                "jobType": workflow_job.job_type,
                "workflowPhase": (workflow_job.output_json or {}).get("publishedPhase") or (workflow_job.output_json or {}).get("phase"),
                "idempotencyKey": workflow_job.idempotency_key,
                "attemptCount": workflow_job.attempt_count,
                "maxAttempts": workflow_job.max_attempts,
                "recoveryCount": workflow_job.recovery_count,
                "lockedBy": workflow_job.locked_by,
                "lockedUntil": _iso(workflow_job.locked_until),
                "publishedPhase": workflow_job.published_phase,
                "publishedAt": _iso(workflow_job.published_at),
                "terminalReason": workflow_job.terminal_reason,
                "errorCode": workflow_job.error_code,
                "errorMessage": workflow_job.error_message,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "workflowJob": {
                    "jobType": workflow_job.job_type,
                    "status": workflow_job.status,
                    "input": workflow_job.input_json or {},
                    "output": workflow_job.output_json or {},
                },
                "events": [
                    {
                        "id": event.id,
                        "eventType": event.event_type,
                        "fromStatus": event.from_status,
                        "toStatus": event.to_status,
                        "message": event.message,
                        "createdAt": _iso(event.created_at),
                    }
                    for event in db.query(WorkflowJobEvent)
                    .filter(WorkflowJobEvent.job_id == workflow_job.id)
                    .order_by(WorkflowJobEvent.created_at.asc())
                    .limit(100)
                    .all()
                ],
                "artifacts": [
                    {
                        "id": artifact.id,
                        "artifactType": artifact.artifact_type,
                        "storageKey": artifact.storage_key,
                        "createdAt": _iso(artifact.created_at),
                        "metadata": artifact.metadata_json or {},
                    }
                    for artifact in db.query(WorkflowJobArtifact)
                    .filter(WorkflowJobArtifact.job_id == workflow_job.id)
                    .order_by(WorkflowJobArtifact.created_at.desc())
                    .limit(50)
                    .all()
                ],
            },
        )

    version = db.get(DesignVersion, run_id)
    if version:
        run = _run_base(
            id=version.id,
            run_type="design_version",
            status=version.status,
            deck_id=version.deck_id,
            context=deck_context.get(version.deck_id),
            created_at=version.created_at,
            updated_at=version.updated_at,
            completed_at=version.applied_at or version.discarded_at,
            artifact_count=len(version.generated_slides),
            metadata={
                "generationJobId": version.generation_job_id,
                "name": version.name,
                "isActive": version.is_active,
                "appliedAt": _iso(version.applied_at),
                "discardedAt": _iso(version.discarded_at),
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "generationJobId": version.generation_job_id,
                "generatedSlides": [_slide_summary(slide) for slide in version.generated_slides[:100]],
            },
        )

    artifact = db.get(DeckLlmArtifact, run_id)
    if artifact:
        metrics = artifact.metrics_json or {}
        provider = metrics.get("provider") if isinstance(metrics, dict) else None
        model = metrics.get("model") if isinstance(metrics, dict) else None
        run = _run_base(
            id=artifact.id,
            run_type=f"llm_artifact:{artifact.artifact_type}",
            status=artifact.status,
            deck_id=artifact.deck_id,
            context=deck_context.get(artifact.deck_id),
            provider=str(provider) if provider else None,
            model=str(model) if model else None,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            selected_slide_count=int(metrics.get("selectedSlideCount", 0)) if isinstance(metrics, dict) else 0,
            artifact_count=1,
            metadata={
                "artifactKey": artifact.artifact_key,
                "schemaVersion": artifact.schema_version,
                "summary": artifact.summary,
            },
        )
        workflow_ref = None
        if artifact.extraction_run_id:
            workflow_ref = _workflow_job_refs_by_extraction_run(db, [artifact.extraction_run_id]).get(artifact.extraction_run_id)
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "artifact": _artifact_summary(artifact),
                "extractionRunId": artifact.extraction_run_id,
                "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
                "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
            },
        )

    analysis_run = db.get(AnalysisRun, run_id)
    if analysis_run:
        run = _run_base(
            id=analysis_run.id,
            run_type="analysis_run",
            status=analysis_run.status,
            deck_id=analysis_run.deck_id,
            context=deck_context.get(analysis_run.deck_id),
            created_at=analysis_run.created_at,
        )
        return _admin_run_detail_response(db, run_id, run=run, related={})

    extraction_run = db.get(DeckExtractionRun, run_id)
    if extraction_run:
        workflow_ref = _workflow_job_refs_by_extraction_run(db, [extraction_run.id]).get(extraction_run.id)
        run = _run_base(
            id=extraction_run.id,
            run_type=f"deck_extraction:{extraction_run.run_type}",
            status=extraction_run.status,
            deck_id=extraction_run.deck_id,
            context=deck_context.get(extraction_run.deck_id),
            provider="deterministic",
            model=extraction_run.extractor_name,
            created_at=extraction_run.created_at,
            updated_at=extraction_run.updated_at,
            completed_at=extraction_run.completed_at,
            selected_slide_count=extraction_run.slide_count,
            artifact_count=extraction_run.asset_count,
            metadata={
                "extractorVersion": extraction_run.extractor_version,
                "sourceFormat": extraction_run.source_format,
                "blockCount": extraction_run.block_count,
                "hasError": bool(extraction_run.error_message or extraction_run.error_json),
                "errorCategory": "extraction" if extraction_run.error_message or extraction_run.error_json else None,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "sourceFileId": extraction_run.source_file_id,
                "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
                "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
                "llmArtifacts": [_artifact_summary(artifact) for artifact in extraction_run.llm_artifacts[:25]],
            },
        )

    smart_edit_run = db.get(SmartEditRun, run_id)
    if smart_edit_run:
        suggestions = (
            db.query(SmartEditSuggestion)
            .filter(SmartEditSuggestion.run_id == smart_edit_run.id)
            .order_by(SmartEditSuggestion.id.asc())
            .limit(25)
            .all()
        )
        run = _run_base(
            id=smart_edit_run.id,
            run_type="smart_edit_run",
            status="completed" if suggestions else "pending",
            deck_id=smart_edit_run.deck_id,
            context=deck_context.get(smart_edit_run.deck_id),
            provider="anthropic_or_deterministic",
            created_at=smart_edit_run.created_at,
            selected_slide_count=1,
            artifact_count=len(suggestions),
            metadata={
                "slideId": smart_edit_run.slide_id,
                "blockId": smart_edit_run.block_id,
                "audienceType": smart_edit_run.audience_type,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "suggestions": [_suggestion_summary(suggestion) for suggestion in suggestions],
            },
        )

    message = db.get(SmartDeckMessage, run_id)
    if message and message.role == "assistant":
        metadata = message.metadata_json or {}
        insight = metadata.get("insight") if isinstance(metadata, dict) else None
        run = _run_base(
            id=message.id,
            run_type="assistant_message",
            status="completed",
            deck_id=message.deck_id,
            context=deck_context.get(message.deck_id),
            provider=str(metadata.get("provider")) if isinstance(metadata, dict) and metadata.get("provider") else None,
            model=str(metadata.get("model")) if isinstance(metadata, dict) and metadata.get("model") else None,
            created_at=message.created_at,
            selected_slide_count=len(message.selected_source_slide_ids_json or []),
            artifact_count=1,
            metadata={
                "messageId": message.id,
                "intentType": metadata.get("intentType") if isinstance(metadata, dict) else None,
                "scope": metadata.get("scope") if isinstance(metadata, dict) else None,
                "summary": insight.get("summary") if isinstance(insight, dict) else None,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "message": _message_summary(message),
                "selectedSourceSlideIds": message.selected_source_slide_ids_json or [],
            },
        )

    assistant_message = next(
        (
            candidate
            for candidate in db.query(SmartDeckMessage)
            .filter(SmartDeckMessage.role == "assistant")
            .order_by(SmartDeckMessage.created_at.desc())
            .limit(1000)
            .all()
            if isinstance(candidate.metadata_json, dict) and candidate.metadata_json.get("assistantRunId") == run_id
        ),
        None,
    )
    if assistant_message:
        metadata = assistant_message.metadata_json or {}
        insight = metadata.get("insight") if isinstance(metadata, dict) else None
        run = _run_base(
            id=run_id,
            run_type="assistant_message",
            status="completed",
            deck_id=assistant_message.deck_id,
            context=deck_context.get(assistant_message.deck_id),
            provider=str(metadata.get("provider")) if isinstance(metadata, dict) and metadata.get("provider") else None,
            model=str(metadata.get("model")) if isinstance(metadata, dict) and metadata.get("model") else None,
            created_at=assistant_message.created_at,
            selected_slide_count=len(assistant_message.selected_source_slide_ids_json or []),
            artifact_count=1,
            metadata={
                "messageId": assistant_message.id,
                "intentType": metadata.get("intentType") if isinstance(metadata, dict) else None,
                "scope": metadata.get("scope") if isinstance(metadata, dict) else None,
                "summary": insight.get("summary") if isinstance(insight, dict) else None,
            },
        )
        return _admin_run_detail_response(
            db,
            run_id,
            run=run,
            related={
                "message": _message_summary(assistant_message),
                "selectedSourceSlideIds": assistant_message.selected_source_slide_ids_json or [],
            },
        )

    return None


def _processing_step_status(
    deck: Deck,
    latest_extraction: DeckExtractionRun | None,
    analysis_runs: list[AnalysisRun],
) -> list[dict[str, Any]]:
    steps = [
        ("upload", "Upload received"),
        ("extraction", "Deck extraction"),
        ("structure", "Slides and blocks persisted"),
        ("analysis", "Analysis runs"),
        ("generation", "Smart Deck generation"),
        ("design", "Design versions"),
        ("workspace", "Workspace ready"),
    ]
    completed_statuses = {"completed", "ready", "valid", "reviewed", "success", "draft", "applied"}
    running_statuses = {"running", "queued", "pending", "processing"}
    failed_statuses = {"failed", "failure", "error"}

    status_by_key: dict[str, str] = {}
    status_by_key["upload"] = "completed" if deck.file is not None else "pending"

    if latest_extraction is None:
        status_by_key["extraction"] = "pending"
    elif latest_extraction.status.lower() in failed_statuses:
        status_by_key["extraction"] = "failed"
    elif latest_extraction.status.lower() in running_statuses:
        status_by_key["extraction"] = "running"
    elif latest_extraction.status.lower() in completed_statuses:
        status_by_key["extraction"] = "completed"
    else:
        status_by_key["extraction"] = latest_extraction.status

    status_by_key["structure"] = "completed" if deck.slides else "pending"

    analysis_statuses = [run.status.lower() for run in analysis_runs]
    if any(status in failed_statuses for status in analysis_statuses):
        status_by_key["analysis"] = "failed"
    elif any(status in running_statuses for status in analysis_statuses):
        status_by_key["analysis"] = "running"
    elif analysis_statuses:
        status_by_key["analysis"] = "completed"
    else:
        status_by_key["analysis"] = "pending"

    generation_statuses = [job.status.lower() for job in deck.generation_jobs]
    if any(status in failed_statuses for status in generation_statuses):
        status_by_key["generation"] = "failed"
    elif any(status in running_statuses for status in generation_statuses):
        status_by_key["generation"] = "running"
    elif generation_statuses:
        status_by_key["generation"] = "completed"
    else:
        status_by_key["generation"] = "pending"

    design_statuses = [version.status.lower() for version in deck.design_versions]
    if any(status in failed_statuses for status in design_statuses):
        status_by_key["design"] = "failed"
    elif any(status in running_statuses for status in design_statuses):
        status_by_key["design"] = "running"
    elif design_statuses:
        status_by_key["design"] = "completed"
    else:
        status_by_key["design"] = "pending"

    status_by_key["workspace"] = "completed" if deck.status in {"ready", "reviewed"} else deck.status

    return [
        {
            "key": key,
            "label": label,
            "status": status_by_key.get(key, "pending"),
        }
        for key, label in steps
    ]


def _queue_position(db: Session, run: DeckExtractionRun | None) -> int | None:
    if run is None or run.status.lower() != "queued":
        return None

    queued_runs = (
        db.query(DeckExtractionRun.id)
        .filter(
            DeckExtractionRun.run_type == run.run_type,
            DeckExtractionRun.status == "queued",
        )
        .order_by(DeckExtractionRun.created_at.asc(), DeckExtractionRun.id.asc())
        .all()
    )
    for index, row in enumerate(queued_runs, start=1):
        if row[0] == run.id:
            return index
    return None


def _latest_error_message(
    latest_extraction: DeckExtractionRun | None,
    generation_jobs: list[GenerationJob],
    artifacts: list[DeckLlmArtifact],
) -> str | None:
    if latest_extraction is not None and latest_extraction.error_message:
        return latest_extraction.error_message

    for job in generation_jobs:
        if job.error_message:
            return job.error_message

    for artifact in artifacts:
        if artifact.summary and artifact.status.lower() == "failed":
            return artifact.summary

    return None


def _brand_status(deck: Deck) -> str:
    profile = deck.brand_profile
    if profile is None:
        return "pending"
    status = (profile.processing_status or "").lower()
    if status in {"queued", "running", "processing"}:
        return status
    if status in {"failed", "error"}:
        return "failed"
    if (
        profile.primary_color
        or profile.secondary_color
        or profile.accent_color
        or profile.background_color
        or profile.text_color
        or (profile.palette_json and len(profile.palette_json) > 0)
    ):
        return "ready"
    return "ready" if status == "ready" else "pending"


def _miniature_status(output_counts: dict, processing: dict | None) -> str:
    preview_count = int(output_counts.get("previewCount") or 0)
    slide_count = int(output_counts.get("slideCount") or 0)
    if preview_count > 0:
        return "ready"
    if slide_count > 0 and (processing is None or str(processing.get("state") or "") in {"processing", "ready"}):
        return "processing"
    return "pending"


def _llm_status(generation_jobs: list[GenerationJob]) -> str:
    if any(job.status.lower() in {"queued", "running", "processing"} for job in generation_jobs):
        return "processing"
    if any(job.status.lower() in {"failed", "error"} for job in generation_jobs):
        return "failed"
    if generation_jobs:
        return "ready"
    return "pending"


def _chat_status(deck: Deck, generation_jobs: list[GenerationJob], generated_slide_count: int) -> str:
    if generated_slide_count > 0:
        return "ready"
    if any(job.status.lower() in {"queued", "running", "processing"} for job in generation_jobs):
        return "processing"
    if deck.status.lower() in {"ready", "reviewed"}:
        return "ready"
    return "pending"


def _visualizer_status(generated_slides: list[GeneratedSlide]) -> str:
    if not generated_slides:
        return "pending"
    if any(
        isinstance(slide.render_schema_json, dict) and len(slide.render_schema_json.get("elements", [])) > 0
        for slide in generated_slides
    ):
        return "ready"
    return "processing"


def _export_status(compiled_decks: list[CompiledDeck], exports: list[DeckExport]) -> str:
    if any(compiled.status.lower() == "ready" for compiled in compiled_decks) or exports:
        return "ready"
    if compiled_decks:
        return "processing"
    return "pending"


def _processing_observability(
    *,
    db: Session,
    deck: Deck,
    latest_extraction: DeckExtractionRun | None,
    processing: dict | None,
    pipeline: list[dict[str, Any]],
    worker: dict,
    output_counts: dict,
    generation_jobs: list[GenerationJob],
    artifacts: list[DeckLlmArtifact],
    generated_slides: list[GeneratedSlide],
    compiled_decks: list[CompiledDeck],
    exports: list[DeckExport],
) -> dict[str, Any]:
    queue_position = worker.get("queuePosition") if isinstance(worker, dict) else None
    current_phase = (processing or {}).get("stageLabel") or next((phase["label"] for phase in pipeline if phase["status"] == "active"), None)
    current_phase = current_phase or (processing or {}).get("stage") or worker.get("message")
    latest_error = (processing or {}).get("errorMessage") or _latest_error_message(latest_extraction, generation_jobs, artifacts)

    return {
        "worker": {
            **worker,
            "queuePosition": queue_position,
        },
        "currentPhase": current_phase,
        "currentPhaseKey": (processing or {}).get("stage"),
        "queuePosition": queue_position,
        "lastError": latest_error,
        "artifactStatus": "ready" if artifacts else "pending",
        "brandStatus": _brand_status(deck),
        "miniatureStatus": _miniature_status(output_counts, processing),
        "llmStatus": _llm_status(generation_jobs),
        "chatStatus": _chat_status(deck, generation_jobs, len(generated_slides)),
        "visualizerStatus": _visualizer_status(generated_slides),
        "exportStatus": _export_status(compiled_decks, exports),
    }


def _admin_processing_snapshot(
    db: Session,
    deck: Deck,
    latest_extraction: DeckExtractionRun | None,
    *,
    slide_count: int,
) -> dict[str, Any] | None:
    if latest_extraction is None:
        return None

    metadata = latest_extraction.metadata_json if isinstance(latest_extraction.metadata_json, dict) else {}
    run_status = str(latest_extraction.status or "")
    workflow_ref = _workflow_job_refs_by_extraction_run(db, [latest_extraction.id]).get(latest_extraction.id)
    return {
        "runId": latest_extraction.id,
        "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
        "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
        "deckId": latest_extraction.deck_id,
        "sourceFileId": latest_extraction.source_file_id,
        "runType": latest_extraction.run_type,
        "status": run_status,
        "runStatus": run_status,
        "state": run_status,
        "stage": metadata.get("stage"),
        "stageLabel": metadata.get("stageLabel"),
        "nextAction": (
            "open_smart_deck"
            if deck.status.lower() in {"ready", "reviewed"} and slide_count > 0
            else str(metadata.get("nextAction") or "wait_for_processing")
        ),
        "createdAt": _iso(latest_extraction.created_at),
        "startedAt": _iso(latest_extraction.started_at),
        "completedAt": _iso(latest_extraction.completed_at),
        "heartbeatAt": _iso(latest_extraction.updated_at),
        "errorMessage": latest_extraction.error_message,
    }


def get_admin_deck_processing(db: Session, deck_id: str) -> dict[str, Any] | None:
    deck = db.get(Deck, deck_id)
    if deck is None:
        return None

    deck_context = _deck_context(db).get(deck.id)
    latest_extraction = (
        db.query(DeckExtractionRun)
        .filter(DeckExtractionRun.deck_id == deck.id)
        .order_by(DeckExtractionRun.created_at.desc())
        .first()
    )
    slide_count = db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id).count()
    block_count = db.query(DeckSlideBlock).filter(DeckSlideBlock.deck_id == deck.id).count()
    asset_count = (
        db.query(DeckSlideAsset)
        .join(DeckSlide, DeckSlideAsset.slide_id == DeckSlide.id)
        .filter(DeckSlide.deck_id == deck.id)
        .count()
    )
    generated_slide_count = db.query(GeneratedSlide).filter(GeneratedSlide.deck_id == deck.id).count()

    analysis_runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.deck_id == deck.id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(25)
        .all()
    )

    extraction_runs = (
        db.query(DeckExtractionRun)
        .filter(DeckExtractionRun.deck_id == deck.id)
        .order_by(DeckExtractionRun.created_at.desc())
        .limit(25)
        .all()
    )
    generation_jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.deck_id == deck.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(25)
        .all()
    )
    design_versions = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck.id)
        .order_by(DesignVersion.created_at.desc())
        .limit(25)
        .all()
    )
    artifacts = (
        db.query(DeckLlmArtifact)
        .filter(DeckLlmArtifact.deck_id == deck.id)
        .order_by(DeckLlmArtifact.created_at.desc())
        .limit(50)
        .all()
    )
    compiled_decks = (
        db.query(CompiledDeck)
        .filter(CompiledDeck.source_deck_id == deck.id)
        .order_by(CompiledDeck.finalized_at.desc())
        .limit(25)
        .all()
    )
    exports = (
        db.query(DeckExport)
        .filter(DeckExport.deck_id == deck.id)
        .order_by(DeckExport.created_at.desc())
        .limit(25)
        .all()
    )
    generated_slides = (
        db.query(GeneratedSlide)
        .filter(GeneratedSlide.deck_id == deck.id)
        .order_by(GeneratedSlide.slide_number.asc())
        .limit(50)
        .all()
    )
    visibility = get_deck_processing_visibility(db, deck.id) or {}
    processing = visibility.get("processing") if isinstance(visibility.get("processing"), dict) else _admin_processing_snapshot(db, deck, latest_extraction, slide_count=slide_count)
    pipeline = visibility.get("phases") if isinstance(visibility.get("phases"), list) and visibility.get("phases") else _processing_step_status(deck, latest_extraction, analysis_runs)
    worker = visibility.get("worker") if isinstance(visibility.get("worker"), dict) else {
        "workerRequired": False,
        "state": "not_started",
        "queueState": "not_queued",
        "runId": None,
        "workflowJobId": None,
        "workflowJobType": None,
        "queuedTooLong": False,
        "heartbeatStale": False,
        "staleReason": None,
        "message": "Smart Deck processing has not been started yet.",
        "oldestQueuedAt": None,
        "lastHeartbeatAt": None,
        "queuedAgeSeconds": None,
        "heartbeatAgeSeconds": None,
    }

    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "status": visibility.get("workflowStatus") or deck.status,
            "workflowId": visibility.get("workflowId"),
            "workflowPhase": visibility.get("workflowPhase"),
            "workflowStatus": visibility.get("workflowStatus"),
            "audience": deck.audience,
            "purpose": deck.purpose,
            "sourceType": deck.source_type,
            "declaredSlideCount": deck.slide_count,
            "summary": deck.summary,
            "createdAt": _iso(deck.created_at),
            "updatedAt": _iso(deck.updated_at),
            "userId": deck_context.get("userId") if deck_context else deck.user_id,
            "userEmail": deck_context.get("userEmail") if deck_context else None,
            "workspaceId": deck.workspace_id,
            "workspaceName": deck_context.get("workspaceName") if deck_context else None,
        },
        "sourceFile": _source_file_summary(deck.file),
        "counts": {
            "slides": slide_count,
            "blocks": block_count,
            "assets": asset_count,
            "extractionRuns": len(extraction_runs),
            "analysisRuns": len(analysis_runs),
            "generationJobs": len(generation_jobs),
            "designVersions": len(design_versions),
            "generatedSlides": generated_slide_count,
            "artifacts": len(artifacts),
        },
        "pipeline": pipeline,
        "observability": _processing_observability(
            db=db,
            deck=deck,
            latest_extraction=latest_extraction,
            processing=processing,
            pipeline=pipeline,
            worker=worker,
            output_counts={
                "slideCount": slide_count,
                "blockCount": block_count,
                "assetCount": asset_count,
                "previewCount": db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id, DeckSlide.thumbnail_path.isnot(None)).count(),
            },
            generation_jobs=generation_jobs,
            artifacts=artifacts,
            generated_slides=generated_slides,
            compiled_decks=compiled_decks,
            exports=exports,
        ),
        "structurePreview": _deck_structure_preview(db, deck.id),
        "extractionRuns": [_extraction_run_summary(run) for run in extraction_runs],
        "analysisRuns": [
            {
                "id": run.id,
                "status": run.status,
                "createdAt": _iso(run.created_at),
            }
            for run in analysis_runs
        ],
        "generationJobs": [_generation_job_summary(job) for job in generation_jobs],
        "designVersions": [_design_version_summary(version) for version in design_versions],
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "redaction": _redaction_notice(
            [
                "storage_path",
                "raw_json",
                "metadata_json",
                "render_schema_json",
                "design_tokens_json",
            ]
        ),
    }


def get_admin_deck_slides(db: Session, deck_id: str) -> dict[str, Any] | None:
    deck = db.get(Deck, deck_id)
    if deck is None:
        return None

    deck_context = _deck_context(db).get(deck.id)
    source_slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck.id)
        .order_by(DeckSlide.slide_index.asc())
        .all()
    )
    generated_slides = (
        db.query(GeneratedSlide)
        .filter(GeneratedSlide.deck_id == deck.id)
        .order_by(GeneratedSlide.slide_number.asc(), GeneratedSlide.created_at.desc())
        .all()
    )
    generated_by_source: dict[str | None, list[GeneratedSlide]] = {}
    for generated in generated_slides:
        generated_by_source.setdefault(generated.source_slide_id, []).append(generated)

    blocks_by_slide: dict[str, list[DeckSlideBlock]] = {}
    for block in (
        db.query(DeckSlideBlock)
        .filter(DeckSlideBlock.deck_id == deck.id)
        .order_by(DeckSlideBlock.slide_id.asc(), DeckSlideBlock.block_index.asc())
        .all()
    ):
        blocks_by_slide.setdefault(block.slide_id, []).append(block)

    assets_by_slide: dict[str, list[DeckSlideAsset]] = {}
    for asset in (
        db.query(DeckSlideAsset)
        .filter(DeckSlideAsset.deck_id == deck.id)
        .order_by(DeckSlideAsset.slide_id.asc(), DeckSlideAsset.created_at.asc())
        .all()
    ):
        assets_by_slide.setdefault(asset.slide_id, []).append(asset)

    design_versions = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck.id)
        .order_by(DesignVersion.created_at.desc())
        .limit(25)
        .all()
    )

    source_payload = []
    extraction_run_ids = [
        run_id
        for run_id in {
            *[slide.extraction_run_id for slide in source_slides if slide.extraction_run_id],
            *[
                asset.extraction_run_id
                for assets in assets_by_slide.values()
                for asset in assets
                if asset.extraction_run_id
            ],
        }
    ]
    workflow_refs = _workflow_job_refs_by_extraction_run(db, extraction_run_ids)
    for slide in source_slides:
        source_payload.append(
            {
                **_source_slide_summary(slide, workflow_refs.get(slide.extraction_run_id or "")),
                "blocks": [_source_block_summary(block) for block in blocks_by_slide.get(slide.id, [])],
                "assets": [
                    _source_asset_summary(asset, workflow_refs.get(asset.extraction_run_id or ""))
                    for asset in assets_by_slide.get(slide.id, [])
                ],
                "generatedSlides": [
                    _generated_slide_detail(generated) for generated in generated_by_source.get(slide.id, [])
                ],
            }
        )

    orphan_generated = [
        _generated_slide_detail(generated)
        for generated in generated_by_source.get(None, [])
    ]

    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "status": deck.status,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "createdAt": _iso(deck.created_at),
            "updatedAt": _iso(deck.updated_at),
            "userId": deck_context.get("userId") if deck_context else deck.user_id,
            "userEmail": deck_context.get("userEmail") if deck_context else None,
            "workspaceId": deck.workspace_id,
            "workspaceName": deck_context.get("workspaceName") if deck_context else None,
        },
        "counts": {
            "sourceSlides": len(source_slides),
            "generatedSlides": len(generated_slides),
            "blocks": sum(len(items) for items in blocks_by_slide.values()),
            "assets": sum(len(items) for items in assets_by_slide.values()),
            "designVersions": len(design_versions),
            "orphanGeneratedSlides": len(orphan_generated),
        },
        "designVersions": [_design_version_summary(version) for version in design_versions],
        "slides": source_payload,
        "orphanGeneratedSlides": orphan_generated,
        "redaction": _redaction_notice(
            [
                "raw_text",
                "normalized_text",
                "html_text",
                "alt_text",
                "raw_json",
                "metadata_json",
                "thumbnail_path",
                "rendered_image_path",
                "storage_path",
                "content_json",
                "style_json",
            ]
        ),
    }


def list_admin_elements(db: Session, *, deck_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    query = db.query(GeneratedSlideElement).order_by(GeneratedSlideElement.updated_at.desc())
    if deck_id:
        query = query.filter(GeneratedSlideElement.deck_id == deck_id)

    total = query.count()
    elements = query.limit(limit).all()
    deck_context = _deck_context(db)

    generated_slide_ids = {element.generated_slide_id for element in elements}
    source_slide_ids = {element.source_slide_id for element in elements if element.source_slide_id}
    design_version_ids = {element.design_version_id for element in elements}
    element_ids = {element.id for element in elements}

    generated_slides = {
        slide.id: slide
        for slide in db.query(GeneratedSlide).filter(GeneratedSlide.id.in_(generated_slide_ids or {""})).all()
    }
    source_slides = {
        slide.id: slide for slide in db.query(DeckSlide).filter(DeckSlide.id.in_(source_slide_ids or {""})).all()
    }
    design_versions = {
        version.id: version
        for version in db.query(DesignVersion).filter(DesignVersion.id.in_(design_version_ids or {""})).all()
    }

    variation_jobs_by_element: dict[str, list[ElementVariationJob]] = {element_id: [] for element_id in element_ids}
    variation_jobs = (
        db.query(ElementVariationJob)
        .filter(ElementVariationJob.element_id.in_(element_ids or {""}))
        .order_by(ElementVariationJob.created_at.desc())
        .limit(max(limit * 5, 100))
        .all()
    )
    for job in variation_jobs:
        variation_jobs_by_element.setdefault(job.element_id, []).append(job)

    element_payload = [
        _admin_element_summary(
            element,
            deck_context=deck_context.get(element.deck_id),
            generated_slide=generated_slides.get(element.generated_slide_id),
            source_slide=source_slides.get(element.source_slide_id) if element.source_slide_id else None,
            design_version=design_versions.get(element.design_version_id),
            variation_jobs=variation_jobs_by_element.get(element.id, [])[:10],
        )
        for element in elements
    ]

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for element in element_payload:
        element_type = str(element.get("elementType") or "unknown")
        type_counts[element_type] = type_counts.get(element_type, 0) + 1
        for version in element.get("versions", []):
            if isinstance(version, dict):
                status = str(version.get("status") or "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "elements": element_payload,
        "total": total,
        "limit": limit,
        "filters": {"deckId": deck_id},
        "typeCounts": type_counts,
        "versionStatusCounts": status_counts,
        "redaction": _redaction_notice(
            [
                "style_json",
                "content_json",
                "retrieval_context_json",
                "instruction",
                "error_message",
            ]
        ),
    }


def get_admin_quotas(db: Session, *, limit: int = 100) -> dict[str, Any]:
    ai_rows = (
        db.query(AiUsageBucket, User.email)
        .outerjoin(User, User.id == AiUsageBucket.user_id)
        .order_by(AiUsageBucket.updated_at.desc())
        .limit(limit)
        .all()
    )
    rate_rows = (
        db.query(RateLimitBucket)
        .order_by(RateLimitBucket.updated_at.desc())
        .limit(limit)
        .all()
    )

    default_ai_quota = settings.ai_daily_generation_quota
    ai_buckets = []
    for bucket, email in ai_rows:
        remaining = max(default_ai_quota - bucket.usage_count, 0) if bucket.quota_key == "daily_generation" else None
        pressure = (
            min(bucket.usage_count / default_ai_quota, 1)
            if bucket.quota_key == "daily_generation" and default_ai_quota > 0
            else None
        )
        ai_buckets.append(
            {
                "id": bucket.id,
                "userId": bucket.user_id,
                "userEmail": email,
                "quotaKey": bucket.quota_key,
                "windowStart": _iso(bucket.window_start),
                "usageCount": bucket.usage_count,
                "configuredLimit": default_ai_quota if bucket.quota_key == "daily_generation" else None,
                "remaining": remaining,
                "pressure": pressure,
                "updatedAt": _iso(bucket.updated_at),
            }
        )

    rate_buckets = [
        {
            "actorKey": bucket.actor_key,
            "windowStart": _iso(bucket.window_start),
            "requestCount": bucket.request_count,
            "updatedAt": _iso(bucket.updated_at),
        }
        for bucket in rate_rows
    ]

    quota_failures = [
        {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "resourceType": event.resource_type,
            "resourceId": event.resource_id,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        }
        for event in db.query(SecurityAuditEvent)
        .filter(SecurityAuditEvent.result == "failure")
        .filter(
            SecurityAuditEvent.action.in_(
                [
                    "deck.upload",
                    "deck_structure.extract",
                    "workspace_ai_provider.save",
                    "workspace_ai_provider.revoke",
                ]
            )
        )
        .order_by(SecurityAuditEvent.created_at.desc())
        .limit(25)
        .all()
    ]

    return {
        "summary": {
            "aiUsageBucketCount": db.query(AiUsageBucket).count(),
            "rateLimitBucketCount": db.query(RateLimitBucket).count(),
            "dailyAiGenerationQuota": default_ai_quota,
            "aiBucketsReturned": len(ai_buckets),
            "rateBucketsReturned": len(rate_buckets),
        },
        "aiUsageBuckets": ai_buckets,
        "rateLimitBuckets": rate_buckets,
        "recentFailures": quota_failures,
        "redaction": _redaction_notice(["actor_key", "source_ip", "user_agent", "details_json"]),
    }


def get_admin_provider_health(db: Session, *, limit: int = 100) -> dict[str, Any]:
    rows = (
        db.query(Workspace, User.email, WorkspaceAiProviderSetting, WorkspaceAiCredential)
        .outerjoin(User, User.id == Workspace.user_id)
        .outerjoin(WorkspaceAiProviderSetting, WorkspaceAiProviderSetting.workspace_id == Workspace.id)
        .outerjoin(WorkspaceAiCredential, WorkspaceAiCredential.id == WorkspaceAiProviderSetting.credential_id)
        .order_by(Workspace.updated_at.desc())
        .limit(limit)
        .all()
    )

    workspaces = []
    configured_count = 0
    skipped_count = 0
    missing_count = 0
    revoked_count = 0
    provider_counts: dict[str, int] = {}

    for workspace, owner_email, setting, credential in rows:
        provider = setting.provider if setting else None
        is_configured = bool(setting and setting.configured_at and credential and credential.is_active)
        is_skipped = bool(setting and setting.skipped_at and not is_configured)
        is_revoked = bool(credential and credential.revoked_at)
        if is_configured:
            configured_count += 1
        elif is_skipped:
            skipped_count += 1
        elif is_revoked:
            revoked_count += 1
        else:
            missing_count += 1
        provider_counts[str(provider or "missing")] = provider_counts.get(str(provider or "missing"), 0) + 1

        workspaces.append(
            {
                "workspaceId": workspace.id,
                "workspaceName": workspace.name,
                "ownerUserId": workspace.user_id,
                "ownerEmail": owner_email,
                "provider": provider,
                "preferredModel": setting.preferred_model if setting else None,
                "isConfigured": is_configured,
                "isSkipped": is_skipped,
                "isRevoked": is_revoked,
                "credentialSource": "workspace" if credential and credential.is_active else None,
                "credentialLast4": credential.api_key_last4 if credential else None,
                "keyVersion": credential.key_version if credential else None,
                "useForSmartDeck": setting.use_for_smart_deck if setting else None,
                "useForSmartEdit": setting.use_for_smart_edit if setting else None,
                "useForAnalysis": setting.use_for_analysis if setting else None,
                "configuredAt": _iso(setting.configured_at) if setting else None,
                "skippedAt": _iso(setting.skipped_at) if setting else None,
                "credentialCreatedAt": _iso(credential.created_at) if credential else None,
                "credentialRevokedAt": _iso(credential.revoked_at) if credential else None,
                "updatedAt": _iso(setting.updated_at) if setting else _iso(workspace.updated_at),
            }
        )

    provider_failures = [
        {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "actorEmail": event.actor_email,
            "action": event.action,
            "result": event.result,
            "resourceType": event.resource_type,
            "resourceId": event.resource_id,
            "requestId": event.request_id,
            "createdAt": _iso(event.created_at),
        }
        for event in db.query(SecurityAuditEvent)
        .filter(SecurityAuditEvent.result == "failure")
        .filter(SecurityAuditEvent.action.in_(["workspace_ai_provider.save", "workspace_ai_provider.revoke"]))
        .order_by(SecurityAuditEvent.created_at.desc())
        .limit(25)
        .all()
    ]

    return {
        "summary": {
            "workspacesReturned": len(workspaces),
            "workspaceCount": db.query(Workspace).count(),
            "configured": configured_count,
            "skipped": skipped_count,
            "missing": missing_count,
            "revoked": revoked_count,
            "systemAnthropicConfigured": bool(settings.anthropic_api_key),
            "systemOpenAiConfigured": bool(settings.openai_api_key),
            "systemDashscopeConfigured": bool(settings.effective_qwen_api_key),
            "generationMode": settings.deck_generation_mode,
            "mockMode": settings.deck_generation_mode.strip().lower() == "mock",
            "uploadStorageBackend": settings.upload_storage_backend,
            "uploadStorageS3Configured": bool(
                settings.upload_storage_backend == "s3"
                and settings.upload_storage_s3_bucket
                and settings.upload_storage_s3_region
                and settings.effective_s3_access_key
                and settings.effective_s3_secret_key
            ),
            "uploadStorageS3BucketConfigured": bool(settings.upload_storage_s3_bucket),
            "uploadStorageS3RegionConfigured": bool(settings.upload_storage_s3_region),
        },
        "providerCounts": provider_counts,
        "workspaces": workspaces,
        "recentFailures": provider_failures,
        "redaction": _redaction_notice(
            [
                "encrypted_api_key",
                "api_key",
                "raw_provider_body",
                "source_ip",
                "user_agent",
                "details_json",
            ]
        ),
    }


def list_admin_audit_events(
    db: Session,
    *,
    limit: int = 100,
    action: str | None = None,
    result: str | None = None,
    resource_type: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    query = db.query(SecurityAuditEvent).order_by(SecurityAuditEvent.created_at.desc())
    if action:
        query = query.filter(SecurityAuditEvent.action == action)
    if result:
        query = query.filter(SecurityAuditEvent.result == result)
    if resource_type:
        query = query.filter(SecurityAuditEvent.resource_type == resource_type)
    if actor:
        actor_like = f"%{actor}%"
        query = query.filter(
            (SecurityAuditEvent.actor_email.ilike(actor_like))
            | (SecurityAuditEvent.actor_user_id.ilike(actor_like))
        )

    total = query.count()
    events = query.limit(limit).all()
    result_counts = dict(db.query(SecurityAuditEvent.result, func.count(SecurityAuditEvent.id)).group_by(SecurityAuditEvent.result).all())
    top_actions = [
        {"action": row.action, "count": row.count}
        for row in (
            db.query(SecurityAuditEvent.action.label("action"), func.count(SecurityAuditEvent.id).label("count"))
            .group_by(SecurityAuditEvent.action)
            .order_by(func.count(SecurityAuditEvent.id).desc())
            .limit(20)
            .all()
        )
    ]
    resource_type_counts = dict(
        db.query(SecurityAuditEvent.resource_type, func.count(SecurityAuditEvent.id))
        .group_by(SecurityAuditEvent.resource_type)
        .all()
    )

    return {
        "events": [
            {
                "id": event.id,
                "actorUserId": event.actor_user_id,
                "actorEmail": event.actor_email,
                "action": event.action,
                "resourceType": event.resource_type,
                "resourceId": event.resource_id,
                "result": event.result,
                "requestId": event.request_id,
                "hasSourceIp": bool(event.source_ip),
                "hasUserAgent": bool(event.user_agent),
                "detailKeys": sorted(event.details_json.keys()) if isinstance(event.details_json, dict) else [],
                "createdAt": _iso(event.created_at),
            }
            for event in events
        ],
        "total": total,
        "limit": limit,
        "filters": {
            "action": action,
            "result": result,
            "resourceType": resource_type,
            "actor": actor,
        },
        "resultCounts": result_counts,
        "resourceTypeCounts": {str(key or "none"): value for key, value in resource_type_counts.items()},
        "topActions": top_actions,
        "redaction": _redaction_notice(["source_ip", "user_agent", "details_json"]),
    }


def get_admin_overview(db: Session) -> dict[str, Any]:
    runs = list_admin_agent_runs(db, limit=50)["runs"]
    failed = [run for run in runs if str(run.get("status", "")).lower() in {"failed", "error"} or run["metadata"].get("hasError")]
    running = [run for run in runs if str(run.get("status", "")).lower() in {"running", "queued", "pending", "processing"}]
    completed = [run for run in runs if str(run.get("status", "")).lower() in {"completed", "ready", "valid", "draft"}]

    provider_counts: dict[str, int] = {}
    for run in runs:
        provider = run.get("provider") or "unknown"
        provider_counts[str(provider)] = provider_counts.get(str(provider), 0) + 1

    return {
        "summary": {
            "users": db.query(User).count(),
            "workspaces": db.query(Workspace).count(),
            "decks": db.query(Deck).count(),
            "authSessions": db.query(AuthSession).count(),
            "workspaceAiConfigured": (
                db.query(WorkspaceAiProviderSetting)
                .filter(WorkspaceAiProviderSetting.configured_at.isnot(None))
                .count()
            ),
            "auditEvents": db.query(SecurityAuditEvent).count(),
            "agentRuns": len(runs),
            "agentRunsFailed": len(failed),
            "agentRunsRunning": len(running),
            "agentRunsCompleted": len(completed),
            "aiUsageBuckets": db.query(AiUsageBucket).count(),
            "rateLimitBuckets": db.query(RateLimitBucket).count(),
        },
        "providerCounts": provider_counts,
        "recentRuns": runs[:12],
        "recentActivity": [
            {
                "id": event.id,
                "actorUserId": event.actor_user_id,
                "actorEmail": event.actor_email,
                "action": event.action,
                "result": event.result,
                "resourceType": event.resource_type,
                "resourceId": event.resource_id,
                "requestId": event.request_id,
                "createdAt": _iso(event.created_at),
            }
            for event in db.query(SecurityAuditEvent).order_by(SecurityAuditEvent.created_at.desc()).limit(12).all()
        ],
    }


def get_admin_safety_controls(db: Session) -> dict[str, Any]:
    guardrails = get_guardrail_health_snapshot()
    superadmin = get_superadmin_aistack_snapshot()

    incident_backlog_query = db.query(FailureTicket)
    incident_backlog_total = incident_backlog_query.count()
    incident_backlog_new = incident_backlog_query.filter(FailureTicket.status == "new").count()
    incident_backlog_critical = incident_backlog_query.filter(FailureTicket.severity == "critical").count()
    incident_backlog_blocked_by_guardrails = incident_backlog_query.filter(
        FailureTicket.source == "backend",
        FailureTicket.error_name == "GuardrailBlocked",
    ).count()
    recent_incidents = [
        _ticket_row(ticket)
        for ticket in incident_backlog_query.order_by(desc(FailureTicket.created_at)).limit(20).all()
    ]

    guardrail_audit_events = (
        db.query(SecurityAuditEvent)
        .filter(SecurityAuditEvent.action == "guardrails.evaluate")
        .order_by(desc(SecurityAuditEvent.created_at))
        .limit(25)
        .all()
    )

    guardrail_audit_rows: list[dict[str, Any]] = []
    for event in guardrail_audit_events:
        details = event.details_json if isinstance(event.details_json, dict) else {}
        guardrail_audit_rows.append(
            {
                "id": event.id,
                "action": event.action,
                "result": event.result,
                "resourceType": event.resource_type,
                "resourceId": event.resource_id,
                "requestId": event.request_id,
                "actorEmail": event.actor_email,
                "createdAt": event.created_at.isoformat(),
                "allowed": bool(details.get("allowed")),
                "riskLevel": details.get("riskLevel"),
                "reason": details.get("reason"),
                "policy": details.get("policy"),
                "blockedReasons": details.get("blockedReasons") or [],
            }
        )

    guardrail_decision_counts = {
        "allowed": len([row for row in guardrail_audit_rows if row["result"] == "allowed"]),
        "blocked": len([row for row in guardrail_audit_rows if row["result"] == "blocked"]),
        "failed": len([row for row in guardrail_audit_rows if row["result"] == "failed"]),
    }

    operator_summary = None
    if isinstance(guardrails.get("operatorSummary"), dict):
        operator_summary = guardrails.get("operatorSummary")

    return {
        "summary": {
            "incidentBacklogTotal": incident_backlog_total,
            "incidentBacklogNew": incident_backlog_new,
            "incidentBacklogCritical": incident_backlog_critical,
            "guardrailBlockedTickets": incident_backlog_blocked_by_guardrails,
            "guardrailEvaluations": guardrail_decision_counts.get("allowed", 0)
            + guardrail_decision_counts.get("blocked", 0)
            + guardrail_decision_counts.get("failed", 0),
            "guardrailsConfigured": bool(guardrails.get("configured")),
            "guardrailStatus": guardrails.get("status"),
            "superAdminConfigured": bool(superadmin.get("configured")),
            "superAdminStatus": superadmin.get("status"),
        },
        "guardrails": guardrails,
        "superAdminService": superadmin,
        "guardrailDecisions": {
            "counts": guardrail_decision_counts,
            "events": guardrail_audit_rows,
            "operatorSummary": operator_summary,
        },
        "incidentBacklog": {
            "total": incident_backlog_total,
            "new": incident_backlog_new,
            "critical": incident_backlog_critical,
            "tickets": recent_incidents,
        },
        "redaction": {
            "sensitiveFieldsRedacted": ["errorStack", "context", "errorMessage"],
            "detailPolicy": "Safety controls keep raw stack and context collapsed; action fields are intended for operator triage.",
        },
    }


def _ticket_row(ticket: FailureTicket) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "status": ticket.status,
        "severity": ticket.severity,
        "source": ticket.source,
        "route": ticket.route,
        "apiPath": ticket.api_path,
        "userEmail": ticket.user_email,
        "deckId": ticket.deck_id,
        "errorName": ticket.error_name,
        "errorMessage": ticket.error_message,
        "createdAt": ticket.created_at.isoformat() if ticket.created_at else None,
        "requestId": ticket.request_id,
        "statusCode": ticket.status_code,
    }


def get_admin_agent_teams(db: Session) -> dict[str, Any]:
    runs = list_admin_agent_runs(db, limit=250)["runs"]
    run_type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for run in runs:
        run_type = str(run.get("runType") or "unknown")
        status = str(run.get("status") or "unknown").lower()
        run_type_counts[run_type] = run_type_counts.get(run_type, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

    teams = [
        _agent_team_template(
            key="smart_deck_production",
            name="Smart Deck Production Team",
            purpose="Coordinate slide redesign from selected source slides into reviewable design versions.",
            run_types=["generation_job", "llm_artifact:smart_deck_generation", "assistant"],
            roles=[
                ("planner", "Planner", "Frames the requested deck outcome and selected slide scope."),
                ("context_builder", "Context builder", "Loads deck, slide, brand, audience, and artifact context."),
                ("designer", "Design generator", "Creates generated slide JSON as a draft design version."),
                ("validator", "Schema validator", "Rejects invalid render payloads before user review."),
                ("reviewer", "Human reviewer", "Accepts, retries, discards, or exports the reviewed iteration."),
            ],
            handoffs=[
                "Planner -> context builder uses selected slide IDs and explicit instruction.",
                "Context builder -> design generator sends bounded JSON context, not direct database access.",
                "Design generator -> validator returns structured render schema only.",
                "Validator -> reviewer stores draft artifacts for non-destructive review.",
            ],
            run_type_counts=run_type_counts,
            runs=runs,
        ),
        _agent_team_template(
            key="diligence_review",
            name="Diligence Review Team",
            purpose="Separate evidence extraction, gap finding, and audience adaptation into inspectable stages.",
            run_types=["analysis_run", "adaptation_run", "llm_artifact:diligence", "llm_artifact:adaptation"],
            roles=[
                ("evidence_mapper", "Evidence mapper", "Connects claims to source slide blocks and extracted artifacts."),
                ("gap_finder", "Gap finder", "Flags unsupported claims, missing proof, and investor review risk."),
                ("audience_adapter", "Audience adapter", "Reframes findings for a selected investor or stakeholder audience."),
                ("review_owner", "Review owner", "Keeps findings and suggestions human-approved before edits."),
            ],
            handoffs=[
                "Evidence mapper -> gap finder passes slide/block references, not free-form deck summaries.",
                "Gap finder -> audience adapter passes typed findings and risk levels.",
                "Audience adapter -> review owner produces suggestions, never silent deck mutation.",
            ],
            run_type_counts=run_type_counts,
            runs=runs,
        ),
        _agent_team_template(
            key="smart_edit_handoff",
            name="Smart Edit Handoff Team",
            purpose="Route block-level changes through suggestion, review, and accepted revision boundaries.",
            run_types=["smart_edit_run", "smart_edit_suggestion"],
            roles=[
                ("block_selector", "Block selector", "Identifies the exact source block and surrounding slide context."),
                ("edit_suggester", "Edit suggester", "Creates a narrow text or structure suggestion."),
                ("consistency_checker", "Consistency checker", "Checks tone, diligence category, and source preservation."),
                ("approver", "Approver", "Applies accepted revisions only after user review."),
            ],
            handoffs=[
                "Block selector -> edit suggester passes one block plus safe context.",
                "Edit suggester -> consistency checker passes a suggestion object.",
                "Consistency checker -> approver leaves the source deck untouched until approval.",
            ],
            run_type_counts=run_type_counts,
            runs=runs,
        ),
        _agent_team_template(
            key="export_assembly",
            name="Export Assembly Team",
            purpose="Treat final deck compilation as a coordinated handoff from reviewed versions to export records.",
            run_types=["compiled_deck", "deck_export", "design_version"],
            roles=[
                ("version_resolver", "Version resolver", "Chooses applied or accepted slide versions."),
                ("assembly_worker", "Assembly worker", "Builds the final deck slide order and export payload."),
                ("provenance_checker", "Provenance checker", "Confirms source/deck links remain traceable."),
                ("export_operator", "Export operator", "Creates downloadable artifacts and status records."),
            ],
            handoffs=[
                "Version resolver -> assembly worker passes reviewed slide version IDs.",
                "Assembly worker -> provenance checker passes final deck composition.",
                "Provenance checker -> export operator records export state and errors.",
            ],
            run_type_counts=run_type_counts,
            runs=runs,
        ),
    ]
    return {
        "summary": {
            "teamCount": len(teams),
            "observedRuns": len(runs),
            "runningRuns": sum(
                count for status, count in status_counts.items() if status in {"running", "queued", "pending", "processing"}
            ),
            "failedRuns": sum(count for status, count in status_counts.items() if status in {"failed", "error", "failure"}),
        },
        "teams": teams,
        "runTypeCounts": run_type_counts,
        "statusCounts": status_counts,
        "principles": [
            "Coordinate agents through persisted handoffs, not direct peer-to-peer autonomy.",
            "Keep each specialist role bounded to one resource type and one output contract.",
            "Make human approval the boundary before generated work mutates deck state.",
            "Use admin observability to debug which role or handoff failed.",
        ],
    }


def _agent_team_template(
    *,
    key: str,
    name: str,
    purpose: str,
    run_types: list[str],
    roles: list[tuple[str, str, str]],
    handoffs: list[str],
    run_type_counts: dict[str, int],
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    observed_count = sum(
        count for run_type, count in run_type_counts.items() if any(run_type.startswith(expected) for expected in run_types)
    )
    live_runs = [
        run
        for run in runs
        if any(str(run.get("runType") or "").startswith(expected) for expected in run_types)
    ][:8]
    return {
        "key": key,
        "name": name,
        "purpose": purpose,
        "status": "observed" if observed_count else "planned",
        "observedRunCount": observed_count,
        "roles": [
            {
                "key": role_key,
                "name": role_name,
                "responsibility": responsibility,
                "status": "active" if observed_count else "planned",
            }
            for role_key, role_name, responsibility in roles
        ],
        "handoffs": handoffs,
        "runTypes": run_types,
        "recentRuns": live_runs,
    }
