"""
Main product routes for deck upload and processing.

CRITICAL PATH: User uploads deck → Storage → Database → Worker queue

This file handles:
1. Deck upload endpoint (/decks/upload)
2. Deck upload session management
3. Deck upload completion
4. Workspace summary
5. First deck upload flow

USER JOURNEY:
1. User clicks "Upload Deck" in frontend
2. Frontend sends POST /decks/upload with file + metadata
3. Server validates file type (PDF/PPTX) and size (max 50MB)
4. Server checks storage readiness (S3 config, bucket access)
5. Server streams file to storage backend (local/S3/Supabase)
6. Server creates deck record in database
7. Server queues source extraction job
8. Server returns deck_id and status to frontend
9. Frontend redirects to /processing/{deck_id}
10. Worker picks up job and processes deck

UPLOAD FLOW:
1. File validation → require_supported_deck_upload()
2. Size limit check → stream_limited_upload()
3. Storage readiness check → get_upload_persistence_readiness()
4. File storage → get_upload_storage().write()
5. Database record → create_first_deck_upload()
6. Job queue → queue_source_extraction()

SECURITY:
- Rate limiting: 20 uploads per hour per user
- File type validation: Only PDF, PPT, PPTX
- File size limit: 50MB max
- Storage readiness check: Fail fast if S3 not configured
- Security scan: Malware scan on uploaded files

ERROR HANDLING:
- 503 if storage not configured (clear diagnostics)
- 400 if file type not supported
- 413 if file too large
- 401 if user not authenticated
"""
import logging
import traceback
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.core.config import settings
from app.db.models import Deck, User
from app.schemas.workspace_summary import FirstDeckUploadResponse, WelcomeStateResponse, WorkspaceSummaryResponse
from app.services.deck_processing.workflow_orchestration import queue_source_extraction
from app.services.deck_processing.processing_visibility import get_deck_processing_visibility
from app.services.deck_processing.state_machine import (
    DeckState,
    canonical_deck_state,
    decorate_deck_payloads_with_state,
    transition_deck_state,
)
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.storage.upload_readiness import get_upload_failure_diagnostic_summary, get_upload_persistence_readiness
from app.services.deck_processing.first_batch_rescue import create_source_true_first_batch_minimal

logger = logging.getLogger(__name__)
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.storage.upload_security import require_supported_deck_upload, stream_limited_upload
from app.services.deck_processing.workspace_summary_service import (
    complete_deck_upload,
    create_deck_upload_session,
    create_first_deck_upload,
    get_welcome_state,
    get_workspace_summary_for_user,
    list_workspace_decks_for_user,
    soft_delete_workspace_deck,
)

router = APIRouter(prefix="/products/deck-aistack-codes", tags=["products"])

PRODUCT_API_PREFIX = "/api/products/deck-aistack-codes"


def _storage_credential_diagnostics() -> dict[str, bool]:
    return {
        "hasRailwayBucketAccessKey": bool(settings.railway_bucket_access_key),
        "hasRailwayBucketSecretKey": bool(settings.railway_bucket_secret_key),
        "hasEffectiveS3AccessKey": bool(settings.effective_s3_access_key),
        "hasEffectiveS3SecretKey": bool(settings.effective_s3_secret_key),
    }


def _manual_smart_deck_fields(deck_id: str) -> dict[str, str]:
    # Contract marker retained for upload clients that inspect the manual-start
    # receipt before the durable worker has claimed the source job.
    # "next_action": "create_smart_deck"
    state = DeckState.UPLOADED.value
    return {
        "workflowId": f"deckwf_{deck_id}",
        "workflowPhase": "source_file_saved",
        "workflowStatus": "completed",
        "workflowJobId": None,
        "workflowJobType": None,
        "workflowJobStatus": None,
        "status": state,
        "state": state,
        "deckStatus": state,
        "ui_state": state,
        "upload_message": "Deck saved",
        "next_step_message": "Click Create Smart Deck to start processing.",
        "next_action": "create_smart_deck",
        "create_smart_deck_url": f"{PRODUCT_API_PREFIX}/decks/{deck_id}/smart-deck/prepare",
        "processing_status_url": f"{PRODUCT_API_PREFIX}/decks/{deck_id}/workflow-state",
        "smart_deck_url": f"/decks/{deck_id}/smart-deck",
    }


def _safe_processing_visibility(db: Session, deck_id: str) -> dict | None:
    try:
        return get_deck_processing_visibility(db, deck_id)
    except Exception:
        logger.exception("processing_visibility_failed", extra={"deck_id": deck_id})
        return None


def _normalize_intake_run_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    return normalized[:128] if normalized else None


def _persist_intake_run_metadata(db: Session, *, deck_id: str, intake_run_id: str | None) -> None:
    normalized_intake_run_id = _normalize_intake_run_id(intake_run_id)
    if not normalized_intake_run_id:
        return

    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return

    metadata = dict(deck.metadata_json or {})
    metadata["intake_run_id"] = normalized_intake_run_id
    metadata["intakeRunId"] = normalized_intake_run_id
    metadata.setdefault("intake_run_source_surface", "deck_intake")
    deck.metadata_json = metadata
    db.commit()


def _hold_uploaded_deck_for_manual_smart_deck_start(
    db: Session,
    *,
    current_user: User,
    deck_id: str,
    intake_run_id: str | None = None,
) -> None:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    current_state = canonical_deck_state(deck.status)
    if current_state in {DeckState.PENDING, DeckState.FAILED}:
        transition_deck_state(
            db,
            deck,
            DeckState.UPLOADED,
            actor_user_id=current_user.id,
            reason="manual_smart_deck_start_hold",
            summary="Source deck saved. Click Create Smart Deck to start processing.",
            source_surface="product_upload",
            source_route="/decks/new",
            metadata={"productRoute": True, "intakeRunId": intake_run_id},
            commit=True,
        )


@router.get("/welcome-state", response_model=WelcomeStateResponse)
def welcome_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WelcomeStateResponse:
    return get_welcome_state(db, current_user)


@router.get("/workspace-summary", response_model=WorkspaceSummaryResponse)
def workspace_summary(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceSummaryResponse:
    return get_workspace_summary_for_user(db, current_user, workspace_id)


@router.get("/decks")
def workspace_decks(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    return {"decks": decorate_deck_payloads_with_state(list_workspace_decks_for_user(db, current_user, workspace_id))}


@router.post("/decks/first-batch")
async def source_true_first_batch(
    request: Request,
    source_type: str = Form(...),
    workspace_id: str | None = Form(default=None),
    intake_run_id: str | None = Form(default=None),
    company_name: str | None = Form(default=None),
    website_url: str | None = Form(default=None),
    audience: str | None = Form(default=None),
    purpose: str | None = Form(default=None),
    founder_name: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    team_notes: str | None = Form(default=None),
    linkedin_urls: str | None = Form(default=None),
    supporting_urls: str | None = Form(default=None),
    preferred_workspace: str | None = Form(default=None),
    brand_guide: UploadFile | None = File(default=None),
    logo_file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    enforce_rate_limit(f"first-batch:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    resolved_intake_run_id = _normalize_intake_run_id(intake_run_id or request.headers.get("x-deck-intake-run-id"))
    try:
        payload = await create_source_true_first_batch_minimal(
            db=db,
            user_id=current_user.id,
            source_type=source_type,
            workspace_id=workspace_id,
            company_name=company_name,
            website_url=website_url,
            audience=audience,
            purpose=purpose,
            founder_name=founder_name,
            notes=notes,
            team_notes=team_notes,
            linkedin_urls=[item.strip() for item in (linkedin_urls or "").splitlines() if item.strip()],
            supporting_urls=[item.strip() for item in (supporting_urls or "").splitlines() if item.strip()],
            brand_guide=brand_guide,
            logo_file=logo_file,
        )
        deck_id = str(payload.get("deck_id") or payload.get("deckId") or "")
        if deck_id and resolved_intake_run_id:
            _persist_intake_run_metadata(db, deck_id=deck_id, intake_run_id=resolved_intake_run_id)
            payload["intake_run_id"] = resolved_intake_run_id
            payload["intakeRunId"] = resolved_intake_run_id
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.first_batch",
            result="failure",
            actor=current_user,
            resource_type="deck",
            request=request,
            details={"sourceType": source_type, "reason": exc.__class__.__name__, "intakeRunId": resolved_intake_run_id},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        ticket_id = None
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": request.url.path,
                    "statusCode": 503,
                    "errorName": exc.__class__.__name__,
                    "errorMessage": str(exc) or "First batch creation failed before a deck id was returned.",
                    "errorStack": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    "severity": "critical",
                    "source": "backend",
                    "context": {
                        "phase": "first_batch_save",
                        "sourceType": source_type,
                        "hasWebsiteUrl": bool(website_url),
                        "hasLogoFile": bool(logo_file),
                        "intakeRunId": resolved_intake_run_id,
                    },
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
            ticket_id = ticket.id
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "First batch creation failed before the deck context was saved.",
                "failureCategory": "first_batch_save",
                "errorName": exc.__class__.__name__,
                "requestId": getattr(request.state, "request_id", None),
                "ticketId": ticket_id,
            },
        ) from exc

    record_security_event(
        db,
        action="deck.first_batch",
        result="success",
        actor=current_user,
        resource_type="deck",
        request=request,
        resource_id=str(payload.get("deck_id") or payload.get("deckId") or ""),
        details={
            "sourceType": source_type,
            "batchId": payload.get("batch_id") or payload.get("batchId"),
            "intakeRunId": resolved_intake_run_id,
        },
        commit=True,
    )
    return payload


@router.post("/decks/upload-session")
def deck_upload_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    enforce_rate_limit(f"upload:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    return create_deck_upload_session()


@router.post("/decks/upload-completion")
def deck_upload_completion(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    enforce_rate_limit(f"upload:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    deck_id = str(payload.get("deck_id") or payload.get("deckId") or "").strip()
    workspace_id = payload.get("workspace_id") or payload.get("workspaceId")
    intake_run_id = _normalize_intake_run_id(str(payload.get("intake_run_id") or payload.get("intakeRunId") or ""))
    if not deck_id:
        raise HTTPException(status_code=400, detail="deck_id is required")
    get_user_deck_or_404(db, current_user, deck_id)

    try:
        completion = complete_deck_upload(db, deck_id, str(workspace_id) if workspace_id else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if intake_run_id:
        _persist_intake_run_metadata(db, deck_id=deck_id, intake_run_id=intake_run_id)
    if isinstance(completion, dict) and completion.get("processing"):
        completion["intake_run_id"] = intake_run_id
        completion["intakeRunId"] = intake_run_id
        return completion
    return {
        **completion,
        **_manual_smart_deck_fields(deck_id),
        "intake_run_id": intake_run_id,
        "intakeRunId": intake_run_id,
    }


# DISABLED ROUTE REGISTRATION: `product_processing.py` owns canonical processing visibility.
# @router.get("/decks/{deck_id}/processing")
def deck_processing_visibility(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    visibility = get_deck_processing_visibility(db, deck_id)
    if visibility is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    return visibility


@router.post("/decks/{deck_id}/smart-deck/start")
def start_smart_deck_processing(
    deck_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"smart-deck-start:user:{current_user.id}", db=db, limit=10, window_seconds=3600)

    try:
        processing = queue_source_extraction(db, deck_id, requested_by_user_id=current_user.id)
        run_id = processing.get("jobId") if isinstance(processing, dict) else None
        run_status = str(processing.get("status") or "") if isinstance(processing, dict) else ""
        run_state = str(processing.get("phase") or "") if isinstance(processing, dict) else ""
        background_started = False
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.smart_deck_start",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        ticket_id = None
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": request.url.path,
                    "statusCode": 503,
                    "errorName": exc.__class__.__name__,
                    "errorMessage": str(exc) or "Smart Deck processing could not be started.",
                    "errorStack": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    "severity": "high",
                    "source": "backend",
                    "deckId": deck_id,
                    "context": {"phase": "manual_smart_deck_start"},
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
            ticket_id = ticket.id
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Smart Deck processing could not be started. Check storage, database, and backend logs.",
                "failureCategory": "manual_smart_deck_start",
                "requestId": getattr(request.state, "request_id", None),
                "ticketId": ticket_id,
            },
        ) from exc

    workflow_phase = str(processing.get("phase") or "") if isinstance(processing, dict) else ""
    workflow_status = str(processing.get("status") or "") if isinstance(processing, dict) else ""
    next_action = str(processing.get("nextAction") or "") if isinstance(processing, dict) else ""
    if not next_action:
        next_action = "open_smart_deck" if workflow_phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready"} else "view_processing"
    record_security_event(
        db,
        action="deck.smart_deck_start",
        result="success",
        actor=current_user,
        resource_type="workflow_job",
        resource_id=str(processing.get("jobId") or deck_id) if isinstance(processing, dict) else deck_id,
        request=request,
        details={"deckId": deck_id, "runStatus": run_status, "deckState": run_state, "backgroundStarted": background_started},
        commit=True,
    )
    return {
        "ok": True,
        "deck_id": deck_id,
        "workflowId": processing.get("workflowId") if isinstance(processing, dict) else None,
        "workflowPhase": workflow_phase or None,
        "workflowStatus": workflow_status or "queued",
        "workflowJobId": processing.get("jobId") if isinstance(processing, dict) else None,
        "workflowJobType": processing.get("jobType") if isinstance(processing, dict) else None,
        "workflowJobStatus": workflow_status or None,
        "state": workflow_status or "queued",
        "status": workflow_status or "queued",
        "deckStatus": workflow_status or "queued",
        "processing": processing,
        "background_started": background_started,
        "next_action": next_action,
        "processing_status_url": f"{PRODUCT_API_PREFIX}/decks/{deck_id}/workflow-state",
        "smart_deck_url": f"/decks/{deck_id}/smart-deck",
    }


# DISABLED ROUTE REGISTRATION: `deck_retry_rescue.py` owns the canonical retry command.
# @router.post("/decks/{deck_id}/retry")
def retry_deck(
    deck_id: str,
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _ = workspace_id
    try:
        processing = queue_source_extraction(db, deck.id, requested_by_user_id=current_user.id)
        visibility = _safe_processing_visibility(db, deck.id)
        return {
            "ok": True,
            "deck_id": deck.id,
            "deckId": deck.id,
            "processing": processing,
            "visibility": visibility,
            "nextAction": (visibility or {}).get("nextAction") or (processing or {}).get("nextAction") or "wait",
        }
    except ValueError as exc:
        db.rollback()
        visibility = _safe_processing_visibility(db, deck.id)
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc) or "Deck processing could not be queued.",
                "deckId": deck.id,
                "visibility": visibility,
                "retryable": "source file" not in str(exc).lower(),
            },
        ) from exc


@router.post("/decks/{deck_id}/soft-delete")
def soft_delete_deck(
    deck_id: str,
    workspace_id: str | None = None,
    reason: str | None = None,
    source: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        return soft_delete_workspace_deck(db, deck_id, workspace_id, reason=reason, source_surface=source)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# DISABLED ROUTE REGISTRATION: `upload_rescue.py` owns canonical deck upload.
# @router.post("/decks/upload", response_model=FirstDeckUploadResponse)
async def first_deck_upload(
    request: Request,
    deck: UploadFile = File(...),
    workspace_id: str | None = Form(default=None),
    intake_run_id: str | None = Form(default=None),
    company_name: str | None = Form(default=None),
    website_url: str | None = Form(default=None),
    audience: str | None = Form(default=None),
    purpose: str | None = Form(default=None),
    founder_name: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    team_notes: str | None = Form(default=None),
    linkedin_urls: str | None = Form(default=None),
    supporting_urls: str | None = Form(default=None),
    brand_guide: UploadFile | None = File(default=None),
    logo_file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FirstDeckUploadResponse:
    enforce_rate_limit(f"upload:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    
    readiness = get_upload_persistence_readiness()
    if not readiness["ok"]:
        missing = readiness.get("missingRequiredChecks", [])
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"Deck upload cannot proceed. Missing required configuration: {', '.join(missing)}",
                "failureCategory": "deck_upload_save",
                "requestId": getattr(request.state, "request_id", None),
                "uploadReadiness": readiness,
                "missingRequiredChecks": missing,
                "warningChecks": readiness.get("warningChecks", []),
                "acceptedVariableGroups": readiness.get("acceptedVariableGroups", {}),
            },
        )
    
    file_name = deck.filename or "uploaded-deck.pdf"
    content_type = deck.content_type or "application/octet-stream"
    resolved_intake_run_id = _normalize_intake_run_id(intake_run_id or request.headers.get("x-deck-intake-run-id"))
    deck_upload = None
    try:
        require_supported_deck_upload(file_name, content_type)
        deck_upload = await stream_limited_upload(deck)
        payload = await create_first_deck_upload(
            db=db,
            user_id=current_user.id,
            file_name=file_name,
            content_type=content_type,
            deck_upload=deck_upload,
            workspace_id=workspace_id,
            company_name=company_name,
            website_url=website_url,
            audience=audience,
            purpose=purpose,
            founder_name=founder_name,
            notes=notes,
            team_notes=team_notes,
            linkedin_urls=[item.strip() for item in (linkedin_urls or "").splitlines() if item.strip()],
            supporting_urls=[item.strip() for item in (supporting_urls or "").splitlines() if item.strip()],
            brand_guide=brand_guide,
            logo_file=logo_file,
        )
        deck_id = str(payload.get("deck_id") or "")
        if deck_id:
            if not payload.get("processing"):
                if resolved_intake_run_id:
                    _persist_intake_run_metadata(db, deck_id=deck_id, intake_run_id=resolved_intake_run_id)
                _hold_uploaded_deck_for_manual_smart_deck_start(db, current_user=current_user, deck_id=deck_id)
                payload.update(_manual_smart_deck_fields(deck_id))
                payload["deck_extraction_status"] = DeckState.UPLOADED.value
            elif resolved_intake_run_id:
                _persist_intake_run_metadata(db, deck_id=deck_id, intake_run_id=resolved_intake_run_id)
            payload["workspace"] = get_workspace_summary_for_user(db, current_user, workspace_id)
            payload["intake_run_id"] = resolved_intake_run_id
            payload["intakeRunId"] = resolved_intake_run_id
    except HTTPException as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload",
            result="failure",
            actor=current_user,
            resource_type="deck",
            request=request,
            details={
                "contentType": content_type,
                "fileExtension": Path(file_name).suffix.lower(),
                "statusCode": exc.status_code,
                "intakeRunId": resolved_intake_run_id,
            },
            commit=True,
        )
        raise
    except ValueError as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload",
            result="failure",
            actor=current_user,
            resource_type="deck",
            request=request,
            details={
                "contentType": content_type,
                "fileExtension": Path(file_name).suffix.lower(),
                "reason": exc.__class__.__name__,
                "intakeRunId": resolved_intake_run_id,
            },
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        ticket_id = None
        error_name = exc.__class__.__name__
        error_message = str(exc) or "Deck upload failed before the source file was saved."
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": request.url.path,
                    "statusCode": 503,
                    "errorName": error_name,
                    "errorMessage": error_message,
                    "errorStack": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    "severity": "critical",
                    "source": "backend",
                    "context": {
                        "phase": "deck_upload_save",
                        "contentType": content_type,
                        "fileExtension": Path(file_name).suffix.lower(),
                        "storageBackend": settings.upload_storage_backend,
                        "hasStorageBucket": bool(settings.upload_storage_s3_bucket),
                        "hasStorageRegion": bool(settings.upload_storage_s3_region),
                        "hasStorageEndpoint": bool(settings.upload_storage_s3_endpoint_url),
                        **_storage_credential_diagnostics(),
                        "intakeRunId": resolved_intake_run_id,
                    },
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
            ticket_id = ticket.id
        except Exception:
            db.rollback()
        readiness = get_upload_failure_diagnostic_summary()
        
        # Build a more specific error message based on the actual exception
        if "database" in error_message.lower() or "connection" in error_message.lower():
            specific_message = f"Database connection failed: {error_message}. Check DATABASE_URL is set correctly in Railway."
        elif "bucket" in error_message.lower() or "s3" in error_message.lower() or "storage" in error_message.lower():
            specific_message = f"Storage upload failed: {error_message}. Check S3 bucket configuration in Railway."
        elif "permission" in error_message.lower() or "access" in error_message.lower():
            specific_message = f"Permission denied: {error_message}. Check S3 access keys and bucket permissions."
        else:
            specific_message = f"Deck upload failed: {error_message}. Check Railway configuration and logs."
        
        raise HTTPException(
            status_code=503,
            detail={
                "message": specific_message,
                "failureCategory": "deck_upload_save",
                "requestId": getattr(request.state, "request_id", None),
                "ticketId": ticket_id,
                "errorName": error_name,
                "errorMessage": error_message,
                "uploadReadiness": readiness,
                "missingRequiredChecks": readiness.get("missingRequiredChecks", []),
                "warningChecks": readiness.get("warningChecks", []),
                "acceptedVariableGroups": readiness.get("acceptedVariableGroups", {}),
            },
        ) from exc
    record_security_event(
        db,
        action="deck.upload",
        result="success",
        actor=current_user,
        resource_type="deck",
        resource_id=str(payload.get("deck_id") or ""),
        request=request,
        details={
            "contentType": content_type,
            "fileExtension": Path(file_name).suffix.lower(),
            "size": payload.get("source_file_size_bytes"),
            "workspaceId": payload.get("workspace", {}).get("id") if isinstance(payload.get("workspace"), dict) else None,
            "nextAction": payload.get("next_action"),
            "deckState": payload.get("state") or payload.get("status"),
            "intakeRunId": resolved_intake_run_id,
        },
        commit=True,
    )

    return FirstDeckUploadResponse(**payload)
