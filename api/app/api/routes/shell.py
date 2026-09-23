from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.shell import (
    BatchSlideDecisionRouteResponse,
    DeckBlockUpdateRouteResponse,
    CreateDeckSlideRequest,
    CreateDesignBatchRequest,
    DeckLatestConfirmationResponse,
    DeckShellPropertiesRouteResponse,
    DeckSlideCreateRouteResponse,
    GeneratedSlideCodeResponse,
    DesignBatchCreateRouteResponse,
    DesignBatchDetailRouteResponse,
    DesignBatchListRouteResponse,
    PrepareFullDeckRequest,
    PrepareFullDeckResponse,
    ReviewGeneratedSlideCandidateRequest,
    SaveBatchSlideDecisionRequest,
    UpdateDeckShellPropertiesRequest,
)
from app.schemas.deck import SlideBlockPatch
from app.schemas.shell_workspace import (
    DeckWorkspacePreferencesRouteResponse,
    UpdateDeckWorkspacePreferencesRequest,
)
from app.services.rendering.final_deck_service import prepare_full_deck, save_batch_slide_decision
from app.services.platform.shell.shell_service import (
    create_design_batch,
    create_shell_slide,
    get_deck_version,
    get_deck_shell_properties,
    get_design_batch,
    get_generated_slide_candidate_code,
    list_design_batches,
    list_deck_versions,
    review_generated_slide_candidate,
    update_shell_block,
    update_deck_shell_properties,
)
from app.services.platform.shell.shell_workspace_service import (
    get_deck_workspace_preferences,
    update_deck_workspace_preferences,
)
from app.services.deck_processing.save_confirmation import get_latest_save_confirmation_for_deck, map_save_confirmation

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["smart-deck-shell"])


def _map_decision(decision) -> dict:
    return {
        "id": decision.id,
        "deckId": decision.deck_id,
        "iterationId": decision.batch_id,
        "batchId": decision.batch_id,
        "slideId": decision.slide_id,
        "generatedSlideVersionId": decision.generated_slide_candidate_id,
        "choice": decision.choice,
        "decidedAt": decision.decided_at.isoformat(),
    }


@router.get("/{deck_id}/properties", response_model=DeckShellPropertiesRouteResponse)
def deck_properties(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckShellPropertiesRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    properties = get_deck_shell_properties(db, deck_id)
    if properties is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckShellPropertiesRouteResponse(deckId=deck_id, properties=properties)


@router.get("/{deck_id}/latest-confirmation", response_model=DeckLatestConfirmationResponse)
def deck_latest_confirmation(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckLatestConfirmationResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    if get_deck_shell_properties(db, deck_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    confirmation = get_latest_save_confirmation_for_deck(db, deck_id)
    return DeckLatestConfirmationResponse(
        deckId=deck_id,
        confirmation=map_save_confirmation(confirmation) if confirmation is not None else None,
    )


@router.patch("/{deck_id}/properties", response_model=DeckShellPropertiesRouteResponse)
def deck_properties_patch(
    deck_id: str,
    payload: UpdateDeckShellPropertiesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckShellPropertiesRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = update_deck_shell_properties(db, deck_id, payload.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckShellPropertiesRouteResponse(
        deckId=deck_id,
        properties=result["properties"],
        confirmation=result.get("confirmation"),
    )


@router.get("/{deck_id}/workspace/preferences", response_model=DeckWorkspacePreferencesRouteResponse)
def deck_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckWorkspacePreferencesRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    workspace = get_deck_workspace_preferences(db, deck_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckWorkspacePreferencesRouteResponse(deckId=deck_id, workspace=workspace)


@router.patch("/{deck_id}/workspace/preferences", response_model=DeckWorkspacePreferencesRouteResponse)
def deck_workspace_patch(
    deck_id: str,
    payload: UpdateDeckWorkspacePreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckWorkspacePreferencesRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        workspace = update_deck_workspace_preferences(db, deck_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckWorkspacePreferencesRouteResponse(deckId=deck_id, workspace=workspace)


@router.get("/{deck_id}/versions", response_model=DesignBatchListRouteResponse)
def deck_versions(
    deck_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchListRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    iterations = list_deck_versions(db, deck_id, limit)
    return DesignBatchListRouteResponse(deckId=deck_id, versions=iterations, iterations=iterations, batches=iterations)


@router.post("/{deck_id}/versions", response_model=DesignBatchCreateRouteResponse)
def deck_versions_create(
    deck_id: str,
    payload: CreateDesignBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchCreateRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    if payload.scopeType == "selected_slides" and not payload.selectedSlideIds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected-slide runs require slide ids")

    batch = create_design_batch(db, deck_id, payload.model_dump())
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck or selected slides not found")

    return DesignBatchCreateRouteResponse(deckId=deck_id, version=batch, iteration=batch, batch=batch)


@router.get("/{deck_id}/versions/{batch_id}", response_model=DesignBatchDetailRouteResponse)
def deck_version_detail(
    deck_id: str,
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchDetailRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    batch = get_deck_version(db, deck_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return DesignBatchDetailRouteResponse(deckId=deck_id, version=batch, iteration=batch, batch=batch)


@router.patch("/{deck_id}/versions/{batch_id}/candidates/{candidate_id}", response_model=DesignBatchDetailRouteResponse)
def deck_version_candidate_review(
    deck_id: str,
    batch_id: str,
    candidate_id: str,
    payload: ReviewGeneratedSlideCandidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchDetailRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        batch = review_generated_slide_candidate(db, deck_id, batch_id, candidate_id, payload.decision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch or candidate not found")

    return DesignBatchDetailRouteResponse(deckId=deck_id, version=batch, iteration=batch, batch=batch)


@router.patch(
    "/{deck_id}/versions/{batch_id}/slide-decisions/{slide_id}",
    response_model=BatchSlideDecisionRouteResponse,
)
def deck_version_slide_decision(
    deck_id: str,
    batch_id: str,
    slide_id: str,
    payload: SaveBatchSlideDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchSlideDecisionRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        decision = save_batch_slide_decision(
            db,
            deck_id,
            batch_id,
            slide_id,
            choice=payload.choice,
            generated_slide_candidate_id=payload.generatedSlideVersionId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch or slide not found")

    batch = get_design_batch(db, deck_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    return BatchSlideDecisionRouteResponse(
        deckId=deck_id,
        iterationId=batch_id,
        batchId=batch_id,
        decision=_map_decision(decision),
        iteration=batch,
        batch=batch,
    )


@router.post(
    "/{deck_id}/versions/{batch_id}/prepare-full-deck",
    response_model=PrepareFullDeckResponse,
)
def deck_version_prepare_full_deck(
    deck_id: str,
    batch_id: str,
    payload: PrepareFullDeckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PrepareFullDeckResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        compiled = prepare_full_deck(
            db,
            deck_id,
            batch_id,
            title=payload.title,
            latest_slide_version_id=payload.latestSlideVersionId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if compiled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck or batch not found")

    return PrepareFullDeckResponse(**compiled)


@router.get(
    "/{deck_id}/versions/{batch_id}/candidates/{candidate_id}/code",
    response_model=GeneratedSlideCodeResponse,
)
def deck_version_candidate_code(
    deck_id: str,
    batch_id: str,
    candidate_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideCodeResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    code = get_generated_slide_candidate_code(db, deck_id, batch_id, candidate_id)
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate code not found")
    return GeneratedSlideCodeResponse(**code)


@router.post("/{deck_id}/slides", response_model=DeckSlideCreateRouteResponse)
def deck_slide_create(
    deck_id: str,
    payload: CreateDeckSlideRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckSlideCreateRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    slide = create_shell_slide(db, deck_id, payload.model_dump(exclude_none=True))
    if slide is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckSlideCreateRouteResponse(deckId=deck_id, slide=slide)


@router.patch("/{deck_id}/blocks/{block_id}", response_model=DeckBlockUpdateRouteResponse)
def deck_block_patch(
    deck_id: str,
    block_id: str,
    payload: SlideBlockPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckBlockUpdateRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = update_shell_block(db, deck_id, block_id, payload.text)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    return DeckBlockUpdateRouteResponse(
        deckId=deck_id,
        block=result["block"],
        confirmation=result.get("confirmation"),
    )
