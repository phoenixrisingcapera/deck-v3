from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.brand_profile import ExtractDeckBrandRouteResponse
from app.schemas.deck_workflow import (
    DeckWorkflowStateResponse,
    WorkflowApplyRequest,
    WorkflowCommandAcceptedResponse,
    WorkflowCommandRequest,
    WorkflowExportRequest,
    WorkflowGenerationRequest,
    WorkflowFailedSlideRetryRequest,
    WorkflowSelectedSlideGenerationRequest,
    WorkflowJobResponse,
    WorkflowSourceExtractionRequest,
)
from app.schemas.shell import PrepareFullDeckRequest
from app.services.platform.billing.ai_usage_quota_service import enforce_ai_generation_quota
from app.services.brand.brand_enrichment import enrich_brand_profile_after_extract
from app.services.brand.brand_extraction import extract_deck_brand, get_deck_brand_profile
from app.services.brand.deterministic_swatches import with_deterministic_swatch_contract
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state, get_workflow_job
from app.services.deck_processing.workflow_orchestration import (
    WorkflowConflictError,
    queue_compile_final_deck,
    queue_apply_design_version,
    queue_export,
    queue_selected_slide_generation,
    queue_smart_deck_generation,
    queue_failed_slide_generation_retry,
    queue_source_extraction,
)
from app.services.admin.guardrail_client import evaluate_deck_guardrail
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.admin.instant_deck_operation_report import build_instant_deck_operation_report
from app.services.llm.generation_provenance_service import GenerationProvenanceError, validate_generation_provenance
from app.services.rendering.export_service import export_download_payload, get_export, list_exports

router = APIRouter(tags=["deck-workflow"])


@router.get("/products/deck-aistack-codes/decks/{deck_id}/instant-deck/operations/{operation_id}/internal-report")
def instant_deck_internal_operation_report(
    deck_id: str,
    operation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal operation reports are restricted to super admins.")
    try:
        return build_instant_deck_operation_report(db, deck_id=deck_id, operation_id=operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _validate_generation_provenance(db: Session, deck_id: str, payload: WorkflowGenerationRequest) -> None:
    try:
        validate_generation_provenance(db, deck_id, payload.provenance)
    except (GenerationProvenanceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_generation_provenance", "message": str(exc)},
        ) from exc


def _require_generation_guardrail(*, db: Session, request: Request, current_user: User, deck_id: str, workspace_id: str | None, prompt: str) -> None:
    decision = evaluate_deck_guardrail(
        db=db,
        request=request,
        actor=current_user,
        task_type="smart_deck_generation",
        source="workflow_generation_jobs",
        deck_id=deck_id,
        workspace_id=workspace_id,
        user_instruction=prompt,
        user_id=current_user.id,
        prompt_preview=prompt,
        commit_events=True,
    )
    if decision.get("allowed", True):
        return
    record_security_event(
        db,
        action="workflow.generation.guardrail_blocked",
        result="blocked",
        actor=current_user,
        resource_type="deck",
        resource_id=deck_id,
        request=request,
        details={"taskType": "smart_deck_generation", "policy": decision.get("policy"), "riskLevel": decision.get("riskLevel")},
        commit=True,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request blocked by safety controls. Please revise your request and try again.")


@router.get("/products/deck-aistack-codes/decks/{deck_id}/workflow-state", response_model=DeckWorkflowStateResponse)
def deck_workflow_state(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckWorkflowStateResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_deck_workflow_state(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckWorkflowStateResponse(**payload)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflow-command",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def deck_workflow_command(
    deck_id: str,
    payload: WorkflowCommandRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    command = payload.command

    if command in {"start_source_extraction", "start_source_processing", "create_smart_deck", "retry"}:
        enforce_rate_limit(f"workflow-source-extraction:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
        accepted = queue_source_extraction(db, deck_id, requested_by_user_id=current_user.id)
        return WorkflowCommandAcceptedResponse(**accepted)

    if command == "generate_preview":
        if payload.generation is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="generation payload is required for generate_preview.")
        _validate_generation_provenance(db, deck_id, payload.generation)
        _require_generation_guardrail(
            db=db,
            request=request,
            current_user=current_user,
            deck_id=deck.id,
            workspace_id=deck.workspace_id,
            prompt=payload.generation.prompt,
        )
        enforce_rate_limit(f"workflow-smart-deck-generation:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
        enforce_ai_generation_quota(db, current_user)
        try:
            accepted = queue_smart_deck_generation(db, deck_id, current_user_id=current_user.id, payload=payload.generation)
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
        return WorkflowCommandAcceptedResponse(**accepted)

    if command == "run_selected_slide_generation":
        if payload.selectedSlideGeneration is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selectedSlideGeneration payload is required for run_selected_slide_generation.",
            )
        try:
            accepted = queue_selected_slide_generation(
                db,
                deck_id,
                current_user_id=current_user.id,
                payload=payload.selectedSlideGeneration,
            )
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
        return WorkflowCommandAcceptedResponse(**accepted)

    if command == "apply_design_version":
        if payload.apply is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="apply payload is required for apply_design_version.")
        try:
            accepted = queue_apply_design_version(db, deck_id, current_user_id=current_user.id, payload=payload.apply)
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
        return WorkflowCommandAcceptedResponse(**accepted)

    if command == "export":
        if payload.export is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="export payload is required for export.")
        enforce_rate_limit(f"workflow-export:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
        try:
            accepted = queue_export(db, deck_id, current_user_id=current_user.id, payload=payload.export)
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
        return WorkflowCommandAcceptedResponse(**accepted)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported workflow command.")


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/smart-deck/prepare",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def prepare_smart_deck_workflow(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"workflow-source-extraction:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=current_user.id)
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_source_extraction_workflow(
    deck_id: str,
    payload: WorkflowSourceExtractionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"workflow-source-extraction:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=current_user.id)
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/brand-extraction",
    response_model=ExtractDeckBrandRouteResponse,
)
async def start_brand_extraction_workflow(
    deck_id: str,
    companyUrl: str | None = Form(default=None),
    logoFile: UploadFile | None = File(default=None),
    brandGuidelinesFile: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtractDeckBrandRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        profile = await extract_deck_brand(db, deck_id, companyUrl, logoFile, brandGuidelinesFile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")

    try:
        # FIX 2: enrichment failures were silently swallowed, leaving profiles without
        # fonts, card swatches, or remote logos. Now we log the error so it surfaces.
        enrich_brand_profile_after_extract(db, deck_id)
        enriched_profile = get_deck_brand_profile(db, deck_id)
        if enriched_profile is not None:
            profile = enriched_profile
    except Exception as enrichment_error:
        # DISABLED: silent db.rollback() with no logging. Now we log the exception
        # so operators can see what went wrong, then still rollback to keep the session usable.
        db.rollback()
        logger.exception(
            "Brand enrichment failed for deck %s after successful extraction: %s",
            deck_id,
            enrichment_error,
        )

    # FIX 3: apply deterministic swatches so this endpoint returns the same shape
    # as the primary /brand/extract endpoint.
    profile = with_deterministic_swatch_contract(profile)
    return ExtractDeckBrandRouteResponse(brandProfileId=profile.id, brandProfile=profile)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_smart_deck_generation_workflow(
    deck_id: str,
    payload: WorkflowGenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _validate_generation_provenance(db, deck_id, payload)
    _require_generation_guardrail(
        db=db,
        request=request,
        current_user=current_user,
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        prompt=payload.prompt,
    )
    enforce_rate_limit(f"workflow-smart-deck-generation:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    if payload.outputContract != "full_html_deck.v1":
        enforce_ai_generation_quota(db, current_user)
    try:
        accepted = queue_smart_deck_generation(
            db,
            deck_id,
            current_user_id=current_user.id,
            payload=payload,
            defer_instant_provider_release=payload.outputContract == "full_html_deck.v1",
        )
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
    if payload.outputContract == "full_html_deck.v1":
        accepted.pop("operationCreated", False)
    accepted.pop("instantOperationId", None)
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation/retry-failed",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_failed_smart_deck_generation_workflow(
    deck_id: str,
    payload: WorkflowFailedSlideRetryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"workflow-smart-deck-retry:user:{current_user.id}", db=db, limit=5, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        accepted = queue_failed_slide_generation_retry(
            db,
            deck_id,
            current_user_id=current_user.id,
            payload=payload,
        )
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
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/compile-final",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_compile_final_workflow(
    deck_id: str,
    payload: PrepareFullDeckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        accepted = queue_compile_final_deck(db, deck_id, current_user_id=current_user.id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/selected-slide-generation",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_selected_slide_generation_workflow(
    deck_id: str,
    payload: WorkflowSelectedSlideGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected-slide generation diagnostics are only available to super admins.")
    try:
        accepted = queue_selected_slide_generation(db, deck_id, current_user_id=current_user.id, payload=payload)
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/apply-design-version",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_apply_design_version_workflow(
    deck_id: str,
    payload: WorkflowApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        accepted = queue_apply_design_version(db, deck_id, current_user_id=current_user.id, payload=payload)
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
    return WorkflowCommandAcceptedResponse(**accepted)


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/workflows/export",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_export_workflow(
    deck_id: str,
    payload: WorkflowExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"workflow-export:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    try:
        accepted = queue_export(db, deck_id, current_user_id=current_user.id, payload=payload)
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
    return WorkflowCommandAcceptedResponse(**accepted)


@router.get("/products/deck-aistack-codes/decks/{deck_id}/exports")
def deck_exports(
    deck_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    return list_exports(db, deck_id, limit=limit, offset=offset)


@router.get("/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}")
def deck_export_detail(
    deck_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    deck_export = get_export(db, deck_id, export_id)
    if deck_export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return {"export": deck_export}


@router.get("/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}/download")
def deck_export_download(
    deck_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = export_download_payload(db, deck_id, export_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    content, media_type, filename = payload
    return Response(
        content=content,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/workflow-jobs/{job_id}", response_model=WorkflowJobResponse)
def workflow_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowJobResponse:
    payload = get_workflow_job(db, job_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow job not found")
    get_user_deck_or_404(db, current_user, payload["deckId"])
    return WorkflowJobResponse(**payload)
