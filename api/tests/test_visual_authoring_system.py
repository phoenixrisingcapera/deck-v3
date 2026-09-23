from xml.etree import ElementTree as ET

import pytest

from app.services.rendering.html_deck_compiler import _validate_visual_plan_binding
from app.services.visual_intelligence.director import build_visual_intelligence
from app.services.visual_intelligence.knowledge import load_visual_knowledge
from app.services.ai_vc.authoring_context import build_ai_vc_contexts


def _strategy(slides: list[dict]) -> dict:
    return {"narrativeStrategy": {"thesis": "Evidence becomes an investor argument."}, "deckArchitecture": slides}


def _slide(**overrides) -> dict:
    return {
        "id": "slide-1", "role": "financial", "title": "Revenue trajectory",
        "purpose": "Show evidence of compounding revenue", "keyMessage": "Growth continues",
        "visualPrimitive": "data_chart", "evidenceRefs": ["actual-2024", "forecast-2025"],
        **overrides,
    }


def test_a_actual_forecast_time_series_is_executable_and_provenanced():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide()]), brand={"primary": "#123456"}, approved_assets=[],
        metric_sets=[{"metric": "ARR", "unit": "USDm", "points": [
            {"period": "2024", "value": 2.4, "status": "actual", "evidenceRefs": ["actual-2024"]},
            {"period": "2025", "value": 4.8, "status": "forecast", "evidenceRefs": ["forecast-2025"]},
        ]}],
    )
    chart = bundle.chart_specs[0]
    assert chart.chart_type == "line"
    assert chart.actual_forecast.transition_after_category == "2024"
    assert chart.series[0].point_bindings[1].status == "forecast"
    assert chart.series[0].point_bindings[1].evidence_ids == ["forecast-2025"]
    assert bundle.slide_visual_briefs[0].required_asset_ids == ["rendered-chart-chart-slide-1"]
    assert "stroke-dasharray" in __import__("base64").b64decode(bundle.rendered_assets[0].data_url.split(",", 1)[1]).decode()


def test_b_historical_income_statement_prefers_inspection_table_not_chart():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide(evidenceShape="historical_income_statement")]),
        brand={}, approved_assets=[], metrics=[{
            "metric": "Revenue", "period": "2024", "value": 10, "unit": "USDm",
            "status": "actual", "evidenceRefs": ["actual-2024"],
        }],
    )
    brief = bundle.slide_visual_briefs[0]
    assert bundle.chart_specs == []
    assert brief.composition_contract.layout_family == "financial_table"
    assert brief.composition_contract.table_policy == "inspection_first"
    assert brief.executable_visual_required is False


def test_c_required_chart_substituted_with_prose_is_an_explicit_advisory_failure():
    slide = ET.fromstring(
        '<section data-plan-slide-id="slide-1" data-visual-primitive="data_chart" '
        'data-evidence-ids="actual-2024 forecast-2025"><h1>Growth</h1><p>Editorial prose only</p></section>'
    )
    brief = _slide()
    brief.update({
        "slide_id": "slide-1", "visual_primitive": "data_chart",
        "evidence_ids": ["actual-2024", "forecast-2025"], "calculation_ids": [],
        "required_asset_ids": ["rendered-chart-chart-slide-1"], "executable_visual_required": True,
        "copy_budget_words": 55,
    })
    warnings = _validate_visual_plan_binding([slide], [brief], advisory_review=True)
    assert warnings[0]["code"] == "required_executable_visual_missing"
    assert warnings[0]["blocking"] is False
    with pytest.raises(Exception, match="execute required visual assets"):
        _validate_visual_plan_binding([slide], [brief], advisory_review=False)


def test_d_scenario_comparison_preserves_scenario_and_source_bindings():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide(evidenceRefs=["base", "upside"])]), brand={}, approved_assets=[],
        metric_sets=[{"metric": "ARR", "unit": "USDm", "series": [
            {"scenario": "Base", "points": [{"period": "2026", "value": 5, "status": "scenario", "evidenceRefs": ["base"]}]},
            {"scenario": "Upside", "points": [{"period": "2026", "value": 8, "status": "scenario", "evidenceRefs": ["upside"]}]},
        ]}],
    )
    assert {series.label for series in bundle.chart_specs[0].series} == {"Base", "Upside"}
    assert set(bundle.chart_specs[0].evidence_ids) == {"base", "upside"}


def test_e_arr_reconciliation_produces_a_waterfall_contract():
    refs = ["opening", "churn", "contraction", "expansion", "new", "closing"]
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide(visualPrimitive="financial_bridge", evidenceRefs=refs)]),
        brand={}, approved_assets=[], metric_sets=[{
            "metric": "ARR bridge", "unit": "USDm", "points": [
                {"category": "Opening", "value": 10, "status": "actual", "evidenceRefs": ["opening"]},
                {"category": "Churn", "value": -1, "status": "actual", "evidenceRefs": ["churn"]},
                {"category": "Contraction", "value": -0.5, "status": "actual", "evidenceRefs": ["contraction"]},
                {"category": "Expansion", "value": 2, "status": "actual", "evidenceRefs": ["expansion"]},
                {"category": "New", "value": 3, "status": "actual", "evidenceRefs": ["new"]},
                {"category": "Closing", "value": 13.5, "status": "actual", "evidenceRefs": ["closing"]},
            ],
        }],
    )
    assert bundle.chart_specs[0].chart_type == "waterfall"
    assert bundle.chart_specs[0].series[0].values == [10.0, -1.0, -0.5, 2.0, 3.0, 13.5]


def test_f_cumulative_sales_stages_produce_funnel_but_non_cumulative_values_do_not():
    slide = _slide(visualPrimitive="funnel", evidenceRefs=["lead", "qualified", "pilot", "won"])
    points = [
        {"stage": "Lead", "value": 100, "shape": "funnel", "unit": "accounts", "evidenceRefs": ["lead"]},
        {"stage": "Qualified", "value": 55, "shape": "funnel", "unit": "accounts", "evidenceRefs": ["qualified"]},
        {"stage": "Pilot", "value": 20, "shape": "funnel", "unit": "accounts", "evidenceRefs": ["pilot"]},
        {"stage": "Won", "value": 8, "shape": "funnel", "unit": "accounts", "evidenceRefs": ["won"]},
    ]
    valid = build_visual_intelligence(
        vc_strategy=_strategy([slide]), brand={}, approved_assets=[],
        metric_sets=[{"metric": "Sales stages", "unit": "accounts", "points": points}],
    )
    assert valid.chart_specs[0].chart_type == "funnel"
    invalid_points = [dict(item) for item in points]
    invalid_points[2]["value"] = 80
    invalid = build_visual_intelligence(
        vc_strategy=_strategy([slide]), brand={}, approved_assets=[],
        metric_sets=[{"metric": "Sales stages", "unit": "accounts", "points": invalid_points}],
    )
    assert invalid.chart_specs == []
    assert any(item["code"] == "funnel_not_cumulative" for item in invalid.compliance_diagnostics)


def test_e_nonfinancial_workflow_gets_an_executable_diagram():
    slide = _slide(
        role="workflow", visualPrimitive="workflow", evidenceRefs=["workflow-source"],
        diagramNodes=[
            {"id": "lead", "label": "Lead", "evidenceIds": ["workflow-source"]},
            {"id": "booking", "label": "Booking", "evidenceIds": ["workflow-source"]},
        ],
    )
    bundle = build_visual_intelligence(vc_strategy=_strategy([slide]), brand={}, approved_assets=[])
    assert bundle.diagram_specs[0].diagram_type == "workflow"
    assert bundle.slide_visual_briefs[0].required_asset_ids == ["rendered-diagram-diagram-slide-1"]


def test_f_product_visual_reuses_only_an_approved_source_asset():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide(role="product", visualPrimitive="product_ui", sourceAssetId="ui-1")]),
        brand={}, approved_assets=[{"assetId": "ui-1"}],
    )
    assert bundle.asset_plan.images[0].source_asset_id == "ui-1"
    assert bundle.asset_plan.images[0].factual_role == "source_evidence"


def test_g_missing_structured_evidence_never_invents_chart_values():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide()]), brand={}, approved_assets=[], metrics=[], metric_sets=[],
    )
    assert bundle.chart_specs == []
    assert bundle.rendered_assets == []
    assert bundle.slide_visual_briefs[0].visual_primitive == "composition"
    assert bundle.compliance_diagnostics[0]["code"] == "required_executable_chart_missing"


def test_h_brand_palette_changes_renderer_output_without_changing_values():
    first = build_visual_intelligence(
        vc_strategy=_strategy([_slide()]), brand={"primary": "#112233"}, approved_assets=[],
        metrics=[{"metric": "ARR", "period": "2024", "value": 2, "unit": "USDm", "status": "actual", "evidenceRefs": ["actual-2024"]}],
    )
    second = build_visual_intelligence(
        vc_strategy=_strategy([_slide()]), brand={"primary": "#AA2244"}, approved_assets=[],
        metrics=[{"metric": "ARR", "period": "2024", "value": 2, "unit": "USDm", "status": "actual", "evidenceRefs": ["actual-2024"]}],
    )
    assert first.chart_specs[0].series[0].values == second.chart_specs[0].series[0].values == [2.0]
    assert first.rendered_assets[0].content_sha256 != second.rendered_assets[0].content_sha256
    _, authoring = build_ai_vc_contexts({
        "sourceSlides": [], "sourceFacts": [], "vcStrategy": _strategy([_slide()]),
        "visualIntelligence": first.model_dump(mode="json"), "brand": {"primary": "#112233"},
    })
    assert authoring["visualIntelligence"]["brand_system"]["palette"] == ["#112233"]


def test_j_background_system_is_cover_distinct_and_interior_harmonized():
    slides = [
        _slide(id="slide-1", role="hero", visualPrimitive="hero"),
        _slide(id="slide-2", role="traction", visualPrimitive="big_number"),
        _slide(id="slide-3", role="market", visualPrimitive="competitive_matrix"),
    ]
    bundle = build_visual_intelligence(
        vc_strategy=_strategy(slides), brand={"primary": "#112233", "emphasisMode": "dark"}, approved_assets=[],
    )
    system = bundle.visual_direction.background_system
    cover = bundle.slide_visual_briefs[0].background
    interior = bundle.slide_visual_briefs[1].background
    assert system.schema_version == "deck-background-system.v1"
    assert cover.distinct is True
    assert cover.canvas != system.interior.canvas
    assert interior.distinct is False
    assert interior.canvas == system.interior.canvas
    assert bundle.slide_visual_briefs[2].background.canvas == interior.canvas
    assert interior.harmonization == "shared_interior"
    assert system.css_tokens["--da-canvas"] == interior.canvas
    assert all(value in {"#0F172A", "#FFFFFF", interior.canvas, interior.surface, interior.accent} or value.startswith("#") for value in [cover.ink, interior.ink, cover.accent, interior.surface])


def test_k_background_tokens_compile_into_scoped_slide_styles():
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION, compile_html_deck
    slide_id = "slide-1"
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([_slide(id=slide_id, visualPrimitive="hero")]),
        brand={"primary": "#123456"}, approved_assets=[],
    )
    background = bundle.slide_visual_briefs[0].background
    html = (
        '<html><body><main><section class="deck-section" data-plan-slide-id="'
        + slide_id + '" data-visual-primitive="hero" data-evidence-ids="actual-2024 forecast-2025" '
        'data-source-slide-ids="source_1"><h1>Overview</h1>'
        '<p data-source-refs="fact_1">Evidence-backed overview.</p></section></main></body></html>'
    )
    compiled = compile_html_deck(
        html,
        selected_source_slide_ids=["source_1"],
        grounded_fact_ids=["fact_1"],
        grounded_fact_sources={"fact_1": ["source_1"]},
        visual_slide_briefs=[item.model_dump(mode="json") for item in bundle.slide_visual_briefs],
        compiler_version=COMPILER_VERSION,
    )
    assert background.canvas in compiled.sanitized_html
    assert f"--da-canvas:{background.canvas}" in compiled.sanitized_html
    assert f"--da-ink:{background.ink}" in compiled.sanitized_html
    assert 'data-da-background="' in compiled.sanitized_html
    assert compiled.manifest["compilerVersion"] == COMPILER_VERSION


def test_l_fallback_deck_background_applies_by_ordinal_without_briefs():
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION, compile_html_deck
    bundle = build_visual_intelligence(
        vc_strategy=_strategy([]),
        brand={"primary": "#123456"}, approved_assets=[],
    )
    assert bundle.slide_visual_briefs == []
    system = bundle.visual_direction.background_system
    html = (
        '<html><body><main>'
        '<section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1>'
        '<p data-source-refs="fact_1">Evidence-backed overview.</p></section>'
        '<section class="deck-section" data-source-slide-ids="source_2"><h1>Evidence</h1>'
        '<p data-source-refs="fact_1">Second slide body.</p></section>'
        '</main></body></html>'
    )
    compiled = compile_html_deck(
        html,
        selected_source_slide_ids=["source_1", "source_2"],
        grounded_fact_ids=["fact_1"],
        grounded_fact_sources={"fact_1": ["source_1", "source_2"]},
        visual_background_system=system.model_dump(mode="json"),
        compiler_version=COMPILER_VERSION,
    )
    assert system.cover.canvas in compiled.sanitized_html
    assert system.interior.canvas in compiled.sanitized_html
    assert 'data-da-background="full-canvas editorial cover field"' in compiled.sanitized_html
    assert 'data-da-background="harmonized interior canvas"' in compiled.sanitized_html
    assert compiled.safe_slide_documents[0].count(system.cover.canvas) >= 1
    assert compiled.safe_slide_documents[1].count(system.interior.canvas) >= 1
    assert system.cover.canvas not in compiled.safe_slide_documents[1]


def test_i_rhythm_and_knowledge_are_versioned_and_sector_neutral():
    slides = [_slide(id=f"slide-{index}", role="traction", visualPrimitive="big_number") for index in range(1, 4)]
    bundle = build_visual_intelligence(vc_strategy=_strategy(slides), brand={}, approved_assets=[])
    knowledge = load_visual_knowledge()
    assert knowledge["classification"] == "PRODUCT_KNOWLEDGE"
    assert knowledge["factualAuthority"] == "none"
    assert len(knowledge["modules"]) == 14
    assert bundle.knowledge_version == knowledge["corpusVersion"]
    assert bundle.visual_rhythm.repeated_layout_warnings
