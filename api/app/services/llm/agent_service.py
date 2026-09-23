from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Deck
from app.schemas.smart_deck_agent import SmartDeckAgentGenerateInput
from app.schemas.deck_workflow import WorkflowGenerationRequest
from app.services.deck_processing.workflow_orchestration import queue_smart_deck_generation


def generate_smart_deck_agent(
    db: Session,
    deck_id: str,
    payload: SmartDeckAgentGenerateInput,
    *,
    run_id: str | None = None,
):
    deck = db.get(Deck, deck_id)
    if deck is None:
        return None

    workflow_payload = WorkflowGenerationRequest(
        prompt=payload.userPrompt,
        selectedSourceSlideIds=payload.selectedSlideIds,
        deckType=payload.deckType,
        audience=payload.audience,
        preferredModel=payload.preferredModel,
        selectedElementId=payload.selectedElementId,
        selectedSubject=payload.selectedSubject,
        detectedSubjects=[item.model_dump() for item in payload.detectedSubjects],
        actionId=payload.actionId,
        actionPrompt=payload.actionPrompt,
        userPrompt=payload.userPrompt,
        latestBatchId=payload.latestBatchId,
        idempotencyKey=":".join(
            [
                "smart_deck_agent",
                deck_id,
                run_id or "no-run",
                payload.actionId or "no-action",
                payload.latestBatchId or "no-batch",
            ]
        ),
    )
    return queue_smart_deck_generation(
        db,
        deck_id,
        current_user_id=deck.user_id,
        payload=workflow_payload,
    )
