import pytest

from app.services.llm.instant_vc_strategy import (
    _fallback_deck_architecture,
    _typed_deck_architecture,
    _validate_evidence_boundaries,
    build_company_intelligence,
    build_research_questions,
    build_evidence_graph,
    build_public_company_descriptor,
)


def _source_facts(count: int = 7) -> list[dict]:
    texts = [
        "Central is a software platform for clinic operations.",
        "Clinic teams manage a fragmented customer workflow.",
        "Manual follow-up creates operational friction.",
        "The product connects booking, treatment and rebooking.",
        "The existing stack includes separate incumbent tools.",
        "The company uses a subscription business model.",
        "The roadmap may expand into workflow intelligence.",
    ]
    return [{"factId": f"fact_{index}", "text": text} for index, text in enumerate(texts[:count], 1)]


def test_fallback_slide_count_follows_supported_investor_arguments_not_input_pages():
    facts = _source_facts()
    architecture = _fallback_deck_architecture(
        source_facts=facts, external_ids={"external_1"},
    )
    assert len(architecture) == 8
    assert len(architecture) != len(facts)
    assert len({slide["role"] for slide in architecture}) == len(architecture)
    allowed = {fact["factId"] for fact in facts} | {"external_1"}
    assert all(set(slide["evidenceRefs"]) <= allowed for slide in architecture)


def test_sparse_evidence_still_creates_core_investor_argument_not_one_poster():
    architecture = _fallback_deck_architecture(
        source_facts=[{"factId": "fact_1", "text": "A workflow software product."}],
        external_ids=set(),
    )
    roles = [slide["role"] for slide in architecture]
    assert {"investment_thesis", "customer_problem", "product_wedge", "investor_case"} <= set(roles)
    assert "workflow_economics" in roles


def test_model_authored_visual_decision_survives_typed_architecture():
    architecture = _typed_deck_architecture({
        "narrativeStrategy": {"thesis": "A new category"},
        "deckArchitecture": [{
            "id": "model-slide",
            "role": "product_wedge",
            "title": "One operating layer",
            "purpose": "Show the integrated workflow",
            "evidenceRefs": ["fact_1"],
            "visualPrimitive": "platform_architecture",
            "visualIntent": "Reveal one connected lifecycle instead of a feature grid.",
        }],
    })
    slide = architecture["slides"][0]
    assert slide["visual_primitive"] == "platform_architecture"
    assert slide["visual_intent"] == "Reveal one connected lifecycle instead of a feature grid."


def test_company_intelligence_excludes_editorial_notes_from_business_evidence():
    company = build_company_intelligence(
        [
            {"factId": "fact_product", "text": "Central connects the client lifecycle."},
            {"factId": "fact_meta", "text": "Use this deck to test Deck V2."},
            {"factId": "fact_plan", "text": "Planned retention automation."},
        ],
        [{"sourceSlideId": "slide_1", "text": "CONCEPT TEST DECK"}],
    )
    assert [item["text"] for item in company["businessEvidence"]] == [
        "Central connects the client lifecycle."
    ]
    assert company["hypotheses"][0]["classification"] == "HYPOTHESIS"
    assert {item["classification"] for item in company["metaEditorial"]} == {"META_EDITORIAL"}


def test_company_intelligence_preserves_financial_status_and_source_lineage():
    company = build_company_intelligence(
        [
            {"factId": "fact_arr", "text": "2025 ARR was USD 1.2 million."},
            {"factId": "fact_target", "text": "Management targets 80% gross margin in 2027."},
            {"factId": "fact_copy", "text": "The product connects the workflow."},
        ],
        [],
    )
    financial = {item["evidenceRefs"][0]: item for item in company["financialEvidence"]}
    assert financial["fact_arr"]["evidenceClass"] == "COMPANY_SOURCE"
    assert financial["fact_arr"]["status"] == "company_supplied_unspecified"
    assert financial["fact_target"]["evidenceClass"] == "MANAGEMENT_PROJECTION"
    assert financial["fact_target"]["status"] == "management_projection"
    assert "fact_copy" not in financial


def test_research_questions_are_conditioned_on_company_evidence():
    questions = build_research_questions({
        "businessEvidence": [{"text": "A workflow product for aesthetics clinics"}]
    })
    assert "aesthetics clinics" in questions[0]
    assert any("incumbent" in question.lower() for question in questions)


def test_industrial_workflow_is_not_misclassified_as_clinical_trial():
    descriptor = build_public_company_descriptor({
        "businessEvidence": [{
            "text": "Industrial maintenance teams use field service workflow software for technicians and work orders."
        }],
    })
    assert descriptor.category == "saas category"
    assert descriptor.product_type == "business workflow software"
    assert descriptor.industry_dimensions == ["manufacturing", "field services"]
    assert "field services" in descriptor.industry_context
    assert "life-sciences" not in descriptor.model_dump_json()


@pytest.mark.parametrize(
    ("source", "expected_industry", "expected_workflow", "expected_geography", "expected_period"),
    [
        ("UK hospitals automate patient scheduling in 2025", "healthcare", "scheduling and dispatch", "United Kingdom", "2025"),
        ("Canadian farms use crop analytics and reporting in 2024", "agriculture", "analytics and reporting", "Canada", "2024"),
        ("Enterprise cybersecurity teams automate threat workflows", "cybersecurity", "operations workflow", "unknown", None),
        ("Retail merchants improve shopper retention", "retail and commerce", "customer retention", "unknown", None),
    ],
)
def test_public_descriptor_generalizes_across_industries(
    source, expected_industry, expected_workflow, expected_geography, expected_period,
):
    descriptor = build_public_company_descriptor({"businessEvidence": [{"text": source}]})
    assert expected_industry in descriptor.industry_dimensions
    assert expected_workflow in descriptor.workflow_dimensions
    assert descriptor.geography == expected_geography
    assert (expected_period in descriptor.reporting_periods) if expected_period else not descriptor.reporting_periods
    assert source not in descriptor.model_dump_json()


@pytest.mark.parametrize(
    "facts",
    [
        [{"factId":"f1", "text":"Pre-revenue prototype for municipal water operators."}],
        [{"factId":"f1", "text":"2024 actual revenue was EUR 2 million."},
         {"factId":"f2", "text":"2026 forecast revenue is EUR 8 million."}],
        [{"factId":f"f{index}", "text":f"Evidence record {index} for a technical platform."} for index in range(80)],
    ],
)
def test_company_intelligence_handles_sparse_financial_and_dense_inputs(facts):
    company = build_company_intelligence(facts, [])
    assert len(company["businessEvidence"]) <= 80
    assert not any(item["evidenceClass"] == "COMPANY_SOURCE" for item in company["financialEvidence"] if "forecast" in item["text"].lower())
    assert not company["metaEditorial"]


def test_evidence_mutations_follow_values_periods_names_and_source_order():
    original = [
        {"factId":"revenue", "text":"2024 actual revenue was USD 3 million."},
        {"factId":"customers", "text":"2025 forecast customers: 60."},
    ]
    mutated = [
        {"factId":"customers", "text":"2027 forecast customers: 90."},
        {"factId":"revenue", "text":"2024 actual revenue was USD 4 million."},
    ]
    first = build_company_intelligence(original, [])
    second = build_company_intelligence(mutated, [])
    assert [item["text"] for item in first["financialEvidence"]] != [item["text"] for item in second["financialEvidence"]]
    assert {item["evidenceRefs"][0] for item in first["financialEvidence"]} == {"revenue", "customers"}
    assert {item["evidenceRefs"][0] for item in second["financialEvidence"]} == {"revenue", "customers"}
    assert all(item["evidenceClass"] == "MANAGEMENT_PROJECTION" for item in second["financialEvidence"] if "forecast" in item["text"].lower())


def test_independent_agriculture_marketplace_fixture_uses_shared_mechanisms():
    company = build_company_intelligence([
        {"factId":"product", "text":"A marketplace connects regional farms with restaurant buyers."},
        {"factId":"status", "text":"The company is pre-revenue and pilots are planned for 2027."},
    ], [])
    descriptor = build_public_company_descriptor(company)
    assert "agriculture" in descriptor.industry_dimensions
    assert descriptor.product_type == "two-sided marketplace"
    assert "regional farms" not in descriptor.model_dump_json()
    assert company["financialEvidence"] == [{
        "text":"The company is pre-revenue and pilots are planned for 2027.",
        "evidenceRefs":["status"], "status":"management_projection",
        "evidenceClass":"MANAGEMENT_PROJECTION",
    }]


def test_vc_inference_cannot_cite_unknown_evidence():
    payload = {
        "vcInferences": [{"statement": "A stronger wedge", "evidenceRefs": ["invented"]}],
        "deckArchitecture": [],
    }
    with pytest.raises(ValueError, match="unknown evidence"):
        _validate_evidence_boundaries(payload, {"fact_1"}, {"external_1"})


def test_evidence_classes_remain_separate():
    payload = _validate_evidence_boundaries(
        {
            "vcInferences": [{"statement": "Position as an orchestration layer", "evidenceRefs": ["fact_1"]}],
            "deckArchitecture": [{"title": "Why now", "evidenceRefs": ["external_1"]}],
            "financialAnalysis": {
                "verifiedCompanyMetrics": [{"label": "ARR", "evidenceRefs": ["fact_1"]}],
                "managementProjections": [],
                "externalBenchmarks": [{"label": "Benchmark", "evidenceRefs": ["external_1"]}],
                "derivedCalculations": [],
                "investorImplications": [{"text": "Potential", "evidenceRefs": ["fact_1", "external_1"]}],
                "narrativeSelections": [{"label": "ARR", "evidenceRefs": ["fact_1"]}],
                "missingFinancialProof": ["Retention"],
            },
        },
        {"fact_1"},
        {"external_1"},
    )
    assert payload["vcInferences"][0]["evidenceClass"] == "VC_INFERENCE"
    assert payload["evidencePolicy"]["companyFacts"] == "COMPANY_SOURCE only"
    assert payload["financialAnalysis"]["verifiedCompanyMetrics"][0]["evidenceClass"] == "COMPANY_SOURCE"
    assert payload["financialAnalysis"]["externalBenchmarks"][0]["evidenceClass"] == "EXTERNAL_RESEARCH"
    assert payload["financialAnalysis"]["investorImplications"][0]["evidenceClass"] == "VC_INFERENCE"


def test_research_impact_cannot_promote_unknown_or_company_evidence():
    base = {
        "vcInferences": [], "deckArchitecture": [],
        "researchSynthesis": {"finding_impacts": [{
            "evidence_ids": ["fact_1"], "disposition": "use",
            "affects": ["thesis"], "explanation": "Changes the thesis.",
            "qualification": "Industry evidence only.",
        }]},
        "financialAnalysis": {
            "verifiedCompanyMetrics": [], "managementProjections": [],
            "externalBenchmarks": [], "derivedCalculations": [],
            "investorImplications": [], "narrativeSelections": [],
            "missingFinancialProof": [],
        },
    }
    with pytest.raises(ValueError, match="non-external"):
        _validate_evidence_boundaries(base, {"fact_1"}, {"external_1"})


def test_external_benchmark_cannot_masquerade_as_company_metric():
    payload = {
        "vcInferences": [],
        "deckArchitecture": [],
        "financialAnalysis": {
            "verifiedCompanyMetrics": [{"label": "Margin", "evidenceRefs": ["external_1"]}],
            "managementProjections": [],
            "externalBenchmarks": [],
            "derivedCalculations": [],
            "investorImplications": [],
            "narrativeSelections": [],
            "missingFinancialProof": [],
        },
    }
    with pytest.raises(ValueError, match="disallowed evidence"):
        _validate_evidence_boundaries(payload, {"fact_1"}, {"external_1"})


def test_evidence_graph_contains_explicit_support_edges():
    graph = build_evidence_graph(
        [{"factId": "fact_1", "text": "Company claim", "sourceSlideIds": ["slide_1"], "confidence": "high"}],
        {"claims": [{"id": "external_1", "text": "Market claim", "category": "external_research",
                     "url": "https://example.com/source", "publisher": "example.com"}]},
    )
    relations = {(edge["source_id"], edge["target_id"], edge["relation"]) for edge in graph["edges"]}
    assert ("fact_1", "slide_1", "SUPPORTED_BY") in relations
    assert ("external_1", "https://example.com/source", "SUPPORTED_BY") in relations
