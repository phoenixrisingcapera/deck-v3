from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import Deck, DeckLlmArtifact, User, Workspace
from app.services.ai_vc.runtime import (
    AIVCStageFailure,
    AnalysisStage,
    NarrativeStage,
    ResearchPlanningStage,
    _prune_unknown_fields,
    _validate_model_research_plan,
    ensure_model_research_plan,
    execute_ai_vc_runtime,
    resolve_strategy_research_questions,
)


def _session_with_deck():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(id="user", email="owner@example.test", name="Owner", password_hash="unused")
    workspace = Workspace(id="workspace", name="Workspace", user_id=user.id)
    deck = Deck(
        id="deck", workspace_id=workspace.id, user_id=user.id, title="Company",
        audience="Investors", purpose="Fundraising", status="ready",
    )
    session.add_all([user, workspace, deck])
    session.commit()
    return engine, session, deck


def test_executed_model_research_questions_replace_the_presearch_plan():
    questions, source = resolve_strategy_research_questions(
        {"businessEvidence": [{"text": "Workflow software for farms"}]},
        {"attemptTrace": [
            {"modelResearchQuestion": "Which adoption barriers matter to farm operators?"},
            {"modelResearchQuestion": "Which adoption barriers matter to farm operators?"},
            {"modelResearchQuestion": "How do incumbents price comparable tools?"},
        ]},
    )
    assert source == "model_authored_search"
    assert questions == [
        "Which adoption barriers matter to farm operators?",
        "How do incumbents price comparable tools?",
    ]


def test_missing_model_plan_does_not_restore_keyword_research_authority():
    questions, source = resolve_strategy_research_questions(
        {"businessEvidence": [{"text": "Workflow software for farms"}]},
        {"attemptTrace": [{"outcome": "unknown_outcome"}]},
    )
    assert source == "unavailable"
    assert questions == []


def _analysis():
    return {
        "researchSynthesis": {"schema_version": "ai-vc-research-synthesis.v1"},
        "investmentMemo": {"thesis": "A workflow category can be rebuilt."},
        "financialAnalysis": {
            "verifiedCompanyMetrics": [], "managementProjections": [],
            "externalBenchmarks": [], "derivedCalculations": [],
            "investorImplications": [], "narrativeSelections": [],
            "missingFinancialProof": ["Retention"],
        },
        "vcInferences": [{"statement": "The wedge can expand", "evidenceRefs": ["fact_1"]}],
        "evidenceGaps": ["Retention"],
        "investmentCommitteeReview": {"publication_blocking": False},
    }


def _research_plan(*, industry, business_model, question, public_context):
    interpretation = lambda statement: {
        "statement": statement, "evidence_ids": ["fact_1"],
        "confidence": "medium", "uncertainty": None,
    }
    return {
        "what_company_sells": interpretation("Predictive equipment diagnostics software"),
        "buyers": [interpretation("Industrial maintenance operators")],
        "business_models": [interpretation(business_model)],
        "industry_contexts": [interpretation(industry)],
        "workflows": [interpretation("Equipment monitoring and maintenance planning")],
        "geographies": [], "reporting_periods": [],
        "uncertainties": ["Commercial model is not explicit"],
        "methodology_selections": [{
            "name":"company-understanding", "reason":"Interpret ambiguous source evidence",
            "priority":"critical",
        }],
        "research_tasks": [{
            "purpose":"market_context", "question":question,
            "rationale":"Establish the relevant public category without assuming the customer industry is the business model.",
            "public_search_context":public_context,
            "evidence_ids":["fact_1"], "importance":"critical",
        }],
    }


def test_model_understanding_controls_industry_and_question_without_keyword_override():
    cases = [
        ("industrial equipment diagnostics", "software subscription", "Which predictive-maintenance adoption barriers affect plant operators?"),
        ("legal operations", "professional workflow software", "Which workflow tools compete in legal matter operations?"),
        ("mixed energy and logistics", "uncertain mixed model", "How do logistics buyers evaluate energy optimization platforms?"),
    ]
    for industry, model, question in cases:
        parsed = ResearchPlanningStage.model_validate(_research_plan(
            industry=industry, business_model=model, question=question,
            public_context=industry + " buyer workflows",
        ))
        result = _validate_model_research_plan(parsed, source_ids={"fact_1"}, deck_title="Private Fixture")
        assert result["companyUnderstanding"]["industryContexts"][0]["statement"] == industry
        assert result["companyUnderstanding"]["businessModels"][0]["statement"] == model
        assert result["researchTasks"][0]["question"] == question


def test_public_search_context_rejects_private_title_and_metrics():
    for unsafe in ("Private Fixture market", "workflow with $4m revenue", "buyer count 28"):
        parsed = ResearchPlanningStage.model_validate(_research_plan(
            industry="operations software", business_model="uncertain",
            question="Which public category evidence is credible?", public_context=unsafe,
        ))
        with pytest.raises(AIVCStageFailure) as exc_info:
            _validate_model_research_plan(
                parsed, source_ids={"fact_1"}, deck_title="Private Fixture",
                private_numeric_tokens={"$4m", "28"},
            )
        assert exc_info.value.recoverable is False


def test_public_category_numbers_are_allowed_when_not_private_source_metrics():
    parsed = ResearchPlanningStage.model_validate(_research_plan(
        industry="industrial software", business_model="B2B subscription",
        question="How does Industry 4.0 affect ISO 27001 buying requirements?",
        public_context="Industry 4.0 and ISO 27001 software procurement",
    ))
    result = _validate_model_research_plan(
        parsed, source_ids={"fact_1"}, deck_title="Private Fixture",
        private_numeric_tokens={"28", "$4m"},
    )
    assert result["researchTasks"][0]["question"].startswith("How does Industry 4.0")


def test_model_research_plan_is_durable_and_not_replayed(monkeypatch):
    engine, db, deck = _session_with_deck()
    calls = []
    plan = _research_plan(
        industry="industrial equipment diagnostics", business_model="software subscription",
        question="Which adoption barriers affect maintenance operators?",
        public_context="industrial equipment diagnostics maintenance workflows",
    )
    monkeypatch.setattr(
        "app.services.ai_vc.runtime._stage_call",
        lambda *args, **kwargs: (calls.append(kwargs["stage"]) or plan, {"providerStarts":1, "costKnown":True}),
    )
    try:
        first = ensure_model_research_plan(
            db, deck=deck, operation_id="operation", company={"businessEvidence":[]},
            source_facts=[{"factId":"fact_1", "text":"Private source evidence"}],
        )
        second = ensure_model_research_plan(
            db, deck=deck, operation_id="operation", company={"businessEvidence":[]},
            source_facts=[{"factId":"fact_1", "text":"Private source evidence"}],
        )
        assert calls == ["research_planning"]
        assert first == second
        assert first["status"] == "model_authored"
        assert first["operationId"] == "operation"
        assert first["researchTasks"][0]["question"].startswith("Which adoption barriers")
    finally:
        db.close(); engine.dispose()


def test_recoverable_validation_failure_triggers_bounded_retry(monkeypatch):
    engine, db, deck = _session_with_deck()
    calls = []
    bad_plan = _research_plan(
        industry="industrial equipment diagnostics", business_model="software subscription",
        question="Which adoption barriers affect maintenance operators?",
        public_context="industrial equipment diagnostics maintenance workflows",
    )
    bad_plan["research_tasks"][0]["evidence_ids"] = ["fact_unknown"]
    good_plan = _research_plan(
        industry="industrial equipment diagnostics", business_model="software subscription",
        question="Which adoption barriers affect maintenance operators?",
        public_context="industrial equipment diagnostics maintenance workflows",
    )

    def stage_call(_db, **kwargs):
        calls.append(kwargs["recovery"])
        return bad_plan if not kwargs["recovery"] else good_plan, {"providerStarts": 1, "costKnown": True}

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    try:
        result = ensure_model_research_plan(
            db, deck=deck, operation_id="recoverable", company={"businessEvidence": []},
            source_facts=[{"factId": "fact_1", "text": "Private source evidence"}],
        )
        assert calls == [False, True]
        assert result["status"] == "model_authored"
        assert result["researchTasks"][0]["evidenceIds"] == ["fact_1"]
    finally:
        db.close(); engine.dispose()


def test_non_recoverable_privacy_violation_skips_retry(monkeypatch):
    engine, db, deck = _session_with_deck()
    calls = []
    privacy_plan = _research_plan(
        industry="operations software", business_model="uncertain",
        question="Which public category evidence is credible?",
        public_context="See https://example.com for details",
    )

    def stage_call(_db, **kwargs):
        calls.append(kwargs["recovery"])
        return privacy_plan, {"providerStarts": 1, "costKnown": True}

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    try:
        result = ensure_model_research_plan(
            db, deck=deck, operation_id="privacy", company={"businessEvidence": []},
            source_facts=[{"factId": "fact_1", "text": "Private source evidence"}],
        )
        assert calls == [False]
        assert result["status"] == "unavailable"
        assert result["researchTasks"] == []
    finally:
        db.close(); engine.dispose()


def _narrative():
    slides = [
        {
            "id": f"model-{index}", "index": index,
            "role": role, "objective": f"Explain {role}",
            "headline_direction": role.replace("_", " ").title(),
            "key_message": "A source-grounded investor argument",
            "evidence_ids": ["fact_1"], "calculation_ids": [],
            "visual_primitive": "hero" if index == 1 else "composition",
            "visual_intent": "Use one clear focal point",
        }
        for index, role in enumerate(
            ["thesis", "problem", "product", "business_model", "expansion"], 1
        )
    ]
    return {
        "narrativeGapAnalysis": {"schema_version": "ai-vc-narrative-gap-analysis.v1"},
        "narrativeStrategy": {"tone": "credible and ambitious"},
        "deckArchitecture": {
            "schema_version": "deck-architecture.v1", "core_thesis": "The workflow layer",
            "recommended_slide_count": len(slides), "rationale": "Five investor beliefs need proof.",
            "slides": slides,
        },
    }


def _patch_evidence_pack(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.ai_vc_retrieval.build_ai_vc_evidence_pack",
        lambda **kwargs: {
            "companyEvidence": [], "companyFinancialEvidence": [],
            "externalEvidenceByPurpose": {}, "methodologyRetrievalTrace": {},
            "designKnowledgeTrace": {},
        },
    )


def test_runtime_mounts_graph_and_persists_model_authored_variable_architecture(monkeypatch):
    engine, session, deck = _session_with_deck()
    _patch_evidence_pack(monkeypatch)
    calls = []
    stage_payloads = {}

    def stage_call(_db, **kwargs):
        calls.append(kwargs["stage"])
        stage_payloads[kwargs["stage"]] = kwargs["payload"]
        value = _analysis() if kwargs["stage"] == "analysis" else _narrative()
        return value, {"providerStarts": 1, "costKnown": True}

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    try:
        payload = execute_ai_vc_runtime(
            session, deck=deck, operation_id="operation", source_facts=[{
                "factId": "fact_1", "text": "The product connects the customer workflow.",
                "sourceSlideIds": ["source_1"], "confidence": "high",
            }], source_slides=[{"sourceSlideId": "source_1", "text": "one source page"}],
            external_research={"claims": []},
        )
        assert calls == ["analysis", "narrative"]
        assert payload["analysisStatus"] == "ready"
        assert payload["architectureSource"] == "model_authored"
        assert len(payload["deckArchitecture"]) == 5
        assert len(payload["deckArchitecture"]) != 1
        assert payload["skillExecutionTrace"]["catalogVersion"] == "ai-vc-product-skills.v1"
        assert {
            skill["name"] for skill in stage_payloads["analysis"]["activeSkills"]["skills"]
        } >= {"company-understanding", "investment-memo", "ic-critique"}
        assert {
            skill["name"] for skill in stage_payloads["narrative"]["activeSkills"]["skills"]
        } >= {"narrative-architecture", "visual-storytelling"}
        assert "narrative-architecture" not in {
            skill["name"] for skill in stage_payloads["analysis"]["activeSkills"]["skills"]
        }
        row = session.query(DeckLlmArtifact).filter_by(artifact_key="vc-strategy:operation").one()
        assert row.metrics_json["analysisStatus"] == "ready"
    finally:
        session.close()
        engine.dispose()


def test_known_strategy_failure_consumes_one_recovery_and_stays_truthful(monkeypatch):
    engine, session, deck = _session_with_deck()
    _patch_evidence_pack(monkeypatch)
    calls = []

    def stage_call(_db, **kwargs):
        calls.append((kwargs["stage"], kwargs["recovery"]))
        if kwargs["stage"] == "analysis" and not kwargs["recovery"]:
            raise AIVCStageFailure(
                stage="analysis", code="schema_validation",
                category="schema_validation", recoverable=True,
            )
        return (_analysis() if kwargs["stage"] == "analysis" else _narrative()), {"providerStarts": 1}

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    try:
        payload = execute_ai_vc_runtime(
            session, deck=deck, operation_id="recover", source_facts=[{
                "factId": "fact_1", "text": "A workflow product.", "sourceSlideIds": ["source_1"],
            }], source_slides=[{"sourceSlideId": "source_1", "text": "source"}],
            external_research={"claims": []},
        )
        assert payload["analysisStatus"] == "ready"
        assert calls == [("analysis", False), ("analysis", True), ("narrative", False)]
        assert payload["diagnostics"][0]["category"] == "schema_validation"
        row = session.query(DeckLlmArtifact).filter_by(artifact_key="vc-strategy:recover").one()
        assert row.metrics_json["recoveryUsed"] is True
    finally:
        session.close()
        engine.dispose()


def test_unknown_transport_failure_is_not_replayed_or_masqueraded_as_ai_success(monkeypatch):
    engine, session, deck = _session_with_deck()
    _patch_evidence_pack(monkeypatch)
    calls = []

    def stage_call(_db, **kwargs):
        calls.append((kwargs["stage"], kwargs["recovery"]))
        raise AIVCStageFailure(
            stage=kwargs["stage"], code="provider_transport",
            category="provider_transport", recoverable=False,
            details={
                "provider": "openai", "model": "gpt-test", "attemptNumber": 1,
                "transportStarted": True, "billingOutcomeKnown": False,
                "contextManifestId": "manifest-1", "recoveryAttempted": False,
            },
        )

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    try:
        payload = execute_ai_vc_runtime(
            session, deck=deck, operation_id="fallback", source_facts=[{
                "factId": "fact_1", "text": "A workflow product.", "sourceSlideIds": ["source_1"],
            }], source_slides=[{"sourceSlideId": "source_1", "text": "source"}],
            external_research={"claims": []},
        )
        assert calls == [("analysis", False)]
        assert payload["analysisStatus"] == "source_only_fallback"
        assert payload["architectureSource"] == "final_designer_source_only"
        assert payload["deckArchitecture"] == []
        assert payload["diagnostics"][0] == {
            "stage": "analysis", "code": "provider_transport",
            "category": "provider_transport", "recoverable": False,
            "provider": "openai", "model": "gpt-test", "attemptNumber": 1,
            "transportStarted": True, "billingOutcomeKnown": False,
            "contextManifestId": "manifest-1", "recoveryAttempted": False,
        }
        trace = session.query(DeckLlmArtifact).filter_by(artifact_key="ai-vc-trace:fallback").one()
        assert trace.payload_json["failureDiagnostics"][0]["contextManifestId"] == "manifest-1"
    finally:
        session.close()
        engine.dispose()


def test_prune_unknown_fields_drops_undeclared_envelope_keys_only():
    payload = {
        "researchSynthesis": {
            "schema_version": "ai-vc-research-synthesis.v1",
            "unknown_internal_key": {"drop": "me"},
        },
        "investmentMemo": {"thesis": "A workflow category can be rebuilt.", "extra": True},
        "financialAnalysis": {"verifiedCompanyMetrics": [], "freeForm": {"keep": "this"}},
        "vcInferences": [{"statement": "The wedge can expand", "evidenceRefs": ["fact_1"]}],
        "evidenceGaps": ["Retention"],
        "investmentCommitteeReview": {"publication_blocking": False},
        "undeclared_top_level": {"whole": "node"},
    }
    pruned, dropped = _prune_unknown_fields(payload, AnalysisStage)
    assert dropped == 2
    assert "undeclared_top_level" not in pruned
    assert pruned["investmentMemo"]["extra"] is True
    assert pruned["financialAnalysis"]["freeForm"] == {"keep": "this"}
    assert "unknown_internal_key" not in pruned["researchSynthesis"]
    revalidated = AnalysisStage.model_validate(pruned)
    assert revalidated.vcInferences[0]["evidenceRefs"] == ["fact_1"]


def test_narrative_stage_also_prunes_undeclared_envelope_keys():
    payload = {
        "narrativeGapAnalysis": {"schema_version": "ai-vc-narrative-gap-analysis.v1"},
        "narrativeStrategy": {"tone": "credible and ambitious"},
        "deckArchitecture": {
            "schema_version": "deck-architecture.v1", "core_thesis": "The workflow layer",
            "recommended_slide_count": 1, "rationale": "One belief.",
            "slides": [{
                "id": "model-1", "index": 1, "role": "thesis",
                "objective": "Explain thesis", "key_message": "arg",
                "evidence_ids": ["fact_1"], "calculation_ids": [],
            }],
            "extra_slide_property": "removed",
        },
        "unexpected": "guard",
    }
    pruned, dropped = _prune_unknown_fields(payload, NarrativeStage)
    assert dropped == 2
    revalidated = NarrativeStage.model_validate(pruned)
    assert revalidated.deckArchitecture.slides[0].key_message == "arg"


def test_known_strategy_failure_consumes_one_recovery_and_recovery_uses_full_stage_budget(monkeypatch):
    engine, session, deck = _session_with_deck()
    _patch_evidence_pack(monkeypatch)
    calls = []

    def stage_call(_db, **kwargs):
        calls.append((kwargs["stage"], kwargs["recovery"], kwargs["max_output_tokens"]))
        if kwargs["stage"] == "analysis" and not kwargs["recovery"]:
            raise AIVCStageFailure(
                stage="analysis", code="schema_validation",
                category="schema_validation", recoverable=True,
            )
        return (_analysis() if kwargs["stage"] == "analysis" else _narrative()), {"providerStarts": 1}

    monkeypatch.setattr("app.services.ai_vc.runtime._stage_call", stage_call)
    monkeypatch.setattr("app.core.config.settings.ai_vc_analysis_max_tokens", 12000, raising=False)
    try:
        payload = execute_ai_vc_runtime(
            session, deck=deck, operation_id="recover_budget", source_facts=[{
                "factId": "fact_1", "text": "A workflow product.", "sourceSlideIds": ["source_1"],
            }], source_slides=[{"sourceSlideId": "source_1", "text": "source"}],
            external_research={"claims": []},
        )
        assert payload["analysisStatus"] == "ready"
        analysis_calls = [c for c in calls if c[0] == "analysis"]
        assert analysis_calls == [("analysis", False, 12000), ("analysis", True, 12000)]
    finally:
        session.close()
        engine.dispose()
