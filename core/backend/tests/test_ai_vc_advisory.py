from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import Deck, DeckLlmArtifact, User, Workspace
from app.services.ai_vc.advisory import (
    CRITIQUE_ARTIFACT_TYPE,
    investment_critique_status,
    persist_investment_critique,
    source_summary,
)


def _session_with_deck():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="user", email="owner@example.test", name="Owner", password_hash="unused")
    workspace = Workspace(id="workspace", name="Workspace", user_id=user.id)
    deck = Deck(
        id="deck", workspace_id=workspace.id, user_id=user.id, title="Deck",
        audience="Investors", purpose="Fundraising", status="ready",
    )
    session.add_all([user, workspace, deck])
    session.commit()
    return engine, session, deck


def test_investment_critique_is_persisted_as_internal_advice_not_a_gate():
    engine, session, deck = _session_with_deck()
    try:
        payload = persist_investment_critique(
            session,
            deck_id=deck.id,
            operation_id="operation-1",
            review={
                "concerns": ["Retention evidence is missing"],
                "critical_for_fundraising": ["Willingness to pay is unproven"],
                "publication_blocking": False,
            },
        )
        session.commit()

        assert payload["internalProductOnly"] is True
        assert payload["publicationBlocking"] is False
        assert investment_critique_status(session, deck.id) == payload
        row = session.query(DeckLlmArtifact).filter_by(artifact_type=CRITIQUE_ARTIFACT_TYPE).one()
        assert row.status == "ready"
        assert row.metrics_json == {"publicationBlocking": False, "advisory": True}
        assert deck.status == "ready"
    finally:
        session.close()
        engine.dispose()


def test_source_summary_is_ui_only_and_uses_verified_external_evidence():
    engine, session, deck = _session_with_deck()
    try:
        session.add(DeckLlmArtifact(
            id="research", deck_id=deck.id,
            artifact_type="instant_deck_verified_public_research", artifact_key="research",
            schema_version="investor-public-evidence.v1", status="ready",
            payload_json={"claims": [{
                "id": "external_1", "category": "external_research",
                "topic": "why_now", "publisher": "example.org",
                "url": "https://example.org/report", "publicationDate": "2026-01-01",
                "retrievalDate": "2026-09-18T00:00:00+00:00", "text": "Verified market context.",
            }]},
        ))
        session.commit()

        payload = source_summary(session, deck.id)
        assert payload["status"] == "verified"
        assert payload["internalProductOnly"] is True
        assert payload["exportedWithDeck"] is False
        assert payload["sources"][0]["evidenceId"] == "external_1"
    finally:
        session.close()
        engine.dispose()
