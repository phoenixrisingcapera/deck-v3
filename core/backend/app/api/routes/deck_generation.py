from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.generation import (
    DeckWorkspaceRouteResponse,
    GenerateSlidesRequest,
    GenerateSlidesRouteResponse,
    SubmitSlideFeedbackRequest,
    SubmitSlideFeedbackRouteResponse,
)
from app.services.llm.deck_generation_service import (
    generate_slides_for_deck,
    get_deck_workspace,
    submit_slide_feedback,
)
from app.services.platform.billing.ai_usage_quota_service import enforce_ai_generation_quota
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.admin.guardrail_client import evaluate_deck_guardrail

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["deck-generation"])


@router.get("/{deck_id}/workspace", response_model=DeckWorkspaceRouteResponse)
def deck_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckWorkspaceRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    workspace_result = get_deck_workspace(db, deck_id)
    if workspace_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    workspace, latest_confirmation = workspace_result
    return DeckWorkspaceRouteResponse(workspace=workspace, latestConfirmation=latest_confirmation)


@router.post("/{deck_id}/generate-slides", response_model=GenerateSlidesRouteResponse)
def deck_generate_slides(
    deck_id: str,
    payload: GenerateSlidesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateSlidesRouteResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    decision = evaluate_deck_guardrail(
        db=db,
        request=request,
        actor=current_user,
        task_type="deck_generate_slides",
        source="deck_generate_slides",
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_instruction=payload.prompt,
        user_id=current_user.id,
        prompt_preview=payload.prompt,
        commit_events=True,
    )
    if not decision.get("allowed", True):
        record_security_event(
            db,
            action="deck.generate_slides.guardrail_blocked",
            result="blocked",
            actor=current_user,
            resource_type="generation_run",
            resource_id=deck.id,
            request=request,
            details={
                "taskType": "deck_generate_slides",
                "riskLevel": decision.get("riskLevel"),
                "policy": decision.get("policy"),
                "reason": decision.get("reason"),
            },
            commit=True,
        )
        raise HTTPException(status_code=403, detail="Request blocked by safety controls. Please revise your prompt and try again.")
    enforce_rate_limit(f"generation:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        generated = generate_slides_for_deck(db, deck_id, payload)
    except ValueError as exc:
        record_security_event(
            db,
            action="deck.generate_slides",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="deck.generate_slides",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Deck AI Stack generation failed") from exc

    if generated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")

    run_id, workspace = generated
    record_security_event(
        db,
        action="deck.generate_slides",
        result="success",
        actor=current_user,
        resource_type="generation_run",
        resource_id=run_id,
        request=request,
        details={"deckId": deck_id},
        commit=True,
    )
    return GenerateSlidesRouteResponse(runId=run_id, workspace=workspace)


@router.post("/{deck_id}/slides/{slide_id}/feedback", response_model=SubmitSlideFeedbackRouteResponse)
def deck_slide_feedback(
    deck_id: str,
    slide_id: str,
    payload: SubmitSlideFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitSlideFeedbackRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        feedback_result = submit_slide_feedback(db, deck_id, slide_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if feedback_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slide version not found")

    feedback, workspace = feedback_result
    return SubmitSlideFeedbackRouteResponse(feedback=feedback, workspace=workspace)
