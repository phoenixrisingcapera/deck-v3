import pytest

from app.services.rendering.html_deck_compiler import (
    HtmlDeckCompileError,
    validate_semantic_numeric_claim,
)
from app.services.visual_intelligence.charts.renderer import render_chart_svg
from app.services.visual_intelligence.decision_engine import chart_for_slide, normalize_evidence_points


def test_customer_period_values_preserve_canonical_associations():
    evidence = ["Customers: 2023 = 16; 2024 = 28; 2025 = 48."]
    validate_semantic_numeric_claim("2023 customers: 16", evidence)
    validate_semantic_numeric_claim("48 customers in 2025", evidence)
    with pytest.raises(HtmlDeckCompileError, match="period/value association"):
        validate_semantic_numeric_claim("48 customers in 2023", evidence)


def test_funnel_stage_values_cannot_be_relabelled():
    evidence = ["Sales funnel: 400 leads, 160 qualified, 80 demos, 40 pilots, 23 wins."]
    for claim in ("400 leads", "160 qualified", "80 demos", "40 pilots", "23 wins"):
        validate_semantic_numeric_claim(claim, evidence)
    with pytest.raises(HtmlDeckCompileError, match="category/value association"):
        validate_semantic_numeric_claim("40 wins", evidence)


def test_revenue_arr_and_actual_forecast_meanings_remain_distinct():
    evidence = [
        "2024 revenue was USD 1.2 million (actual).",
        "2024 ARR was USD 1.8 million (actual).",
        "2025 revenue forecast is USD 2.4 million.",
    ]
    validate_semantic_numeric_claim("2024 revenue: USD 1.2 million actual", evidence)
    validate_semantic_numeric_claim("2025 revenue forecast: USD 2.4 million", evidence)
    with pytest.raises(HtmlDeckCompileError):
        validate_semantic_numeric_claim("2024 ARR: USD 1.2 million", evidence)
    with pytest.raises(HtmlDeckCompileError):
        validate_semantic_numeric_claim("2025 revenue achieved: USD 2.4 million", evidence)


def test_rendered_chart_uses_exact_bound_values_and_shows_forecast_boundary():
    points = normalize_evidence_points([{
        "metric": "Customers", "unit": "customers", "seriesLabel": "Customers",
        "points": [
            {"category": "2023", "period": "2023", "value": 16, "status": "actual", "evidenceRefs": ["fact_2023"]},
            {"category": "2024", "period": "2024", "value": 28, "status": "actual", "evidenceRefs": ["fact_2024"]},
            {"category": "2025", "period": "2025", "value": 48, "status": "forecast", "evidenceRefs": ["fact_2025"]},
        ],
    }], [])
    spec, diagnostics = chart_for_slide(
        slide_id="traction", title="Customer trajectory", primitive="data_chart",
        evidence_ids=["fact_2023", "fact_2024", "fact_2025"], calculation_ids=[],
        points=points, brand={"accent": "#00AEEF"},
    )
    assert diagnostics == []
    assert spec is not None
    assert spec.series[0].values == [16.0, 28.0, 48.0]
    assert [point.status for point in spec.series[0].point_bindings] == ["actual", "actual", "forecast"]
    svg = render_chart_svg(spec)
    assert ">16<" in svg and ">28<" in svg and ">48<" in svg
    assert ">Forecast<" in svg
    assert 'stroke-dasharray="12 9"' in svg
