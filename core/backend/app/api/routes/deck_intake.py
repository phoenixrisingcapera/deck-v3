from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.core.security import generate_id
from app.db.models import User
from app.schemas.deck_intake import DeckIntakeStatusResponse
from app.schemas.deck_structure import DeckStructureResponse
from app.schemas.deck_workflow import WorkflowCommandAcceptedResponse
from app.schemas.due_diligence import (
    DueDiligenceChatRequest,
    DueDiligenceChatResponse,
    DueDiligenceChatPendingResponse,
    DueDiligenceCommandAcceptedResponse,
    DueDiligenceRunRequest,
    DueDiligenceWorkspacePayload,
)
from app.services.visualizer.deck_artifact_listing import list_deck_llm_artifacts
from app.services.deck_processing.deck_intake_service import get_deck_intake_status
from app.services.deck_processing.source_structure_read_model import get_deck_structure
from app.services.llm.due_diligence_service import (
    chat_with_diligence_workspace,
    complete_diligence_exchange,
    DiligenceExchangePending,
    get_diligence_conversation,
    persist_diligence_exchange,
    reserve_diligence_exchange,
)
from app.services.visualizer.generated_deck_read_model import (
    apply_field_change,
    build_due_diligence_workspace_payload,
    get_diligence_workspace,
    get_editable_field,
    list_editable_fields,
    preview_field_change,
)
from app.services.visualizer.persistent_field_service import (
    apply_persistent_field_change,
    get_persistent_field,
    list_persistent_fields,
    preview_persistent_field_change,
    save_persistent_field_change,
)
# DISABLED: The canonical HTTP command no longer imports or calls analyse_deck.
# Reason: Due Diligence provider work must run only in the durable worker.
# from app.services.deck_processing.deck_mutation_service import analyse_deck
from app.services.deck_processing.workflow_orchestration import (
    WorkflowConflictError,
    queue_due_diligence,
    queue_source_extraction,
)
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["deck-intake"])


def extract_and_persist_deck_structure(db: Session, deck_id: str, *, requested_by_user_id: str) -> dict:
    """Compatibility seam for structure extraction requests.

    The durable implementation is workflow-backed; this named seam exists so
    route-level failure masking tests can patch it directly.
    """
    return queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)


@router.get("/{deck_id}/status", response_model=DeckIntakeStatusResponse)
def deck_intake_status(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckIntakeStatusResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_deck_intake_status(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckIntakeStatusResponse(**payload)


@router.get("/{deck_id}/structure", response_model=DeckStructureResponse)
def deck_structure(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckStructureResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        return DeckStructureResponse(**get_deck_structure(db, deck_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{deck_id}/artifacts")
def deck_llm_artifacts(
    deck_id: str,
    request: Request,
    artifact_type: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        return list_deck_llm_artifacts(
            db,
            deck_id,
            artifact_type=artifact_type,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Deck LLM artifacts are temporarily unavailable.",
                "failureCategory": "deck_llm_artifacts_load",
                "requestId": getattr(request.state, "request_id", None),
            },
        ) from exc


@router.get("/{deck_id}/diligence-workspace")
def deck_diligence_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_diligence_workspace(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return payload


@router.get("/{deck_id}/due-diligence", response_model=DueDiligenceWorkspacePayload, response_model_by_alias=False)
def deck_due_diligence_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    audience: str | None = None,
) -> DueDiligenceWorkspacePayload:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = build_due_diligence_workspace_payload(db, deck_id, audience=audience)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    selected_audience = str(payload.get("selected_audience") or "seed_vc")
    payload["conversation"] = get_diligence_conversation(db, deck_id, user_id=current_user.id, audience=selected_audience)
    return DueDiligenceWorkspacePayload(**payload)


@router.get("/{deck_id}/audience", response_model=DueDiligenceWorkspacePayload, response_model_by_alias=False)
def deck_audience_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    audience: str | None = None,
) -> DueDiligenceWorkspacePayload:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = build_due_diligence_workspace_payload(db, deck_id, audience=audience)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DueDiligenceWorkspacePayload(**payload)


@router.post(
    "/{deck_id}/due-diligence/run",
    response_model=DueDiligenceCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def deck_due_diligence_run(
    deck_id: str,
    payload: DueDiligenceRunRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"workflow-due-diligence:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    try:
        accepted = queue_due_diligence(
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
                "requestId": getattr(request.state, "request_id", None),
            },
        ) from exc

    # DISABLED: synchronous analysis and report loading kept the provider call
    # inside HTTP and could time out while still mutating persisted findings.
    # analyse_deck(db, deck_id, audience=payload.audience)
    # diligence = build_due_diligence_workspace_payload(db, deck_id, audience=payload.audience)
    # return DueDiligenceWorkspacePayload(**diligence)
    record_security_event(
        db,
        action="workflow.due_diligence.queued",
        result="accepted",
        actor=current_user,
        resource_type="deck",
        resource_id=deck_id,
        request=request,
        details={"workflowJobId": accepted["jobId"], "audience": payload.audience},
        commit=True,
    )
    return DueDiligenceCommandAcceptedResponse(**accepted)


@router.post(
    "/{deck_id}/due-diligence/chat",
    response_model=DueDiligenceChatResponse,
    responses={409: {"model": DueDiligenceChatPendingResponse}},
)
def deck_due_diligence_chat(
    deck_id: str,
    payload: DueDiligenceChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueDiligenceChatResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"diligence-chat:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    messages = [{"role": msg.role, "content": msg.content} for msg in payload.messages]
    audience = payload.audience or "seed_vc"
    client_exchange_key = payload.clientExchangeKey or generate_id("ddexchange")
    existing = get_diligence_conversation(db, deck_id, user_id=current_user.id, audience=audience)
    if existing and payload.conversationId and existing.get("conversationId") != payload.conversationId:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diligence conversation does not match this deck, user, and audience.")
    try:
        reservation, replayed = reserve_diligence_exchange(
            db, deck_id, user_id=current_user.id, audience=audience, conversation_id=payload.conversationId,
            client_exchange_key=client_exchange_key, user_content=messages[-1]["content"],
        )
        if replayed:
            if isinstance(reservation, DiligenceExchangePending):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=DueDiligenceChatPendingResponse(clientExchangeKey=client_exchange_key).model_dump(),
                )
            return DueDiligenceChatResponse(
                reply=reservation["reply"], conversationId=reservation["conversationId"], messageId=reservation["messageId"],
                clientExchangeKey=client_exchange_key, provider=reservation.get("provider"), model=reservation.get("model"), replayed=True,
            )
        result = chat_with_diligence_workspace(db, deck_id, messages=messages, audience=audience)
        exchange, replayed = persist_diligence_exchange(
            db, deck_id, user_id=current_user.id, audience=audience, conversation_id=payload.conversationId,
            client_exchange_key=client_exchange_key, user_content=messages[-1]["content"], assistant_content=result["reply"],
            provider=result.get("provider"), model=result.get("model"),
        )
        complete_diligence_exchange(
            db, reservation.id, ownership_token=reservation.payload_json["ownershipToken"],
            conversation_id=exchange["conversationId"], message_id=exchange["messageId"],
            reply=exchange.get("reply", result["reply"]), provider=exchange.get("provider", result.get("provider")),
            model=exchange.get("model", result.get("model")),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diligence chat is temporarily unavailable. Please try again.",
        ) from exc
    record_security_event(
        db,
        action="workflow.diligence_chat.message",
        result="success",
        actor=current_user,
        resource_type="deck",
        resource_id=deck_id,
        request=request,
        details={"provider": exchange.get("provider", result.get("provider")), "model": exchange.get("model", result.get("model"))},
        commit=True,
    )
    return DueDiligenceChatResponse(
        reply=exchange.get("reply", result["reply"]),
        provider=exchange.get("provider", result.get("provider")),
        model=exchange.get("model", result.get("model")),
        conversationId=exchange["conversationId"],
        messageId=exchange["messageId"],
        clientExchangeKey=client_exchange_key,
        replayed=replayed,
    )


@router.get("/{deck_id}/editable-fields")
def deck_editable_fields(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = list_editable_fields(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return payload


@router.get("/{deck_id}/fields/{field_key:path}")
def deck_editable_field(
    deck_id: str,
    field_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_editable_field(db, deck_id, field_key)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return payload


@router.get("/{deck_id}/persistent-fields")
def deck_persistent_fields(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = list_persistent_fields(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return payload


@router.get("/{deck_id}/persistent-fields/{field_key:path}")
def deck_persistent_field(
    deck_id: str,
    field_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_persistent_field(db, deck_id, field_key)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return payload


@router.post("/{deck_id}/persistent-fields/{field_key:path}/preview")
def deck_persistent_field_preview(
    deck_id: str,
    field_key: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    value = str(payload.get("value") or payload.get("nextValue") or "")
    preview = preview_persistent_field_change(db, deck_id, field_key, value)
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return preview


@router.post("/{deck_id}/persistent-fields/{field_key:path}/save")
def deck_persistent_field_save(
    deck_id: str,
    field_key: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    value = str(payload.get("value") or payload.get("nextValue") or "")
    if not value.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value is required")
    saved = save_persistent_field_change(db, deck_id, field_key, value)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return saved


@router.post("/{deck_id}/persistent-fields/{field_key:path}/apply")
def deck_persistent_field_apply(
    deck_id: str,
    field_key: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    raw_value = payload.get("value") or payload.get("nextValue")
    value = str(raw_value) if raw_value is not None else None
    applied = apply_persistent_field_change(db, deck_id, field_key, value)
    if applied is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found or no saved draft available")
    return applied


@router.post("/{deck_id}/changes/preview")
def deck_change_preview(
    deck_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    field_key = str(payload.get("fieldKey") or payload.get("field_key") or "").strip()
    value = str(payload.get("value") or payload.get("nextValue") or "")
    if not field_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fieldKey is required")
    preview = preview_field_change(db, deck_id, field_key, value)
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return preview


@router.post("/{deck_id}/changes/apply")
def deck_change_apply(
    deck_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    field_key = str(payload.get("fieldKey") or payload.get("field_key") or "").strip()
    value = str(payload.get("value") or payload.get("nextValue") or "")
    if not field_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fieldKey is required")
    applied = apply_field_change(db, deck_id, field_key, value)
    if applied is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return applied


@router.post(
    "/{deck_id}/extract-structure",
    response_model=WorkflowCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_structure(
    deck_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCommandAcceptedResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    enforce_rate_limit(f"deck-structure-extract:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    try:
        accepted = extract_and_persist_deck_structure(db, deck_id, requested_by_user_id=current_user.id)
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="deck_structure.extract",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deck structure extraction failed",
        ) from exc
    record_security_event(
        db,
        action="deck_structure.extract",
        result="accepted",
        actor=current_user,
        resource_type="deck",
        resource_id=deck_id,
        request=request,
        details={
            "workflowJobId": accepted["jobId"],
            "jobType": accepted["jobType"],
            "phase": accepted["phase"],
        },
        commit=True,
    )
    return WorkflowCommandAcceptedResponse(**accepted)
