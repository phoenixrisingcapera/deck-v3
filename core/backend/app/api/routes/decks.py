from pathlib import Path
import json

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact, User
from app.schemas.analysis import AnalysisFindingsRouteResponse
from app.schemas.audience_diligence import AudienceDiligenceRequest, AudienceDiligenceResponse
from app.schemas.audience_conversion import AudienceConversionWorkflowResponse
from app.schemas.deck import DeckCreate, ExportCreate, SlideBlockPatch, SmartEditCreate, SuggestionPatch
from app.schemas.due_diligence_workflow import DueDiligenceWorkflowResponse
from app.schemas.deck_workflow import WorkflowExportRequest
from app.schemas.smart_edit import SmartEditResponse, SmartEditSuggestionRouteResponse
from app.schemas.smart_edit_workflow import (
    SmartEditClassifyRequest,
    SmartEditIntentClassificationResponse,
    SmartEditPatchRequest,
    SmartEditSlideSummaryRequest,
    SmartEditSlideSummaryResponse,
    SmartEditWorkflowRunResponse,
)
from app.schemas.analysis import AdaptationSuggestionsRouteResponse
from app.services.deck_processing.deck_mutation_service import analyse_deck, create_deck, patch_block, patch_suggestion, patch_suggestion_with_audit
from app.services.visualizer.slide_read_model import get_findings, get_suggestions
from app.services.visualizer.slide_read_model import get_blocks, get_deck, get_slides, get_status, list_decks
from app.services.rendering.export_service import export_download_payload, get_export
from app.services.visualizer.deck_iteration_read_model import get_deck_iterations
from app.services.rendering.final_deck_service import get_compiled_deck, get_final_deck_for_iteration, get_latest_compiled_deck, prepare_full_deck
from app.services.platform.billing.ai_usage_quota_service import enforce_ai_generation_quota
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.admin.guardrail_client import evaluate_deck_guardrail
from app.services.llm.smart_edit_rate_limit import enforce_smart_edit_quota
from app.services.llm.due_diligence_service import (
    analyze_due_diligence_risks,
    build_due_diligence_report,
    extract_due_diligence_claims,
    get_latest_due_diligence_report,
)
from app.services.llm.audience_diligence_service import (
    analyze_audience_diligence,
    generate_smart_deck_instructions,
    get_latest_audience_diligence,
    plan_audience_diligence,
    run_audience_diligence,
)
from app.services.llm.smart_edit_service import (
    classify_smart_edit_intent,
    create_reviewable_smart_edit_patch,
    create_smart_edit,
    get_reviewable_smart_edit_run,
)
from app.services.llm.generation_service import SmartDeckProviderUnavailableError
from app.services.llm.slide_summary_service import generate_persisted_slide_summary
from app.services.visualizer.slide_read_model import SMART_DECK_ASSISTANT_ARTIFACT_TYPE, load_deck_llm_artifact_payload
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.services.deck_processing.workflow_orchestration import (
    WorkflowConflictError,
    export_fallback_idempotency_key,
    queue_export,
    queue_source_extraction,
)
from app.services.deck_processing.upload_service import attach_limited_upload, complete_deck_upload, create_deck_upload_url
from app.services.storage.upload_security import require_supported_deck_upload, stream_limited_upload

router = APIRouter(prefix="/decks", tags=["decks"])


def _is_smart_edit_provider_capacity_error(exc: Exception) -> bool:
    # Compatibility wrapper retained for existing route tests and imports.
    from app.services.llm.provider_errors import is_provider_capacity_error

    return is_provider_capacity_error(exc)


def _raise_provider_capacity_http_error(exc: Exception, *, feature: str) -> None:
    from app.services.llm.provider_errors import is_provider_capacity_error, provider_capacity_error_detail

    if is_provider_capacity_error(exc):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=provider_capacity_error_detail(feature=feature)) from exc
    raise exc


@router.get("")
def decks_index(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    return {"decks": list_decks(db, current_user.id, include_all=current_user.role == "super_admin")}


@router.post("")
def decks_create(payload: DeckCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    deck = create_deck(db, payload.model_dump(), current_user.id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return deck




@router.get("/generated/latest")
def decks_latest_generated(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    compiled = get_latest_compiled_deck(
        db,
        user_id=current_user.id,
        include_all=current_user.role == "super_admin",
    )
    if compiled is None:
        return {"latestGeneratedDeck": None}
    return {"latestGeneratedDeck": compiled["featuredCard"], "compiledDeck": compiled}


@router.get("/{deck_id}")
def decks_show(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    deck = get_deck(db, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@router.post("/{deck_id}/upload-url")
def decks_upload_url(
    deck_id: str,
    request: Request,
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    filename = str(payload.get("filename") or payload.get("fileName") or "deck.pdf")
    mime_type = str(payload.get("mimeType") or payload.get("contentType") or "application/octet-stream")
    size_value = payload.get("sizeBytes") if payload.get("sizeBytes") is not None else payload.get("size")
    size = int(size_value) if size_value is not None else None
    try:
        upload = create_deck_upload_url(db, deck_id=deck_id, filename=filename, mime_type=mime_type, size=size)
        record_security_event(
            db,
            action="deck.upload_url.create",
            result="success",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={
                "filename": filename,
                "mimeType": mime_type,
                "size": size,
                "storagePath": upload.get("storagePath"),
                "expiresIn": upload.get("expiresIn"),
            },
            commit=True,
        )
    except LookupError as exc:
        record_security_event(
            db,
            action="deck.upload_url.create",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": "not_found", "filename": filename, "mimeType": mime_type},
            commit=True,
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.upload_url.create",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__, "filename": filename, "mimeType": mime_type},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        record_security_event(
            db,
            action="deck.upload_url.create",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__, "filename": filename, "mimeType": mime_type},
            commit=True,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"upload": upload}


@router.post("/{deck_id}/upload-complete")
def decks_upload_complete(
    deck_id: str,
    request: Request,
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    storage_path = str(payload.get("storagePath") or payload.get("storage_path") or "")
    filename = str(payload.get("filename") or payload.get("fileName") or Path(storage_path).name or "deck.pdf")
    mime_type = str(payload.get("mimeType") or payload.get("contentType") or "application/octet-stream")
    size_value = payload.get("sizeBytes") if payload.get("sizeBytes") is not None else payload.get("size")
    size = int(size_value) if size_value is not None else None
    preferred_workspace = str(payload.get("preferredWorkspace") or payload.get("preferred_workspace") or "smart_deck")
    if not storage_path:
        raise HTTPException(status_code=400, detail="storagePath is required")
    try:
        result = complete_deck_upload(
            db,
            deck_id=deck_id,
            storage_path=storage_path,
            filename=filename,
            mime_type=mime_type,
            size=size,
            preferred_workspace=preferred_workspace,
            website_url=payload.get("websiteUrl") or payload.get("website_url"),
        )
        record_security_event(
            db,
            action="deck.upload_complete",
            result="success",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={
                "filename": filename,
                "mimeType": mime_type,
                "size": size,
                "storagePath": storage_path,
                "object": result.get("object"),
            },
            commit=True,
        )
        return result
    except LookupError as exc:
        record_security_event(
            db,
            action="deck.upload_complete",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": "not_found", "storagePath": storage_path},
            commit=True,
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        record_security_event(
            db,
            action="deck.upload_complete",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": "missing_object", "storagePath": storage_path},
            commit=True,
        )
        raise HTTPException(status_code=404, detail="Uploaded object was not found in storage") from exc
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.upload_complete",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__, "storagePath": storage_path},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deck_id}/process")
def decks_process(
    deck_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        processing = queue_source_extraction(db, deck_id, requested_by_user_id=current_user.id)
        workflow_job_id = str(processing.get("jobId") or "") if isinstance(processing, dict) else ""
        result = {"processing": processing, "deck": get_deck(db, deck_id)}
        record_security_event(
            db,
            action="deck.processing.queue",
            result="success",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"workflowJobId": workflow_job_id or None},
            commit=True,
        )
        return result
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.processing.queue",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{deck_id}/insights")
def decks_insights(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    artifacts = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == SMART_DECK_ASSISTANT_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .all()
    )
    insights = []
    for artifact in artifacts:
        payload = load_deck_llm_artifact_payload(artifact)
        insight = payload.get("insight") if isinstance(payload, dict) else {}
        insights.append(
            {
                "id": artifact.id,
                "assistantRunId": payload.get("runId") or artifact.artifact_key,
                "deckId": artifact.deck_id,
                "intentType": payload.get("intentType"),
                "scope": payload.get("scope"),
                "outputType": payload.get("outputType"),
                "title": insight.get("title") if isinstance(insight, dict) else None,
                "summary": artifact.summary,
                "content": insight.get("content", {}) if isinstance(insight, dict) else {},
                "confidence": insight.get("confidence") if isinstance(insight, dict) else None,
                "assumptions": insight.get("assumptions", []) if isinstance(insight, dict) else [],
                "missingEvidence": insight.get("missingEvidence", []) if isinstance(insight, dict) else [],
                "suggestedSlideUpdate": insight.get("suggestedSlideUpdate") if isinstance(insight, dict) else None,
                "recommendedAction": insight.get("recommendedAction") if isinstance(insight, dict) else None,
                "createdAt": artifact.created_at.isoformat(),
            }
        )
    return {"insights": insights}


@router.post("/{deck_id}/insights/{insight_id}/apply-to-slide")
def decks_apply_insight_to_slide(
    deck_id: str,
    insight_id: str,
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.id == insight_id,
            DeckLlmArtifact.artifact_type == SMART_DECK_ASSISTANT_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .first()
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Insight not found")

    artifact_payload = load_deck_llm_artifact_payload(artifact)
    insight = artifact_payload.get("insight") if isinstance(artifact_payload, dict) else {}
    target_slide_id = payload.get("slideId") or payload.get("targetSlideId")
    if target_slide_id:
        slide_ids = {slide.id for slide in artifact.deck.slides}
        if target_slide_id not in slide_ids:
            raise HTTPException(status_code=400, detail="slideId does not belong to this deck")

    application_id = generate_id("artifact")
    application_payload = {
        "insightId": insight_id,
        "assistantRunId": artifact_payload.get("runId") or artifact.artifact_key,
        "targetSlideId": target_slide_id,
        "suggestedSlideUpdate": insight.get("suggestedSlideUpdate") if isinstance(insight, dict) else None,
        "appliedByUserId": current_user.id,
        "notes": payload.get("notes"),
    }
    storage = get_upload_storage()
    storage_path = f"artifacts/decks/{deck_id}/deck_insight_slide_application/{application_id}.json"
    stored = storage.write_bytes(
        storage_path,
        json.dumps(application_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    )
    try:
        stored = promote_upload(stored)
    except Exception:
        storage.delete(stored.storage_path)
        raise

    application = DeckLlmArtifact(
        id=application_id,
        deck_id=deck_id,
        extraction_run_id=None,
        artifact_type="deck_insight_slide_application",
        artifact_key=f"{insight_id}:{target_slide_id or 'unassigned'}",
        schema_version="deck-insight-application.v1",
        status="ready",
        summary=(
            insight.get("suggestedSlideUpdate")
            if isinstance(insight, dict) and insight.get("suggestedSlideUpdate")
            else artifact.summary
        ),
        payload_json={
            "artifactStorageVersion": "deck-insight-application.v1",
            "storageProvider": stored.provider,
            "storagePath": stored.storage_path,
            "contentType": "application/json",
        },
    )
    db.add(application)
    db.commit()

    return {
        "applied": True,
        "applicationId": application.id,
        "insightId": insight_id,
        "deckId": deck_id,
        "targetSlideId": target_slide_id,
        "storageProvider": stored.provider,
        "storagePath": stored.storage_path,
        "suggestedSlideUpdate": application_payload.get("suggestedSlideUpdate"),
    }


@router.post("/{deck_id}/upload")
async def decks_upload(
    deck_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"upload:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    file_name = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"
    upload = None
    try:
        require_supported_deck_upload(file_name, content_type)
        upload = await stream_limited_upload(file)
        payload = attach_limited_upload(db, deck_id, file_name, content_type, upload)
    except HTTPException as exc:
        if upload is not None:
            upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"contentType": content_type, "fileExtension": Path(file_name).suffix.lower(), "statusCode": exc.status_code},
            commit=True,
        )
        raise
    except ValueError as exc:
        if upload is not None:
            upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"contentType": content_type, "fileExtension": Path(file_name).suffix.lower(), "reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    if payload is None:
        record_security_event(
            db,
            action="deck.upload",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"contentType": content_type, "fileExtension": Path(file_name).suffix.lower(), "statusCode": 404},
            commit=True,
        )
        raise HTTPException(status_code=404, detail="Deck not found")
    record_security_event(
        db,
        action="deck.upload",
        result="success",
        actor=current_user,
        resource_type="deck",
        resource_id=deck_id,
        request=request,
        details={
            "contentType": content_type,
            "fileExtension": Path(file_name).suffix.lower(),
            "size": payload.get("size"),
        },
        commit=True,
    )
    return {"file": payload}


@router.post("/{deck_id}/analyse")
def decks_analyse(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    result = analyse_deck(db, deck_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deck not found")
    return result


@router.post("/{deck_id}/finalize")
def decks_finalize(
    deck_id: str,
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    batch_id = payload.get("batchId")
    if not batch_id:
        raise HTTPException(status_code=400, detail="batchId is required")

    try:
        compiled = prepare_full_deck(
            db,
            deck_id,
            batch_id,
            title=payload.get("title"),
            latest_slide_version_id=payload.get("slideVersionId"),
            created_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if compiled is None:
        raise HTTPException(status_code=404, detail="Deck or batch not found")

    return {
        "deckId": compiled["deckId"],
        "finalDeckId": compiled["compiledDeckId"],
        "compiledDeckId": compiled["compiledDeckId"],
        "latestBatchId": compiled["batchId"],
        "latestSlideVersionId": compiled.get("latestSlideVersionId"),
        "status": compiled["status"],
        "redirectTo": compiled["redirectTo"],
        "featuredCard": compiled["featuredCard"],
        "manifest": compiled["manifest"],
    }


@router.get("/{deck_id}/compiled-decks/{compiled_deck_id}")
def decks_compiled_show(
    deck_id: str,
    compiled_deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    compiled = get_compiled_deck(db, deck_id, compiled_deck_id)
    if compiled is None:
        raise HTTPException(status_code=404, detail="Compiled deck not found")
    return {"compiledDeck": compiled}


@router.get("/{deck_id}/iterations/{iteration_id}/final-deck")
def decks_iteration_final_deck(
    deck_id: str,
    iteration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    return {"compiledDeck": get_final_deck_for_iteration(db, deck_id, iteration_id)}


@router.get("/{deck_id}/iterations")
def decks_iterations(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    iterations = get_deck_iterations(db, deck_id)
    if iterations is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    return iterations


@router.get("/{deck_id}/status")
def decks_status(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    status = get_status(db, deck_id)
    if not status:
        raise HTTPException(status_code=404, detail="Deck not found")
    return status


@router.get("/{deck_id}/slides")
def decks_slides(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    get_user_deck_or_404(db, current_user, deck_id)
    return {"slides": get_slides(db, deck_id)}


@router.get("/{deck_id}/slides/{slide_id}/blocks")
def decks_slide_blocks(
    deck_id: str,
    slide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    get_user_deck_or_404(db, current_user, deck_id)
    return {"blocks": get_blocks(db, deck_id, slide_id)}


@router.patch("/{deck_id}/blocks/{block_id}")
def decks_patch_block(
    deck_id: str,
    block_id: str,
    payload: SlideBlockPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    block = patch_block(db, deck_id, block_id, payload.text)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"block": block}


@router.get("/{deck_id}/findings", response_model=AnalysisFindingsRouteResponse)
def decks_findings(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisFindingsRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    return AnalysisFindingsRouteResponse(findings=get_findings(db, deck_id))


@router.get("/{deck_id}/suggestions", response_model=AdaptationSuggestionsRouteResponse)
def decks_suggestions(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdaptationSuggestionsRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    return AdaptationSuggestionsRouteResponse(suggestions=get_suggestions(db, deck_id))


@router.patch("/{deck_id}/suggestions/{suggestion_id}")
def decks_patch_suggestion(
    deck_id: str,
    suggestion_id: str,
    payload: SuggestionPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    suggestion = patch_suggestion(db, deck_id, suggestion_id, payload.status, payload.edited_text)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {
        "suggestion": {
            "id": suggestion.get("id"),
            "runId": suggestion.get("runId") or suggestion.get("run_id"),
            "deckId": suggestion.get("deckId") or suggestion.get("deck_id"),
            "slideId": suggestion.get("slideId") or suggestion.get("slide_id"),
            "blockId": suggestion.get("blockId") or suggestion.get("block_id"),
            "originalText": suggestion.get("originalText") or suggestion.get("original_text"),
            "suggestedText": suggestion.get("suggestedText") or suggestion.get("suggested_text"),
            "reason": suggestion.get("reason"),
            "riskLevel": suggestion.get("riskLevel") or suggestion.get("risk_level"),
            "status": suggestion.get("status"),
            "slideVersionId": suggestion.get("slideVersionId") or suggestion.get("slide_version_id"),
        }
    }


@router.post("/{deck_id}/smart-edit", response_model=SmartEditResponse)
def decks_smart_edit(
    deck_id: str,
    payload: SmartEditCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditResponse:
    # Compatibility route only. The canonical Smart Edit workflow is the
    # slide-scoped classify + patch + run-lookup route family below.
    # DISABLED: this compatibility generation route previously owned a second
    # Smart Edit execution lifecycle. Mounted callers have been moved to the
    # canonical slide-scoped patch workflow, so keep this route only as an
    # explicit stop under the code-preservation rule.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_smart_edit_route_disabled",
            "message": "Legacy Smart Edit generation is disabled. Use the slide-scoped Smart Edit workflow routes.",
            "recoverable": True,
            "nextAction": "open_smart_edit",
        },
    )


@router.get("/{deck_id}/smart-edit/{smart_edit_run_id}", response_model=SmartEditSuggestionRouteResponse)
def decks_smart_edit_run(
    deck_id: str,
    smart_edit_run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditSuggestionRouteResponse:
    # Compatibility route only. Canonical Smart Edit retrieval is
    # GET /decks/{deck_id}/slides/{slide_id}/smart-edit/runs/{run_id}.
    get_user_deck_or_404(db, current_user, deck_id)
    deck = get_deck(db, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    suggestion = next((item for item in deck["smart_edit_suggestions"] if item["run_id"] == smart_edit_run_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Smart edit run not found")
    return SmartEditSuggestionRouteResponse(suggestion=suggestion)


@router.patch("/{deck_id}/smart-edit/suggestions/{suggestion_id}")
def decks_patch_smart_edit_suggestion(
    deck_id: str,
    suggestion_id: str,
    payload: SuggestionPatch,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # Compatibility route only. The canonical patch workflow persists reviewable
    # run artifacts and should be preferred for new integrations.
    # This route remains as a review-decision adapter until the mounted Smart
    # Edit UI converges fully on one ChangeRequest-based review artifact.
    get_user_deck_or_404(db, current_user, deck_id)
    suggestion = patch_suggestion_with_audit(
        db,
        deck_id,
        suggestion_id,
        payload.status,
        payload.edited_text,
        audit_metadata=_audit_metadata(request),
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"suggestion": suggestion}


@router.post("/{deck_id}/slides/{slide_id}/smart-edit/classify", response_model=SmartEditIntentClassificationResponse)
def classify_slide_smart_edit(
    deck_id: str,
    slide_id: str,
    payload: SmartEditClassifyRequest,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditIntentClassificationResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    instruction = payload.instruction.strip()
    result = classify_smart_edit_intent(
        db,
        deck_id=deck_id,
        slide_id=slide_id,
        block_id=payload.blockId,
        instruction=instruction,
        audience_type=payload.audienceType,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Deck, slide, or block not found")
    return SmartEditIntentClassificationResponse(**{k: v for k, v in result.items() if k != "system"})


@router.post("/{deck_id}/slides/{slide_id}/smart-edit/patch", response_model=SmartEditWorkflowRunResponse)
def create_slide_smart_edit_patch(
    deck_id: str,
    slide_id: str,
    payload: SmartEditPatchRequest,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditWorkflowRunResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    instruction = payload.instruction.strip()
    decision = evaluate_deck_guardrail(
        db=db,
        request=request,
        actor=current_user,
        task_type="smart_edit_patch",
        source="smart_edit",
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_instruction=instruction,
        user_id=current_user.id,
        prompt_preview=instruction,
        commit_events=True,
    )
    if not decision.get("allowed", True):
        raise HTTPException(status_code=403, detail="Request blocked by safety controls. Please revise your instruction and try again.")
    enforce_smart_edit_quota(f"user:{current_user.id}:deck:{deck_id}")
    enforce_rate_limit(f"smart-edit-patch:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    result = create_reviewable_smart_edit_patch(
        db,
        deck_id=deck_id,
        slide_id=slide_id,
        block_id=payload.blockId,
        instruction=instruction,
        audience_type=payload.audienceType,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Deck, slide, or block not found")
    return SmartEditWorkflowRunResponse(**result)


@router.get("/{deck_id}/slides/{slide_id}/smart-edit/runs/{run_id}", response_model=SmartEditWorkflowRunResponse)
def get_slide_smart_edit_patch(
    deck_id: str,
    slide_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditWorkflowRunResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = get_reviewable_smart_edit_run(db, deck_id=deck_id, slide_id=slide_id, run_id=run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Smart edit run not found")
    return SmartEditWorkflowRunResponse(**result)


@router.post("/{deck_id}/slides/{slide_id}/smart-edit/summary", response_model=SmartEditSlideSummaryResponse)
def create_slide_smart_edit_summary(
    deck_id: str,
    slide_id: str,
    payload: SmartEditSlideSummaryRequest,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartEditSlideSummaryResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"smart-edit-summary:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        result = generate_persisted_slide_summary(
            db,
            deck_id=deck_id,
            slide_id=slide_id,
            force=payload.force,
        )
    except SmartDeckProviderUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "provider_not_configured",
                "message": "Connect an AI provider before generating a slide summary.",
                "recoverable": True,
                "nextAction": "configure_provider",
            },
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="deck.smart_edit.summary.generate",
            result="failure",
            actor=current_user,
            resource_type="deck_slide",
            resource_id=slide_id,
            request=request,
            details={"deckId": deck_id, "reason": exc.__class__.__name__},
            commit=True,
        )
        if _is_smart_edit_provider_capacity_error(exc):
            _raise_provider_capacity_http_error(exc, feature="Slide summary generation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slide summary generation is temporarily unavailable. Please try again.",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    record_security_event(
        db,
        action="deck.smart_edit.summary.generate",
        result="success",
        actor=current_user,
        resource_type="deck_slide",
        resource_id=slide_id,
        request=request,
        details={"deckId": deck_id, "cached": bool(result.get("cached"))},
        commit=True,
    )
    return SmartEditSlideSummaryResponse(**result)


@router.post("/{deck_id}/due-diligence/extract-claims", response_model=DueDiligenceWorkflowResponse)
def due_diligence_extract_claims(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceWorkflowResponse:
    # Transitional compatibility route. The canonical backend identity for this
    # product surface is Audience Conversion, not report-first diligence.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_due_diligence_route_disabled",
            "message": "Legacy Due Diligence compatibility routes are disabled. Use the canonical queued Due Diligence route or audience-conversion endpoints.",
            "recoverable": True,
            "nextAction": "open_due_diligence",
        },
    )


@router.post("/{deck_id}/due-diligence/analyze-risks", response_model=DueDiligenceWorkflowResponse)
def due_diligence_analyze_risks(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceWorkflowResponse:
    # Transitional compatibility route. Keep only while the frontend label stays
    # on Due Diligence / Smart Audit.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_due_diligence_route_disabled",
            "message": "Legacy Due Diligence compatibility routes are disabled. Use the canonical queued Due Diligence route or audience-conversion endpoints.",
            "recoverable": True,
            "nextAction": "open_due_diligence",
        },
    )


@router.post("/{deck_id}/due-diligence/report", response_model=DueDiligenceWorkflowResponse)
def due_diligence_report(
    deck_id: str,
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceWorkflowResponse:
    # Transitional compatibility route backed by Audience Conversion generate.
    # New backend integrations should prefer /audience-conversion/* directly.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_due_diligence_route_disabled",
            "message": "Legacy Due Diligence report routes are disabled. Use the canonical queued Due Diligence route or audience-conversion endpoints.",
            "recoverable": True,
            "nextAction": "open_due_diligence",
        },
    )


@router.get("/{deck_id}/due-diligence/latest", response_model=DueDiligenceWorkflowResponse)
def due_diligence_latest(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceWorkflowResponse:
    # Transitional compatibility route backed by latest Audience Conversion.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_due_diligence_route_disabled",
            "message": "Legacy Due Diligence latest-report routes are disabled. Use the canonical queued Due Diligence route or audience-conversion endpoints.",
            "recoverable": True,
            "nextAction": "open_due_diligence",
        },
    )


def _audience_diligence_response(payload: dict) -> AudienceDiligenceResponse:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    return AudienceDiligenceResponse(
        artifactId=payload.get("artifactId"),
        deckId=str(payload.get("deckId") or result.get("deckId") or ""),
        status=str(payload.get("status") or "ready"),
        selectedAudience=str(result.get("selectedAudience") or ""),
        audiencePriorities=list(result.get("audiencePriorities") or []),
        audienceObjections=list(result.get("audienceObjections") or []),
        audienceDecisionCriteria=list(result.get("audienceDecisionCriteria") or []),
        currentDeckFit=str(result.get("currentDeckFit") or ""),
        currentDeckFitScore=int(result.get("currentDeckFitScore") or 0),
        currentDeckFitReason=str(result.get("currentDeckFitReason") or ""),
        deckDiagnosis=dict(result.get("deckDiagnosis") or {}),
        financialInsights=dict(result.get("financialInsights") or {}),
        narrativeShift=str(result.get("narrativeShift") or ""),
        deckImplementationPlan=dict(result.get("deckImplementationPlan") or {}),
        slideLevelInstructions=list(result.get("slideLevelInstructions") or []),
        missingEvidence=list(result.get("missingEvidence") or []),
        smartDeckInstruction=dict(result.get("smartDeckInstruction") or {}),
        smartEditInstructions=list(result.get("smartEditInstructions") or []),
        requiresReview=bool(result.get("requiresReview", True)),
        result=result,
        createdAt=payload.get("createdAt"),
    )


def _selected_audience(payload: AudienceDiligenceRequest) -> str:
    return str(payload.selectedAudience or payload.audience or "VC Partner").strip() or "VC Partner"


def generate_audience_conversion(db: Session, deck_id: str, *, target_audience: str | None = None) -> dict:
    """Compatibility seam that now delegates to audience diligence."""
    payload = generate_smart_deck_instructions(
        db,
        deck_id,
        selected_audience=str(target_audience or "VC Partner"),
    )
    return _audience_conversion_response_from_diligence(payload).model_dump()


def get_latest_audience_conversion(db: Session, deck_id: str) -> dict | None:
    """Compatibility seam that exposes the latest audience diligence result."""
    payload = get_latest_audience_diligence(db, deck_id)
    if payload is None:
        return None
    return _audience_conversion_response_from_diligence(payload).model_dump()


def _audience_conversion_response_from_diligence(payload: dict) -> AudienceConversionWorkflowResponse:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    smart_deck_instruction = result.get("smartDeckInstruction") if isinstance(result.get("smartDeckInstruction"), dict) else {}
    return AudienceConversionWorkflowResponse(
        runId=str(payload.get("artifactId") or payload.get("runId") or ""),
        deckId=str(payload.get("deckId") or result.get("deckId") or ""),
        status=str(payload.get("status") or "completed"),
        cached=bool(payload.get("cached", False)),
        conversion={
            "targetAudience": result.get("selectedAudience"),
            "audiencePriorities": result.get("audiencePriorities") or [],
            "likelyObjections": [
                item.get("objection") if isinstance(item, dict) else str(item)
                for item in (result.get("audienceObjections") or [])
            ],
            "decisionCriteria": result.get("audienceDecisionCriteria") or [],
            "deckConversionPlan": result.get("deckImplementationPlan") or {},
            "slideLevelActions": [
                {
                    "slideId": item.get("slideId"),
                    "slideTitle": item.get("slideTitle"),
                    "currentRole": item.get("currentRole"),
                    "audienceNeed": item.get("audienceReason") or item.get("audienceProblem") or "Audience-specific deck change",
                    "objection": None,
                    "action": item.get("implementationInstruction") or item.get("action") or "rewrite",
                    "evidenceNeeded": item.get("evidenceNeeded") or [],
                    "priority": item.get("priority") or "medium",
                }
                for item in (result.get("slideLevelInstructions") or [])
                if isinstance(item, dict)
            ],
            "missingEvidence": [
                item.get("evidence") if isinstance(item, dict) else str(item)
                for item in (result.get("missingEvidence") or [])
            ],
            "recommendedDeckVersion": {
                "title": ((result.get("recommendedDeckVersion") or {}).get("title")) if isinstance(result.get("recommendedDeckVersion"), dict) else None,
                "audience": result.get("selectedAudience"),
                "summary": result.get("narrativeShift"),
                "generationPrompt": smart_deck_instruction.get("generationPrompt") or result.get("narrativeShift"),
            },
            "requiresReview": bool(result.get("requiresReview", True)),
            "system": {"artifactType": "audience_diligence_conversion_plan"},
        },
    )


@router.post("/{deck_id}/due-diligence/audience/analyze", response_model=AudienceDiligenceResponse)
def due_diligence_audience_analyze(
    deck_id: str,
    payload: AudienceDiligenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceDiligenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        result = analyze_audience_diligence(
            db,
            deck_id,
            selected_audience=_selected_audience(payload),
            conversion_goal=payload.conversionGoal,
            user_instruction=payload.userInstruction,
            preferred_model=payload.preferredModel,
        )
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience analysis")
    return _audience_diligence_response(result)


@router.post("/{deck_id}/due-diligence/audience/plan", response_model=AudienceDiligenceResponse)
def due_diligence_audience_plan(
    deck_id: str,
    payload: AudienceDiligenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceDiligenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        result = plan_audience_diligence(
            db,
            deck_id,
            selected_audience=_selected_audience(payload),
            conversion_goal=payload.conversionGoal,
            user_instruction=payload.userInstruction,
            preferred_model=payload.preferredModel,
        )
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience planning")
    return _audience_diligence_response(result)


@router.post("/{deck_id}/due-diligence/audience/generate-smart-deck-instructions", response_model=AudienceDiligenceResponse)
def due_diligence_audience_generate_smart_deck_instructions(
    deck_id: str,
    payload: AudienceDiligenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceDiligenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        result = generate_smart_deck_instructions(
            db,
            deck_id,
            selected_audience=_selected_audience(payload),
            conversion_goal=payload.conversionGoal,
            user_instruction=payload.userInstruction,
            preferred_model=payload.preferredModel,
        )
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience conversion")
    return _audience_diligence_response(result)


@router.get("/{deck_id}/due-diligence/audience/latest", response_model=AudienceDiligenceResponse)
def due_diligence_audience_latest(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceDiligenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = get_latest_audience_diligence(db, deck_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Audience diligence result not found")
    return _audience_diligence_response(result)


@router.post("/{deck_id}/audience-conversion/analyze", response_model=AudienceConversionWorkflowResponse)
def audience_conversion_analyze(
    deck_id: str,
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceConversionWorkflowResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    audience = str(payload.get("targetAudience") or payload.get("audience") or "").strip() or "VC Partner"
    try:
        return _audience_conversion_response_from_diligence(analyze_audience_diligence(db, deck_id, selected_audience=audience))
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience analysis")


@router.post("/{deck_id}/audience-conversion/plan", response_model=AudienceConversionWorkflowResponse)
def audience_conversion_plan(
    deck_id: str,
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceConversionWorkflowResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    audience = str(payload.get("targetAudience") or payload.get("audience") or "").strip() or "VC Partner"
    try:
        return _audience_conversion_response_from_diligence(plan_audience_diligence(db, deck_id, selected_audience=audience))
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience planning")


@router.post("/{deck_id}/audience-conversion/generate", response_model=AudienceConversionWorkflowResponse)
def audience_conversion_generate(
    deck_id: str,
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceConversionWorkflowResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    audience = str(payload.get("targetAudience") or payload.get("audience") or "").strip() or "VC Partner"
    try:
        return _audience_conversion_response_from_diligence(generate_smart_deck_instructions(db, deck_id, selected_audience=audience))
    except Exception as exc:
        db.rollback()
        _raise_provider_capacity_http_error(exc, feature="Audience conversion")


@router.get("/{deck_id}/audience-conversion/latest", response_model=AudienceConversionWorkflowResponse)
def audience_conversion_latest(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceConversionWorkflowResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = get_latest_audience_diligence(db, deck_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Audience conversion not found")
    return _audience_conversion_response_from_diligence(result)


@router.post("/{deck_id}/export")
def decks_export(
    deck_id: str,
    payload: ExportCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"export:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    export_type = payload.normalized_type
    if not export_type:
        raise HTTPException(status_code=422, detail="Export type is required")
    if payload.format == "html" and not payload.designVersionId:
        raise HTTPException(status_code=422, detail="designVersionId is required for final deck export")
    workflow_request = WorkflowExportRequest(
        type=export_type,
        format=payload.format,
        designVersionId=payload.designVersionId,
        idempotencyKey=payload.clientEventId
        or export_fallback_idempotency_key(
            deck_id,
            export_type=export_type,
            export_format=payload.format,
            design_version_id=payload.designVersionId,
        ),
    )
    try:
        accepted = queue_export(db, deck_id, current_user_id=current_user.id, payload=workflow_request)
    except WorkflowConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": exc.message,
                "recoverable": exc.recoverable,
                "nextAction": exc.next_action,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    record_security_event(
        db,
        action="deck.export",
        result="success",
        actor=current_user,
        resource_type="workflow_job",
        resource_id=accepted["jobId"],
        request=request,
        details={"deckId": deck_id, "exportType": export_type, "workflowJobId": accepted["jobId"]},
        commit=True,
    )
    return {"workflow": accepted}


@router.get("/{deck_id}/exports/{export_id}")
def decks_export_show(
    deck_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    deck_export = get_export(db, deck_id, export_id)
    if deck_export is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return {"export": deck_export}


@router.get("/{deck_id}/exports/{export_id}/download")
def decks_export_download(
    deck_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = export_download_payload(db, deck_id, export_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Export not found")
    content, media_type, filename = payload
    return Response(
        content=content,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def _rate_limit_key(deck_id: str, request: Request) -> str:
    host = request.client.host if request.client is not None else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")[:120]
    return f"{deck_id}:{host}:{user_agent}"


def _audit_metadata(request: Request) -> dict:
    return {
        "clientHost": request.client.host if request.client is not None else None,
        "userAgent": request.headers.get("user-agent"),
        "requestPath": str(request.url.path),
    }
