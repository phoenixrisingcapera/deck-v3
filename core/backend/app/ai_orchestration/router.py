from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai_orchestration.errors import AiOrchestrationError
from app.ai_orchestration.orchestrator import SmartDeckOrchestrator, serialize_ai_run
from app.ai_orchestration.provider_resolver import resolve_orchestration_provider
from app.ai_orchestration.schemas import AiOrchestrationRequest, AiOrchestrationResponse
from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import AiRun, DesignBatch, GeneratedSlideCandidate, User
from app.schemas.shell import (
    BatchSlideDecisionRouteResponse,
    DesignBatchDetailRouteResponse,
    DesignBatchListRouteResponse,
    PrepareFullDeckRequest,
    PrepareFullDeckResponse,
)
from app.services.platform.billing.ai_usage_quota_service import enforce_ai_generation_quota
from app.services.admin.agent_telemetry import record_agent_event
from app.services.rendering.final_deck_service import GENERATED_VERSION, ORIGINAL, get_latest_compiled_deck, prepare_full_deck, save_batch_slide_decision
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.platform.shell.shell_service import get_design_batch, list_design_batches

router = APIRouter(prefix="/products/deck-aistack-codes", tags=["deck-aistack-codes-ai"])


def _map_decision(decision) -> dict:
    return {
        "id": decision.id,
        "deckId": decision.deck_id,
        "batchId": decision.batch_id,
        "slideId": decision.slide_id,
        "generatedSlideVersionId": decision.generated_slide_candidate_id,
        "choice": decision.choice,
        "decidedAt": decision.decided_at.isoformat(),
    }


def _latest_batch_id_for_slide(db: Session, deck_id: str, slide_id: str) -> str | None:
    batch = (
        db.query(DesignBatch)
        .join(GeneratedSlideCandidate, GeneratedSlideCandidate.batch_id == DesignBatch.id)
        .filter(DesignBatch.deck_id == deck_id, GeneratedSlideCandidate.source_slide_id == slide_id)
        .order_by(DesignBatch.created_at.desc())
        .first()
    )
    return batch.id if batch is not None else None


@router.post("/ai/orchestrate", response_model=AiOrchestrationResponse)
def orchestrate(
    payload: AiOrchestrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiOrchestrationResponse:
    # DISABLED: `/ai/orchestrate` is a duplicate orchestration root that
    # competes with the canonical durable workflow_jobs control plane. Keep the
    # route mounted only as an explicit compatibility stop, not as an active AI
    # execution entrypoint.
    # deck = get_user_deck_or_404(db, current_user, payload.deck_id)
    # enforce_rate_limit(f"deck-aistack-codes-ai:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    # enforce_ai_generation_quota(db, current_user)
    # try:
    #     provider = resolve_orchestration_provider(db, deck, preferred_model=payload.preferred_model)
    #     return SmartDeckOrchestrator(provider=provider).run(db, user=current_user, request=payload)
    # except (AiOrchestrationError, ValueError) as exc:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "legacy_orchestration_disabled",
            "message": "Legacy AI orchestration is disabled. Use the canonical workflow command routes.",
            "recoverable": True,
            "nextAction": "open_smart_deck",
        },
    )


@router.get("/decks/{deck_id}/ai-runs")
def deck_ai_runs(
    deck_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    runs = (
        db.query(AiRun)
        .filter(AiRun.deck_id == deck_id)
        .order_by(AiRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"deckId": deck_id, "aiRuns": [serialize_ai_run(run) for run in runs]}


@router.get("/decks/{deck_id}/batches", response_model=DesignBatchListRouteResponse)
def deck_batches(
    deck_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchListRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    return DesignBatchListRouteResponse(deckId=deck_id, batches=list_design_batches(db, deck_id, limit))


@router.get("/decks/{deck_id}/batches/{batch_id}", response_model=DesignBatchDetailRouteResponse)
def deck_batch_detail(
    deck_id: str,
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignBatchDetailRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    batch = get_design_batch(db, deck_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return DesignBatchDetailRouteResponse(deckId=deck_id, batch=batch)


@router.post("/slides/{slide_id}/accept-version", response_model=BatchSlideDecisionRouteResponse)
def accept_version(
    slide_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchSlideDecisionRouteResponse:
    deck_id = str(payload.get("deckId") or "").strip()
    candidate_id = str(payload.get("generatedVersionId") or payload.get("generatedSlideVersionId") or "").strip()
    batch_id = str(payload.get("batchId") or "").strip()
    if not deck_id or not candidate_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="deckId and generatedVersionId are required")
    get_user_deck_or_404(db, current_user, deck_id)
    if not batch_id:
        candidate = db.query(GeneratedSlideCandidate).filter(GeneratedSlideCandidate.id == candidate_id).one_or_none()
        batch_id = candidate.batch_id if candidate is not None else ""
    if not batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated version not found")

    try:
        decision = save_batch_slide_decision(
            db,
            deck_id,
            batch_id,
            slide_id,
            choice=GENERATED_VERSION,
            generated_slide_candidate_id=candidate_id,
            decided_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch or slide not found")
    batch = get_design_batch(db, deck_id, batch_id)
    record_agent_event(
        db,
        event_name="ai.user.accepted_generated",
        run_type="deck_aistack_orchestration",
        deck_id=deck_id,
        user_id=current_user.id,
        run_id=batch_id,
        status="completed",
        metadata={"batchId": batch_id, "slideId": slide_id, "generatedSlideVersionId": candidate_id},
        commit=True,
    )
    return BatchSlideDecisionRouteResponse(deckId=deck_id, batchId=batch_id, decision=_map_decision(decision), batch=batch)


@router.post("/slides/{slide_id}/keep-original", response_model=BatchSlideDecisionRouteResponse)
def keep_original(
    slide_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchSlideDecisionRouteResponse:
    deck_id = str(payload.get("deckId") or "").strip()
    batch_id = str(payload.get("batchId") or "").strip() or (_latest_batch_id_for_slide(db, deck_id, slide_id) or "")
    if not deck_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="deckId is required")
    get_user_deck_or_404(db, current_user, deck_id)
    if not batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    try:
        decision = save_batch_slide_decision(
            db,
            deck_id,
            batch_id,
            slide_id,
            choice=ORIGINAL,
            decided_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch or slide not found")
    batch = get_design_batch(db, deck_id, batch_id)
    record_agent_event(
        db,
        event_name="ai.user.kept_original",
        run_type="deck_aistack_orchestration",
        deck_id=deck_id,
        user_id=current_user.id,
        run_id=batch_id,
        status="completed",
        metadata={"batchId": batch_id, "slideId": slide_id},
        commit=True,
    )
    return BatchSlideDecisionRouteResponse(deckId=deck_id, batchId=batch_id, decision=_map_decision(decision), batch=batch)


@router.post("/decks/{deck_id}/compile-final", response_model=PrepareFullDeckResponse)
def compile_final_deck(
    deck_id: str,
    payload: PrepareFullDeckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PrepareFullDeckResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    latest_batch = db.query(DesignBatch).filter(DesignBatch.deck_id == deck_id).order_by(DesignBatch.created_at.desc()).first()
    payload_batch_id = getattr(payload, "batchId", None)
    batch_id = payload_batch_id or (latest_batch.id if latest_batch is not None else "")
    if not batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    try:
        compiled = prepare_full_deck(
            db,
            deck_id,
            batch_id,
            title=payload.title,
            latest_slide_version_id=payload.latestSlideVersionId,
            created_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if compiled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck or batch not found")
    record_agent_event(
        db,
        event_name="ai.final_deck.compiled",
        run_type="deck_aistack_orchestration",
        deck_id=deck_id,
        user_id=current_user.id,
        run_id=batch_id,
        status="completed",
        metadata={
            "batchId": batch_id,
            "compiledDeckId": compiled.get("compiledDeckId"),
            "slideCount": compiled.get("slideCount"),
        },
        commit=True,
    )
    return PrepareFullDeckResponse(**compiled)


@router.get("/decks/{deck_id}/final-deck")
def final_deck(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    compiled = get_latest_compiled_deck(db, deck_id, user_id=current_user.id)
    if compiled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final deck not found")
    return compiled
