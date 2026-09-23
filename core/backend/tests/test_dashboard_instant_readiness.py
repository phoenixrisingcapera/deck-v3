from types import SimpleNamespace

import pytest

from app.services.visualizer import workspace_dashboard_read_model as dashboard


@pytest.mark.parametrize("state,can_open,expected", [("failed_final", False, "failed"), ("running", False, "preparing"), ("completed", True, "ready_to_review")])
def test_instant_dashboard_requires_generated_publication(monkeypatch, state, can_open, expected):
    deck = SimpleNamespace(id="deck", status="ready", file=SimpleNamespace(metadata_json={"preferredWorkspace": "instant_deck"}))
    monkeypatch.setattr(dashboard, "get_deck_workflow_state", lambda *args: {"phase": "smart_deck_ready", "status": state, "canOpenSmartDeck": True, "canOpenInstantDeck": can_open})
    assert dashboard._dashboard_deck_status(None, deck) == expected


def test_standard_source_review_remains_available(monkeypatch):
    deck = SimpleNamespace(id="deck", status="ready", file=None)
    monkeypatch.setattr(dashboard, "get_deck_workflow_state", lambda *args: {"phase": "smart_deck_ready", "status": "completed", "canOpenSmartDeck": True})
    assert dashboard._dashboard_deck_status(None, deck) == "ready_to_review"
