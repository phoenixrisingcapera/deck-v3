from __future__ import annotations

import base64
from hashlib import sha256

from app.services.visual_intelligence.charts import render_chart_svg
from app.services.visual_intelligence.diagrams import render_diagram_svg
from app.services.visual_intelligence.models import (
    AssetPlan, RenderedVisualAsset,
)


def _svg_asset(*, asset_id: str, spec_id: str, asset_type: str, svg: str,
               evidence_ids: list[str], calculation_ids: list[str]) -> RenderedVisualAsset:
    payload = svg.encode("utf-8")
    return RenderedVisualAsset(
        id=asset_id,
        spec_id=spec_id,
        asset_type=asset_type,
        content_sha256=sha256(payload).hexdigest(),
        data_url="data:image/svg+xml;base64," + base64.b64encode(payload).decode("ascii"),
        evidence_ids=evidence_ids,
        calculation_ids=calculation_ids,
    )


def render_asset_plan(plan: AssetPlan) -> list[RenderedVisualAsset]:
    """Render validated specs deterministically; no provider or authored geometry."""
    rendered = [
        _svg_asset(
            asset_id=f"rendered-chart-{spec.id}", spec_id=spec.id,
            asset_type="chart_svg", svg=render_chart_svg(spec),
            evidence_ids=spec.evidence_ids,
            calculation_ids=spec.calculation_ids or [item for series in spec.series for item in series.calculation_ids if item],
        )
        for spec in plan.charts
    ]
    rendered.extend(
        _svg_asset(
            asset_id=f"rendered-diagram-{spec.id}", spec_id=spec.id,
            asset_type="diagram_svg", svg=render_diagram_svg(spec),
            evidence_ids=spec.evidence_ids,
            calculation_ids=[],
        )
        for spec in plan.diagrams
    )
    return rendered
