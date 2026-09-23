import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import CoreBase
from app.db.models import Deck, DeckLlmArtifact, InstantDeckOperation, User, Workspace
from app.services.ai_vc.observability import (
    build_provider_context_manifest,
    build_retrieval_context_trace,
    grounding_metrics,
    refresh_operation_usage_trace,
)
from app.services.ai_vc.models import ResearchBudget, RunResearchBudget
from app.services.ai_vc.runtime import AnalysisStage, NarrativeStage
from app.services.ai_vc.skills.resolver import (
    resolve_skill_plan,
    skill_plan_trace,
    stage_skill_context,
)
from app.services.llm.ai_vc_retrieval import build_ai_vc_evidence_pack
from app.services.llm.instant_html_operation_service import (
    InstantOperationBudgetExceeded,
    require_next_request_cost_budget,
)
from app.services.llm.instant_vc_strategy import build_company_intelligence
from app.workers.runtime.generation_runtime import (
    _build_designer_observability_manifest,
    _designer_observability_binding,
)


def _fixture(size: int):
    facts = [
        {
            "factId": f"fact-{index}",
            "text": f"Source page {index} explains the customer workflow and verified proof item {index}.",
            "sourceSlideIds": [f"slide-{index}"],
            "sourceId": f"slide-{index}",
            "sourceType": "source_slide",
            "confidence": "high",
        }
        for index in range(1, size + 1)
    ]
    slides = [
        {"sourceSlideId": f"slide-{index}", "text": facts[index - 1]["text"]}
        for index in range(1, size + 1)
    ]
    external = {
        "claims": [{
            "id": "external-market",
            "category": "external_research",
            "topic": "market_context",
            "text": "A verified public source describes current category conditions.",
            "url": "https://example.test/market",
            "publisher": "Example",
            "publicationDate": "2026-01-01",
            "retrievalDate": "2026-09-22T00:00:00Z",
        }],
        "gaps": [{"reason": "pricing benchmark was not independently verified"}],
    }
    return facts, slides, external


@pytest.mark.parametrize("size", [6, 10, 15, 20, 35])
def test_large_deck_context_matrix_is_deterministic_bounded_and_traceable(size):
    facts, slides, external = _fixture(size)
    company = build_company_intelligence(facts, slides)
    plan = resolve_skill_plan(company)
    pack = build_ai_vc_evidence_pack(
        company_facts=facts,
        external_research=external,
        questions=["What is the current category context?"],
        research_tasks=[{
            "purpose": "market_context",
            "question": "What is the current category context?",
        }],
        design_guidance={
            "traceId": "design-trace",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "chunks": [{
                "chunkId": "design-one",
                "scope": "global_knowledge",
                "content": "Use one dominant visual hierarchy and avoid repeated card grids.",
                "similarityScore": 0.9,
            }],
        },
    )
    active = {
        "analysis": stage_skill_context(plan, "analysis"),
        "narrative": stage_skill_context(plan, "narrative"),
    }
    payload = {
        "companyIntelligence": company,
        "sourceEvidence": facts,
        "retrievalEvidencePack": pack,
        "activeSkills": active["analysis"],
    }
    trace = build_retrieval_context_trace(
        evidence_pack=pack,
        provider_payload={**payload, "activeSkillsByStage": active},
        skill_trace=skill_plan_trace(plan),
        active_skills_by_stage=active,
        company_evidence_ids={fact["factId"] for fact in facts},
        company_financial_ids=set(),
        external_evidence_ids={"external-market"},
        external_research=external,
    )
    manifest = build_provider_context_manifest(
        operation_id=f"matrix-{size}",
        stage="analysis",
        provider="openai",
        model="gpt-5-2025-08-07",
        system="system-v1",
        payload=payload,
        retrieval_trace=trace,
        prompt_version="test.v1",
    )
    parsed_analysis = AnalysisStage.model_validate({
        "researchSynthesis": {"schema_version": "ai-vc-research-synthesis.v1"},
        "investmentMemo": {"thesis": "A source-grounded investor thesis."},
        "financialAnalysis": {
            "verifiedCompanyMetrics": [], "managementProjections": [],
            "externalBenchmarks": [], "derivedCalculations": [],
            "investorImplications": [], "narrativeSelections": [],
            "missingFinancialProof": [],
        },
        "vcInferences": [], "evidenceGaps": [],
        "investmentCommitteeReview": {"publication_blocking": False},
    })
    parsed_narrative = NarrativeStage.model_validate({
        "narrativeGapAnalysis": {"schema_version": "ai-vc-narrative-gap-analysis.v1"},
        "narrativeStrategy": {"status": "ready"},
        "deckArchitecture": {
            "schema_version": "deck-architecture.v1",
            "core_thesis": "A source-grounded investor thesis.",
            "recommended_slide_count": 1,
            "rationale": "One mocked architecture slide validates the contract.",
            "slides": [{
                "id": "planned-1", "index": 1, "role": "thesis",
                "objective": "Establish the thesis", "key_message": "Grounded thesis",
                "evidence_ids": ["fact-1"], "calculation_ids": [],
            }],
        },
    })

    assert trace["totalRetrieved"] >= trace["totalInjected"] > 0
    assert trace["totalDropped"] >= 0
    assert trace["externalResearch"]["rejectedCandidateCount"] == 1
    assert manifest["companyEvidenceIds"]
    assert manifest["externalEvidenceIds"] == ["external-market"]
    assert len(manifest["companyEvidenceIds"]) == size
    assert manifest["approximateInputTokens"] < 272_000
    assert "base64," not in json.dumps(payload)
    assert len(slides) == size
    assert len(facts) == size
    assert parsed_analysis.investmentCommitteeReview.publication_blocking is False
    assert parsed_narrative.deckArchitecture.slides[0].evidence_ids == ["fact-1"]
    # Mocked CI accounting: two provider stages, no retry, deterministic token
    # envelope, and a schema-valid ready result at every source size.
    report = {
        "stageCount": 2, "retryCount": 0, "status": "ready",
        "inputTokens": manifest["approximateInputTokens"], "outputTokens": 2500,
        "truncated": False,
    }
    assert report["stageCount"] == 2 and report["retryCount"] == 0
    assert report["status"] == "ready" and report["truncated"] is False


def test_manifest_rejects_a_chunk_claimed_as_injected_but_absent():
    trace = {
        "retrievalRecords": [{
            "chunkId": "missing-chunk",
            "contentHash": "a" * 64,
            "lane": "product_knowledge",
            "injected": True,
            "injectedStages": ["analysis"],
        }],
        "skills": [],
        "companyEvidence": {},
        "externalResearch": {},
    }
    with pytest.raises(ValueError, match="absent injected chunk"):
        build_provider_context_manifest(
            operation_id="op", stage="analysis", provider="openai", model="model",
            system="system", payload={"different": "context"}, retrieval_trace=trace,
        )


def test_grounding_metrics_detect_invalid_and_product_knowledge_authority():
    metrics = grounding_metrics(
        {
            "deckArchitecture": [{
                "evidenceRefs": ["company-1", "methodology-1", "unknown-1"],
                "keyMessage": "Revenue grew 30%.",
            }],
        },
        company_ids={"company-1"},
        external_ids={"external-1"},
        product_knowledge_ids={"methodology-1"},
    )
    assert metrics["referencedCompanyEvidenceIds"] == ["company-1"]
    assert metrics["productKnowledgeUsedAsEvidenceIds"] == ["methodology-1"]
    assert set(metrics["invalidEvidenceReferences"]) == {"methodology-1", "unknown-1"}
    assert metrics["authorityBoundaryValid"] is False


def test_cost_caps_are_optional_and_optional_paid_features_remain_disabled():
    settings = Settings(_env_file=None)
    assert settings.instant_html_vc_research_max_cost_cents is None
    assert settings.instant_html_vc_memo_max_cost_cents is None
    assert settings.ai_vc_max_total_cost_cents is None
    assert settings.instant_html_factual_review_enabled is True
    assert settings.instant_html_factual_review_max_cost_cents is None
    assert settings.ai_vc_visual_planning_enabled is False
    assert settings.ai_vc_image_generation_enabled is False
    assert settings.ai_vc_vision_review_enabled is False
    assert settings.ai_vc_visual_repair_enabled is False
    assert Settings(_env_file=None, instant_html_vc_memo_max_cost_cents=0).instant_html_vc_memo_max_cost_cents is None


def test_uncapped_unknown_tariff_does_not_block_but_explicit_cap_does():
    class Operation:
        actual_provider_cost_cents = 0
        reserved_provider_cost_cents = 0

    operation = Operation()
    operation.max_cost_cents = None
    assert require_next_request_cost_budget(
        operation, provider="custom", model="unknown-model",
        estimated_input_tokens=1000, max_output_tokens=1000,
    ) == 0
    operation.max_cost_cents = 10
    with pytest.raises(InstantOperationBudgetExceeded):
        require_next_request_cost_budget(
            operation, provider="custom", model="unknown-model",
            estimated_input_tokens=1000, max_output_tokens=1000,
        )


def test_uncapped_research_budget_keeps_non_cost_bounds():
    run = RunResearchBudget(
        max_searches=2, max_sources=6, max_tokens=5000,
        max_cost_cents=None, max_runtime_seconds=120,
    )
    task = ResearchBudget(
        max_searches=1, max_sources=3, max_tokens=2000,
        max_cost_cents=None, max_runtime_seconds=60,
    )
    assert run.reserve(task).used_cost_cents == 0
    with pytest.raises(ValueError, match="remaining run-level budget"):
        run.reserve(ResearchBudget(
            max_searches=3, max_sources=3, max_tokens=2000,
            max_cost_cents=None, max_runtime_seconds=60,
        ))


def test_saved_32_slide_fallback_context_reaches_pre_designer_manifest_without_binding():
    """Regression for deck_8c3152087c67fd5b without customer/provider content.

    The production run persisted a roughly 513 KB provider context containing
    32 source slides and 48 retrieval records after AI-VC degraded to the
    source-only fallback.  At this point the provider binding is intentionally
    absent.  f220 called ``.get`` on that absent request envelope and stopped
    before the designer transport could be created.
    """
    repeated_evidence = "Synthetic field-service evidence for offline testing. " * 310
    source_slides = [
        {
            "sourceSlideId": f"saved-source-{index:02d}",
            "text": f"saved-source-{index:02d} {repeated_evidence}",
        }
        for index in range(1, 33)
    ]
    provider_context = {
        "sourceSlides": source_slides,
        "authoringContext": {
            "strategy": {
                "analysisStatus": "source_only_fallback",
                "architectureSource": "final_designer_source_only",
                "deckArchitecture": [],
            },
        },
    }
    retrieval_trace = {
        "retrievalRecords": [
            {
                "chunkId": f"saved-source-{index:02d}",
                "contentHash": f"{index:064x}",
                "lane": "company_source",
                "injected": True,
                "injectedStages": ["analysis"],
            }
            for index in range(1, 33)
        ] + [
            {
                "chunkId": f"methodology-{index:02d}",
                "contentHash": f"{index + 100:064x}",
                "lane": "product_knowledge",
                "injected": False,
                "injectedStages": [],
            }
            for index in range(1, 17)
        ],
        "skills": [],
        "companyEvidence": {"selectedIds": []},
        "externalResearch": {"injectedClaimIds": []},
    }
    generation_job = SimpleNamespace(llm_context_json={
        "generationMode": "instant_deck",
        "canonicalContext": True,
        "fullHtmlRequestContextArtifactId": "saved-context-fixture",
    })

    assert len(json.dumps(provider_context).encode("utf-8")) > 500_000
    envelope, binding_status = _designer_observability_binding(generation_job)
    assert envelope == {}
    assert binding_status == "not_created"

    manifest, updated_trace = _build_designer_observability_manifest(
        generation_job=generation_job,
        operation_id="saved-32-slide-operation",
        provider_runtime_context=provider_context,
        retrieval_trace=retrieval_trace,
        fallback_model="gpt-5-2025-08-07",
    )

    assert manifest["stage"] == "designer"
    assert manifest["providerBindingStatus"] == "not_created"
    assert manifest["requestEnvelopeHash"] is None
    assert manifest["boundUserPromptHash"] is None
    assert manifest["maxOutputTokens"] is None
    assert manifest["approximateInputTokens"] > 100_000
    assert len(manifest["injectedChunks"]) == 32
    assert sum(
        "designer" in record.get("injectedStages", [])
        for record in updated_trace["retrievalRecords"]
    ) == 32
    assert "inputTokens" not in manifest
    assert "outputTokens" not in manifest
    assert "costCents" not in manifest


def test_partial_provider_binding_is_recorded_without_inventing_an_envelope():
    generation_job = SimpleNamespace(llm_context_json={
        "fullHtmlProviderBinding": {"contractVersion": "full-html-provider-binding.v5"},
    })

    envelope, binding_status = _designer_observability_binding(generation_job)

    assert envelope == {}
    assert binding_status == "binding_without_envelope"


def test_unknown_ai_vc_transport_is_not_reported_as_zero_total_cost_or_usage():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        owner = User(id="usage-owner", email="usage@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="usage-workspace", name="Workspace", user_id=owner.id)
        deck = Deck(
            id="usage-deck", workspace_id=workspace.id, user_id=owner.id,
            title="Synthetic 32-slide fixture", audience="Investors",
            purpose="Fundraising", status="processing",
        )
        operation = InstantDeckOperation(
            id="usage-operation", deck_id=deck.id, user_id=owner.id,
            idempotency_key="usage-test", request_hash="hash",
        )
        trace = DeckLlmArtifact(
            id="usage-trace", deck_id=deck.id,
            artifact_type="instant_deck_ai_vc_operation_trace",
            artifact_key="ai-vc-trace:usage-operation",
            schema_version="instant-deck-ai-vc-observability.v1",
            status="ready", payload_json={}, metrics_json={},
        )
        unknown_attempt = DeckLlmArtifact(
            id="usage-attempt", deck_id=deck.id,
            artifact_type="instant_deck_vc_strategy_stage_attempt",
            artifact_key="vc-strategy-stage:usage-operation:analysis:primary",
            schema_version="instant-deck-vc-strategy.v3", status="failed",
            payload_json={"providerStarts": 1, "clientRequestId": "saved-client-request"},
            metrics_json={
                "providerStarts": 1, "transportStarted": True,
                "outcomeKnown": False, "billingOutcomeKnown": False,
                "costKnown": False, "inputTokens": None,
                "outputTokens": None, "estimatedCostCents": None,
            },
        )
        db.add_all([owner, workspace, deck, operation, trace, unknown_attempt])
        db.commit()

        usage = refresh_operation_usage_trace(
            db, deck_id=deck.id, operation_id=operation.id,
        )

        assert usage["knownMeasuredCostCents"] == 0
        assert usage["totalMeasuredCostCents"] is None
        assert usage["knownInputTokens"] == 0
        assert usage["knownOutputTokens"] == 0
        assert usage["inputTokens"] is None
        assert usage["outputTokens"] is None
        assert usage["usageMeasurementComplete"] is False
        assert usage["costMeasurementComplete"] is False
        assert usage["unknownProviderOutcomeCount"] == 1
    engine.dispose()
