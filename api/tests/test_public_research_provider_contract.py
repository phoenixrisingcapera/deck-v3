import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import CoreBase
from app.db.models import Deck, DeckLlmArtifact, User, Workspace
from app.services.llm import investor_public_research as research


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = Session(engine)
    user = User(id="owner", email="research@example.test", name="Owner", password_hash="unused")
    workspace = Workspace(id="workspace", user_id=user.id, name="Test")
    deck = Deck(id="deck", user_id=user.id, workspace_id=workspace.id, title="Fixture", audience="Investors", purpose="Pitch", status="ready")
    db.add_all([user, workspace, deck])
    db.commit()
    return db


def _response(text: str):
    return {
        "id": "resp_fixture", "status": "completed",
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "output": [
            {"type": "web_search_call", "action": {
                "query": "industrial maintenance field service software adoption",
                "sources": [{"url": "https://example.org/report"}],
            }},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
    }


def _patch_provider(monkeypatch, transport):
    monkeypatch.setattr(
        "app.services.llm.generation_service.get_generation_provider_config",
        lambda *args, **kwargs: {"provider": "openai", "model": "gpt-4.1-mini-2025-04-14", "apiKey": "fixture"},
    )
    monkeypatch.setattr("app.services.llm.openai_provider.call_openai_response", transport)


def test_schema_constrained_research_records_actual_query_and_verified_handoff(monkeypatch):
    db = _db()
    try:
        payload = {
            "research_question": "Which maintenance workflow barriers shape field-service software adoption?",
            "query_rationale": "Adoption evidence informs positioning and investor objections.",
            "directions": [{"url": "https://example.org/report", "topic": "customer_economics",
                            "comparison_key": "field-service-adoption", "keywords": ["maintenance", "adoption"]}],
            "gaps": [],
        }
        captured = {}

        def transport(**kwargs):
            captured.update(kwargs)
            return _response(json.dumps(payload))

        _patch_provider(monkeypatch, transport)
        monkeypatch.setattr(research, "verify_research_directions", lambda directions: {
            "schemaVersion": research.SCHEMA_VERSION,
            "claims": [{"id": "external_1", "category": "external_research"}],
            "gaps": [], "conflicts": [], "costs": {"publicFetchAttempts": 1},
            "policy": {},
        })
        result = research.discover_public_research(db, "deck", {
            "authorization_id": "fixture-success", "public_brief": "Research industrial maintenance workflows and adoption barriers.",
            "max_provider_requests": 1, "max_dollars": None,
        })
        discovery = result["research"]["discovery"]
        assert captured["response_format"]["type"] == "json_schema"
        assert discovery["executedQueries"] == ["industrial maintenance field service software adoption"]
        assert discovery["verifiedEvidenceIds"] == ["external_1"]
        assert result["status"] == "completed"
    finally:
        db.close()


def test_no_useful_results_is_truthful_not_forced_to_a_source_quota(monkeypatch):
    db = _db()
    try:
        _patch_provider(monkeypatch, lambda **kwargs: _response(json.dumps({
            "research_question": "What reliable current evidence exists?",
            "query_rationale": "Weak results should be rejected rather than promoted.",
            "directions": [], "gaps": ["No authoritative current evidence was found."],
        })))
        result = research.discover_public_research(db, "deck", {
            "authorization_id": "fixture-empty", "public_brief": "Research a real industry without private company lookup.",
            "max_provider_requests": 1, "max_dollars": None,
        })
        assert result["status"] == "no_verified_evidence"
        assert result["research"]["claims"] == []
        assert result["research"]["costs"]["paidResearchRequests"] == 1
    finally:
        db.close()


@pytest.mark.parametrize("mode,known,code", [("malformed", True, "structured_validation"), ("timeout", False, "provider_transport")])
def test_research_failure_classifies_known_and_unknown_outcomes(monkeypatch, mode, known, code):
    db = _db()
    try:
        def transport(**kwargs):
            if mode == "timeout":
                raise TimeoutError("fixture timeout")
            return _response('{"research_question":"truncated')

        _patch_provider(monkeypatch, transport)
        with pytest.raises(research.PublicResearchAttemptFailed) as captured:
            research.discover_public_research(db, "deck", {
                "authorization_id": "fixture-" + mode,
                "public_brief": "Research an industry while preserving unknown-outcome replay safety.",
                "max_provider_requests": 1, "max_dollars": None,
            })
        assert captured.value.outcome_known is known
        assert captured.value.code == code
        if known:
            assert captured.value.search_tool_calls == 1
        else:
            assert captured.value.search_tool_calls == 0
    finally:
        db.close()


def test_model_plan_controls_mounted_research_brief_and_no_keyword_fallback(monkeypatch):
    db = _db()
    captured = []
    model_plan = {
        "status":"model_authored",
        "researchTasks":[{
            "id":"research_01", "purpose":"market_context",
            "question":"Which adoption barriers affect predictive equipment diagnostics?",
            "publicSearchContext":"predictive equipment diagnostics maintenance workflows",
            "evidenceIds":["fact_1"], "importance":"critical",
        }],
    }
    def discover(_db, _deck_id, command):
        captured.append(command["public_brief"])
        return {"research": {
            "claims":[], "gaps":[{"reason":"No verified source"}], "conflicts":[],
            "discoveryAttemptId":"attempt", "discovery":{
                "researchQuestion":"Which adoption barriers affect predictive equipment diagnostics?",
                "queryRationale":"The model selected this question.", "searchToolCalls":1,
                "executedQueries":["predictive equipment diagnostics adoption"],
                "returnedSourceUrls":[], "rejectionReasons":["No verified source"],
                "evidenceSufficient":False, "sufficiencyReason":"Evidence remains insufficient.",
                "followUpQuestion":None,
            },
            "costs":{"searchToolCalls":1, "researchProviderDollars":"0.01"},
        }}
    monkeypatch.setattr(research, "discover_public_research", discover)
    try:
        deck = db.get(Deck, "deck")
        research.ensure_generation_public_research(
            db, deck, "operation",
            public_brief="Research the model-authored public category question.",
            research_tasks=model_plan["researchTasks"],
            research_guidance={"skills":[]}, model_research_plan=model_plan,
        )
        assert len(captured) == 1
        assert model_plan["researchTasks"][0]["question"] in captured[0]
        assert model_plan["researchTasks"][0]["publicSearchContext"] in captured[0]
        dossier = db.query(DeckLlmArtifact).filter_by(
            artifact_key="instant-research:operation",
        ).one().payload_json
        assert dossier["modelResearchPlan"] == model_plan

        research.ensure_generation_public_research(
            db, deck, "operation-no-plan", research_tasks=[],
            research_guidance={"skills":[]}, model_research_plan={"status":"unavailable"},
        )
        unavailable = db.query(DeckLlmArtifact).filter_by(
            artifact_key="instant-research:operation-no-plan",
        ).one().payload_json
        assert len(captured) == 1
        assert unavailable["status"] == "unavailable"
        assert "no keyword-derived search agenda" in unavailable["gaps"][0]["reason"]
    finally:
        db.close()


def test_worker_restart_rehydrates_settled_evidence_without_replaying_provider(monkeypatch):
    db = _db()
    task = {
        "id":"research_01", "purpose":"market_context",
        "question":"Which adoption barriers affect industrial workflow software?",
        "publicSearchContext":"industrial workflow software adoption",
    }
    attempt = DeckLlmArtifact(
        id="attempt-settled", deck_id="deck",
        artifact_type="instant_deck_public_research_attempt",
        artifact_key="public-research-attempt:instant-restart-1",
        schema_version=research.SCHEMA_VERSION, status="completed",
        summary="Settled fixture request.",
        payload_json={"providerStarts":1},
        metrics_json={"searchToolCalls":1, "researchProviderDollars":"0.02", "outcomeKnown":True},
    )
    settled = DeckLlmArtifact(
        id="settled-result", deck_id="deck", artifact_type=research.ARTIFACT_TYPE,
        artifact_key="settled-result", schema_version=research.SCHEMA_VERSION,
        status="ready", summary="Settled verified fixture evidence.",
        payload_json={
            "discoveryAttemptId":"attempt-settled",
            "claims":[{"id":"external_settled", "topic":"market_context"}],
            "gaps":[], "conflicts":[],
            "discovery":{
                "researchQuestion":task["question"], "queryRationale":"Useful category evidence.",
                "searchToolCalls":1, "executedQueries":["industrial workflow adoption"],
                "returnedSourceUrls":["https://example.org/report"],
                "evidenceSufficient":True, "sufficiencyReason":"One authoritative source answers the question.",
                "followUpQuestion":None,
            },
        },
        metrics_json={"researchProviderDollars":"0.02"},
    )
    db.add_all([attempt, settled])
    db.commit()
    monkeypatch.setattr(
        research, "discover_public_research",
        lambda *_args, **_kwargs: pytest.fail("settled request must not be replayed"),
    )
    try:
        research.ensure_generation_public_research(
            db, db.get(Deck, "deck"), "restart",
            research_tasks=[task], research_guidance={"skills":[]},
            model_research_plan={"status":"model_authored", "researchTasks":[task]},
        )
        dossier = db.query(DeckLlmArtifact).filter_by(
            artifact_key="instant-research:restart",
        ).one().payload_json
        assert [claim["id"] for claim in dossier["claims"]] == ["external_settled"]
        assert dossier["attemptTrace"][0]["outcome"] == "resumed_verified"
        assert dossier["attemptTrace"][0]["replayedProviderRequest"] is False
        assert dossier["costs"]["paidResearchRequests"] == 1
    finally:
        db.close()
