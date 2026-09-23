"""Strict versioned domain models for the offline Instant Deck foundation."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


DECK_SPEC_VERSION = "deck_spec.v1"
SOURCE_PACKAGE_VERSION = "instant-deck-source-package.v1"
COMPILER_CONTRACT_VERSION = "instant-deck-composition-compiler.v1"

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
HexColour = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class SlideArchetype(str, Enum):
    THESIS_COVER = "thesis_cover"
    PROBLEM_LANDSCAPE = "problem_landscape"
    KEY_INSIGHT = "key_insight"
    PROCESS_PATHWAY = "process_pathway"
    SYSTEM_MAP = "system_map"
    COMPARISON_SHIFT = "comparison_shift"
    TIMELINE_MILESTONES = "timeline_milestones"
    METRIC_PROOF = "metric_proof"
    TRACTION_STRIP = "traction_strip"
    BUSINESS_MODEL_FLOW = "business_model_flow"
    MARKET_MAP = "market_map"
    GO_TO_MARKET = "go_to_market"
    PEOPLE_PROOF = "people_proof"
    PARTNERSHIP_ECOSYSTEM = "partnership_ecosystem"
    CAPITAL_PLAN = "capital_plan"
    QUOTE_EVIDENCE = "quote_evidence"
    IMAGE_EVIDENCE = "image_evidence"
    DECISIVE_CLOSE = "decisive_close"


class CompositionVariant(str, Enum):
    LEFT_FOCAL = "left_focal"
    RIGHT_FOCAL = "right_focal"
    CENTERED_MONUMENT = "centered_monument"
    SPLIT_40_60 = "split_40_60"
    SPLIT_60_40 = "split_60_40"
    EDGE_TO_EDGE = "edge_to_edge"
    DIAGONAL_FLOW = "diagonal_flow"
    RADIAL = "radial"
    ORBIT = "orbit"
    STACKED = "stacked"
    STRIP = "strip"
    FIELD = "field"


class VisualType(str, Enum):
    TYPOGRAPHIC = "typographic"
    IMAGE = "image"
    METRIC = "metric"
    PROCESS = "process"
    TIMELINE = "timeline"
    SYSTEM_MAP = "system_map"
    COMPARISON = "comparison"
    MARKET_MAP = "market_map"
    PROOF_STRIP = "proof_strip"
    PEOPLE = "people"
    CAPITAL_PLAN = "capital_plan"
    QUOTE = "quote"
    MATRIX = "matrix"


class SourceFileIdentity(StrictModel):
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    mime_type: Literal["application/pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation"]
    byte_size: int = Field(gt=0)
    page_count: int = Field(ge=1, le=500)
    extraction_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    extractor_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class SourceReference(StrictModel):
    reference_id: Annotated[str, StringConstraints(pattern=r"^ref_s[0-9]{2}_(?:slide|b[0-9]{2}|a[0-9]{2})$")]
    source_slide_id: Annotated[str, StringConstraints(pattern=r"^src_s[0-9]{2}$")]
    kind: Literal["slide", "block", "asset"]
    block_index: int | None = Field(default=None, ge=0)
    quoted_text: Annotated[str, StringConstraints(max_length=2400)] | None = None


class SourceFactRecord(StrictModel):
    fact_id: Annotated[str, StringConstraints(pattern=r"^fact_s[0-9]{2}_[0-9]{2}$")]
    kind: Literal["identity", "positioning", "product", "process", "metric", "financial", "team", "partnership", "general"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=2400)]
    material: bool = True
    source_reference_ids: list[str] = Field(min_length=1, max_length=8)


class SourceClaimRecord(StrictModel):
    claim_id: Annotated[str, StringConstraints(pattern=r"^claim_s[0-9]{2}_[0-9]{2}$")]
    text: Annotated[str, StringConstraints(min_length=1, max_length=2400)]
    fact_ids: list[str] = Field(min_length=1, max_length=8)
    source_reference_ids: list[str] = Field(min_length=1, max_length=8)
    material: bool = True


class SourceNumberRecord(StrictModel):
    number_id: Annotated[str, StringConstraints(pattern=r"^num_s[0-9]{2}_[0-9]{2}$")]
    exact_text: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    normalized_value: float | None = None
    unit: Annotated[str, StringConstraints(max_length=40)] | None = None
    qualifier: Annotated[str, StringConstraints(max_length=80)] | None = None
    source_reference_ids: list[str] = Field(min_length=1, max_length=4)


class SourceAssetRecord(StrictModel):
    asset_id: Annotated[str, StringConstraints(pattern=r"^asset_s[0-9]{2}_[0-9]{2}$")]
    asset_type: Literal["embedded_image", "page_render", "logo", "portrait", "diagram"]
    mime_type: Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"]
    sha256: Sha256
    width: int = Field(gt=0, le=20000)
    height: int = Field(gt=0, le=20000)
    alt_text: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    source_reference_ids: list[str] = Field(min_length=1, max_length=4)


class BrandRoleRecord(StrictModel):
    role_id: Annotated[str, StringConstraints(pattern=r"^brand_[a-z0-9_]+$")]
    colour: HexColour
    provenance: Literal["source_observed", "source_confirmed", "product_default"]
    source_reference_ids: list[str] = Field(min_length=0, max_length=500)

    @field_validator("colour")
    @classmethod
    def normalize_colour(cls, value: str) -> str:
        return value.upper()


    @model_validator(mode="after")
    def validate_colour_provenance(self):
        if self.provenance != "product_default" and not self.source_reference_ids:
            raise ValueError("Source colours require source provenance")
        if self.provenance == "product_default" and self.source_reference_ids:
            raise ValueError("Product defaults cannot claim source provenance")
        return self


class SourceBackedBrandMetadata(StrictModel):
    organization_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    organization_source_reference_ids: list[str] = Field(min_length=1, max_length=8)
    product_candidate: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    product_source_reference_ids: list[str] = Field(min_length=1, max_length=8)
    audience_candidate: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    audience_source_reference_ids: list[str] = Field(min_length=1, max_length=8)
    deck_type_candidate: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    deck_type_source_reference_ids: list[str] = Field(min_length=1, max_length=8)
    roles: list[BrandRoleRecord] = Field(min_length=3, max_length=8)
    logo_asset_id: str | None = None


class SourceSlideRecord(StrictModel):
    source_slide_id: Annotated[str, StringConstraints(pattern=r"^src_s[0-9]{2}$")]
    position: int = Field(ge=1, le=500)
    source_page_number: int = Field(ge=1, le=500)
    title: Annotated[str, StringConstraints(max_length=500)]
    normalized_text: Annotated[str, StringConstraints(max_length=8000)]
    fact_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    number_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    omission_eligible: bool = False
    omission_reason: Annotated[str, StringConstraints(max_length=180)] | None = None


class DebrisExclusion(StrictModel):
    source_slide_id: str
    reason: Literal["ocr_debris", "page_counter", "duplicate_reference", "decorative_only"]
    source_reference_ids: list[str] = Field(default_factory=list, max_length=20)


class MissingEvidenceRecord(StrictModel):
    topic: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=240)]


class SourceConflictRecord(StrictModel):
    topic: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    evidence_ids: list[str] = Field(min_length=2, max_length=12)
    detail: Annotated[str, StringConstraints(min_length=1, max_length=240)]


class SourceEmbeddingPolicy(StrictModel):
    scope: Literal["request_data_only"] = "request_data_only"
    global_knowledge_eligible: Literal[False] = False
    embedding_action: Literal["none"] = "none"


class NormalizedSourcePackage(StrictModel):
    schema_version: Literal["instant-deck-source-package.v1"]
    package_id: Annotated[str, StringConstraints(pattern=r"^srcpkg_[a-f0-9]{16}$")]
    source_checksum: Sha256
    source_file: SourceFileIdentity
    source_slides: list[SourceSlideRecord] = Field(min_length=1, max_length=500)
    source_references: list[SourceReference] = Field(min_length=1)
    facts: list[SourceFactRecord] = Field(min_length=1)
    claims: list[SourceClaimRecord] = Field(min_length=1)
    numbers: list[SourceNumberRecord] = Field(default_factory=list)
    assets: list[SourceAssetRecord] = Field(default_factory=list)
    brand: SourceBackedBrandMetadata
    debris_exclusions: list[DebrisExclusion] = Field(default_factory=list)
    missing_evidence: list[MissingEvidenceRecord] = Field(default_factory=list)
    conflicts: list[SourceConflictRecord] = Field(default_factory=list)
    embedding_policy: SourceEmbeddingPolicy = Field(default_factory=SourceEmbeddingPolicy)


class NarrativeSpec(StrictModel):
    audience_need: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    arc: list[Literal[
        "identity", "proposition", "problem", "insight", "solution", "product_system", "proof",
        "traction", "business_model", "market", "go_to_market", "team", "partnerships",
        "capital_plan", "decision",
    ]] = Field(min_length=4, max_length=12)
    opening_move: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    closing_move: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    represented_source_slide_ids: list[str] = Field(min_length=1)
    omitted_source_slide_ids: list[str]


class ArtDirectionSpec(StrictModel):
    concept: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    tone: Literal["editorial", "austere", "technical", "human", "bold", "atmospheric", "playful", "luxury"]
    display_strategy: Literal["serif_contrast", "grotesk_monument", "humanist", "condensed", "mono_technical"]
    motif: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    rhythm: Literal["dark_dominant", "light_dominant", "alternating", "tonal_progression", "chaptered"]
    paper_role: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    ink_role: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    signature_role: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    support_roles: list[str] = Field(max_length=3)


class CopyBlock(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^c[0-9]{2}$")]
    kind: Literal["assertion", "body", "label", "caption", "quote"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=420)]
    evidence_refs: list[str] = Field(min_length=1)
    emphasis: Literal["primary", "secondary", "quiet"]


class CompositionSpec(StrictModel):
    primitive: SlideArchetype
    variant: CompositionVariant
    background_role: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    accent_role: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    density: Literal["sparse", "balanced", "dense"]
    focal_alignment: Literal["left", "center", "right", "distributed"]
    visual_weight: float = Field(ge=0, le=1)
    maximum_text_area: float = Field(ge=0.2, le=0.7)


class VisualItem(StrictModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=180)] | None
    value: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    group: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    evidence_refs: list[str] = Field(min_length=1)
    asset_ref: str | None


class VisualEdge(StrictModel):
    from_id: Annotated[str, StringConstraints(min_length=1, max_length=40)] = Field(alias="from")
    to: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    evidence_refs: list[str] = Field(min_length=1)


class VisualMetric(StrictModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    value: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    context: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    evidence_refs: list[str] = Field(min_length=1)


class VisualPoint(StrictModel):
    x: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    y: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    evidence_refs: list[str] = Field(min_length=1)


class VisualSeries(StrictModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    points: list[VisualPoint] = Field(min_length=2, max_length=12)
    evidence_refs: list[str] = Field(min_length=1)


class VisualStep(StrictModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=160)] | None
    evidence_refs: list[str] = Field(min_length=1)


class VisualPerson(StrictModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    role: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    proof: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    evidence_refs: list[str] = Field(min_length=1)
    asset_ref: str | None


class VisualQuote(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    attribution: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None
    evidence_refs: list[str] = Field(min_length=1)


class VisualSpec(StrictModel):
    type: VisualType
    narrative_function: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    title: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None
    asset_ref: str | None
    items: list[VisualItem] = Field(max_length=12)
    edges: list[VisualEdge] = Field(max_length=16)
    metrics: list[VisualMetric] = Field(max_length=6)
    series: list[VisualSeries] = Field(max_length=4)
    steps: list[VisualStep] = Field(max_length=7)
    people: list[VisualPerson] = Field(max_length=8)
    quotes: list[VisualQuote] = Field(max_length=3)


class SlideSpec(StrictModel):
    slide_id: Annotated[str, StringConstraints(pattern=r"^s[0-9]{2}$")]
    position: int = Field(ge=1, le=18)
    archetype: SlideArchetype
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    headline: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    subhead: Annotated[str, StringConstraints(min_length=1, max_length=180)] | None
    copy_blocks: list[CopyBlock] = Field(max_length=5)
    evidence_refs: list[str] = Field(min_length=1)
    source_slide_ids: list[str] = Field(min_length=1)
    omitted_source_slide_ids: list[str]
    asset_refs: list[str] = Field(max_length=3)
    composition: CompositionSpec
    visual: VisualSpec


class DeckSpec(StrictModel):
    schema_version: Literal["deck_spec.v1"]
    compiler_version: Literal["instant-deck-composition-compiler.v1"]
    source_package_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    source_checksum: Sha256
    deck_title: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    deck_thesis: Annotated[str, StringConstraints(min_length=1, max_length=220)]
    audience: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    narrative: NarrativeSpec
    art_direction: ArtDirectionSpec
    slides: list[SlideSpec] = Field(min_length=6, max_length=18)
