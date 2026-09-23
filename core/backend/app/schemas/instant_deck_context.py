"""Canonical typed schemas for Instant Deck whole-deck generation context.

These schemas replace the ad-hoc dict contracts that currently flow through
``_build_llm_context`` -> ``build_grounded_context_pack`` -> provider call.
Typed context ensures source coverage, brand preservation, and provenance
are validated before any LLM request is made.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Source primitives
# ---------------------------------------------------------------------------


class CanonicalTable(BaseModel):
    """A table extracted from a source slide."""

    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class CanonicalChart(BaseModel):
    """A chart or graph extracted from a source slide."""

    model_config = ConfigDict(extra="forbid")

    chart_type: str = ""
    title: str = ""
    data_summary: str = ""


class AssetReference(BaseModel):
    """Provider-safe reference to an approved immutable image asset.

    Storage paths and signed/private URLs are intentionally absent.  A usable
    provider/renderer reference must be a bounded inline image prepared by the
    backend from canonical storage.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId")
    mime_type: str = Field(default="", alias="mimeType")
    alt_text: str = Field(default="", alias="altText")
    role: str = "source_image"
    provenance: Literal["confirmed", "source-extracted"] = "source-extracted"
    source_slide_ids: list[str] = Field(default_factory=list, alias="sourceSlideIds")
    resolved_data_url: str | None = Field(default=None, alias="resolvedDataUrl")
    preparation_policy: str | None = Field(default=None, alias="preparationPolicy")
    original_sha256: str | None = Field(default=None, alias="originalSha256")
    rendered_sha256: str | None = Field(default=None, alias="renderedSha256")


class SourceReference(BaseModel):
    """Provenance link from a fact or claim back to its source."""

    model_config = ConfigDict(extra="forbid")

    source_slide_id: str
    source_type: str = "source_slide"
    confidence: str = "high"


class SourceFact(BaseModel):
    """A single grounded fact extracted from the source deck or brand profile."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    source_type: str  # "source_slide" | "deck_metadata" | "brand_profile" | "user_instruction"
    source_id: str = ""
    field: str = ""
    text: str
    confidence: str = "high"
    scope: str = "slide"  # "deck" | "job" | "brand" | "slide"
    source_slide_ids: list[str] = Field(default_factory=list)


class CanonicalSourceBlock(BaseModel):
    """One deterministically ordered text block from a source slide."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    block_index: int
    block_type: str | None = None
    text: str | None = None
    normalized_text: str | None = None


class CanonicalSourceSlide(BaseModel):
    """One slide from the uploaded source presentation, fully represented."""

    model_config = ConfigDict(extra="forbid")

    id: str
    index: int
    slide_number: int | None = None
    title: str = ""
    role: str = ""
    raw_text: str = ""
    summary: str | None = None
    notes: str | None = None
    semantic_slide_type: str | None = None
    blocks: list[CanonicalSourceBlock] = Field(default_factory=list)
    tables: list[CanonicalTable] = Field(default_factory=list)
    charts: list[CanonicalChart] = Field(default_factory=list)
    images: list[AssetReference] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)  # fact_id references
    provenance: list[SourceReference] = Field(default_factory=list)


class CanonicalSourceDeck(BaseModel):
    """The complete uploaded source presentation, canonically represented."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    slide_count: int = 0
    document_page_count: int | None = None
    source_file_id: str | None = None
    source_sha256: str | None = None
    source_document_identity: dict[str, Any] | None = None
    slides: list[CanonicalSourceSlide] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Brand / design primitives
# ---------------------------------------------------------------------------


class BrandTokenProvenance(BaseModel):
    """Evidence class for one brand value sent to the provider."""

    model_config = ConfigDict(extra="forbid")

    classification: Literal["confirmed", "source-extracted", "inferred"]
    source: str
    confidence: float | None = None


class BrandProfileSnapshot(BaseModel):
    """Snapshot of the deck's brand profile for generation context."""

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = None
    visual_direction: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    text_color: str | None = None
    palette: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    logo_url: str | None = None
    instructions: list[str] = Field(default_factory=list)
    website_source_url: str | None = None
    website_evidence_sha256: str | None = None
    token_provenance: dict[str, BrandTokenProvenance] = Field(default_factory=dict)


class DesignTokens(BaseModel):
    """Renderer-safe design token mapping."""

    model_config = ConfigDict(extra="forbid")

    surface: str = "#070A12"
    surface_alt: str = "#111827"
    heading: str = "#F8FAFC"
    body: str = "#CBD5E1"
    accent: str = "#6EE7B7"
    muted: str = "#64748B"
    heading_font: str = "Inter, sans-serif"
    body_font: str = "Inter, sans-serif"


# ---------------------------------------------------------------------------
# Generation constraints
# ---------------------------------------------------------------------------


class GenerationConstraints(BaseModel):
    """Immutable constraints for a generation run."""

    model_config = ConfigDict(extra="forbid")

    max_input_tokens: int = 272_000
    max_output_tokens: int = 16_384
    provider: str = "openai"
    model: str = ""
    budget_cents: int = 500
    max_provider_starts: int = 1


class InstantDeckOutputContract(BaseModel):
    """Defines the expected output shape from the LLM."""

    model_config = ConfigDict(extra="forbid")

    format: str = "full_html_deck.v1"
    require_source_coverage: bool = True
    require_factual_grounding: bool = True
    require_brand_preservation: bool = True


# ---------------------------------------------------------------------------
# Top-level canonical context
# ---------------------------------------------------------------------------


class InstantDeckGenerationContext(BaseModel):
    """The single canonical context object for Instant Deck generation.

    This replaces the ad-hoc dict that currently flows through
    ``_build_llm_context`` + ``build_grounded_context_pack``.
    Every field is typed and validated before any LLM request.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "instant-deck-context.v1"
    deck_id: str
    source_version_id: str | None = None

    # User intent
    user_goal: str = ""
    audience: str | None = None
    deck_type: str | None = None

    # Source material — the complete uploaded deck
    source_deck: CanonicalSourceDeck

    # Grounded facts extracted from the source
    source_facts: list[SourceFact] = Field(default_factory=list)

    # Verified external evidence is separate from uploaded company facts.
    external_research: dict[str, Any] = Field(default_factory=dict)

    # Persisted pre-generation AI-VC analysis. This is strategic guidance, not
    # a new factual-authority lane; its inferences retain evidence references.
    vc_strategy: dict[str, Any] = Field(default_factory=dict)

    # Versioned visual direction is an execution contract, never evidence.
    visual_intelligence: dict[str, Any] = Field(default_factory=dict)

    # Brand / visual identity
    brand_profile: BrandProfileSnapshot | None = None
    design_tokens: DesignTokens = Field(default_factory=DesignTokens)

    # References to approved assets
    assets: list[AssetReference] = Field(default_factory=list)

    # Product knowledge (launch variants, VC modules, etc.)
    product_knowledge: dict[str, Any] = Field(default_factory=dict)

    # Bounded non-source guidance. Neither lane is factual authority; source
    # facts and canonical source slides remain the only founder-claim inputs.
    agent_context: dict[str, Any] = Field(default_factory=dict)
    retrieved_guidance: dict[str, Any] = Field(default_factory=dict)

    # Generation constraints
    generation_constraints: GenerationConstraints = Field(default_factory=GenerationConstraints)
    output_contract: InstantDeckOutputContract = Field(default_factory=InstantDeckOutputContract)

    # For follow-up generation against a previous version
    base_design_version_id: str | None = None
    validated_baseline: dict[str, Any] | None = None

    # Metrics and analytics carried from the source
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    metric_sets: list[dict[str, Any]] = Field(default_factory=list)

    # Conflict / missing-input tracking
    accepted_decisions: list[dict[str, Any]] = Field(default_factory=list)
    missing_inputs: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Grounded context pack — typed version of the existing dict contract
# ---------------------------------------------------------------------------


class GroundedContextPack(BaseModel):
    """Typed version of the ``grounded-deck-context.v1`` contract.

    This is what gets JSON-serialized as the user message to the LLM.
    It is a strict subset / reshape of ``InstantDeckGenerationContext``
    formatted for provider consumption.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default="grounded-deck-context.v1", alias="contractVersion")
    deck_id: str = Field(alias="deckId")
    objective: str = ""
    audience: str | None = None
    deck_type: str | None = Field(None, alias="deckType")
    source_document_page_count: int | None = Field(None, alias="sourceDocumentPageCount")

    source_slides: list[dict[str, Any]] = Field(default_factory=list, alias="sourceSlides")
    source_facts: list[dict[str, Any]] = Field(default_factory=list, alias="sourceFacts")
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    metric_sets: list[dict[str, Any]] = Field(default_factory=list, alias="metricSets")
    approved_assets: list[dict[str, Any]] = Field(default_factory=list, alias="approvedAssets")
    brand: dict[str, Any] = Field(default_factory=dict)
    accepted_decisions: list[dict[str, Any]] = Field(default_factory=list, alias="acceptedDecisions")
    missing_inputs: list[dict[str, Any]] = Field(default_factory=list, alias="missingInputs")
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    base_design_version_id: str | None = Field(None, alias="baseDesignVersionId")
    source_policy: dict[str, Any] = Field(default_factory=lambda: {"allowAssumptions": False, "requireProvenanceForMaterialMetrics": True}, alias="sourcePolicy")
    claim_catalog: list[dict[str, Any]] = Field(default_factory=list, alias="claimCatalog")
    required_source_coverage: list[dict[str, Any]] = Field(default_factory=list, alias="requiredSourceCoverage")
    agent_context: dict[str, Any] = Field(default_factory=dict, alias="agentContext")
    retrieved_guidance: dict[str, Any] = Field(default_factory=dict, alias="retrievedGuidance")
    validated_baseline: dict[str, Any] | None = Field(None, alias="validatedBaseline")


# ---------------------------------------------------------------------------
# Transformation plan — maps source slides to generated output
# ---------------------------------------------------------------------------


class TransformationPlanSlide(BaseModel):
    """One planned output slide in the transformation plan.

    Defines how source material maps to a generated slide before
    the LLM produces HTML. This prevents silent content loss.
    """

    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(ge=0)
    purpose: str = ""
    source_slide_ids: list[str] = Field(default_factory=list)
    source_fact_ids: list[str] = Field(default_factory=list)
    treatment: str = "rewrite"  # "preserve" | "merge" | "split" | "rewrite" | "reorder"


class OmittedSourceSlide(BaseModel):
    """Records a source slide that is intentionally not mapped to any output."""

    model_config = ConfigDict(extra="forbid")

    source_slide_id: str
    reason: str


class DeckTransformationPlan(BaseModel):
    """A persisted plan describing how the source deck maps to the output.

    Created before generation to ensure every source slide is accounted for.
    Validated after generation to prove no material was silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "transformation-plan.v1"
    deck_id: str
    goal: str = ""
    narrative_strategy: str = ""
    visual_strategy: str = ""
    slides: list[TransformationPlanSlide] = Field(default_factory=list)
    omitted_sources: list[OmittedSourceSlide] = Field(default_factory=list)

    def covered_source_ids(self) -> set[str]:
        """Return all source slide IDs referenced by the plan."""
        ids: set[str] = set()
        for slide in self.slides:
            ids.update(slide.source_slide_ids)
        return ids

    def all_source_slide_ids(self) -> set[str]:
        """Return all source slide IDs from both mapped and omitted."""
        return self.covered_source_ids() | {o.source_slide_id for o in self.omitted_sources}

    def missing_source_ids(self, selected_ids: list[str]) -> list[str]:
        """Return source slide IDs from selected_ids not accounted for."""
        covered = self.all_source_slide_ids()
        return [sid for sid in selected_ids if sid not in covered]

    def duplicate_output_indices(self) -> list[int]:
        """Return output indices that appear more than once."""
        seen: dict[int, int] = {}
        dupes: list[int] = []
        for slide in self.slides:
            count = seen.get(slide.output_index, 0) + 1
            seen[slide.output_index] = count
            if count == 2:
                dupes.append(slide.output_index)
        return dupes


# ---------------------------------------------------------------------------
# Source coverage validation
# ---------------------------------------------------------------------------


class SourceCoverageGap(BaseModel):
    """A gap found during source coverage validation."""

    model_config = ConfigDict(extra="forbid")

    source_slide_id: str
    gap_type: str  # "missing_from_plan" | "duplicate_output_index" | "empty_treatment"


class SourceCoverageReport(BaseModel):
    """Result of validating a transformation plan against selected source slides."""

    model_config = ConfigDict(extra="forbid")

    is_complete: bool
    selected_count: int
    covered_count: int
    omitted_count: int
    gaps: list[SourceCoverageGap] = Field(default_factory=list)


def validate_source_coverage(
    plan: DeckTransformationPlan,
    selected_source_ids: list[str],
) -> SourceCoverageReport:
    """Validate that a transformation plan accounts for every selected source slide.

    Rules:
    - Every selected source slide must appear in plan.slides or plan.omitted_sources.
    - Output indices must be unique.
    - No gap type is tolerated silently.
    """
    gaps: list[SourceCoverageGap] = []

    # Check for missing source slides
    missing = plan.missing_source_ids(selected_source_ids)
    for sid in missing:
        gaps.append(SourceCoverageGap(source_slide_id=sid, gap_type="missing_from_plan"))

    # Check for duplicate output indices
    dupes = plan.duplicate_output_indices()
    for idx in dupes:
        gaps.append(SourceCoverageGap(source_slide_id=f"output_index_{idx}", gap_type="duplicate_output_index"))

    covered = plan.covered_source_ids()
    omitted = {o.source_slide_id for o in plan.omitted_sources}

    return SourceCoverageReport(
        is_complete=len(gaps) == 0,
        selected_count=len(selected_source_ids),
        covered_count=len(covered & set(selected_source_ids)),
        omitted_count=len(omitted & set(selected_source_ids)),
        gaps=gaps,
    )


# ---------------------------------------------------------------------------
# Output contract — typed version of the LLM output
# ---------------------------------------------------------------------------


class FactUsage(BaseModel):
    """Tracks which source facts were used in the generated output."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    used_in_slide_ids: list[str] = Field(default_factory=list)


class GeneratedSlideManifest(BaseModel):
    """Manifest entry for one generated slide in the output."""

    model_config = ConfigDict(extra="forbid")

    slide_id: str
    output_index: int
    source_slide_ids: list[str] = Field(default_factory=list)
    source_fact_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    html_section: str = ""  # the HTML for this slide section


class DesignMetadata(BaseModel):
    """Metadata about the generated design."""

    model_config = ConfigDict(extra="forbid")

    variant_id: str | None = None
    variant_rationale: str | None = None
    narrative_strategy: str = ""
    visual_strategy: str = ""
    section_count: int = 0
    source_coverage_complete: bool = False


class InstantDeckOutput(BaseModel):
    """Canonical typed output from Instant Deck generation.

    This is what the LLM should produce (or what the backend extracts
    from the LLM's HTML response). It becomes the basis for the
    persisted DesignVersion.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "instant-deck-output.v1"
    document_html: str = ""
    slides: list[GeneratedSlideManifest] = Field(default_factory=list)
    fact_usage: list[FactUsage] = Field(default_factory=list)
    design_metadata: DesignMetadata = Field(default_factory=DesignMetadata)
    transformation_plan_hash: str | None = None
    source_coverage_complete: bool = False

    def all_source_slide_ids(self) -> set[str]:
        """Return all source slide IDs referenced across all slides."""
        ids: set[str] = set()
        for slide in self.slides:
            ids.update(slide.source_slide_ids)
        return ids

    def all_source_fact_ids(self) -> set[str]:
        """Return all source fact IDs referenced across all slides."""
        ids: set[str] = set()
        for slide in self.slides:
            ids.update(slide.source_fact_ids)
        return ids
