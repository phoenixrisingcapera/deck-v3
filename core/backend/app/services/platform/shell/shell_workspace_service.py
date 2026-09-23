from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import Deck, DeckSlide, DeckWorkspacePreference, DesignBatch, DeckGenerationWorkspace, DeckSlideVersion

ALLOWED_TOOLS = {
    "deck_map",
    "research",
    "slides",
    "elements",
    "text",
    "media",
    "data",
    "ai_tools",
    "brand",
    "settings",
}


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(selectinload(Deck.workspace), selectinload(Deck.workspace_preferences))
        .filter(Deck.id == deck_id)
        .first()
    )


def _default_workspace_state(deck: Deck) -> dict:
    return {
        "deckId": deck.id,
        "activeTool": "slides",
        "leftPanelOpen": True,
        "selectedSlideId": None,
        "lastBatchId": None,
        "lastSlideVersionId": None,
        "selectedElementType": None,
        "selectedDataView": None,
        "chatOpen": False,
        "updatedAt": _iso(deck.updated_at),
    }


def _map_workspace_state(preference: DeckWorkspacePreference | None, deck: Deck) -> dict:
    if preference is None:
        return _default_workspace_state(deck)

    return {
        "deckId": deck.id,
        "activeTool": preference.active_tool,
        "leftPanelOpen": preference.left_panel_open,
        "selectedSlideId": preference.selected_slide_id,
        "lastBatchId": preference.last_batch_id,
        "lastSlideVersionId": preference.last_slide_version_id,
        "selectedElementType": preference.selected_element_type,
        "selectedDataView": preference.selected_data_view,
        "chatOpen": preference.chat_open,
        "updatedAt": _iso(preference.updated_at),
    }


def _resolve_preference(deck: Deck) -> DeckWorkspacePreference | None:
    workspace_user_id = deck.workspace.user_id if deck.workspace is not None else None
    if workspace_user_id is None:
        return None

    for preference in deck.workspace_preferences:
        if preference.user_id == workspace_user_id:
            return preference

    return None


def get_deck_workspace_preferences(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    return _map_workspace_state(_resolve_preference(deck), deck)


def update_deck_workspace_preferences(db: Session, deck_id: str, payload: dict) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    workspace_user_id = deck.workspace.user_id if deck.workspace is not None else None
    if workspace_user_id is None:
        return _default_workspace_state(deck)

    if payload.get("activeTool") is not None and payload["activeTool"] not in ALLOWED_TOOLS:
        raise ValueError("Unsupported shell tool.")

    if payload.get("selectedSlideId") is not None:
        selected_slide = (
            db.query(DeckSlide)
            .filter(DeckSlide.id == payload["selectedSlideId"], DeckSlide.deck_id == deck_id)
            .one_or_none()
        )
        if selected_slide is None:
            raise ValueError("Selected slide does not belong to this deck.")

    if payload.get("lastBatchId") is not None:
        batch = (
            db.query(DesignBatch)
            .filter(DesignBatch.id == payload["lastBatchId"], DesignBatch.deck_id == deck_id)
            .one_or_none()
        )
        if batch is None:
            raise ValueError("Batch does not belong to this deck.")

    if payload.get("lastSlideVersionId") is not None:
        slide_version = (
            db.query(DeckSlideVersion)
            .join(DeckGenerationWorkspace, DeckGenerationWorkspace.id == DeckSlideVersion.deck_generation_workspace_id)
            .filter(
                DeckSlideVersion.id == payload["lastSlideVersionId"],
                DeckGenerationWorkspace.deck_id == deck_id,
            )
            .one_or_none()
        )
        if slide_version is None:
            raise ValueError("Slide version not found.")

    preference = _resolve_preference(deck)
    if preference is None:
        preference = DeckWorkspacePreference(
            id=generate_id("shellpref"),
            deck_id=deck.id,
            user_id=workspace_user_id,
            active_tool="slides",
            left_panel_open=True,
            chat_open=False,
        )
        db.add(preference)

    # Keep this payload narrow and user-facing so the shell state remains easy to reason about.
    if "activeTool" in payload and payload.get("activeTool") is not None:
        preference.active_tool = payload["activeTool"]
    if "leftPanelOpen" in payload and payload.get("leftPanelOpen") is not None:
        preference.left_panel_open = payload["leftPanelOpen"]
    if "selectedSlideId" in payload:
        preference.selected_slide_id = payload.get("selectedSlideId")
    if "lastBatchId" in payload:
        preference.last_batch_id = payload.get("lastBatchId")
    if "lastSlideVersionId" in payload:
        preference.last_slide_version_id = payload.get("lastSlideVersionId")
    if "selectedElementType" in payload:
        preference.selected_element_type = payload.get("selectedElementType")
    if "selectedDataView" in payload:
        preference.selected_data_view = payload.get("selectedDataView")
    if "chatOpen" in payload and payload.get("chatOpen") is not None:
        preference.chat_open = payload["chatOpen"]

    db.commit()
    db.refresh(preference)
    return _map_workspace_state(preference, deck)
