from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.api.deps import get_user_deck_or_404
from app.db.base import CoreBase
from app.db.models import Deck, DeckSlide, User, Workspace
from app.schemas.smart_deck import SmartDeckWorkspaceResponse
from app.services.llm.generation_service import get_instant_deck_workspace


def test_failed_instant_job_retains_its_mode_without_a_success_result():
    from app.db.models import GenerationJob
    from app.services.llm.generation_service import _map_job
    job = GenerationJob(
        id="failed_instant", deck_id="deck", status="failed", prompt="Synthetic test",
        result_json={}, llm_context_json={"fullHtmlRequestContextArtifactId": "context"},
    )
    assert _map_job(job)["generationMode"] == "instant_deck"


def test_first_generation_workspace_uses_only_minimal_instant_contract() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(
            id="user_owner",
            email="owner@example.test",
            name="Owner",
            password_hash="not-used",
        )
        workspace = Workspace(id="workspace_owner", name="Owner workspace", user_id=user.id)
        deck = Deck(
            id="deck_first_generation",
            workspace_id=workspace.id,
            user_id=user.id,
            title="Customer source",
            audience="Investors",
            purpose="Fundraising",
            status="ready",
            summary="Persisted customer source",
        )
        slide = DeckSlide(
            id="source_slide_1",
            deck_id=deck.id,
            slide_index=0,
            slide_number=1,
            title="Problem",
            role="problem",
            raw_text="A source-grounded problem statement.",
        )
        session.add_all([user, workspace, deck, slide])
        session.commit()

        payload = get_instant_deck_workspace(session, deck.id)

        assert payload is not None
        SmartDeckWorkspaceResponse(**payload)
        assert payload["deck"]["id"] == deck.id
        assert [item["id"] for item in payload["sourceSlides"]] == [slide.id]
        assert payload["generationJobs"] == []
        assert payload["designVersions"] == []
        assert payload["messages"] == []
        assert payload["designTokens"] == []
        assert payload["activeSourceSlideId"] == slide.id
        assert payload["preferences"]["selectedSourceSlideIds"] == [slide.id]
        assert payload["preferences"]["preferredModel"] is None
        assert "knowledgeMetadata" not in payload
        assert "runtimeContext" not in payload
        assert "runtimeCapabilities" not in payload
    finally:
        session.close()
        engine.dispose()


def test_dedicated_instant_routes_are_registered() -> None:
    from app.main import app

    methods_by_path: dict[str, set[str]] = {}
    for route in app.routes:
        if hasattr(route, "methods"):
            methods_by_path.setdefault(route.path, set()).update(route.methods or set())
    root = "/api/products/deck-aistack-codes/decks/{deck_id}/instant-deck"

    assert "GET" in methods_by_path[root]
    assert "PATCH" in methods_by_path[f"{root}/session-state"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/ai-vc-runs/latest/visual-direction"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/ai-vc-runs/latest/vision-review"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/graph"]
    assert "POST" in methods_by_path["/api/decks/{deck_id}/upload-url"]
    assert "POST" in methods_by_path["/api/decks/{deck_id}/upload-complete"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state"]
    assert "POST" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction"]
    assert "POST" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/workflows/brand-extraction"]
    assert "POST" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation"]
    assert "POST" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/workflows/export"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/exports"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}/download"]
    assert "GET" in methods_by_path["/api/workflow-jobs/{job_id}"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/brand-profile"]
    assert "PATCH" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/brand-profile"]
    assert "GET" in methods_by_path["/api/products/deck-aistack-codes/decks/{deck_id}/brand-assets/{asset_id}"]
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/generate-slides" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/media" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/properties" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/versions" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generate" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/smart-agent/generate" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/brand/status" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/brand/extract" not in methods_by_path
    assert "/api/decks/{deck_id}/slides/{slide_id}/preview" not in methods_by_path
    assert "/api/decks/{deck_id}/smart-edit" not in methods_by_path
    assert "/api/decks/{deck_id}/due-diligence/report" not in methods_by_path
    assert "/api/decks/{deck_id}/export" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/persistent-fields" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/workflows/selected-slide-generation" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/workflows/apply-design-version" not in methods_by_path
    assert "/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/start" not in methods_by_path
    assert "/api/workspace/dashboard/notifications" not in methods_by_path
    assert "/api/workspace/dashboard/tasks" not in methods_by_path


def test_ordinary_owner_cannot_resolve_another_users_deck() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        owner = User(id="user_owner", email="owner@example.com", name="Owner", password_hash="unused")
        stranger = User(id="user_stranger", email="stranger@example.com", name="Stranger", password_hash="unused")
        workspace = Workspace(id="workspace_owner", name="Owner workspace", user_id=owner.id)
        deck = Deck(
            id="deck_private",
            workspace_id=workspace.id,
            user_id=owner.id,
            title="Private deck",
            audience="Investors",
            purpose="Fundraising",
            status="ready",
        )
        session.add_all([owner, stranger, workspace, deck])
        session.commit()

        assert get_user_deck_or_404(session, owner, deck.id).id == deck.id
        try:
            get_user_deck_or_404(session, stranger, deck.id)
        except HTTPException as exc:
            assert exc.status_code == 404
            assert exc.detail == "Deck not found"
        else:
            raise AssertionError("Another user's deck was visible")
    finally:
        session.close()
        engine.dispose()
