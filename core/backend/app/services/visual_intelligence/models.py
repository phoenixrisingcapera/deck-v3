from __future__ import annotations

from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


VisualPrimitive = Literal[
    "hero", "editorial_statement", "big_number", "data_chart", "market_size",
    "market_map", "competitive_matrix", "comparison", "workflow", "lifecycle",
    "timeline", "flywheel", "funnel", "ecosystem", "platform_architecture",
    "technology_stack", "value_chain", "wedge_expansion", "financial_bridge",
    "business_model", "product_ui", "process", "team", "photography", "mixed",
    # Backward-compatible v1 values retained for persisted artifacts.
    "statement", "system_map", "metric", "chart", "evidence", "image", "people",
    "composition",
]
ALLOWED_VISUAL_PRIMITIVES = frozenset(VisualPrimitive.__args__)


class SlideBackground(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canvas: str = Field(min_length=1, max_length=200)
    surface: str = Field(default="", max_length=80)
    surface_alt: str = Field(default="", max_length=80)
    accent: str = Field(default="", max_length=80)
    ink: str = Field(default="", max_length=80)
    treatment: str = Field(default="", max_length=240)
    harmonization: str = Field(default="shared", max_length=120)
    distinct: bool = False
    rationale: str = Field(default="", max_length=400)


class DeckBackgroundSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["deck-background-system.v1"] = "deck-background-system.v1"
    cover: SlideBackground = Field(default_factory=SlideBackground)
    interior: SlideBackground = Field(default_factory=SlideBackground)
    harmonization_principle: str = Field(max_length=300)
    css_tokens: dict[str, str] = Field(default_factory=dict)


class VisualDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["visual-direction.v1"] = "visual-direction.v1"
    concept: str = Field(min_length=1, max_length=300)
    composition_principles: list[str] = Field(min_length=1, max_length=8)
    rhythm: list[str] = Field(min_length=1, max_length=8)
    brand_token_policy: Literal["canonical_brand_tokens_only"] = "canonical_brand_tokens_only"
    factual_authority: Literal["none"] = "none"
    brand_interpretation: dict[str, str] = Field(default_factory=dict)
    design_thesis: str = Field(default="", max_length=500)
    brand_character: list[str] = Field(default_factory=list, max_length=8)
    typography_direction: str = Field(default="", max_length=300)
    color_strategy: str = Field(default="", max_length=300)
    imagery_strategy: str = Field(default="", max_length=300)
    data_visualization_direction: str = Field(default="", max_length=300)
    diagram_language: str = Field(default="", max_length=300)
    density: Literal["sparse", "balanced", "dense", "variable"] = "variable"
    whitespace_strategy: str = Field(default="", max_length=300)
    avoid: list[str] = Field(default_factory=list, max_length=12)
    background_system: DeckBackgroundSystem = Field(default_factory=DeckBackgroundSystem)


class BrandVisualSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    palette: list[str] = Field(default_factory=list, max_length=8)
    typography_tokens: dict[str, str] = Field(default_factory=dict)
    logo_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    source_image_treatment: str = Field(default="preserve_provenance_and_aspect_ratio", max_length=120)
    spacing_character: Literal["compact", "balanced", "expansive"] = "balanced"
    radius_tendency: str = Field(default="observed_or_neutral", max_length=80)
    emphasis_mode: Literal["light", "dark", "mixed"] = "mixed"
    fallback_style: Literal["brand_led", "neutral_investor"] = "neutral_investor"


class VisualRhythmBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_id: str = Field(min_length=1, max_length=120)
    intensity: Literal["low", "medium", "high"]
    visual_mode: VisualPrimitive
    density: Literal["sparse", "balanced", "dense"] = "balanced"


class DeckVisualRhythm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["deck-visual-rhythm.v1"] = "deck-visual-rhythm.v1"
    beats: list[VisualRhythmBeat] = Field(default_factory=list, max_length=40)
    composition_families: list[str] = Field(default_factory=list, max_length=40)
    repeated_layout_warnings: list[str] = Field(default_factory=list, max_length=20)


class CompositionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layout_family: Literal[
        "editorial_hero", "dominant_chart", "financial_table", "system_diagram",
        "comparison_field", "product_stage", "metric_focus", "evidence_composition",
    ]
    dominant_object: str = Field(min_length=1, max_length=120)
    max_supporting_groups: int = Field(default=2, ge=0, le=3)
    minimum_canvas_occupancy: float = Field(default=0.48, ge=0.25, le=0.9)
    hierarchy_rules: list[str] = Field(default_factory=list, max_length=6)
    table_policy: Literal["not_applicable", "inspection_first", "summary_only"] = "not_applicable"


class SlideVisualBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_id: str = Field(min_length=1, max_length=120)
    slide_index: int = Field(ge=1, le=40)
    communication_goal: str = Field(min_length=1, max_length=500)
    dominant_message: str = Field(default="", max_length=500)
    visual_primitive: VisualPrimitive = "composition"
    focal_element: str = Field(default="", max_length=240)
    composition_strategy: str = Field(default="", max_length=300)
    visual_story: str = Field(default="", max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    calculation_ids: list[str] = Field(default_factory=list, max_length=40)
    chart_spec_id: str | None = None
    diagram_spec_id: str | None = None
    image_brief_id: str | None = None
    chart_spec_ids: list[str] = Field(default_factory=list, max_length=8)
    diagram_spec_ids: list[str] = Field(default_factory=list, max_length=8)
    image_brief_ids: list[str] = Field(default_factory=list, max_length=8)
    copy_budget_words: int = Field(default=55, ge=5, le=180)
    relationship_to_previous_slide: str = Field(default="opening", max_length=240)
    relationship_to_next_slide: str = Field(default="conclusion", max_length=240)
    hierarchy_notes: str = Field(default="", max_length=300)
    investor_belief: str = Field(default="", max_length=400)
    evidence_shape: str = Field(default="qualitative", max_length=80)
    evidence_authority: Literal["company_source", "external_research", "calculation", "mixed", "none"] = "none"
    uncertainty: Literal["observed", "estimated", "projected", "scenario", "unknown"] = "unknown"
    composition_contract: CompositionContract | None = None
    selected_rule_ids: list[str] = Field(default_factory=list, max_length=16)
    required_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    executable_visual_required: bool = False
    background: SlideBackground = Field(default_factory=SlideBackground)


ValueStatus = Literal["actual", "forecast", "projected", "scenario", "target", "unknown"]


class ChartPointBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    period: str = Field(min_length=1, max_length=80)
    status: ValueStatus
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    calculation_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def finite_value(self) -> "ChartPointBinding":
        if not isfinite(self.value):
            raise ValueError("Chart point values must be finite")
        if not self.evidence_ids and not self.calculation_id:
            raise ValueError("Every chart point requires evidence or calculation lineage")
        return self


class ActualForecastContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actual_categories: list[str] = Field(default_factory=list, max_length=24)
    forecast_categories: list[str] = Field(default_factory=list, max_length=24)
    transition_after_category: str | None = Field(default=None, max_length=80)
    assumption_evidence_ids: list[str] = Field(default_factory=list, max_length=40)
    actual_style: Literal["solid"] = "solid"
    forecast_style: Literal["dashed_translucent"] = "dashed_translucent"


class ChartSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=100)
    values: list[float] = Field(min_length=1, max_length=24)
    calculation_ids: list[str] = Field(default_factory=list, max_length=24)
    point_bindings: list[ChartPointBinding] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def finite_values(self) -> "ChartSeries":
        if any(not isfinite(value) for value in self.values):
            raise ValueError("Chart values must be finite")
        if self.calculation_ids and len(self.calculation_ids) != len(self.values):
            raise ValueError("Chart calculation IDs must align with values")
        if self.point_bindings and len(self.point_bindings) != len(self.values):
            raise ValueError("Every chart value must retain a point binding")
        if self.point_bindings and any(binding.value != value for binding, value in zip(self.point_bindings, self.values)):
            raise ValueError("Point bindings must preserve exact plotted values")
        if not self.point_bindings and not self.calculation_ids:
            raise ValueError("Every chart series requires point or calculation lineage")
        if self.calculation_ids and any(not item.strip() for item in self.calculation_ids):
            raise ValueError("Chart calculation IDs cannot be blank")
        return self


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    schema_version: Literal["chart-spec.v1", "chart-spec.v2"] = "chart-spec.v2"
    chart_type: Literal["bar", "line", "area", "waterfall", "funnel"]
    purpose: str = Field(default="", max_length=300)
    title: str = Field(min_length=1, max_length=180)
    categories: list[str] = Field(min_length=1, max_length=24)
    series: list[ChartSeries] = Field(min_length=1, max_length=8)
    evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    calculation_ids: list[str] = Field(default_factory=list, max_length=80)
    x_axis: dict[str, Any] | None = None
    y_axis: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=400)
    value_unit: str | None = Field(default=None, max_length=40)
    actual_forecast: ActualForecastContract | None = None
    scenario_semantics: dict[str, str] = Field(default_factory=dict)
    brand_palette: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def aligned_values(self) -> "ChartSpec":
        if any(len(series.values) != len(self.categories) for series in self.series):
            raise ValueError("Every chart series must align with the category count")
        for series in self.series:
            if series.point_bindings and any(
                binding.category != category
                for binding, category in zip(series.point_bindings, self.categories)
            ):
                raise ValueError("Chart point categories must align with chart categories")
        return self


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str = Field(min_length=1, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    kind: str = Field(default="concept", max_length=80)
    group: str | None = Field(default=None, max_length=80)


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    label: str = Field(default="", max_length=80)


class DiagramSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    schema_version: Literal["diagram-spec.v1"] = "diagram-spec.v1"
    diagram_type: Literal[
        "workflow", "system_map", "timeline", "ecosystem", "platform",
        "architecture", "process", "customer_journey", "value_chain",
        "flywheel", "funnel", "wedge_expansion",
    ]
    purpose: str = Field(default="", max_length=300)
    title: str = Field(min_length=1, max_length=180)
    nodes: list[DiagramNode] = Field(min_length=2, max_length=16)
    edges: list[DiagramEdge] = Field(default_factory=list, max_length=32)
    evidence_ids: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def valid_edges(self) -> "DiagramSpec":
        node_ids = {node.id for node in self.nodes}
        if any(edge.source not in node_ids or edge.target not in node_ids for edge in self.edges):
            raise ValueError("Diagram edges must reference declared nodes")
        return self


class ImageBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    slide_id: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=300)
    source: Literal["source_asset", "generated", "public_asset", "product_capture", "none"]
    subject: str = Field(default="", max_length=300)
    composition: str = Field(default="", max_length=300)
    brand_attributes: list[str] = Field(default_factory=list, max_length=8)
    negative_space: str | None = Field(default=None, max_length=160)
    prohibited_elements: list[str] = Field(default_factory=list, max_length=12)
    aspect_ratio: str = Field(default="16:9", max_length=20)
    factual_role: Literal["decorative", "conceptual", "source_evidence"] = "decorative"
    source_asset_id: str | None = None

    @model_validator(mode="after")
    def generated_images_are_not_evidence(self) -> "ImageBrief":
        if self.source == "generated" and self.factual_role == "source_evidence":
            raise ValueError("Generated images cannot be factual evidence")
        return self


class AssetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_asset_ids: list[str] = Field(default_factory=list, max_length=40)
    public_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    generated_image_briefs: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    generated_images_are_evidence: Literal[False] = False
    charts: list[ChartSpec] = Field(default_factory=list, max_length=24)
    diagrams: list[DiagramSpec] = Field(default_factory=list, max_length=24)
    images: list[ImageBrief] = Field(default_factory=list, max_length=40)
    source_asset_reuse_counts: dict[str, int] = Field(default_factory=dict)


class VisionFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_id: str | None = None
    issue: str = Field(min_length=1, max_length=400)
    severity: Literal["advisory", "important", "critical_for_visual_quality"] = "advisory"
    dimension: Literal[
        "focal_point", "hierarchy", "balance", "composition", "scale", "alignment",
        "contrast", "text_density", "chart_readability", "diagram_readability",
        "image_quality", "brand_fit", "visual_storytelling", "rhythm", "repetition",
    ]


class VisionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["vision-review.v1", "vision-review.v2"] = "vision-review.v2"
    rendered_artifact_ids: list[str] = Field(min_length=1, max_length=41)
    findings: list[VisionFinding] = Field(default_factory=list, max_length=160)
    strengths: list[str] = Field(default_factory=list, max_length=40)
    recommended_changes: list[str] = Field(default_factory=list, max_length=40)
    handoff_assessment: str = Field(default="", max_length=1200)
    overall_score: int | None = Field(default=None, ge=0, le=100)
    narrative_score: int | None = Field(default=None, ge=0, le=100)
    financial_credibility_score: int | None = Field(default=None, ge=0, le=100)
    investor_clarity_score: int | None = Field(default=None, ge=0, le=100)
    visual_quality_score: int | None = Field(default=None, ge=0, le=100)
    brand_consistency_score: int | None = Field(default=None, ge=0, le=100)
    review_source: Literal["deterministic", "llm_assisted"] = "deterministic"
    publication_blocking: Literal[False] = False


class VisualRepairInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_id: str
    issue: str = Field(min_length=1, max_length=400)
    repair_type: Literal["hierarchy", "density", "composition", "chart", "diagram", "image", "typography"]
    requested_change: str = Field(min_length=1, max_length=600)
    preserve: list[str] = Field(default_factory=list, max_length=20)


class VisualRepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["visual-repair-plan.v1"] = "visual-repair-plan.v1"
    instructions: list[VisualRepairInstruction] = Field(default_factory=list, max_length=20)
    max_repair_passes: Literal[1] = 1
    publication_blocking: Literal[False] = False


class RenderedVisualAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    spec_id: str
    asset_type: Literal["chart_svg", "diagram_svg"]
    mime_type: Literal["image/svg+xml"] = "image/svg+xml"
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_url: str
    evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    calculation_ids: list[str] = Field(default_factory=list, max_length=80)
    factual_authority: Literal["bound_to_spec"] = "bound_to_spec"


class VisualIntelligenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["visual-intelligence.v1"] = "visual-intelligence.v1"
    knowledge_version: Literal[
        "instant-deck-visual-knowledge.2026-09-22.v1",
        "investor-visual-design.2026-09-22.v2",
    ] = "investor-visual-design.2026-09-22.v2"
    visual_direction: VisualDirection
    visual_rhythm: DeckVisualRhythm | None = None
    slide_visual_briefs: list[SlideVisualBrief] = Field(default_factory=list, max_length=40)
    asset_plan: AssetPlan = Field(default_factory=AssetPlan)
    chart_specs: list[ChartSpec] = Field(default_factory=list, max_length=24)
    diagram_specs: list[DiagramSpec] = Field(default_factory=list, max_length=24)
    rendered_assets: list[RenderedVisualAsset] = Field(default_factory=list, max_length=48)
    input_artifact_ids: list[str] = Field(default_factory=list, max_length=20)
    vision_review_status: Literal["not_requested", "pending", "completed"] = "not_requested"
    publication_blocking: Literal[False] = False
    selected_knowledge_modules: list[str] = Field(default_factory=list, max_length=20)
    compliance_diagnostics: list[dict[str, Any]] = Field(default_factory=list, max_length=80)
    brand_system: BrandVisualSystem = Field(default_factory=BrandVisualSystem)
    knowledge_trace: dict[str, Any] = Field(default_factory=dict)
