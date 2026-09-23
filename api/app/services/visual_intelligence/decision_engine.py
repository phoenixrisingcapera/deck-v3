from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable

from app.services.visual_intelligence.models import (
    ActualForecastContract,
    ChartPointBinding,
    ChartSeries,
    ChartSpec,
    CompositionContract,
)


_STATUSES = {"actual", "forecast", "projected", "scenario", "target", "unknown"}
_FORECAST = {"forecast", "projected", "scenario", "target"}
_CHART_PRIMITIVES = {"data_chart", "market_size", "financial_bridge", "funnel", "chart"}


@dataclass(frozen=True)
class EvidencePoint:
    metric: str
    category: str
    value: float
    unit: str
    period: str
    status: str
    evidence_ids: tuple[str, ...]
    calculation_id: str | None = None
    series: str = "Value"
    shape: str = ""


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _first(record: dict[str, Any], *keys: str) -> object:
    return next((record[key] for key in keys if record.get(key) not in (None, "")), None)


def _points_from_record(record: dict[str, Any], inherited: dict[str, Any] | None = None) -> list[EvidencePoint]:
    inherited = inherited or {}
    raw_nested = record.get("points") or record.get("values")
    nested = _list(raw_nested)
    if nested:
        common = {**inherited, **{key: value for key, value in record.items() if key not in {"points", "values", "series"}}}
        return [point for item in nested if isinstance(item, dict) for point in _points_from_record(item, common)]
    series = _list(record.get("series"))
    if series:
        common = {**inherited, **{key: value for key, value in record.items() if key != "series"}}
        return [point for item in series if isinstance(item, dict) for point in _points_from_record(item, common)]
    merged = {**inherited, **record}
    raw_value = _first(merged, "value", "amount", "numericValue", "numeric_value")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return []
    if not isfinite(value):
        return []
    evidence = _first(merged, "evidenceIds", "evidenceRefs", "evidence_ids")
    evidence_ids = tuple(str(item) for item in _list(evidence) if str(item).strip())
    calculation_id = _first(merged, "calculationId", "calculation_id")
    # A plotted mark without source evidence or a durable calculation is prohibited.
    if not evidence_ids and not calculation_id:
        return []
    status = str(_first(merged, "status", "actualProjected", "actual_projected") or "unknown").lower()
    status = status if status in _STATUSES else "unknown"
    category = str(_first(merged, "category", "period", "date", "stage", "label") or "").strip()
    period = str(_first(merged, "period", "date", "category") or category or "unspecified").strip()
    metric = str(_first(merged, "metric", "metricName", "metric_name", "name", "title") or "Metric").strip()
    unit = str(_first(merged, "unit", "currency", "format") or "number").strip()
    series_label = str(_first(merged, "seriesLabel", "series_label", "scenario", "cohort") or "Value").strip()
    return [EvidencePoint(
        metric=metric, category=category or period, value=value, unit=unit, period=period,
        status=status, evidence_ids=evidence_ids,
        calculation_id=str(calculation_id) if calculation_id else None,
        series=series_label, shape=str(merged.get("shape") or merged.get("structure") or "").lower(),
    )]


def normalize_evidence_points(metrics: Iterable[dict[str, Any]], metric_sets: Iterable[dict[str, Any]]) -> list[EvidencePoint]:
    points: list[EvidencePoint] = []
    for record in [*metrics, *metric_sets]:
        if isinstance(record, dict):
            points.extend(_points_from_record(record))
    return points


def brand_palette(brand: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for value in brand.values():
        if isinstance(value, str) and value.startswith("#") and len(value) in {4, 7}:
            candidates.append(value)
        elif isinstance(value, list):
            candidates.extend(str(item) for item in value if isinstance(item, str) and item.startswith("#"))
        elif isinstance(value, dict):
            candidates.extend(str(item) for item in value.values() if isinstance(item, str) and item.startswith("#"))
    return list(dict.fromkeys(candidates))[:8]


def _chart_type(points: list[EvidencePoint], primitive: str) -> str:
    shapes = {point.shape for point in points}
    categories = [point.category.lower() for point in points]
    bridge_terms = {"opening", "churn", "contraction", "expansion", "new", "closing"}
    if primitive == "financial_bridge" and len(bridge_terms.intersection(" ".join(categories).split())) >= 2:
        return "waterfall"
    if "funnel" in shapes or primitive == "funnel":
        return "funnel"
    if len({point.period for point in points}) >= 2:
        return "line"
    return "bar"


def chart_for_slide(
    *, slide_id: str, title: str, primitive: str, evidence_ids: list[str], calculation_ids: list[str],
    points: list[EvidencePoint], brand: dict[str, Any],
) -> tuple[ChartSpec | None, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    if primitive not in _CHART_PRIMITIVES:
        return None, diagnostics
    allowed = set(evidence_ids) | set(calculation_ids)
    selected = [
        point for point in points
        if (not allowed or allowed.intersection(point.evidence_ids) or (point.calculation_id and point.calculation_id in allowed))
    ]
    if not selected:
        diagnostics.append({
            "code": "required_executable_chart_missing",
            "slideId": slide_id,
            "reason": "No structured evidence-bound numeric points matched this slide.",
            "publicationBlocking": False,
        })
        return None, diagnostics
    # Avoid plotting unrelated metrics on one axis. Prefer the most represented metric/unit pair.
    winning_key, _ = Counter((point.metric, point.unit) for point in selected).most_common(1)[0]
    selected = [point for point in selected if (point.metric, point.unit) == winning_key][:24]
    grouped: dict[str, list[EvidencePoint]] = {}
    for point in selected:
        grouped.setdefault(point.series, []).append(point)
    categories = list(dict.fromkeys(point.category for point in selected))
    complete = {name: rows for name, rows in grouped.items() if {row.category for row in rows} == set(categories)}
    if not complete:
        diagnostics.append({
            "code": "chart_series_incomplete", "slideId": slide_id,
            "reason": "Structured points did not form a complete comparable series.", "publicationBlocking": False,
        })
        return None, diagnostics
    series: list[ChartSeries] = []
    for label, rows in complete.items():
        by_category = {row.category: row for row in rows}
        ordered = [by_category[category] for category in categories]
        calculation_lineage = [row.calculation_id or "" for row in ordered]
        series.append(ChartSeries(
            label=label,
            values=[row.value for row in ordered],
            calculation_ids=calculation_lineage if any(calculation_lineage) else [],
            point_bindings=[ChartPointBinding(
                category=row.category, value=row.value, unit=row.unit, period=row.period,
                status=row.status, evidence_ids=list(row.evidence_ids), calculation_id=row.calculation_id,
            ) for row in ordered],
        ))
    actual = list(dict.fromkeys(point.category for point in selected if point.status == "actual"))
    forecast = list(dict.fromkeys(point.category for point in selected if point.status in _FORECAST))
    af_contract = None
    if actual and forecast:
        af_contract = ActualForecastContract(
            actual_categories=actual, forecast_categories=forecast,
            transition_after_category=actual[-1],
            assumption_evidence_ids=list(dict.fromkeys(
                evidence for point in selected if point.status in _FORECAST for evidence in point.evidence_ids
            )),
        )
    selected_chart_type = _chart_type(selected, primitive)
    if selected_chart_type == "funnel" and any(
        right > left for chart_series in series
        for left, right in zip(chart_series.values, chart_series.values[1:])
    ):
        diagnostics.append({
            "code": "funnel_not_cumulative", "slideId": slide_id,
            "reason": "A funnel requires non-increasing semantically cumulative stage values.",
            "publicationBlocking": False,
        })
        return None, diagnostics
    return ChartSpec(
        id=f"chart-{slide_id}", chart_type=selected_chart_type,
        purpose="Turn structured, evidence-bound numeric support into investor-readable proof.",
        title=title, categories=categories, series=series,
        evidence_ids=list(dict.fromkeys(evidence for point in selected for evidence in point.evidence_ids)),
        calculation_ids=list(dict.fromkeys(point.calculation_id for point in selected if point.calculation_id)),
        value_unit=winning_key[1], actual_forecast=af_contract, brand_palette=brand_palette(brand),
    ), diagnostics


def composition_for(primitive: str, *, has_chart: bool, income_statement: bool = False) -> CompositionContract:
    if income_statement:
        return CompositionContract(
            layout_family="financial_table", dominant_object="auditable financial table",
            max_supporting_groups=1, minimum_canvas_occupancy=0.58,
            hierarchy_rules=["Preserve row and period comparability", "Keep assumptions visually separate"],
            table_policy="inspection_first",
        )
    if has_chart:
        return CompositionContract(
            layout_family="dominant_chart", dominant_object="evidence-bound chart",
            max_supporting_groups=2, minimum_canvas_occupancy=0.55,
            hierarchy_rules=["Chart is the largest object", "One implication, not a prose panel"],
        )
    family = "editorial_hero" if primitive in {"hero", "editorial_statement"} else "evidence_composition"
    return CompositionContract(
        layout_family=family, dominant_object="single investor-relevant proof",
        hierarchy_rules=["One dominant focal point", "Supporting copy remains subordinate"],
    )


def rhythm_warnings(families: list[str]) -> list[str]:
    warnings: list[str] = []
    for index in range(2, len(families)):
        if families[index - 2:index + 1].count(families[index]) == 3:
            warnings.append(f"Slides {index - 1}-{index + 1} repeat {families[index]} three times.")
    return warnings
