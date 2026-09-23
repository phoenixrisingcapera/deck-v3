"""Offline, source-bound whole-deck planning contract v4.

Planner v4 is additive and deliberately unmounted.  It consumes the strict
``instant-deck-source-package.v2`` contract, validates deck-level strategy and
cross-slide relationships, and deterministically normalizes to the historical
``deck_spec.v1`` domain model.  It performs no provider, network, persistence,
worker, or publication operation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
import json
import re
from typing import Annotated, Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from .grammar import grammar_for
from .models import (
    ArtDirectionSpec,
    CompositionSpec,
    CompositionVariant,
    CopyBlock,
    DeckSpec,
    NarrativeSpec,
    NormalizedSourcePackage,
    SlideArchetype,
    SlideSpec,
    VisualEdge,
    VisualItem,
    VisualMetric,
    VisualPerson,
    VisualSpec,
    VisualStep,
    VisualType,
)
from .source_package import canonical_sha256
from .source_package_v2 import (
    AssetSemanticRole,
    MaterialityBand,
    NormalizedSourcePackageV2,
    ProtectedCoverageCategory,
)


PLANNER_SCHEMA_VERSION_V4 = "planner_deck_spec.v4"
PLANNER_NORMALIZER_VERSION_V4 = "instant-deck-planner-normalizer.v4"


class PlannerV4Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class SemanticSlideRoleV4(str, Enum):
    COVER = "cover"
    THESIS = "thesis"
    PROBLEM = "problem"
    SOLUTION = "solution"
    PROCESS = "process"
    TRACTION = "traction"
    BUSINESS_MODEL = "business_model"
    MARKET_OPPORTUNITY = "market_opportunity"
    FOUNDER_TEAM = "founder_team"
    ECOSYSTEM = "ecosystem"
    NETWORK_DEFENSIBILITY = "network_defensibility"
    INVESTMENT_PROPOSITION = "investment_proposition"
    CLOSING = "closing"


class CommercialCoverageStatusV4(str, Enum):
    PRESENT = "present"
    MISSING = "missing"


class MaterialExclusionReasonV4(str, Enum):
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    SUPERSEDED_VALUE = "superseded_value"
    INCOMPATIBLE_AUDIENCE_PURPOSE = "incompatible_audience_purpose"
    UNSUPPORTED_OR_AMBIGUOUS_SOURCE = "unsupported_or_ambiguous_source"
    LIMITED_RELEVANCE = "limited_relevance_to_selected_narrative"


class CopyBudgetProfileV4(str, Enum):
    COVER = "cover"
    THESIS_PROBLEM = "thesis_problem"
    PROCESS_PRODUCT = "process_product"
    EVIDENCE_TRACTION = "evidence_traction"
    BUSINESS_MARKET = "business_market"
    FOUNDER_NETWORK = "founder_network"
    CLOSING = "closing"


class CompositionSilhouetteV4(str, Enum):
    HERO = "hero"
    MONUMENT = "monument"
    LANDSCAPE = "landscape"
    SPLIT = "split"
    PATHWAY = "pathway"
    METRIC = "metric"
    FLOW = "flow"
    PORTRAIT = "portrait"
    NETWORK = "network"
    CAPITAL = "capital"
    CLOSE = "close"


class TonalModeV4(str, Enum):
    PAPER = "paper"
    INK = "ink"
    SIGNATURE = "signature"
    IMAGE_LED = "image_led"
    QUIET = "quiet"


class AssetIntentRoleV4(str, Enum):
    NONE = "none"
    LITERAL_LOGO = "literal_logo"
    WORDMARK = "wordmark"
    BRAND_SYMBOL = "brand_symbol"
    BRAND_ARCHITECTURE = "brand_architecture"
    EVENT_PHOTOGRAPHY = "event_photography"
    FOUNDER_PORTRAIT = "founder_portrait"
    PROGRAMME_IMAGERY = "programme_imagery"
    EVIDENCE_IMAGE = "evidence_image"
    DIAGRAM = "diagram"


class AssetTreatmentV4(str, Enum):
    NONE = "none"
    CONTAIN = "contain"
    COVER = "cover"
    EDGE_CROP = "edge_crop"
    FULL_BLEED = "full_bleed"
    WATERMARK = "watermark"


class MetricEncodingV4(str, Enum):
    NONE = "none"
    SINGLE_METRIC = "single_metric"
    INDEPENDENT_STATS = "independent_stats"
    SHARED_SCALE = "shared_scale"
    ORDINAL_STAGES = "ordinal_stages"


class CompilerSupportV4(str, Enum):
    COMPILER_V2 = "compiler_v2"
    COMPILER_V3_REQUIRED = "compiler_v3_required"


class PlannerMaterialExclusionV4(PlannerV4Model):
    fact_id: str
    reason: MaterialExclusionReasonV4
    explanation: Annotated[str, StringConstraints(min_length=12, max_length=180)]
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class PlannerCommercialCategoryV4(PlannerV4Model):
    category: ProtectedCoverageCategory
    source_status: CommercialCoverageStatusV4
    used_fact_ids: list[str] = Field(min_length=0, max_length=8)
    exclusions: list[PlannerMaterialExclusionV4] = Field(min_length=0, max_length=8)


class PlannerBrandDirectionV4(PlannerV4Model):
    concept: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    tone: Literal[
        "editorial",
        "austere",
        "technical",
        "human",
        "bold",
        "atmospheric",
        "playful",
        "luxury",
    ]
    display_strategy: Literal[
        "serif_contrast",
        "grotesk_monument",
        "humanist",
        "condensed",
        "mono_technical",
    ]
    motif: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    paper_role: str
    ink_role: str
    signature_role: str
    support_roles: list[str] = Field(min_length=0, max_length=3)


class PlannerVisualRhythmV4(PlannerV4Model):
    tonal_sequence: list[TonalModeV4] = Field(min_length=8, max_length=14)
    silhouette_sequence: list[CompositionSilhouetteV4] = Field(min_length=8, max_length=14)
    image_led_positions: list[int] = Field(min_length=0, max_length=5)
    evidence_rich_positions: list[int] = Field(min_length=1, max_length=6)
    breathing_space_positions: list[int] = Field(min_length=0, max_length=2)


class PlannerDeckAssetUseV4(PlannerV4Model):
    asset_id: str
    role: AssetIntentRoleV4
    treatment: AssetTreatmentV4
    slide_positions: list[int] = Field(min_length=1, max_length=4)


class PlannerAssetStrategyV4(PlannerV4Model):
    high_value_asset_ids: list[str] = Field(min_length=0, max_length=12)
    required_asset_ids: list[str] = Field(min_length=0, max_length=8)
    uses: list[PlannerDeckAssetUseV4] = Field(min_length=0, max_length=12)


class PlannerDeckStrategyV4(PlannerV4Model):
    audience: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=140)]
    desired_decision: Annotated[str, StringConstraints(min_length=1, max_length=140)]
    central_thesis: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    narrative_tension: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    narrative_arc: list[SemanticSlideRoleV4] = Field(min_length=8, max_length=14)
    opening_promise: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    closing_resolution: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    mandatory_fact_ids: list[str] = Field(min_length=0, max_length=24)
    commercial_coverage: list[PlannerCommercialCategoryV4] = Field(
        min_length=4,
        max_length=4,
    )
    brand_direction: PlannerBrandDirectionV4
    visual_rhythm: PlannerVisualRhythmV4
    asset_strategy: PlannerAssetStrategyV4


class PlannerCopyV4(PlannerV4Model):
    kind: Literal["assertion", "body", "label", "caption", "quote"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    emphasis: Literal["primary", "secondary", "quiet"]


class PlannerVisualItemV4(PlannerV4Model):
    item_id: Annotated[str, StringConstraints(pattern=r"^v[0-9]{2}$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=140)] | None
    value: Annotated[str, StringConstraints(min_length=1, max_length=48)] | None
    group: Annotated[str, StringConstraints(min_length=1, max_length=48)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    asset_ref: str | None


class PlannerMetricV4(PlannerV4Model):
    metric_id: Annotated[str, StringConstraints(pattern=r"^m[0-9]{2}$")]
    number_ref: str
    value: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    context: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None


class PlannerStepV4(PlannerV4Model):
    step_id: Annotated[str, StringConstraints(pattern=r"^t[0-9]{2}$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class PlannerPersonV4(PlannerV4Model):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    role: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    proof: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    asset_ref: str | None


class PlannerEdgeV4(PlannerV4Model):
    from_item_id: Annotated[str, StringConstraints(pattern=r"^v[0-9]{2}$")]
    to_item_id: Annotated[str, StringConstraints(pattern=r"^v[0-9]{2}$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class PlannerVisualV4(PlannerV4Model):
    metric_encoding: MetricEncodingV4
    items: list[PlannerVisualItemV4] = Field(min_length=0, max_length=10)
    metrics: list[PlannerMetricV4] = Field(min_length=0, max_length=6)
    steps: list[PlannerStepV4] = Field(min_length=0, max_length=7)
    people: list[PlannerPersonV4] = Field(min_length=0, max_length=6)
    edges: list[PlannerEdgeV4] = Field(min_length=0, max_length=14)


class PlannerAssetIntentV4(PlannerV4Model):
    asset_ref: str | None
    role: AssetIntentRoleV4
    treatment: AssetTreatmentV4
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None


class PlannerCopyBudgetV4(PlannerV4Model):
    profile: CopyBudgetProfileV4
    audience_facing_words: int = Field(ge=0, le=180)


class PlannerSlideV4(PlannerV4Model):
    slide_id: Annotated[str, StringConstraints(pattern=r"^p[0-9]{2}$")]
    position: int = Field(ge=1, le=14)
    semantic_role: SemanticSlideRoleV4
    narrative_job: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    audience_claim: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    consequence: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    headline: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    subhead: Annotated[str, StringConstraints(min_length=1, max_length=180)] | None
    body: list[PlannerCopyV4] = Field(min_length=0, max_length=3)
    evidence_ids: list[str] = Field(min_length=1, max_length=14)
    protected_fact_ids: list[str] = Field(min_length=0, max_length=8)
    source_slide_ids: list[str] = Field(min_length=1, max_length=8)
    visual_archetype: SlideArchetype
    composition_variant: CompositionVariant
    composition_silhouette: CompositionSilhouetteV4
    visual_type: VisualType
    visual: PlannerVisualV4
    asset_intent: PlannerAssetIntentV4
    previous_argument_id: str | None
    next_argument_id: str | None
    resolves_argument_ids: list[str] = Field(min_length=0, max_length=6)
    opens_question: bool
    copy_budget: PlannerCopyBudgetV4
    compiler_support: CompilerSupportV4
    compiler_gap_code: str | None


class PlannerDeckSpecV4(PlannerV4Model):
    schema_version: Literal["planner_deck_spec.v4"]
    normalizer_version: Literal["instant-deck-planner-normalizer.v4"]
    source_package_id: str
    source_checksum: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    deck_title: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    deck_strategy: PlannerDeckStrategyV4
    slides: list[PlannerSlideV4] = Field(min_length=8, max_length=14)


@dataclass(frozen=True, slots=True)
class PlannerV4Issue:
    code: str
    path: str
    message: str


class PlannerV4ValidationError(ValueError):
    def __init__(self, issues: Iterable[PlannerV4Issue]):
        self.issues = tuple(issues)
        summary = "; ".join(f"{row.code}@{row.path}" for row in self.issues)
        super().__init__(summary or "planner_v4_validation_failed")


@dataclass(frozen=True, slots=True)
class CompilerV3GapV4:
    slide_id: str
    position: int
    semantic_role: str
    canonical_archetype: str
    gap_code: str


_ROLE_BUDGETS: dict[SemanticSlideRoleV4, tuple[CopyBudgetProfileV4, int, int]] = {
    SemanticSlideRoleV4.COVER: (CopyBudgetProfileV4.COVER, 10, 35),
    SemanticSlideRoleV4.THESIS: (CopyBudgetProfileV4.THESIS_PROBLEM, 30, 85),
    SemanticSlideRoleV4.PROBLEM: (CopyBudgetProfileV4.THESIS_PROBLEM, 30, 85),
    SemanticSlideRoleV4.SOLUTION: (CopyBudgetProfileV4.PROCESS_PRODUCT, 35, 95),
    SemanticSlideRoleV4.PROCESS: (CopyBudgetProfileV4.PROCESS_PRODUCT, 35, 95),
    SemanticSlideRoleV4.TRACTION: (CopyBudgetProfileV4.EVIDENCE_TRACTION, 35, 110),
    SemanticSlideRoleV4.BUSINESS_MODEL: (CopyBudgetProfileV4.BUSINESS_MARKET, 45, 120),
    SemanticSlideRoleV4.MARKET_OPPORTUNITY: (
        CopyBudgetProfileV4.BUSINESS_MARKET,
        45,
        120,
    ),
    SemanticSlideRoleV4.FOUNDER_TEAM: (CopyBudgetProfileV4.FOUNDER_NETWORK, 35, 100),
    SemanticSlideRoleV4.ECOSYSTEM: (CopyBudgetProfileV4.FOUNDER_NETWORK, 35, 100),
    SemanticSlideRoleV4.NETWORK_DEFENSIBILITY: (
        CopyBudgetProfileV4.FOUNDER_NETWORK,
        35,
        100,
    ),
    SemanticSlideRoleV4.INVESTMENT_PROPOSITION: (
        CopyBudgetProfileV4.BUSINESS_MARKET,
        45,
        120,
    ),
    SemanticSlideRoleV4.CLOSING: (CopyBudgetProfileV4.CLOSING, 20, 70),
}

_COMPILER_V2_ARCHETYPES = {
    SlideArchetype.THESIS_COVER,
    SlideArchetype.PROBLEM_LANDSCAPE,
    SlideArchetype.KEY_INSIGHT,
    SlideArchetype.PROCESS_PATHWAY,
    SlideArchetype.TIMELINE_MILESTONES,
    SlideArchetype.METRIC_PROOF,
    SlideArchetype.SYSTEM_MAP,
    SlideArchetype.COMPARISON_SHIFT,
}

_NARRATIVE_ARC = {
    SemanticSlideRoleV4.COVER: "identity",
    SemanticSlideRoleV4.THESIS: "proposition",
    SemanticSlideRoleV4.PROBLEM: "problem",
    SemanticSlideRoleV4.SOLUTION: "solution",
    SemanticSlideRoleV4.PROCESS: "product_system",
    SemanticSlideRoleV4.TRACTION: "traction",
    SemanticSlideRoleV4.BUSINESS_MODEL: "business_model",
    SemanticSlideRoleV4.MARKET_OPPORTUNITY: "market",
    SemanticSlideRoleV4.FOUNDER_TEAM: "team",
    SemanticSlideRoleV4.ECOSYSTEM: "partnerships",
    SemanticSlideRoleV4.NETWORK_DEFENSIBILITY: "partnerships",
    SemanticSlideRoleV4.INVESTMENT_PROPOSITION: "capital_plan",
    SemanticSlideRoleV4.CLOSING: "decision",
}


def planner_v4_slide_bounds(package: NormalizedSourcePackageV2) -> tuple[int, int]:
    material_sources = len(
        {source_id for row in package.protected_coverage for source_id in row.source_slide_ids}
    )
    if len(package.source_slides) >= 10 or material_sources >= 6:
        return 10, 11
    return 8, 10


def _nullable_ref(name: str) -> dict[str, Any]:
    return {"anyOf": [{"$ref": f"#/$defs/{name}"}, {"type": "null"}]}


def source_bound_planner_schema_v4(package: NormalizedSourcePackageV2) -> dict[str, Any]:
    """Bind Planner v4 to the finite IDs in one request-scoped source package."""

    schema = PlannerDeckSpecV4.model_json_schema()
    protected = sorted(
        {fact_id for row in package.protected_coverage for fact_id in row.protected_fact_ids}
    )
    evidence = sorted(
        {row.fact_id for row in package.facts}
        | {row.claim_id for row in package.claims}
        | {row.number_id for row in package.numbers}
    )
    definitions = schema.setdefault("$defs", {})
    definitions.update(
        {
            "AllowedEvidenceId": {"type": "string", "enum": evidence},
            "AllowedProtectedFactId": {"type": "string", "enum": protected},
            "AllowedSourceSlideId": {
                "type": "string",
                "enum": [row.source_slide_id for row in package.source_slides],
            },
            "AllowedAssetId": {
                "type": "string",
                "enum": [row.asset_id for row in package.assets],
            },
            "AllowedNumberId": {
                "type": "string",
                "enum": [row.number_id for row in package.numbers],
            },
            "AllowedBrandRole": {
                "type": "string",
                "enum": [row.role_id for row in package.brand.roles],
            },
        }
    )

    array_refs = {
        "evidence_ids": "AllowedEvidenceId",
        "mandatory_fact_ids": "AllowedProtectedFactId",
        "used_fact_ids": "AllowedProtectedFactId",
        "protected_fact_ids": "AllowedProtectedFactId",
        "source_slide_ids": "AllowedSourceSlideId",
        "high_value_asset_ids": "AllowedAssetId",
        "required_asset_ids": "AllowedAssetId",
        "support_roles": "AllowedBrandRole",
    }
    scalar_refs = {
        "fact_id": "AllowedProtectedFactId",
        "number_ref": "AllowedNumberId",
        "asset_id": "AllowedAssetId",
        "paper_role": "AllowedBrandRole",
        "ink_role": "AllowedBrandRole",
        "signature_role": "AllowedBrandRole",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("discriminator", None)
            if "oneOf" in value:
                value["anyOf"] = value.pop("oneOf")
            properties = value.get("properties")
            if isinstance(properties, dict):
                for key, child in list(properties.items()):
                    if key in array_refs:
                        child["items"] = {"$ref": f"#/$defs/{array_refs[key]}"}
                    elif key in scalar_refs:
                        properties[key] = {"$ref": f"#/$defs/{scalar_refs[key]}"}
                    elif key == "asset_ref":
                        properties[key] = _nullable_ref("AllowedAssetId")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    minimum, maximum = planner_v4_slide_bounds(package)
    schema["properties"]["slides"]["minItems"] = minimum
    schema["properties"]["slides"]["maxItems"] = maximum
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://deck.aistack.codes/schemas/planner-deck-spec.v4.json"
    return schema


def validate_provider_schema_compatibility_v4(schema: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    def visit(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                properties = value.get("properties", {})
                if value.get("additionalProperties") is not False:
                    issues.append(f"{path}:additionalProperties")
                if set(value.get("required", [])) != set(properties):
                    issues.append(f"{path}:required")
            if "default" in value:
                issues.append(f"{path}:default")
            if any(key in value for key in ("oneOf", "allOf", "discriminator")):
                issues.append(f"{path}:unsupported_composition_keyword")
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(schema)
    return issues


def _issue(
    issues: list[PlannerV4Issue],
    code: str,
    path: str,
    message: str,
) -> None:
    issues.append(PlannerV4Issue(code=code, path=path, message=message))


def _duplicates(values: Iterable[str | int | Enum]) -> set[str | int | Enum]:
    seen: set[str | int | Enum] = set()
    duplicates: set[str | int | Enum] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _words(value: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", value, flags=re.UNICODE))


def audience_facing_word_count_v4(slide: PlannerSlideV4) -> int:
    values = [
        slide.audience_claim,
        slide.consequence,
        slide.headline,
        slide.subhead or "",
        *(row.text for row in slide.body),
        *(row.label for row in slide.visual.items),
        *(row.detail or "" for row in slide.visual.items),
        *(row.value or "" for row in slide.visual.items),
        *(row.value for row in slide.visual.metrics),
        *(row.label for row in slide.visual.metrics),
        *(row.context or "" for row in slide.visual.metrics),
        *(row.label for row in slide.visual.steps),
        *(row.detail or "" for row in slide.visual.steps),
        *(row.name for row in slide.visual.people),
        *(row.role for row in slide.visual.people),
        *(row.proof for row in slide.visual.people),
    ]
    return sum(_words(value) for value in values)


def _evidence_sources(package: NormalizedSourcePackageV2) -> dict[str, set[str]]:
    reference_sources = {row.reference_id: row.source_slide_id for row in package.source_references}
    rows = [*package.facts, *package.claims, *package.numbers]
    result: dict[str, set[str]] = {}
    for row in rows:
        identifier = getattr(
            row,
            "fact_id",
            getattr(row, "claim_id", getattr(row, "number_id", "")),
        )
        result[identifier] = {
            reference_sources[reference]
            for reference in row.source_reference_ids
            if reference in reference_sources
        }
    return result


def _canonical_metric(value: str) -> str:
    return re.sub(r"[\s,]", "", value).casefold()


def _metric_semantics_text(metric: PlannerMetricV4) -> str:
    return " ".join(
        value for value in (metric.value, metric.label, metric.context or "") if value
    ).casefold()


def _unit_is_preserved(unit: str | None, metric: PlannerMetricV4) -> bool:
    if not unit:
        return True
    text = _metric_semantics_text(metric)
    normalized = unit.casefold()
    if normalized in {"usd", "us dollars", "dollars"}:
        return "$" in metric.value or "usd" in text or "dollar" in text
    if normalized in {"eur", "euros"}:
        return "€" in metric.value or "eur" in text or "euro" in text
    if normalized in {"%", "percent", "percentage"}:
        return "%" in metric.value or "percent" in text
    return normalized in text


def _commercial_validation(
    planner: PlannerDeckSpecV4,
    package: NormalizedSourcePackageV2,
    issues: list[PlannerV4Issue],
) -> None:
    package_rows = {row.category: row for row in package.protected_coverage}
    plan_rows = {row.category: row for row in planner.deck_strategy.commercial_coverage}
    if len(plan_rows) != 4 or set(plan_rows) != set(ProtectedCoverageCategory):
        _issue(
            issues,
            "commercial_coverage_categories_invalid",
            "deck_strategy.commercial_coverage",
            "Every protected category must appear exactly once.",
        )
        return

    used_by_slides = {fact_id for slide in planner.slides for fact_id in slide.protected_fact_ids}
    all_protected = {
        fact_id for row in package.protected_coverage for fact_id in row.protected_fact_ids
    }
    if set(planner.deck_strategy.mandatory_fact_ids) != all_protected:
        _issue(
            issues,
            "mandatory_fact_manifest_mismatch",
            "deck_strategy.mandatory_fact_ids",
            "The strategy must enumerate every protected source fact.",
        )

    facts = {row.fact_id: row for row in package.facts}
    conflict_evidence = {evidence for row in package.conflicts for evidence in row.evidence_ids}
    for category in ProtectedCoverageCategory:
        source = package_rows[category]
        plan = plan_rows[category]
        expected_status = CommercialCoverageStatusV4(source.status)
        if plan.source_status != expected_status:
            _issue(
                issues,
                "commercial_source_status_mismatch",
                f"deck_strategy.commercial_coverage.{category.value}",
                f"{plan.source_status.value}!={source.status}",
            )
        protected = set(source.protected_fact_ids)
        used = protected & used_by_slides
        excluded = {row.fact_id for row in plan.exclusions}
        if set(plan.used_fact_ids) != used:
            _issue(
                issues,
                "commercial_used_fact_manifest_mismatch",
                f"deck_strategy.commercial_coverage.{category.value}.used_fact_ids",
                "Used fact IDs must match slide-level protected fact use.",
            )
        if plan.source_status == CommercialCoverageStatusV4.MISSING:
            if plan.used_fact_ids or plan.exclusions:
                _issue(
                    issues,
                    "fabricated_missing_category",
                    f"deck_strategy.commercial_coverage.{category.value}",
                    "A missing source category cannot contain invented coverage.",
                )
            continue
        if used | excluded != protected or used & excluded:
            code = {
                ProtectedCoverageCategory.FINANCIAL: "missing_protected_financial_fact",
                ProtectedCoverageCategory.TRACTION: "missing_protected_traction_fact",
                ProtectedCoverageCategory.FOUNDER: "missing_protected_founder_fact",
                ProtectedCoverageCategory.ASK: "missing_protected_ask_fact",
            }[category]
            _issue(
                issues,
                code,
                f"deck_strategy.commercial_coverage.{category.value}",
                "Every protected fact must be used or validly excluded.",
            )
        for exclusion in plan.exclusions:
            fact = facts.get(exclusion.fact_id)
            if fact is None or exclusion.fact_id not in protected:
                _issue(
                    issues,
                    "invalid_material_exclusion_fact",
                    f"deck_strategy.commercial_coverage.{category.value}.exclusions",
                    exclusion.fact_id,
                )
                continue
            if exclusion.fact_id not in exclusion.evidence_ids:
                _issue(
                    issues,
                    "material_exclusion_not_source_grounded",
                    f"deck_strategy.commercial_coverage.{category.value}.exclusions",
                    exclusion.fact_id,
                )
            if exclusion.reason in {
                MaterialExclusionReasonV4.INCOMPATIBLE_AUDIENCE_PURPOSE,
                MaterialExclusionReasonV4.LIMITED_RELEVANCE,
            } and fact.materiality_band in {MaterialityBand.CRITICAL, MaterialityBand.HIGH}:
                _issue(
                    issues,
                    "high_materiality_exclusion_forbidden",
                    f"deck_strategy.commercial_coverage.{category.value}.exclusions",
                    exclusion.fact_id,
                )
            if (
                exclusion.reason
                in {
                    MaterialExclusionReasonV4.SUPERSEDED_VALUE,
                    MaterialExclusionReasonV4.UNSUPPORTED_OR_AMBIGUOUS_SOURCE,
                }
                and exclusion.fact_id not in conflict_evidence
            ):
                _issue(
                    issues,
                    "unsupported_exclusion_reason",
                    f"deck_strategy.commercial_coverage.{category.value}.exclusions",
                    exclusion.fact_id,
                )
            if exclusion.reason == MaterialExclusionReasonV4.DUPLICATE_EVIDENCE:
                duplicate_candidates = [
                    facts[fact_id]
                    for fact_id in used
                    if fact_id in facts and fact_id in exclusion.evidence_ids
                ]
                if not any(
                    candidate.kind == fact.kind
                    and SequenceMatcher(
                        a=_normalize_text(candidate.text),
                        b=_normalize_text(fact.text),
                    ).ratio()
                    >= 0.82
                    for candidate in duplicate_candidates
                ):
                    _issue(
                        issues,
                        "duplicate_evidence_exclusion_unsubstantiated",
                        f"deck_strategy.commercial_coverage.{category.value}.exclusions",
                        exclusion.fact_id,
                    )


def _asset_validation(
    planner: PlannerDeckSpecV4,
    package: NormalizedSourcePackageV2,
    issues: list[PlannerV4Issue],
) -> None:
    assets = {row.asset_id: row for row in package.assets}
    high_value = {
        row.asset_id
        for row in package.assets
        if row.required_for_planner
        or row.semantic_role
        in {
            AssetSemanticRole.LITERAL_LOGO,
            AssetSemanticRole.WORDMARK,
            AssetSemanticRole.FOUNDER_PORTRAIT,
        }
    }
    strategy = planner.deck_strategy.asset_strategy
    if set(strategy.high_value_asset_ids) != high_value:
        _issue(
            issues,
            "high_value_asset_manifest_mismatch",
            "deck_strategy.asset_strategy.high_value_asset_ids",
            "Every high-value source asset must be declared.",
        )
    if set(strategy.required_asset_ids) != high_value:
        _issue(
            issues,
            "required_asset_manifest_mismatch",
            "deck_strategy.asset_strategy.required_asset_ids",
            "High-value planner assets are mandatory in this offline contract.",
        )

    slide_uses: dict[str, list[int]] = {}
    for index, slide in enumerate(planner.slides):
        intent = slide.asset_intent
        path = f"slides[{index}].asset_intent"
        if intent.asset_ref is None:
            if (
                intent.role != AssetIntentRoleV4.NONE
                or intent.treatment != AssetTreatmentV4.NONE
                or intent.rationale is not None
            ):
                _issue(issues, "empty_asset_intent_inconsistent", path, slide.slide_id)
            continue
        asset = assets.get(intent.asset_ref)
        if asset is None:
            _issue(issues, "unsupported_asset_reference", path, intent.asset_ref)
            continue
        slide_uses.setdefault(intent.asset_ref, []).append(slide.position)
        if intent.role.value != asset.semantic_role.value:
            code = (
                "brand_image_used_as_literal_logo"
                if intent.role in {AssetIntentRoleV4.LITERAL_LOGO, AssetIntentRoleV4.WORDMARK}
                else "asset_semantic_role_mismatch"
            )
            _issue(issues, code, path, f"{intent.role.value}!={asset.semantic_role.value}")
        if intent.rationale is None:
            _issue(issues, "asset_rationale_missing", path, intent.asset_ref)
        if asset.semantic_role == AssetSemanticRole.FOUNDER_PORTRAIT:
            if slide.semantic_role != SemanticSlideRoleV4.FOUNDER_TEAM:
                _issue(
                    issues,
                    "founder_portrait_without_founder_credibility",
                    path,
                    slide.slide_id,
                )
            founder_facts = {
                fact_id
                for row in package.protected_coverage
                if row.category == ProtectedCoverageCategory.FOUNDER
                for fact_id in row.protected_fact_ids
            }
            if not founder_facts & set(slide.protected_fact_ids):
                _issue(
                    issues,
                    "founder_portrait_without_founder_evidence",
                    path,
                    slide.slide_id,
                )

    for asset_id in high_value - set(slide_uses):
        asset = assets[asset_id]
        code = (
            "unused_high_value_portrait"
            if asset.semantic_role == AssetSemanticRole.FOUNDER_PORTRAIT
            else "unused_high_value_asset"
        )
        _issue(issues, code, "deck_strategy.asset_strategy", asset_id)

    strategy_uses = {row.asset_id: row for row in strategy.uses}
    if len(strategy_uses) != len(strategy.uses):
        _issue(
            issues,
            "duplicate_asset_strategy_use",
            "deck_strategy.asset_strategy.uses",
            "Asset strategy entries must be unique.",
        )
    for asset_id in set(strategy_uses) - set(assets):
        _issue(
            issues,
            "unsupported_asset_strategy_reference",
            "deck_strategy.asset_strategy.uses",
            asset_id,
        )
    for asset_id, positions in slide_uses.items():
        row = strategy_uses.get(asset_id)
        if row is None or row.slide_positions != positions:
            _issue(
                issues,
                "asset_strategy_use_mismatch",
                "deck_strategy.asset_strategy.uses",
                asset_id,
            )


def _visual_and_metric_validation(
    slide: PlannerSlideV4,
    package: NormalizedSourcePackageV2,
    path: str,
    issues: list[PlannerV4Issue],
) -> None:
    numbers = {row.number_id: row for row in package.numbers}
    item_ids = {row.item_id for row in slide.visual.items}
    for edge in slide.visual.edges:
        if edge.from_item_id not in item_ids or edge.to_item_id not in item_ids:
            _issue(
                issues,
                "unknown_visual_edge_endpoint",
                f"{path}.visual.edges",
                f"{edge.from_item_id}->{edge.to_item_id}",
            )
    if slide.visual.metric_encoding == MetricEncodingV4.SHARED_SCALE:
        units = {
            numbers[row.number_ref].unit
            for row in slide.visual.metrics
            if row.number_ref in numbers
        }
        if len(units) != 1 or None in units:
            _issue(
                issues,
                "mixed_unit_shared_scale",
                f"{path}.visual.metrics",
                str(sorted(str(unit) for unit in units)),
            )
    if slide.visual.steps and slide.visual.metric_encoding in {
        MetricEncodingV4.SINGLE_METRIC,
        MetricEncodingV4.INDEPENDENT_STATS,
        MetricEncodingV4.SHARED_SCALE,
    }:
        _issue(
            issues,
            "ordinal_stages_rendered_as_quantitative_bars",
            f"{path}.visual.metric_encoding",
            slide.visual.metric_encoding.value,
        )
    if slide.visual.metric_encoding == MetricEncodingV4.ORDINAL_STAGES:
        if not slide.visual.steps or slide.visual.metrics:
            _issue(
                issues,
                "ordinal_stage_contract_invalid",
                f"{path}.visual",
                slide.slide_id,
            )
    if slide.visual.metric_encoding == MetricEncodingV4.NONE and slide.visual.metrics:
        _issue(
            issues,
            "metric_encoding_missing",
            f"{path}.visual.metric_encoding",
            slide.slide_id,
        )
    for metric in slide.visual.metrics:
        number = numbers.get(metric.number_ref)
        if number is None:
            _issue(issues, "unknown_number_reference", f"{path}.visual.metrics", metric.number_ref)
            continue
        if _canonical_metric(metric.value) != _canonical_metric(number.exact_text):
            _issue(
                issues,
                "metric_value_unit_or_magnitude_altered",
                f"{path}.visual.metrics.{metric.metric_id}",
                f"{metric.value}!={number.exact_text}",
            )
        if not _unit_is_preserved(number.unit, metric):
            _issue(
                issues,
                "metric_unit_lost",
                f"{path}.visual.metrics.{metric.metric_id}",
                str(number.unit),
            )
        temporal_terms = set(
            re.findall(
                r"\b(?:annual|annually|year|yearly|quarter|quarterly|month|monthly|week|weekly|day|daily)\b",
                " ".join((number.exact_text, number.qualifier or "")).casefold(),
            )
        )
        if temporal_terms and not temporal_terms & set(
            re.findall(r"[a-z]+", _metric_semantics_text(metric))
        ):
            _issue(
                issues,
                "metric_time_basis_lost",
                f"{path}.visual.metrics.{metric.metric_id}",
                ",".join(sorted(temporal_terms)),
            )
        if metric.number_ref not in slide.evidence_ids:
            _issue(
                issues,
                "metric_number_not_in_slide_evidence",
                f"{path}.visual.metrics.{metric.metric_id}",
                metric.number_ref,
            )


def validate_planner_deck_spec_v4(
    planner: PlannerDeckSpecV4,
    package: NormalizedSourcePackageV2,
) -> None:
    issues: list[PlannerV4Issue] = []
    if planner.source_package_id != package.package_id:
        _issue(
            issues,
            "source_package_identity_mismatch",
            "source_package_id",
            planner.source_package_id,
        )
    if planner.source_checksum != package.source_checksum:
        _issue(
            issues,
            "source_checksum_mismatch",
            "source_checksum",
            planner.source_checksum,
        )

    valid_brand_roles = {row.role_id for row in package.brand.roles}
    brand_direction = planner.deck_strategy.brand_direction
    selected_brand_roles = {
        brand_direction.paper_role,
        brand_direction.ink_role,
        brand_direction.signature_role,
        *brand_direction.support_roles,
    }
    for role in sorted(selected_brand_roles - valid_brand_roles):
        _issue(
            issues,
            "unknown_source_brand_role",
            "deck_strategy.brand_direction",
            role,
        )

    minimum, maximum = planner_v4_slide_bounds(package)
    if not minimum <= len(planner.slides) <= maximum:
        _issue(
            issues,
            "planner_slide_count_outside_source_bound",
            "slides",
            f"{len(planner.slides)} not in {minimum}..{maximum}",
        )
    positions = [row.position for row in planner.slides]
    if positions != list(range(1, len(planner.slides) + 1)):
        _issue(issues, "invalid_slide_order", "slides", str(positions))
    for duplicate in _duplicates(row.slide_id for row in planner.slides):
        _issue(issues, "duplicate_slide_id", "slides", str(duplicate))
    for duplicate in _duplicates(row.semantic_role for row in planner.slides):
        _issue(issues, "duplicate_semantic_role", "slides", str(duplicate))
    normalized_jobs = [_normalize_text(row.narrative_job) for row in planner.slides]
    for duplicate in _duplicates(normalized_jobs):
        _issue(issues, "duplicate_narrative_job", "slides", str(duplicate))
    if planner.deck_strategy.narrative_arc != [row.semantic_role for row in planner.slides]:
        _issue(
            issues,
            "narrative_arc_sequence_mismatch",
            "deck_strategy.narrative_arc",
            "Strategy arc must match the ordered slide roles.",
        )
    if not planner.slides or planner.slides[0].semantic_role != SemanticSlideRoleV4.COVER:
        _issue(issues, "high_impact_opening_missing", "slides[0]", "cover")
    if not planner.slides or planner.slides[-1].semantic_role != SemanticSlideRoleV4.CLOSING:
        _issue(issues, "decisive_closing_missing", "slides[-1]", "closing")

    argument_ids = [row.slide_id for row in planner.slides]
    for index, slide in enumerate(planner.slides):
        path = f"slides[{index}]"
        expected_previous = argument_ids[index - 1] if index else None
        expected_next = argument_ids[index + 1] if index + 1 < len(argument_ids) else None
        if slide.previous_argument_id != expected_previous:
            _issue(
                issues,
                "previous_argument_relationship_invalid",
                f"{path}.previous_argument_id",
                str(slide.previous_argument_id),
            )
        if slide.next_argument_id != expected_next:
            _issue(
                issues,
                "next_argument_relationship_invalid",
                f"{path}.next_argument_id",
                str(slide.next_argument_id),
            )
        for resolved in slide.resolves_argument_ids:
            if resolved not in argument_ids[:index]:
                _issue(
                    issues,
                    "invalid_resolved_argument",
                    f"{path}.resolves_argument_ids",
                    resolved,
                )
        expected_profile, minimum_words, maximum_words = _ROLE_BUDGETS[slide.semantic_role]
        actual_words = audience_facing_word_count_v4(slide)
        if slide.copy_budget.profile != expected_profile:
            _issue(
                issues,
                "copy_budget_profile_mismatch",
                f"{path}.copy_budget.profile",
                f"{slide.copy_budget.profile.value}!={expected_profile.value}",
            )
        if slide.copy_budget.audience_facing_words != actual_words:
            _issue(
                issues,
                "copy_budget_count_mismatch",
                f"{path}.copy_budget.audience_facing_words",
                f"{slide.copy_budget.audience_facing_words}!={actual_words}",
            )
        if actual_words < minimum_words:
            _issue(
                issues,
                "copy_below_role_capacity",
                path,
                f"{actual_words}<{minimum_words}",
            )
            if slide.semantic_role != SemanticSlideRoleV4.COVER:
                _issue(
                    issues,
                    "sparse_non_cover_slide",
                    path,
                    f"{actual_words}<{minimum_words}",
                )
        if actual_words > maximum_words:
            _issue(
                issues,
                "copy_above_role_capacity",
                path,
                f"{actual_words}>{maximum_words}",
            )
        if slide.compiler_support == CompilerSupportV4.COMPILER_V2:
            if slide.visual_archetype not in _COMPILER_V2_ARCHETYPES:
                _issue(
                    issues,
                    "compiler_support_misdeclared",
                    f"{path}.compiler_support",
                    slide.visual_archetype.value,
                )
            if slide.compiler_gap_code is not None:
                _issue(
                    issues,
                    "compiler_gap_inconsistent",
                    f"{path}.compiler_gap_code",
                    slide.compiler_gap_code,
                )
            grammar = grammar_for(slide.visual_archetype)
            if grammar is None:
                _issue(
                    issues,
                    "compiler_v2_grammar_missing",
                    f"{path}.visual_archetype",
                    slide.visual_archetype.value,
                )
            else:
                if slide.composition_variant not in grammar.variants:
                    _issue(
                        issues,
                        "unsupported_compiler_v2_variant",
                        f"{path}.composition_variant",
                        slide.composition_variant.value,
                    )
                if slide.visual_type not in grammar.visual_types:
                    _issue(
                        issues,
                        "unsupported_compiler_v2_visual_type",
                        f"{path}.visual_type",
                        slide.visual_type.value,
                    )
        else:
            if slide.visual_archetype in _COMPILER_V2_ARCHETYPES:
                _issue(
                    issues,
                    "compiler_v3_gap_not_demonstrated",
                    f"{path}.compiler_support",
                    slide.visual_archetype.value,
                )
            if slide.compiler_gap_code is None:
                _issue(
                    issues,
                    "compiler_gap_code_missing",
                    f"{path}.compiler_gap_code",
                    slide.slide_id,
                )
        if not slide.evidence_ids:
            _issue(issues, "unsupported_abstract_claim", f"{path}.evidence_ids", slide.slide_id)
        if not set(slide.protected_fact_ids) <= set(slide.evidence_ids):
            _issue(
                issues,
                "protected_fact_not_in_slide_evidence",
                f"{path}.protected_fact_ids",
                slide.slide_id,
            )
        _visual_and_metric_validation(slide, package, path, issues)

        for label, values in (
            ("visual_item", [row.item_id for row in slide.visual.items]),
            ("visual_step", [row.step_id for row in slide.visual.steps]),
            ("visual_metric", [row.metric_id for row in slide.visual.metrics]),
        ):
            for duplicate in _duplicates(values):
                _issue(
                    issues,
                    f"duplicate_{label}_id",
                    f"{path}.visual",
                    str(duplicate),
                )
        if slide.visual_archetype == SlideArchetype.PROBLEM_LANDSCAPE and not (
            3 <= len(slide.visual.items) <= 6
        ):
            _issue(
                issues,
                "problem_landscape_cardinality_invalid",
                f"{path}.visual.items",
                slide.slide_id,
            )
        if slide.visual_archetype == SlideArchetype.COMPARISON_SHIFT:
            groups = {row.group for row in slide.visual.items if row.group}
            if len(groups) != 2 or any(
                sum(row.group == group for row in slide.visual.items) < 2 for group in groups
            ):
                _issue(
                    issues,
                    "comparison_shift_groups_invalid",
                    f"{path}.visual.items",
                    slide.slide_id,
                )
        if slide.visual_archetype in {
            SlideArchetype.PROCESS_PATHWAY,
            SlideArchetype.TIMELINE_MILESTONES,
        } and not (3 <= len(slide.visual.steps) <= 7):
            _issue(
                issues,
                "progression_cardinality_invalid",
                f"{path}.visual.steps",
                slide.slide_id,
            )
        if slide.visual_archetype == SlideArchetype.METRIC_PROOF and not (
            1 <= len(slide.visual.metrics) <= 4
        ):
            _issue(
                issues,
                "metric_proof_cardinality_invalid",
                f"{path}.visual.metrics",
                slide.slide_id,
            )
        if slide.visual_archetype == SlideArchetype.SYSTEM_MAP and (
            not (3 <= len(slide.visual.items) <= 8) or len(slide.visual.edges) < 2
        ):
            _issue(
                issues,
                "system_map_cardinality_invalid",
                f"{path}.visual",
                slide.slide_id,
            )

    if planner.slides:
        closing = planner.slides[-1]
        opening = planner.slides[0]
        if opening.slide_id not in closing.resolves_argument_ids:
            _issue(
                issues,
                "weak_opening_closing_relationship",
                f"slides[{len(planner.slides)-1}].resolves_argument_ids",
                opening.slide_id,
            )
        if closing.opens_question or closing.next_argument_id is not None:
            _issue(
                issues,
                "closing_introduces_unresolved_argument",
                f"slides[{len(planner.slides)-1}]",
                closing.slide_id,
            )

    evidence_sources = _evidence_sources(package)
    valid_sources = {row.source_slide_id for row in package.source_slides}
    represented_sources: set[str] = set()
    normalized_claims: list[tuple[str, set[str]]] = []
    for index, slide in enumerate(planner.slides):
        path = f"slides[{index}]"
        represented_sources.update(slide.source_slide_ids)
        if not set(slide.source_slide_ids) <= valid_sources:
            _issue(
                issues,
                "unknown_source_slide_reference",
                f"{path}.source_slide_ids",
                slide.slide_id,
            )
        nested_evidence = [
            *(reference for row in slide.body for reference in row.evidence_ids),
            *(reference for row in slide.visual.items for reference in row.evidence_ids),
            *(row.number_ref for row in slide.visual.metrics),
            *(reference for row in slide.visual.steps for reference in row.evidence_ids),
            *(reference for row in slide.visual.people for reference in row.evidence_ids),
            *(reference for row in slide.visual.edges for reference in row.evidence_ids),
        ]
        declared = set(slide.evidence_ids)
        if not set(nested_evidence) <= declared:
            _issue(
                issues,
                "nested_evidence_not_declared",
                path,
                slide.slide_id,
            )
        for evidence_id in declared:
            sources = evidence_sources.get(evidence_id)
            if sources is None:
                _issue(issues, "unknown_evidence_reference", f"{path}.evidence_ids", evidence_id)
            elif not sources <= set(slide.source_slide_ids):
                _issue(issues, "evidence_source_mismatch", f"{path}.evidence_ids", evidence_id)
        normalized_claims.append((_normalize_text(slide.audience_claim), declared))
    if represented_sources != valid_sources:
        _issue(
            issues,
            "incomplete_source_coverage",
            "slides.source_slide_ids",
            f"missing={sorted(valid_sources - represented_sources)}",
        )
    for index, (claim, evidence) in enumerate(normalized_claims):
        for other_index, (other, other_evidence) in enumerate(normalized_claims[:index]):
            similarity = SequenceMatcher(a=claim, b=other).ratio()
            if similarity >= 0.88 and evidence & other_evidence:
                _issue(
                    issues,
                    "repeated_audience_claim",
                    f"slides[{index}].audience_claim",
                    f"similar_to={other_index};ratio={similarity:.2f}",
                )

    for index, (previous, current) in enumerate(zip(planner.slides, planner.slides[1:]), start=1):
        progression = {SemanticSlideRoleV4.PROCESS}
        progression_archetypes = {
            SlideArchetype.PROCESS_PATHWAY,
            SlideArchetype.TIMELINE_MILESTONES,
        }
        if (previous.semantic_role in progression and current.semantic_role in progression) or (
            previous.visual_archetype in progression_archetypes
            and current.visual_archetype in progression_archetypes
        ):
            _issue(
                issues,
                "adjacent_equivalent_progression_slides",
                f"slides[{index}]",
                current.slide_id,
            )

    rhythm = planner.deck_strategy.visual_rhythm
    silhouettes = [row.composition_silhouette for row in planner.slides]
    if rhythm.silhouette_sequence != silhouettes:
        _issue(
            issues,
            "silhouette_sequence_mismatch",
            "deck_strategy.visual_rhythm.silhouette_sequence",
            "Strategy and slides must match.",
        )
    if len(rhythm.tonal_sequence) != len(planner.slides):
        _issue(
            issues,
            "tonal_sequence_length_mismatch",
            "deck_strategy.visual_rhythm.tonal_sequence",
            str(len(rhythm.tonal_sequence)),
        )
    for duplicate, count in Counter(silhouettes).items():
        if count > 2:
            _issue(
                issues,
                "repeated_composition_silhouette",
                "slides",
                f"{duplicate.value}:{count}",
            )
    for index, (previous, current) in enumerate(zip(silhouettes, silhouettes[1:]), start=1):
        if previous == current:
            _issue(
                issues,
                "adjacent_repeated_composition_silhouette",
                f"slides[{index}]",
                current.value,
            )
    if silhouettes and silhouettes[0] not in {
        CompositionSilhouetteV4.HERO,
        CompositionSilhouetteV4.MONUMENT,
    }:
        _issue(issues, "high_impact_opening_silhouette_missing", "slides[0]", silhouettes[0])
    if silhouettes and silhouettes[-1] not in {
        CompositionSilhouetteV4.CLOSE,
        CompositionSilhouetteV4.MONUMENT,
    }:
        _issue(
            issues,
            "decisive_closing_silhouette_missing",
            "slides[-1]",
            silhouettes[-1],
        )
    positions = set(range(1, len(planner.slides) + 1))
    for label, values in (
        ("image_led_positions", rhythm.image_led_positions),
        ("evidence_rich_positions", rhythm.evidence_rich_positions),
        ("breathing_space_positions", rhythm.breathing_space_positions),
    ):
        if not set(values) <= positions or _duplicates(values):
            _issue(
                issues,
                "invalid_visual_rhythm_positions",
                f"deck_strategy.visual_rhythm.{label}",
                str(values),
            )
    for position in rhythm.image_led_positions:
        if planner.slides[position - 1].asset_intent.asset_ref is None:
            _issue(
                issues,
                "image_led_moment_without_asset",
                f"deck_strategy.visual_rhythm.image_led_positions[{position}]",
                str(position),
            )

    _commercial_validation(planner, package, issues)
    _asset_validation(planner, package, issues)

    founder_rows = [
        slide for slide in planner.slides if slide.semantic_role == SemanticSlideRoleV4.FOUNDER_TEAM
    ]
    founder_coverage = next(
        row
        for row in package.protected_coverage
        if row.category == ProtectedCoverageCategory.FOUNDER
    )
    if founder_coverage.status == "present":
        if not founder_rows:
            _issue(issues, "missing_founder_evidence", "slides", "founder_team")
        else:
            founder = founder_rows[0]
            if founder.visual_archetype != SlideArchetype.PEOPLE_PROOF or not founder.visual.people:
                _issue(
                    issues,
                    "founder_reduced_to_unlabelled_system_node",
                    f"slides[{founder.position - 1}]",
                    founder.slide_id,
                )

    ask_coverage = next(
        row for row in package.protected_coverage if row.category == ProtectedCoverageCategory.ASK
    )
    if ask_coverage.status == "present":
        ask_ids = set(ask_coverage.protected_fact_ids)
        if not any(
            slide.semantic_role
            in {SemanticSlideRoleV4.INVESTMENT_PROPOSITION, SemanticSlideRoleV4.CLOSING}
            and ask_ids & set(slide.protected_fact_ids)
            for slide in planner.slides
        ):
            _issue(issues, "missing_source_backed_ask", "slides", "ask")

    if issues:
        raise PlannerV4ValidationError(issues)


def parse_and_validate_planner_v4(
    raw_json: str,
    package: NormalizedSourcePackageV2,
) -> PlannerDeckSpecV4:
    try:
        planner = PlannerDeckSpecV4.model_validate_json(raw_json, strict=True)
    except ValidationError as exc:
        issues = [
            PlannerV4Issue(
                code="planner_schema_invalid",
                path=".".join(str(part) for part in row["loc"]),
                message=row["msg"],
            )
            for row in exc.errors(include_url=False)
        ]
        raise PlannerV4ValidationError(issues) from exc
    validate_planner_deck_spec_v4(planner, package)
    return planner


def compiler_v3_gaps_v4(planner: PlannerDeckSpecV4) -> tuple[CompilerV3GapV4, ...]:
    return tuple(
        CompilerV3GapV4(
            slide_id=slide.slide_id,
            position=slide.position,
            semantic_role=slide.semantic_role.value,
            canonical_archetype=slide.visual_archetype.value,
            gap_code=slide.compiler_gap_code or "compiler_v3_gap_unspecified",
        )
        for slide in planner.slides
        if slide.compiler_support == CompilerSupportV4.COMPILER_V3_REQUIRED
    )


def _canonical_visual(slide: PlannerSlideV4) -> VisualSpec:
    return VisualSpec(
        type=slide.visual_type,
        narrative_function=slide.consequence,
        title=None,
        asset_ref=slide.asset_intent.asset_ref,
        items=[
            VisualItem(
                id=row.item_id,
                label=row.label,
                detail=row.detail,
                value=row.value,
                group=row.group,
                evidence_refs=list(row.evidence_ids),
                asset_ref=row.asset_ref,
            )
            for row in slide.visual.items
        ],
        edges=[
            VisualEdge(
                **{
                    "from": row.from_item_id,
                    "to": row.to_item_id,
                    "label": row.label,
                    "evidence_refs": list(row.evidence_ids),
                }
            )
            for row in slide.visual.edges
        ],
        metrics=[
            VisualMetric(
                id=row.metric_id,
                value=row.value,
                label=row.label,
                context=row.context,
                evidence_refs=[row.number_ref],
            )
            for row in slide.visual.metrics
        ],
        series=[],
        steps=[
            VisualStep(
                id=row.step_id,
                label=row.label,
                detail=row.detail,
                evidence_refs=list(row.evidence_ids),
            )
            for row in slide.visual.steps
        ],
        people=[
            VisualPerson(
                name=row.name,
                role=row.role,
                proof=row.proof,
                evidence_refs=list(row.evidence_ids),
                asset_ref=row.asset_ref,
            )
            for row in slide.visual.people
        ],
        quotes=[],
    )


def normalize_planner_deck_spec_v4(
    planner: PlannerDeckSpecV4,
    package_v2: NormalizedSourcePackageV2,
    canonical_package_v1: NormalizedSourcePackage,
) -> DeckSpec:
    """Normalize validated Planner v4 output without repairing or truncating it."""

    validate_planner_deck_spec_v4(planner, package_v2)
    if canonical_package_v1.source_checksum != package_v2.source_checksum:
        raise ValueError("canonical_source_checksum_mismatch")
    if canonical_sha256(canonical_package_v1) != package_v2.source_package_v1_sha256:
        raise ValueError("canonical_source_package_v1_hash_mismatch")
    canonical_assets = {row.asset_id for row in canonical_package_v1.assets}
    for slide in planner.slides:
        if (
            slide.asset_intent.asset_ref is not None
            and slide.asset_intent.asset_ref not in canonical_assets
        ):
            raise ValueError(
                f"compiler_v2_asset_unavailable_in_canonical_v1:{slide.asset_intent.asset_ref}"
            )

    represented = sorted(
        {source_id for slide in planner.slides for source_id in slide.source_slide_ids}
    )
    all_sources = {row.source_slide_id for row in package_v2.source_slides}
    omitted = sorted(all_sources - set(represented))
    strategy = planner.deck_strategy
    slides: list[SlideSpec] = []
    for index, slide in enumerate(planner.slides, start=1):
        evidence = list(dict.fromkeys(slide.evidence_ids))
        blocks = (
            []
            if slide.semantic_role == SemanticSlideRoleV4.COVER
            else [
                CopyBlock(
                    id="c01",
                    kind="assertion",
                    text=slide.audience_claim,
                    evidence_refs=evidence,
                    emphasis="primary",
                )
            ]
        )
        blocks.extend(
            CopyBlock(
                id=f"c{body_index + 2:02d}",
                kind=row.kind,
                text=row.text,
                evidence_refs=list(row.evidence_ids),
                emphasis=row.emphasis,
            )
            for body_index, row in enumerate(slide.body)
        )
        slides.append(
            SlideSpec(
                slide_id=f"s{index:02d}",
                position=index,
                archetype=slide.visual_archetype,
                purpose=slide.narrative_job,
                headline=slide.headline,
                subhead=(
                    slide.subhead
                    or (
                        slide.audience_claim
                        if slide.semantic_role == SemanticSlideRoleV4.COVER
                        else None
                    )
                ),
                copy_blocks=blocks,
                evidence_refs=evidence,
                source_slide_ids=list(slide.source_slide_ids),
                omitted_source_slide_ids=[],
                asset_refs=(
                    [slide.asset_intent.asset_ref]
                    if slide.asset_intent.asset_ref is not None
                    else []
                ),
                composition=CompositionSpec(
                    primitive=slide.visual_archetype,
                    variant=slide.composition_variant,
                    background_role=strategy.brand_direction.paper_role,
                    accent_role=strategy.brand_direction.signature_role,
                    density=(
                        "sparse"
                        if slide.semantic_role
                        in {SemanticSlideRoleV4.COVER, SemanticSlideRoleV4.CLOSING}
                        else "balanced"
                    ),
                    focal_alignment=(
                        "center"
                        if slide.composition_silhouette
                        in {
                            CompositionSilhouetteV4.MONUMENT,
                            CompositionSilhouetteV4.METRIC,
                            CompositionSilhouetteV4.CLOSE,
                        }
                        else "distributed"
                    ),
                    visual_weight=0.72,
                    maximum_text_area=0.48,
                ),
                visual=_canonical_visual(slide),
            )
        )

    return DeckSpec(
        schema_version="deck_spec.v1",
        compiler_version="instant-deck-composition-compiler.v1",
        source_package_id=canonical_package_v1.package_id,
        source_checksum=package_v2.source_checksum,
        deck_title=planner.deck_title,
        deck_thesis=strategy.central_thesis,
        audience=strategy.audience,
        narrative=NarrativeSpec(
            audience_need=strategy.desired_decision,
            arc=[_NARRATIVE_ARC[slide.semantic_role] for slide in planner.slides],
            opening_move=strategy.opening_promise,
            closing_move=strategy.closing_resolution,
            represented_source_slide_ids=represented,
            omitted_source_slide_ids=omitted,
        ),
        art_direction=ArtDirectionSpec(
            concept=strategy.brand_direction.concept,
            tone=strategy.brand_direction.tone,
            display_strategy=strategy.brand_direction.display_strategy,
            motif=strategy.brand_direction.motif,
            rhythm="chaptered",
            paper_role=strategy.brand_direction.paper_role,
            ink_role=strategy.brand_direction.ink_role,
            signature_role=strategy.brand_direction.signature_role,
            support_roles=list(strategy.brand_direction.support_roles),
        ),
        slides=slides,
    )


def canonical_planner_v4_bytes(planner: PlannerDeckSpecV4) -> bytes:
    return json.dumps(
        planner.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
