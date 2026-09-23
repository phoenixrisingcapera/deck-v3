from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import (
    BatchSlideDecision,
    Deck,
    DeckSlide,
    DesignBatch,
    DesignVersion,
    GeneratedSlide,
    GeneratedSlideCandidate,
    SmartDeckPreference,
    SmartDeckWorkspace,
    User,
    Workspace,
)
from app.workers.runtime.publisher_runtime import _select_published_instant_version


def test_only_publisher_selects_complete_ordered_instant_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(id="publish_user", email="publish@example.test", name="Owner", password_hash="unused")
        account_workspace = Workspace(id="publish_account", name="Workspace", user_id=user.id)
        deck = Deck(
            id="publish_deck",
            workspace_id=account_workspace.id,
            user_id=user.id,
            title="Publication contract",
            audience="Investors",
            purpose="Fundraising",
            status="processing",
        )
        previous = DesignVersion(
            id="designver_previous",
            deck_id=deck.id,
            name="Previous",
            status="applied",
            is_active=True,
        )
        candidate = DesignVersion(
            id="designver_candidate",
            deck_id=deck.id,
            name="Candidate",
            status="preview",
            is_active=False,
            artifact_type="full_html_deck.v1",
            render_mode="html_compiled.v1",
        )
        source_slide = DeckSlide(
            id="source_shared",
            deck_id=deck.id,
            slide_index=0,
            slide_number=1,
            title="Shared evidence",
            role="evidence",
            raw_text="One source can support several reconstructed narrative slides.",
        )
        later_slide = GeneratedSlide(
            id="genslide_later",
            deck_id=deck.id,
            design_version_id=candidate.id,
            slide_number=2,
            title="Second",
            status="ready",
            source_slide_id=source_slide.id,
        )
        first_slide = GeneratedSlide(
            id="genslide_first",
            deck_id=deck.id,
            design_version_id=candidate.id,
            slide_number=1,
            title="First",
            status="ready",
            source_slide_id=source_slide.id,
        )
        product_workspace = SmartDeckWorkspace(
            id="instant_workspace",
            deck_id=deck.id,
            user_id=user.id,
            active_design_version_id=previous.id,
            status="reviewing",
        )
        preference = SmartDeckPreference(
            id="instant_preference",
            workspace_id=product_workspace.id,
            deck_id=deck.id,
            user_id=user.id,
            active_design_version_id=previous.id,
        )
        deck.current_design_version_id = previous.id
        db.add_all([
            user,
            account_workspace,
            deck,
            previous,
            candidate,
            source_slide,
            later_slide,
            first_slide,
            product_workspace,
            preference,
        ])
        db.commit()

        # Persisting the provisional candidate does not change authoritative
        # server-side selection before the publisher runs.
        assert candidate.status == "preview"
        assert candidate.is_active is False
        assert deck.current_design_version_id == previous.id
        assert product_workspace.active_design_version_id == previous.id

        _select_published_instant_version(db, deck=deck, version=candidate)
        db.commit()
        db.expire_all()

        persisted_deck = db.get(Deck, deck.id)
        persisted_previous = db.get(DesignVersion, previous.id)
        persisted_candidate = db.get(DesignVersion, candidate.id)
        persisted_workspace = db.get(SmartDeckWorkspace, product_workspace.id)
        persisted_preference = db.get(SmartDeckPreference, preference.id)

        assert persisted_candidate.status == "applied"
        assert persisted_candidate.is_active is True
        assert persisted_candidate.applied_at is not None
        assert persisted_previous.is_active is False
        assert persisted_deck.current_design_version_id == candidate.id
        assert persisted_workspace.status == "ready"
        assert persisted_workspace.active_design_version_id == candidate.id
        assert persisted_workspace.active_generated_slide_id == first_slide.id
        assert persisted_preference.active_design_version_id == candidate.id
        assert persisted_preference.active_generated_slide_id == first_slide.id
        accepted_history = (
            db.query(DesignBatch)
            .filter(
                DesignBatch.deck_id == deck.id,
                DesignBatch.source_design_version_id == candidate.id,
                DesignBatch.source_surface == "instant_deck",
                DesignBatch.status == "saved",
                DesignBatch.accepted_at.is_not(None),
            )
            .one()
        )
        assert accepted_history.source_artifact_id == candidate.id
        assert accepted_history.accepted_by_user_id == user.id
        assert db.query(GeneratedSlideCandidate).filter_by(batch_id=accepted_history.id).count() == 2
        decisions = db.query(BatchSlideDecision).filter_by(batch_id=accepted_history.id).all()
        assert len(decisions) == 1
        assert decisions[0].slide_id == source_slide.id
    finally:
        db.close()
        engine.dispose()


def test_publisher_refuses_version_without_persisted_slides() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(id="empty_user", email="empty@example.test", name="Owner", password_hash="unused")
        account_workspace = Workspace(id="empty_account", name="Workspace", user_id=user.id)
        deck = Deck(
            id="empty_deck",
            workspace_id=account_workspace.id,
            user_id=user.id,
            title="Incomplete candidate",
            audience="Investors",
            purpose="Fundraising",
            status="processing",
        )
        candidate = DesignVersion(
            id="designver_empty",
            deck_id=deck.id,
            name="Incomplete",
            status="preview",
            is_active=False,
            artifact_type="full_html_deck.v1",
            render_mode="html_compiled.v1",
        )
        db.add_all([user, account_workspace, deck, candidate])
        db.commit()

        try:
            _select_published_instant_version(db, deck=deck, version=candidate)
        except ValueError as exc:
            assert str(exc) == "Instant Deck publication requires persisted ordered slides."
        else:
            raise AssertionError("An incomplete DesignVersion became publishable")

        assert candidate.status == "preview"
        assert candidate.is_active is False
        assert deck.current_design_version_id is None
    finally:
        db.close()
        engine.dispose()
