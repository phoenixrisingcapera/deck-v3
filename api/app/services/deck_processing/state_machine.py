from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Deck
from app.services.deck_processing.save_confirmation import record_save_confirmation


class DeckState(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


CANONICAL_DECK_STATES = tuple(state.value for state in DeckState)

# Backward-compatible read map. This lets old persisted values be interpreted
# consistently while all new writes go through the canonical vocabulary above.
LEGACY_DECK_STATE_MAP: dict[str, str] = {
    "draft": DeckState.UPLOADED.value,
    "saved": DeckState.UPLOADED.value,
    "source_saved": DeckState.UPLOADED.value,
    "preparing": DeckState.PROCESSING.value,
    "queued": DeckState.PROCESSING.value,
    "running": DeckState.PROCESSING.value,
    "starting": DeckState.PROCESSING.value,
    "parsing": DeckState.PROCESSING.value,
    "structuring": DeckState.PROCESSING.value,
    "extracting_blocks": DeckState.PROCESSING.value,
    "classifying_blocks": DeckState.PROCESSING.value,
    "analysing": DeckState.PROCESSING.value,
    "analyzing": DeckState.PROCESSING.value,
    "adapting": DeckState.PROCESSING.value,
    "workspace_ready": DeckState.READY.value,
    "completed": DeckState.READY.value,
    "reviewed": DeckState.READY.value,
    "dead_letter": DeckState.FAILED.value,
    "error": DeckState.FAILED.value,
}

ALLOWED_DECK_STATE_TRANSITIONS: dict[DeckState, set[DeckState]] = {
    DeckState.PENDING: {DeckState.UPLOADED, DeckState.PROCESSING, DeckState.FAILED},
    DeckState.UPLOADED: {DeckState.PROCESSING, DeckState.READY, DeckState.FAILED},
    DeckState.PROCESSING: {DeckState.UPLOADED, DeckState.READY, DeckState.FAILED},
    DeckState.READY: {DeckState.UPLOADED, DeckState.PROCESSING, DeckState.FAILED},
    DeckState.FAILED: {DeckState.UPLOADED, DeckState.PROCESSING},
}


class InvalidDeckStateTransition(ValueError):
    """Raised when a deck lifecycle mutation violates the canonical state graph."""


def _coerce_state_value(value: str | DeckState | None) -> str:
    if isinstance(value, DeckState):
        return value.value
    return str(value or "").strip().lower()


def canonical_deck_state(value: str | DeckState | None) -> DeckState:
    raw_value = _coerce_state_value(value)
    if raw_value in CANONICAL_DECK_STATES:
        return DeckState(raw_value)

    mapped_value = LEGACY_DECK_STATE_MAP.get(raw_value)
    if mapped_value is not None:
        return DeckState(mapped_value)

    raise ValueError(f"Unknown deck state: {value!r}")


def processing_run_status_to_deck_state(value: str | DeckState | None) -> DeckState:
    """Map worker/run-specific statuses onto the deck lifecycle vocabulary."""

    return canonical_deck_state(value)


def assert_valid_deck_state_transition(
    previous_state: str | DeckState | None,
    target_state: str | DeckState,
) -> None:
    previous = canonical_deck_state(previous_state)
    target = canonical_deck_state(target_state)

    if previous == target:
        return

    if target not in ALLOWED_DECK_STATE_TRANSITIONS[previous]:
        raise InvalidDeckStateTransition(f"Invalid deck state transition: {previous.value} -> {target.value}")


def _audit_metadata(
    *,
    previous_raw_state: str | None,
    previous_state: DeckState,
    target_state: DeckState,
    reason: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "previousRawState": previous_raw_state,
        "previousState": previous_state.value,
        "targetState": target_state.value,
        "reason": reason,
        **(metadata or {}),
    }


def transition_deck_state(
    db: Session,
    deck: Deck,
    target_state: str | DeckState,
    *,
    actor_user_id: str | None = None,
    reason: str,
    summary: str | None = None,
    source_surface: str | None = None,
    source_route: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> str:
    """Move a deck through the canonical lifecycle and persist an audit event.

    This is the only supported write path for deck.status in production flows.
    Worker-specific run statuses stay on DeckExtractionRun; frontend-facing deck
    status/state must use the five canonical values in DeckState.
    """

    previous_raw_state = deck.status
    previous_state = canonical_deck_state(previous_raw_state)
    next_state = canonical_deck_state(target_state)
    assert_valid_deck_state_transition(previous_state, next_state)

    state_changed = previous_raw_state != next_state.value
    summary_changed = summary is not None and deck.summary != summary

    deck.status = next_state.value
    deck.updated_at = datetime.utcnow()
    if summary is not None:
        deck.summary = summary

    if state_changed or summary_changed:
        record_save_confirmation(
            db,
            deck_id=deck.id,
            workspace_id=deck.workspace_id,
            user_id=actor_user_id,
            event_type="deck_state_transition",
            entity_type="deck",
            entity_id=deck.id,
            title="Deck state updated",
            message=f"Deck moved from {previous_state.value} to {next_state.value}.",
            source_surface=source_surface,
            source_route=source_route,
            dedupe_key=f"deck_state:{deck.id}:{previous_raw_state}:{next_state.value}:{datetime.utcnow().isoformat()}",
            metadata=_audit_metadata(
                previous_raw_state=previous_raw_state,
                previous_state=previous_state,
                target_state=next_state,
                reason=reason,
                metadata=metadata,
            ),
        )

    if commit:
        db.commit()

    return next_state.value


def deck_state_payload(deck: Deck) -> dict[str, str]:
    state = canonical_deck_state(deck.status).value
    return {
        "status": state,
        "state": state,
        "deckStatus": state,
    }


def decorate_deck_payload_with_state(payload: dict[str, Any]) -> dict[str, Any]:
    raw_state = payload.get("status") or payload.get("state") or payload.get("deckStatus")
    state = canonical_deck_state(str(raw_state or DeckState.PENDING.value)).value
    return {**payload, "status": state, "state": state, "deckStatus": state}


def decorate_deck_payloads_with_state(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [decorate_deck_payload_with_state(payload) for payload in payloads]
