import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import Deck, DeckSlide, InstantDeckOperation, User, WorkflowJob, Workspace
from app.schemas.deck_workflow import WorkflowGenerationRequest
from app.services.deck_processing.workflow_orchestration import (
    WorkflowConflictError,
    queue_smart_deck_generation,
)


def _payload(*, prompt: str = "Redesign this deck") -> WorkflowGenerationRequest:
    return WorkflowGenerationRequest(
        prompt=prompt,
        selectedSourceSlideIds=["source_1", "source_2"],
        activeSourceSlideId="source_1",
        idempotencyKey="browser-command-1",
        generationMode="instant_deck",
        outputContract="full_html_deck.v1",
        deckType="startup_pitch",
    )


def test_replayed_instant_command_reuses_one_operation_and_pipeline(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(id="command_user", email="command@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="command_workspace", name="Workspace", user_id=user.id)
        deck = Deck(
            id="command_deck",
            workspace_id=workspace.id,
            user_id=user.id,
            title="Command deck",
            audience="Investors",
            purpose="Fundraising",
            status="ready",
        )
        slides = [
            DeckSlide(id="source_1", deck_id=deck.id, slide_index=0, slide_number=1, title="One", role="opening", raw_text="One"),
            DeckSlide(id="source_2", deck_id=deck.id, slide_index=1, slide_number=2, title="Two", role="problem", raw_text="Two"),
        ]
        db.add_all([user, workspace, deck, *slides])
        db.commit()
        monkeypatch.setattr(
            "app.services.deck_processing.workflow_state_read_model.get_deck_workflow_state",
            lambda _db, _deck_id: {"canOpenSmartDeck": True},
        )

        first = queue_smart_deck_generation(
            db,
            deck.id,
            current_user_id=user.id,
            payload=_payload(),
            defer_instant_provider_release=True,
        )
        replay = queue_smart_deck_generation(
            db,
            deck.id,
            current_user_id=user.id,
            payload=_payload(),
            defer_instant_provider_release=True,
        )

        assert first["operationCreated"] is True
        assert replay["operationCreated"] is False
        assert replay["jobId"] == first["jobId"]
        assert replay["instantOperationId"] == first["instantOperationId"]
        persisted_job = db.query(WorkflowJob).filter_by(id=first["jobId"]).one()
        assert persisted_job.input_json["publicResearchPolicy"] == "bounded-ai-vc-research.v2"
        assert db.query(InstantDeckOperation).count() == 1
        jobs = db.query(WorkflowJob).order_by(WorkflowJob.job_type).all()
        assert [job.job_type for job in jobs] == [
            "db_publisher",
            "instant_deck_generation",
            "preview_render",
            "schema_validation",
        ]

        with pytest.raises(WorkflowConflictError) as raised:
            queue_smart_deck_generation(
                db,
                deck.id,
                current_user_id=user.id,
                payload=_payload(prompt="A different request"),
                defer_instant_provider_release=True,
            )
        assert raised.value.code == "idempotency_key_conflict"
        assert db.query(InstantDeckOperation).count() == 1
        assert db.query(WorkflowJob).count() == 4
    finally:
        db.close()
        engine.dispose()
