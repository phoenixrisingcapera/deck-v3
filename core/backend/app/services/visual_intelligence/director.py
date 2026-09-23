from __future__ import annotations

from typing import Any

from app.services.visual_intelligence.models import (
    ALLOWED_VISUAL_PRIMITIVES, AssetPlan, BrandVisualSystem, DeckVisualRhythm, DiagramEdge, DiagramNode,
    DiagramSpec, ImageBrief, SlideVisualBrief, VisualDirection, VisualIntelligenceBundle,
    VisualRhythmBeat,
)
from app.services.visual_intelligence.decision_engine import (
    brand_palette, chart_for_slide, composition_for, normalize_evidence_points, rhythm_warnings,
)
from app.services.visual_intelligence.background import (
    author_deck_background_system,
    author_slide_background,
)
from app.services.visual_intelligence.knowledge import load_visual_knowledge, selected_modules, visual_rule_ids
from app.services.visual_intelligence.assets import render_asset_plan


_PRIMITIVES = {
    "thesis": "hero", "problem": "editorial_statement", "solution": "platform_architecture",
    "product": "product_ui", "workflow": "workflow", "market": "market_size",
    "traction": "big_number", "business_model": "business_model",
    "competition": "competitive_matrix", "roadmap": "timeline", "team": "team",
    "why_now": "data_chart", "expansion": "wedge_expansion", "financial": "financial_bridge",
}

_DIAGRAM_PRIMITIVES = {
    "workflow": "workflow", "lifecycle": "customer_journey", "ecosystem": "ecosystem",
    "platform_architecture": "platform", "technology_stack": "architecture",
    "value_chain": "value_chain", "flywheel": "flywheel", "funnel": "funnel",
    "wedge_expansion": "wedge_expansion", "process": "process", "timeline": "timeline",
    "system_map": "system_map",
}

_COMPOSITIONS = {
    "hero": "Use an asymmetric editorial field: one thesis at display scale, one restrained proof cue, and brand-led negative space.",
    "editorial_statement": "Stage the problem as one decisive assertion with a contrasting evidence rail; do not use a card grid.",
    "platform_architecture": "Build one large connected system map with a clear centre of gravity, directional flow, and sparse labels.",
    "product_ui": "Use one product moment at presentation scale, annotated by outcome rather than feature inventory.",
    "workflow": "Show the before-to-after operating flow as a left-to-right journey with one highlighted bottleneck and one resolved state.",
    "market_size": "Lead with the defensible market definition, then show scope and growth as a nested or stepped evidence structure with citations.",
    "big_number": "Give the strongest verified metric most of the canvas; pair it with definition, period, and one comparison only.",
    "business_model": "Connect buyer, pricing unit, gross-margin logic, and expansion path in one economic system rather than four equal boxes.",
    "competitive_matrix": "Map the meaningful buying criteria and category boundaries; highlight the wedge without decorative logo walls.",
    "timeline": "Use a paced milestone line with achieved and future states visibly distinct; never imply an unverified milestone is complete.",
    "team": "Curate the few capabilities that de-risk the thesis; use people and credentials at human scale, not a directory.",
    "data_chart": "Use one evidence-led chart with direct labels, explicit units and period, and a short investor implication.",
    "wedge_expansion": "Show the initial wedge expanding into adjacent workflows or revenue pools with clear sequencing and boundaries.",
    "financial_bridge": "Visualize the economic bridge from current evidence to modeled outcome, separating actuals, assumptions, and projections.",
    "composition": "Choose one dominant visual proof—statement, metric, relationship, or approved image—and subordinate all supporting copy to it.",
}


def _text(value: object, fallback: str, limit: int = 500) -> str:
    normalized = " ".join(str(value or "").split())
    return (normalized or fallback)[:limit]


def _copy_budget(value: object) -> int:
    try:
        return max(5, min(180, int(value or 55)))
    except (TypeError, ValueError):
        return 55


def _brand_interpretation(brand: dict[str, Any]) -> dict[str, str]:
    return {
        key: _text(brand.get(key), "", 120)
        for key in ("companyName", "visualDirection", "websiteSourceUrl")
        if brand.get(key)
    }


def build_visual_intelligence(
    *, vc_strategy: dict[str, Any], brand: dict[str, Any], approved_assets: list[dict[str, Any]],
    metrics: list[dict[str, Any]] | None = None,
    metric_sets: list[dict[str, Any]] | None = None,
    input_artifact_ids: list[str] | None = None,
) -> VisualIntelligenceBundle:
    """Compile narrative intent into a typed, sector-neutral visual contract.

    This stage does not invent facts, calculations, images, or chart values. It
    carries model-authored narrative/visual intent into application-owned types.
    """
    typed_architecture = vc_strategy.get("typedDeckArchitecture") if isinstance(vc_strategy.get("typedDeckArchitecture"), dict) else {}
    architecture = list(typed_architecture.get("slides") or vc_strategy.get("deckArchitecture") or [])
    background_system = author_deck_background_system(
        brand,
        slide_count=max(1, len(architecture)),
        design_emphasis=str(brand.get("emphasisMode") or ""),
    )
    narrative = vc_strategy.get("narrativeStrategy") if isinstance(vc_strategy.get("narrativeStrategy"), dict) else {}
    concept = _text(
        narrative.get("visualThesis") or narrative.get("thesis"),
        "A clear investor story led by evidence, hierarchy and purposeful visual contrast.",
        300,
    )
    direction = VisualDirection(
        concept=concept,
        design_thesis=concept,
        brand_character=[value for value in (
            _text(narrative.get("tone"), "", 80),
            _text(narrative.get("category"), "", 80),
        ) if value],
        typography_direction="Use canonical brand typography with presentation-scale hierarchy and restrained copy.",
        color_strategy="Use only canonical brand tokens; reserve accent color for argument and evidence emphasis.",
        imagery_strategy="Use an image only when it advances the investment argument; never repeat a source hero by default.",
        data_visualization_direction="Prefer direct labels and a single comparison point; render only verified values with calculation lineage.",
        diagram_language="Use a small number of large semantic nodes with explicit relationships and application-owned geometry.",
        whitespace_strategy="Use whitespace to establish hierarchy while keeping evidence and diagrams at presentation scale.",
        avoid=["repeated card grids", "small generic diagrams", "decorative evidence", "repeated source imagery"],
        composition_principles=[
            "One dominant message and focal element per slide",
            "Use charts and diagrams only when their evidence and relationships are explicit",
            "Vary composition while preserving a coherent deck-level rhythm",
            "Keep source, external research and inference visually distinguishable",
        ],
        rhythm=["thesis", "evidence", "explanation", "proof", "implication"],
        brand_interpretation=_brand_interpretation(brand),
        background_system=background_system,
    )
    briefs: list[SlideVisualBrief] = []
    chart_specs = []
    diagram_specs: list[DiagramSpec] = []
    image_briefs: list[ImageBrief] = []
    beats: list[VisualRhythmBeat] = []
    source_asset_ids = [str(asset.get("assetId") or asset.get("id")) for asset in approved_assets if asset.get("assetId") or asset.get("id")]
    reuse_counts: dict[str, int] = {}
    financial = vc_strategy.get("financialAnalysis") if isinstance(vc_strategy.get("financialAnalysis"), dict) else {}
    financial_records = [
        item
        for key in ("verifiedCompanyMetrics", "managementProjections", "externalBenchmarks", "derivedCalculations")
        for item in financial.get(key, [])
        if isinstance(item, dict)
    ]
    evidence_points = normalize_evidence_points([*(metrics or []), *financial_records], metric_sets or [])
    compliance_diagnostics: list[dict[str, Any]] = []
    composition_families: list[str] = []
    external_evidence_ids = {str(value) for value in vc_strategy.get("externalEvidenceIds") or []}
    for index, slide in enumerate(architecture, 1):
        role = str(slide.get("role") or slide.get("type") or "").strip().lower()
        requested = str(slide.get("visualPrimitive") or slide.get("visual_primitive") or "").strip().lower()
        primitive = requested if requested in ALLOWED_VISUAL_PRIMITIVES else _PRIMITIVES.get(role, "composition")
        title = _text(slide.get("title") or slide.get("headline") or slide.get("headline_direction"), f"Slide {index}", 240)
        slide_id = str(slide.get("id") or f"visual-slide-{index:02d}")
        evidence_ids = [str(value) for value in slide.get("evidenceRefs") or slide.get("evidence_ids") or []]
        calculation_ids = [str(value) for value in slide.get("calculationIds") or slide.get("calculation_ids") or []]
        raw_shape = str(slide.get("evidenceShape") or slide.get("evidence_shape") or "").lower()
        income_statement = raw_shape in {"income_statement", "historical_income_statement", "financial_table"}
        chart_spec, chart_diagnostics = (None, []) if income_statement else chart_for_slide(
            slide_id=slide_id, title=title, primitive=primitive,
            evidence_ids=evidence_ids, calculation_ids=calculation_ids,
            points=evidence_points, brand=brand,
        )
        compliance_diagnostics.extend(chart_diagnostics)
        chart_id = chart_spec.id if chart_spec else None
        if chart_spec:
            chart_specs.append(chart_spec)
        elif primitive in {"data_chart", "market_size", "financial_bridge", "funnel", "chart"} and not income_statement:
            # The model may request a chart, but the application cannot make
            # one without a complete structured series. Select a truthful
            # non-chart composition and retain the incompatibility diagnostic.
            primitive = "composition"
        diagram_id = None
        if primitive in _DIAGRAM_PRIMITIVES:
            raw_nodes = slide.get("diagramNodes") or slide.get("diagram_nodes") or []
            nodes = [
                DiagramNode(
                    id=str(item.get("id") or f"{slide_id}-node-{node_index}"),
                    label=_text(item.get("label"), f"Step {node_index}", 120),
                    kind=_text(item.get("kind"), "concept", 80),
                    group=_text(item.get("group"), "", 80) or None,
                    evidence_ids=[str(value) for value in item.get("evidenceIds") or []],
                )
                for node_index, item in enumerate(raw_nodes, 1)
                if isinstance(item, dict)
            ]
            if len(nodes) >= 2:
                diagram_id = f"diagram-{slide_id}"
                diagram_specs.append(DiagramSpec(
                    id=diagram_id,
                    diagram_type=_DIAGRAM_PRIMITIVES[primitive],
                    purpose=_text(slide.get("purpose"), title, 300),
                    title=title,
                    nodes=nodes,
                    edges=[DiagramEdge(source=nodes[i].id, target=nodes[i + 1].id) for i in range(len(nodes) - 1)],
                    evidence_ids=[str(value) for value in slide.get("evidenceRefs") or []],
                ))
        image_id = None
        requested_asset = str(slide.get("sourceAssetId") or "")
        if requested_asset and requested_asset in source_asset_ids:
            reuse_counts[requested_asset] = reuse_counts.get(requested_asset, 0) + 1
            if reuse_counts[requested_asset] <= 2:
                image_id = f"image-{slide_id}"
                image_briefs.append(ImageBrief(
                    id=image_id, slide_id=slide_id, purpose=_text(slide.get("purpose"), title, 300),
                    source="source_asset", subject=title,
                    composition=_text(slide.get("imageComposition"), "Use once at presentation scale with purposeful negative space.", 300),
                    factual_role="source_evidence", source_asset_id=requested_asset,
                    prohibited_elements=["invented UI", "uncited logos", "fabricated customers"],
                ))
        composition_contract = composition_for(primitive, has_chart=chart_spec is not None, income_statement=income_statement)
        composition_families.append(composition_contract.layout_family)
        required_assets = ([f"rendered-chart-{chart_id}"] if chart_id else []) + ([f"rendered-diagram-{diagram_id}"] if diagram_id else [])
        briefs.append(SlideVisualBrief(
            slide_id=slide_id,
            slide_index=index,
            communication_goal=_text(slide.get("purpose") or slide.get("objective"), title),
            dominant_message=_text(slide.get("keyMessage") or slide.get("key_message") or slide.get("headlineDirection") or slide.get("headline_direction"), title),
            visual_primitive=primitive,
            focal_element=_text(slide.get("focalElement"), title, 240),
            composition_strategy=_text(slide.get("visualIntent") or slide.get("visual_intent"), _COMPOSITIONS.get(primitive, _COMPOSITIONS["composition"]), 300),
            visual_story=_text(slide.get("visualStory"), f"Make the investor understand why {title.lower()} matters.", 600),
            evidence_ids=evidence_ids,
            calculation_ids=calculation_ids,
            chart_spec_id=chart_id,
            chart_spec_ids=[chart_id] if chart_id else [],
            copy_budget_words=_copy_budget(slide.get("copyBudgetWords")),
            diagram_spec_id=diagram_id,
            image_brief_id=image_id,
            diagram_spec_ids=[diagram_id] if diagram_id else [],
            image_brief_ids=[image_id] if image_id else [],
            hierarchy_notes="One primary focal element; supporting evidence remains subordinate and readable.",
            investor_belief=_text(slide.get("investorBelief") or slide.get("keyMessage"), title, 400),
            evidence_shape=raw_shape or ("time_series" if chart_spec and chart_spec.chart_type == "line" else "structured_numeric" if chart_spec else "qualitative"),
            evidence_authority=(
                "mixed" if evidence_ids and external_evidence_ids.intersection(evidence_ids) and set(evidence_ids) - external_evidence_ids
                else "external_research" if evidence_ids and set(evidence_ids) <= external_evidence_ids
                else "company_source" if evidence_ids
                else "calculation" if calculation_ids
                else "none"
            ),
            uncertainty="projected" if chart_spec and chart_spec.actual_forecast else "observed" if chart_spec else "unknown",
            composition_contract=composition_contract,
            selected_rule_ids=[
                "composition.one_dominant_object",
                "forecast.visible_boundary" if chart_spec and chart_spec.actual_forecast else "evidence.no_invention",
                *([{
                    "line": "chart.series", "area": "chart.series", "bar": "chart.comparison",
                    "waterfall": "chart.bridge", "funnel": "chart.funnel",
                }[chart_spec.chart_type]] if chart_spec else []),
            ],
            required_asset_ids=required_assets,
            executable_visual_required=bool(chart_id or diagram_id),
            background=author_slide_background(
                background_system,
                slide_index=index,
                visual_primitive=primitive,
                design_emphasis=str(brand.get("emphasisMode") or ""),
            ),
            relationship_to_previous_slide="opening" if index == 1 else f"Develop the implication of slide {index - 1}",
            relationship_to_next_slide="conclusion" if index == len(architecture) else f"Create the question answered by slide {index + 1}",
        ))
        beats.append(VisualRhythmBeat(
            slide_id=slide_id,
            intensity="high" if index in {1, len(architecture)} or primitive in {"big_number", "hero"} else "medium" if index % 3 else "low",
            visual_mode=primitive,
            density="sparse" if primitive in {"hero", "editorial_statement", "big_number"} else "dense" if primitive in {"data_chart", "competitive_matrix"} else "balanced",
        ))
    asset_plan = AssetPlan(
        source_asset_ids=source_asset_ids,
        charts=chart_specs,
        diagrams=diagram_specs,
        images=image_briefs,
        source_asset_reuse_counts=reuse_counts,
    )
    selected_knowledge = selected_modules(has_financials=bool(evidence_points), has_brand=bool(brand))
    selected_rule_ids = list(dict.fromkeys(
        rule_id for brief in briefs for rule_id in brief.selected_rule_ids
    ))
    knowledge = load_visual_knowledge()
    unknown_rules = set(selected_rule_ids) - visual_rule_ids()
    if unknown_rules:
        raise ValueError(f"Visual decision selected unknown knowledge rules: {sorted(unknown_rules)}")
    logo_ids = [
        str(asset.get("assetId") or asset.get("id")) for asset in approved_assets
        if str(asset.get("type") or asset.get("assetType") or "").lower() == "logo"
        and (asset.get("assetId") or asset.get("id"))
    ]
    return VisualIntelligenceBundle(
        visual_direction=direction,
        visual_rhythm=DeckVisualRhythm(
            beats=beats, composition_families=composition_families,
            repeated_layout_warnings=rhythm_warnings(composition_families),
        ),
        slide_visual_briefs=briefs,
        asset_plan=asset_plan,
        chart_specs=chart_specs,
        diagram_specs=diagram_specs,
        rendered_assets=render_asset_plan(asset_plan),
        input_artifact_ids=input_artifact_ids or [],
        selected_knowledge_modules=selected_knowledge,
        compliance_diagnostics=compliance_diagnostics,
        brand_system=BrandVisualSystem(
            palette=brand_palette(brand),
            typography_tokens={
                key: str(brand[key]) for key in ("headingFont", "bodyFont", "fontFamily") if brand.get(key)
            },
            logo_asset_ids=logo_ids,
            spacing_character=str(brand.get("spacingCharacter") or "balanced") if str(brand.get("spacingCharacter") or "balanced") in {"compact", "balanced", "expansive"} else "balanced",
            radius_tendency=_text(brand.get("radiusTendency"), "observed_or_neutral", 80),
            emphasis_mode=str(brand.get("emphasisMode") or "mixed") if str(brand.get("emphasisMode") or "mixed") in {"light", "dark", "mixed"} else "mixed",
            fallback_style="brand_led" if brand else "neutral_investor",
        ),
        knowledge_trace={
            "corpusVersion": knowledge["corpusVersion"],
            "consideredModuleIds": knowledge["modules"],
            "selectedModuleIds": selected_knowledge,
            "injectedModuleIds": selected_knowledge,
            "usedRuleIds": selected_rule_ids,
            "droppedModuleIds": [module for module in knowledge["modules"] if module not in selected_knowledge],
        },
    )
