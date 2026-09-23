"""Offline Planner v4.2: narrow creative output plus deterministic application envelope.

The model owns whole-deck narrative and composition judgment.  Python owns
request-scoped facts, identities, provenance, counts, capabilities, and the
investment-close boundary.  This module is deliberately unmounted: it imports
no provider, worker, API, database, retrieval, embedding, or publication code.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Annotated, Any, Iterable, Literal

from pydantic import Field, StringConstraints, ValidationError, model_validator

from .grammar import grammar_for
from .models import CompositionVariant, SlideArchetype, VisualType
from .planner_v4 import (
    AssetTreatmentV4,
    CompositionSilhouetteV4,
    CopyBudgetProfileV4,
    PlannerBrandDirectionV4,
    PlannerCopyV4,
    PlannerV4Model,
    SemanticSlideRoleV4,
    TonalModeV4,
)
from .planner_v4_1 import (
    DesiredInvestorDecisionV4_1,
    DiligencePriorityV4_1,
    EvidenceGapTypeV4_1,
    FundraisingStageV4_1,
    InvestmentContextV4_1,
    InvestorArgumentStageV4_1,
    InvestorCoverageCategoryV4_1,
    InvestorCoverageStatusV4_1,
    InvestorEvaluationCriterionV4_1,
    InvestorFinancialKindV4_1,
    InvestorSophisticationV4_1,
    InvestorSubtypeV4_1,
    PlannerDeckSpecV4_1,
    derive_investor_coverage_v4_1,
    InvestorCoverageV4_1,
)
from .source_package_v2 import AssetSemanticRole, NormalizedSourcePackageV2


PLANNER_SCHEMA_VERSION_V4_2 = "planner_deck_spec.v4.2"
PLANNER_ENVELOPE_VERSION_V4_2 = "instant-deck-deterministic-envelope.v4.2"
PLANNER_ENRICHER_VERSION_V4_2 = "instant-deck-planner-enricher.v4.2"
COMPILER_CAPABILITY_VERSION_V4_2 = "instant-deck-compiler-v3-capabilities.v1"


class ViolationOwnershipV4_2(str, Enum):
    DETERMINISTIC = "deterministically_derivable"
    PRE_GENERATION = "pre_generation_evidence_fact_validation"
    CREATIVE = "genuinely_creative_model_judgement"
    OBSOLETE = "unsupported_or_obsolete_contract_requirement"


class SlidePacingV4_2(str, Enum):
    OPEN = "open"
    BUILD = "build"
    PROVE = "prove"
    BREATHE = "breathe"
    CLOSE = "close"


class PlannerSectionV4_2(PlannerV4Model):
    stage: InvestorArgumentStageV4_1
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=140)]
    slide_ordinals: list[int] = Field(min_length=1, max_length=4)


class PlannerCreativeStrategyV4_2(PlannerV4Model):
    central_thesis: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    narrative_tension: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    opening_promise: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    closing_resolution: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    sections: list[PlannerSectionV4_2] = Field(min_length=1, max_length=9)
    brand_direction: PlannerBrandDirectionV4


class PlannerVisualItemV4_2(PlannerV4Model):
    label: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=140)] | None
    value: Annotated[str, StringConstraints(min_length=1, max_length=48)] | None
    group: Annotated[str, StringConstraints(min_length=1, max_length=48)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    asset_ref: str | None


class PlannerMetricV4_2(PlannerV4Model):
    number_ref: str
    value: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    context: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None


class PlannerStepV4_2(PlannerV4Model):
    label: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class PlannerPersonV4_2(PlannerV4Model):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    role: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    proof: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    asset_ref: str | None


class PlannerEdgeV4_2(PlannerV4Model):
    from_item_ordinal: int = Field(ge=1, le=10)
    to_item_ordinal: int = Field(ge=1, le=10)
    label: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class PlannerVisualV4_2(PlannerV4Model):
    metric_encoding: Literal[
        "none", "single_metric", "independent_stats", "shared_scale", "ordinal_stages"
    ]
    items: list[PlannerVisualItemV4_2] = Field(min_length=0, max_length=10)
    metrics: list[PlannerMetricV4_2] = Field(min_length=0, max_length=6)
    steps: list[PlannerStepV4_2] = Field(min_length=0, max_length=7)
    people: list[PlannerPersonV4_2] = Field(min_length=0, max_length=6)
    edges: list[PlannerEdgeV4_2] = Field(min_length=0, max_length=14)


class PlannerAssetPlacementV4_2(PlannerV4Model):
    asset_ref: str | None
    treatment: AssetTreatmentV4
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None

    @model_validator(mode="after")
    def validate_empty_placement(self) -> "PlannerAssetPlacementV4_2":
        if self.asset_ref is None and (
            self.treatment != AssetTreatmentV4.NONE or self.rationale is not None
        ):
            raise ValueError("empty asset placement must not carry treatment or rationale")
        if self.asset_ref is not None and (
            self.treatment == AssetTreatmentV4.NONE or self.rationale is None
        ):
            raise ValueError("selected asset requires treatment and rationale")
        return self


class PlannerSlideV4_2(PlannerV4Model):
    semantic_role: SemanticSlideRoleV4
    narrative_job: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    audience_claim: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    consequence: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    headline: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    subhead: Annotated[str, StringConstraints(min_length=1, max_length=180)] | None
    body: list[PlannerCopyV4] = Field(min_length=0, max_length=3)
    selected_evidence_ids: list[str] = Field(min_length=1, max_length=14)
    visual_archetype: SlideArchetype
    composition_variant: CompositionVariant
    composition_silhouette: CompositionSilhouetteV4
    visual_type: VisualType
    visual: PlannerVisualV4_2
    asset_placement: PlannerAssetPlacementV4_2
    resolves_opening: bool
    opens_question: bool
    tonal_mode: TonalModeV4
    pacing: SlidePacingV4_2


class PlannerDeckSpecV4_2(PlannerV4Model):
    schema_version: Literal["planner_deck_spec.v4.2"]
    deck_title: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    deck_strategy: PlannerCreativeStrategyV4_2
    slides: list[PlannerSlideV4_2] = Field(min_length=8, max_length=14)


class EvidenceEnvelopeRecordV4_2(PlannerV4Model):
    evidence_id: str
    kind: Literal["fact", "claim", "number"]
    source_reference_ids: list[str]
    source_slide_ids: list[str]


class FinancialMetricEnvelopeV4_2(PlannerV4Model):
    number_id: str
    classification: InvestorFinancialKindV4_1
    exact_text: str
    unit: str | None
    source_reference_ids: list[str]
    source_slide_ids: list[str]


class CoverageEnvelopeRecordV4_2(PlannerV4Model):
    category: InvestorCoverageCategoryV4_1
    source_status: InvestorCoverageStatusV4_1
    available_evidence_ids: list[str]
    gap_type: EvidenceGapTypeV4_1 | None
    gap_detail: str | None


class AssetCapabilityV4_2(PlannerV4Model):
    asset_id: str
    semantic_role: AssetSemanticRole
    mime_type: str
    width: int
    height: int
    source_document_sha256: str
    required_for_planner: bool
    supported_treatments: list[AssetTreatmentV4]


class PrimitiveCapabilityV4_2(PlannerV4Model):
    archetype: SlideArchetype
    variants: list[CompositionVariant]
    visual_types: list[VisualType]


class CompilerCapabilityEnvelopeV4_2(PlannerV4Model):
    capability_version: Literal["instant-deck-compiler-v3-capabilities.v1"]
    compiler_version: Literal["instant-deck-composition-compiler.v3"]
    primitives: list[PrimitiveCapabilityV4_2]


class InvestmentCloseEnvelopeV4_2(PlannerV4Model):
    eligible: bool
    allowed_decisions: list[DesiredInvestorDecisionV4_1]
    selected_decision: DesiredInvestorDecisionV4_1 | None
    evidence_ids: list[str]
    reason: str


class InvestorProfileEnvelopeV4_2(PlannerV4Model):
    investor_subtype: InvestorSubtypeV4_1
    company_stage: FundraisingStageV4_1
    investment_context: InvestmentContextV4_1
    sophistication_level: InvestorSophisticationV4_1
    likely_diligence_priorities: list[DiligencePriorityV4_1]


class PlannerDeterministicEnvelopeV4_2(PlannerV4Model):
    envelope_version: Literal["instant-deck-deterministic-envelope.v4.2"]
    source_package_id: str
    source_checksum: str
    evidence: list[EvidenceEnvelopeRecordV4_2]
    investor_profile: InvestorProfileEnvelopeV4_2
    investor_coverage: list[CoverageEnvelopeRecordV4_2]
    financial_metrics: list[FinancialMetricEnvelopeV4_2]
    assets: list[AssetCapabilityV4_2]
    compiler: CompilerCapabilityEnvelopeV4_2
    evaluation_criteria: list[InvestorEvaluationCriterionV4_1]
    investment_close: InvestmentCloseEnvelopeV4_2


class SourceCoverageLedgerV4_2(PlannerV4Model):
    source_slide_id: str
    status: Literal["represented", "not_selected"]
    generated_slide_ids: list[str]


class EnrichedSlideV4_2(PlannerV4Model):
    slide_id: str
    position: int
    previous_argument_id: str | None
    next_argument_id: str | None
    resolves_argument_ids: list[str]
    evidence_ids: list[str]
    protected_fact_ids: list[str]
    source_slide_ids: list[str]
    copy_budget_profile: CopyBudgetProfileV4
    audience_facing_words: int
    visual_item_ids: list[str]
    visual_metric_ids: list[str]
    visual_step_ids: list[str]
    edge_endpoints: list[tuple[str, str]]
    asset_role: AssetSemanticRole | None
    compiler_supported: bool
    creative: PlannerSlideV4_2


class InvestorArgumentEnvelopeMoveV4_2(PlannerV4Model):
    stage: InvestorArgumentStageV4_1
    slide_ids: list[str]
    status: Literal["represented", "evidence_gap"]


class EnrichedPlannerDeckV4_2(PlannerV4Model):
    enricher_version: Literal["instant-deck-planner-enricher.v4.2"]
    source_package_id: str
    source_checksum: str
    deck_title: str
    narrative_arc: list[SemanticSlideRoleV4]
    investor_argument: list[InvestorArgumentEnvelopeMoveV4_2]
    evaluation_criteria: list[InvestorEvaluationCriterionV4_1]
    source_coverage: list[SourceCoverageLedgerV4_2]
    financial_evidence: list[FinancialMetricEnvelopeV4_2]
    high_value_asset_ids: list[str]
    slides: list[EnrichedSlideV4_2]


@dataclass(frozen=True, slots=True)
class PlannerV4_2Issue:
    code: str
    path: str
    message: str


class PlannerV4_2ValidationError(ValueError):
    def __init__(self, issues: Iterable[PlannerV4_2Issue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{row.code}@{row.path}" for row in self.issues))


@dataclass(frozen=True, slots=True)
class ViolationPolicyV4_2:
    ownership: ViolationOwnershipV4_2
    current_owner: str
    proposed_owner: str
    derivation: str
    required_input: str
    failure: str
    replay_disposition: Literal["disappears", "remains", "redesigned"]


_ROLE_BUDGETS_V4_2: dict[SemanticSlideRoleV4, tuple[CopyBudgetProfileV4, int, int]] = {
    SemanticSlideRoleV4.COVER: (CopyBudgetProfileV4.COVER, 10, 35),
    SemanticSlideRoleV4.THESIS: (CopyBudgetProfileV4.THESIS_PROBLEM, 30, 85),
    SemanticSlideRoleV4.PROBLEM: (CopyBudgetProfileV4.THESIS_PROBLEM, 30, 85),
    SemanticSlideRoleV4.SOLUTION: (CopyBudgetProfileV4.PROCESS_PRODUCT, 35, 95),
    SemanticSlideRoleV4.PROCESS: (CopyBudgetProfileV4.PROCESS_PRODUCT, 35, 95),
    SemanticSlideRoleV4.TRACTION: (CopyBudgetProfileV4.EVIDENCE_TRACTION, 35, 110),
    SemanticSlideRoleV4.BUSINESS_MODEL: (CopyBudgetProfileV4.BUSINESS_MARKET, 45, 120),
    SemanticSlideRoleV4.MARKET_OPPORTUNITY: (CopyBudgetProfileV4.BUSINESS_MARKET, 45, 120),
    SemanticSlideRoleV4.FOUNDER_TEAM: (CopyBudgetProfileV4.FOUNDER_NETWORK, 35, 100),
    SemanticSlideRoleV4.ECOSYSTEM: (CopyBudgetProfileV4.FOUNDER_NETWORK, 35, 100),
    SemanticSlideRoleV4.NETWORK_DEFENSIBILITY: (CopyBudgetProfileV4.FOUNDER_NETWORK, 35, 100),
    SemanticSlideRoleV4.INVESTMENT_PROPOSITION: (CopyBudgetProfileV4.BUSINESS_MARKET, 45, 120),
    SemanticSlideRoleV4.CLOSING: (CopyBudgetProfileV4.CLOSING, 20, 70),
}


_ARGUMENT_STAGE_BY_ROLE = {
    SemanticSlideRoleV4.COVER: InvestorArgumentStageV4_1.OPPORTUNITY,
    SemanticSlideRoleV4.THESIS: InvestorArgumentStageV4_1.OPPORTUNITY,
    SemanticSlideRoleV4.PROBLEM: InvestorArgumentStageV4_1.PROBLEM_CHANGE,
    SemanticSlideRoleV4.SOLUTION: InvestorArgumentStageV4_1.SOLUTION,
    SemanticSlideRoleV4.PROCESS: InvestorArgumentStageV4_1.SOLUTION,
    SemanticSlideRoleV4.TRACTION: InvestorArgumentStageV4_1.EVIDENCE,
    SemanticSlideRoleV4.BUSINESS_MODEL: InvestorArgumentStageV4_1.ECONOMICS,
    SemanticSlideRoleV4.MARKET_OPPORTUNITY: InvestorArgumentStageV4_1.SCALE,
    SemanticSlideRoleV4.FOUNDER_TEAM: InvestorArgumentStageV4_1.RIGHT_TO_WIN,
    SemanticSlideRoleV4.ECOSYSTEM: InvestorArgumentStageV4_1.RIGHT_TO_WIN,
    SemanticSlideRoleV4.NETWORK_DEFENSIBILITY: InvestorArgumentStageV4_1.RIGHT_TO_WIN,
    SemanticSlideRoleV4.INVESTMENT_PROPOSITION: InvestorArgumentStageV4_1.CAPITAL_PROPOSITION,
    SemanticSlideRoleV4.CLOSING: InvestorArgumentStageV4_1.INVESTOR_DECISION,
}


_V3_EXTRA_CAPABILITIES: dict[
    SlideArchetype, tuple[tuple[CompositionVariant, ...], tuple[VisualType, ...]]
] = {
    SlideArchetype.IMAGE_EVIDENCE: ((CompositionVariant.SPLIT_60_40,), (VisualType.IMAGE,)),
    SlideArchetype.TRACTION_STRIP: ((CompositionVariant.STRIP,), (VisualType.PROOF_STRIP,)),
    SlideArchetype.BUSINESS_MODEL_FLOW: (
        (CompositionVariant.DIAGONAL_FLOW,),
        (VisualType.SYSTEM_MAP,),
    ),
    SlideArchetype.PEOPLE_PROOF: (
        (CompositionVariant.LEFT_FOCAL, CompositionVariant.RIGHT_FOCAL),
        (VisualType.PEOPLE,),
    ),
    SlideArchetype.PARTNERSHIP_ECOSYSTEM: (
        (CompositionVariant.ORBIT, CompositionVariant.RADIAL),
        (VisualType.MARKET_MAP, VisualType.SYSTEM_MAP),
    ),
    SlideArchetype.CAPITAL_PLAN: (
        (CompositionVariant.SPLIT_40_60, CompositionVariant.SPLIT_60_40),
        (VisualType.CAPITAL_PLAN,),
    ),
    SlideArchetype.DECISIVE_CLOSE: (
        (CompositionVariant.CENTERED_MONUMENT,),
        (VisualType.TYPOGRAPHIC, VisualType.METRIC),
    ),
}


def _issue(rows: list[PlannerV4_2Issue], code: str, path: str, message: str) -> None:
    rows.append(PlannerV4_2Issue(code=code, path=path, message=message))


def _identifier(row: Any) -> str:
    return getattr(row, "fact_id", getattr(row, "claim_id", getattr(row, "number_id", "")))


def _words(value: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", value, flags=re.UNICODE))


def _canonical_metric(value: str) -> str:
    return re.sub(r"[\s,]", "", value).casefold()


def _stable_union(*groups: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for group in groups for value in group))


def _slide_word_count(slide: PlannerSlideV4_2) -> int:
    values = [
        slide.audience_claim,
        slide.consequence,
        slide.headline,
        slide.subhead or "",
        *(row.text for row in slide.body),
        *(
            value
            for row in slide.visual.items
            for value in (row.label, row.detail or "", row.value or "")
        ),
        *(
            value
            for row in slide.visual.metrics
            for value in (row.value, row.label, row.context or "")
        ),
        *(value for row in slide.visual.steps for value in (row.label, row.detail or "")),
        *(value for row in slide.visual.people for value in (row.name, row.role, row.proof)),
    ]
    return sum(_words(value) for value in values)


def _reference_maps(
    package: NormalizedSourcePackageV2,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    reference_sources = {row.reference_id: row.source_slide_id for row in package.source_references}
    evidence_sources: dict[str, list[str]] = {}
    for row in [*package.facts, *package.claims, *package.numbers]:
        evidence_sources[_identifier(row)] = sorted(
            {reference_sources[ref] for ref in row.source_reference_ids}
        )
    return reference_sources, evidence_sources


def _number_local_context(package: NormalizedSourcePackageV2, number: Any) -> str:
    reference_ids = set(number.source_reference_ids)
    source_text = " ".join(
        row.text for row in package.facts if reference_ids & set(row.source_reference_ids)
    )
    normalized_source = source_text.casefold()
    needle = number.exact_text.casefold()
    index = normalized_source.find(needle)
    if index < 0:
        compact = re.sub(r"\s+", "", normalized_source)
        compact_needle = re.sub(r"\s+", "", needle)
        index = compact.find(compact_needle)
        if index < 0:
            return f"{number.exact_text} {number.qualifier or ''}".casefold()
        normalized_source = compact
        needle = compact_needle
    return normalized_source[max(0, index - 90) : index + len(needle) + 110]


def classify_financial_metric_v4_2(
    package: NormalizedSourcePackageV2, number: Any
) -> InvestorFinancialKindV4_1:
    """Classify a source number from its local, request-bound source context."""

    text = _number_local_context(package, number)
    if re.search(r"\b(?:seeking|raising|raise)\s+(?:usd\s*)?[$€£]\s*[0-9]", text):
        return InvestorFinancialKindV4_1.FUNDING_REQUEST
    if "under management" in text or re.search(r"\baum\b", text):
        return InvestorFinancialKindV4_1.ASSETS_UNDER_MANAGEMENT
    if any(term in text for term in ("valuation", "post money", "pre money")):
        return InvestorFinancialKindV4_1.VALUATION
    if any(
        term in text
        for term in (
            "angel check",
            "funding request",
            "funding sought",
            "funding ask",
            "capital raise",
            "welcome to contribute",
        )
    ):
        return InvestorFinancialKindV4_1.FUNDING_REQUEST
    if any(term in text for term in ("transaction fee", "take rate", "commission")):
        return InvestorFinancialKindV4_1.TRANSACTION_FEE
    if any(term in text for term in ("market size", "addressable market", "transaction value")):
        return InvestorFinancialKindV4_1.MARKET_SIZE
    if any(term in text for term in ("revenue", "arr", "mrr", "sales")):
        return InvestorFinancialKindV4_1.REVENUE
    if any(
        term in text
        for term in (
            "houses",
            "families",
            "workshops",
            "consultations",
            "projects",
            "clients",
            "events",
        )
    ):
        return InvestorFinancialKindV4_1.TRACTION_METRIC
    return InvestorFinancialKindV4_1.OTHER


def _asset_treatments(role: AssetSemanticRole) -> list[AssetTreatmentV4]:
    if role in {
        AssetSemanticRole.LITERAL_LOGO,
        AssetSemanticRole.WORDMARK,
        AssetSemanticRole.BRAND_SYMBOL,
        AssetSemanticRole.BRAND_ARCHITECTURE,
        AssetSemanticRole.DIAGRAM,
    }:
        return [AssetTreatmentV4.CONTAIN, AssetTreatmentV4.WATERMARK]
    return [
        AssetTreatmentV4.CONTAIN,
        AssetTreatmentV4.COVER,
        AssetTreatmentV4.EDGE_CROP,
        AssetTreatmentV4.FULL_BLEED,
    ]


def _compiler_capabilities_v4_2() -> CompilerCapabilityEnvelopeV4_2:
    from .composition_renderers_v3 import RENDERER_REGISTRY_V3
    rows: list[PrimitiveCapabilityV4_2] = []
    for archetype in RENDERER_REGISTRY_V3:
        grammar = grammar_for(archetype)
        capability = _V3_EXTRA_CAPABILITIES.get(archetype)
        if grammar is not None:
            capability = (grammar.variants, grammar.visual_types)
        if capability is None:
            continue
        rows.append(
            PrimitiveCapabilityV4_2(
                archetype=archetype,
                variants=list(capability[0]),
                visual_types=list(capability[1]),
            )
        )
    return CompilerCapabilityEnvelopeV4_2(
        capability_version=COMPILER_CAPABILITY_VERSION_V4_2,
        compiler_version="instant-deck-composition-compiler.v3",
        primitives=rows,
    )


class SourceCoverageV4_2(InvestorCoverageV4_1):
    # The application records every available fact. The v4.1 ten-selection
    # limit describes model choices, not the size of the source evidence set.
    used_evidence_ids: list[str] = Field(default_factory=list)


def _derive_close(package: NormalizedSourcePackageV2) -> InvestmentCloseEnvelopeV4_2:
    coverage = {row.category: row for row in derive_investor_coverage_v4_1(package, coverage_model=SourceCoverageV4_2)}
    ask = coverage[InvestorCoverageCategoryV4_1.FUNDING_ASK]
    evidence_ids = list(ask.used_evidence_ids)
    facts = {row.fact_id: row.text.casefold() for row in package.facts}
    text = " ".join(facts.get(evidence, "") for evidence in evidence_ids)
    allowed: list[DesiredInvestorDecisionV4_1] = []
    if any(term in text for term in ("meeting", "next step")):
        allowed.append(DesiredInvestorDecisionV4_1.REQUEST_MEETING)
    if re.search(r"\bdiligence\b", text):
        allowed.append(DesiredInvestorDecisionV4_1.ADVANCE_TO_DILIGENCE)
    if re.search(r"\bround\b", text):
        allowed.append(DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND)
    if any(term in text for term in ("programme funding", "program funding", "fund programme")):
        allowed.append(DesiredInvestorDecisionV4_1.FUND_PROGRAMME)
    if any(term in text for term in ("next investment stage", "next stage")):
        allowed.append(DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE)
    if any(
        term in text
        for term in ("investment", "funding", "angel check", "contribute", "ticket size")
    ):
        allowed.append(DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT)
    allowed = list(dict.fromkeys(allowed))
    priority = (
        DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND,
        DesiredInvestorDecisionV4_1.FUND_PROGRAMME,
        DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE,
        DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT,
        DesiredInvestorDecisionV4_1.ADVANCE_TO_DILIGENCE,
        DesiredInvestorDecisionV4_1.REQUEST_MEETING,
    )
    selected = next((row for row in priority if row in allowed), None)
    return InvestmentCloseEnvelopeV4_2(
        eligible=selected is not None,
        allowed_decisions=allowed,
        selected_decision=selected,
        evidence_ids=evidence_ids,
        reason=(
            "A close is permitted only from the request-scoped funding/next-step evidence."
            if selected is not None
            else "No explicit investor decision is evidenced; close with supported conclusions and disclose remaining gaps."
        ),
    )


def build_deterministic_envelope_v4_2(
    package: NormalizedSourcePackageV2,
    *,
    require_investment_close: bool = True,
) -> PlannerDeterministicEnvelopeV4_2:
    """Build and fail-close the exact request-scoped application envelope."""

    reference_sources, evidence_sources = _reference_maps(package)
    evidence = []
    for kind, rows in (
        ("fact", package.facts),
        ("claim", package.claims),
        ("number", package.numbers),
    ):
        for row in rows:
            identifier = _identifier(row)
            evidence.append(
                EvidenceEnvelopeRecordV4_2(
                    evidence_id=identifier,
                    kind=kind,
                    source_reference_ids=list(row.source_reference_ids),
                    source_slide_ids=evidence_sources[identifier],
                )
            )
    financial = [
        FinancialMetricEnvelopeV4_2(
            number_id=row.number_id,
            classification=classify_financial_metric_v4_2(package, row),
            exact_text=row.exact_text,
            unit=row.unit,
            source_reference_ids=list(row.source_reference_ids),
            source_slide_ids=evidence_sources[row.number_id],
        )
        for row in package.numbers
    ]
    coverage_rows = derive_investor_coverage_v4_1(package, coverage_model=SourceCoverageV4_2)
    coverage = [
        CoverageEnvelopeRecordV4_2(
            category=row.category,
            source_status=row.status,
            available_evidence_ids=list(row.used_evidence_ids),
            gap_type=row.evidence_gap.gap_type if row.evidence_gap else None,
            gap_detail=row.evidence_gap.explanation if row.evidence_gap else None,
        )
        for row in coverage_rows
    ]
    assets = [
        AssetCapabilityV4_2(
            asset_id=row.asset_id,
            semantic_role=row.semantic_role,
            mime_type=row.mime_type,
            width=row.width,
            height=row.height,
            source_document_sha256=row.source_document_sha256,
            required_for_planner=row.required_for_planner,
            supported_treatments=_asset_treatments(row.semantic_role),
        )
        for row in package.assets
    ]
    if any(row.source_document_sha256 != package.source_checksum for row in assets):
        raise PlannerV4_2ValidationError(
            [PlannerV4_2Issue("cross_source_asset", "assets", package.source_checksum)]
        )
    close = _derive_close(package)
    if require_investment_close and not close.eligible:
        raise PlannerV4_2ValidationError(
            [PlannerV4_2Issue("investment_close_unsupported", "investment_close", close.reason)]
        )
    present = {
        row.category
        for row in coverage
        if row.source_status == InvestorCoverageStatusV4_1.PRESENT_AND_USED
    }
    priority_map = {
        InvestorCoverageCategoryV4_1.TRACTION: DiligencePriorityV4_1.TRACTION,
        InvestorCoverageCategoryV4_1.BUSINESS_MODEL: DiligencePriorityV4_1.BUSINESS_MODEL,
        InvestorCoverageCategoryV4_1.MARKET: DiligencePriorityV4_1.MARKET,
        InvestorCoverageCategoryV4_1.TEAM_FOUNDER: DiligencePriorityV4_1.TEAM,
        InvestorCoverageCategoryV4_1.DEFENSIBILITY: DiligencePriorityV4_1.DEFENSIBILITY,
        InvestorCoverageCategoryV4_1.FINANCIAL_EVIDENCE: DiligencePriorityV4_1.FINANCIALS,
        InvestorCoverageCategoryV4_1.USE_OF_FUNDS: DiligencePriorityV4_1.USE_OF_FUNDS,
    }
    return PlannerDeterministicEnvelopeV4_2(
        envelope_version=PLANNER_ENVELOPE_VERSION_V4_2,
        source_package_id=package.package_id,
        source_checksum=package.source_checksum,
        evidence=evidence,
        investor_profile=InvestorProfileEnvelopeV4_2(
            investor_subtype=InvestorSubtypeV4_1.UNSPECIFIED_INVESTOR,
            company_stage=FundraisingStageV4_1.UNSPECIFIED,
            investment_context=InvestmentContextV4_1.UNSPECIFIED,
            sophistication_level=InvestorSophisticationV4_1.UNSPECIFIED,
            likely_diligence_priorities=[
                value for category, value in priority_map.items() if category in present
            ],
        ),
        investor_coverage=coverage,
        financial_metrics=financial,
        assets=assets,
        compiler=_compiler_capabilities_v4_2(),
        evaluation_criteria=list(InvestorEvaluationCriterionV4_1),
        investment_close=close,
    )


def _slide_evidence(slide: PlannerSlideV4_2) -> list[str]:
    return _stable_union(
        slide.selected_evidence_ids,
        *(row.evidence_ids for row in slide.body),
        *(row.evidence_ids for row in slide.visual.items),
        (row.number_ref for row in slide.visual.metrics),
        *(row.evidence_ids for row in slide.visual.steps),
        *(row.evidence_ids for row in slide.visual.people),
        *(row.evidence_ids for row in slide.visual.edges),
    )


def _decision_terms(decision: DesiredInvestorDecisionV4_1) -> tuple[str, ...]:
    return {
        DesiredInvestorDecisionV4_1.REQUEST_MEETING: ("meeting", "meet"),
        DesiredInvestorDecisionV4_1.ADVANCE_TO_DILIGENCE: ("diligence",),
        DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT: ("fund", "back", "invest", "contribute"),
        DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND: ("round", "participate"),
        DesiredInvestorDecisionV4_1.FUND_PROGRAMME: ("fund", "programme", "program"),
        DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE: ("approve", "stage"),
    }[decision]


def validate_planner_deck_spec_v4_2(
    planner: PlannerDeckSpecV4_2,
    envelope: PlannerDeterministicEnvelopeV4_2,
) -> None:
    """Validate only creative choices against the immutable application envelope."""

    issues: list[PlannerV4_2Issue] = []
    evidence = {row.evidence_id: row for row in envelope.evidence}
    numbers = {row.number_id: row for row in envelope.financial_metrics}
    assets = {row.asset_id: row for row in envelope.assets}
    capabilities = {row.archetype: row for row in envelope.compiler.primitives}
    slide_count = len(planner.slides)

    section_ordinals = [
        ordinal for row in planner.deck_strategy.sections for ordinal in row.slide_ordinals
    ]
    for ordinal in section_ordinals:
        if ordinal < 1 or ordinal > slide_count:
            _issue(issues, "section_ordinal_out_of_range", "deck_strategy.sections", str(ordinal))
    duplicates = sorted(value for value, count in Counter(section_ordinals).items() if count > 1)
    if duplicates:
        _issue(
            issues, "section_grouping_duplicate_ordinal", "deck_strategy.sections", str(duplicates)
        )
    missing = sorted(set(range(1, slide_count + 1)) - set(section_ordinals))
    if missing:
        _issue(issues, "section_grouping_incomplete", "deck_strategy.sections", str(missing))

    if not planner.slides or planner.slides[0].semantic_role != SemanticSlideRoleV4.COVER:
        _issue(issues, "high_impact_opening_missing", "slides[0]", "cover")
    if not planner.slides or planner.slides[-1].semantic_role != SemanticSlideRoleV4.CLOSING:
        _issue(issues, "decisive_closing_missing", "slides[-1]", "closing")

    for index, slide in enumerate(planner.slides):
        path = f"slides[{index}]"
        declared = _slide_evidence(slide)
        unknown = sorted(set(declared) - set(evidence))
        if unknown:
            _issue(issues, "unknown_evidence_reference", path, str(unknown))

        profile, minimum, maximum = _ROLE_BUDGETS_V4_2[slide.semantic_role]
        word_count = _slide_word_count(slide)
        if word_count < minimum:
            _issue(issues, "copy_below_role_capacity", path, f"{word_count}<{minimum}")
        if word_count > maximum:
            _issue(issues, "copy_above_role_capacity", path, f"{word_count}>{maximum}")

        capability = capabilities.get(slide.visual_archetype)
        if capability is None:
            _issue(
                issues,
                "compiler_v3_archetype_unsupported",
                f"{path}.visual_archetype",
                slide.visual_archetype.value,
            )
        elif (
            slide.composition_variant not in capability.variants
            or slide.visual_type not in capability.visual_types
        ):
            _issue(
                issues,
                "compiler_v3_combination_unsupported",
                f"{path}.composition",
                f"{slide.visual_archetype.value}/{slide.composition_variant.value}/{slide.visual_type.value}",
            )

        item_count = len(slide.visual.items)
        metric_count = len(slide.visual.metrics)
        step_count = len(slide.visual.steps)
        if slide.visual_archetype == SlideArchetype.PROBLEM_LANDSCAPE and not 3 <= item_count <= 6:
            _issue(
                issues,
                "problem_landscape_cardinality_invalid",
                f"{path}.visual.items",
                str(item_count),
            )
        if slide.visual_archetype == SlideArchetype.METRIC_PROOF and not 1 <= metric_count <= 4:
            _issue(
                issues,
                "metric_proof_cardinality_invalid",
                f"{path}.visual.metrics",
                str(metric_count),
            )
        if (
            slide.visual_archetype
            in {SlideArchetype.PROCESS_PATHWAY, SlideArchetype.TIMELINE_MILESTONES}
            and not 3 <= step_count <= 7
        ):
            _issue(
                issues, "progression_cardinality_invalid", f"{path}.visual.steps", str(step_count)
            )

        if slide.visual.metric_encoding == "ordinal_stages" and (not step_count or metric_count):
            _issue(issues, "ordinal_stage_contract_invalid", f"{path}.visual", slide.headline)
        if slide.visual.metric_encoding == "none" and metric_count:
            _issue(
                issues, "metric_encoding_missing", f"{path}.visual.metric_encoding", slide.headline
            )
        if slide.visual.metric_encoding == "shared_scale":
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
                    str(sorted(str(row) for row in units)),
                )

        for metric_index, metric in enumerate(slide.visual.metrics):
            source = numbers.get(metric.number_ref)
            if source is None:
                _issue(
                    issues,
                    "unknown_number_reference",
                    f"{path}.visual.metrics[{metric_index}]",
                    metric.number_ref,
                )
            elif _canonical_metric(metric.value) != _canonical_metric(source.exact_text):
                _issue(
                    issues,
                    "metric_value_altered",
                    f"{path}.visual.metrics[{metric_index}]",
                    f"{metric.value}!={source.exact_text}",
                )

        for edge_index, edge in enumerate(slide.visual.edges):
            if edge.from_item_ordinal > item_count or edge.to_item_ordinal > item_count:
                _issue(
                    issues,
                    "visual_edge_endpoint_invalid",
                    f"{path}.visual.edges[{edge_index}]",
                    f"{edge.from_item_ordinal}->{edge.to_item_ordinal}",
                )

        placement = slide.asset_placement
        if placement.asset_ref is not None:
            asset = assets.get(placement.asset_ref)
            if asset is None:
                _issue(
                    issues, "asset_not_in_request", f"{path}.asset_placement", placement.asset_ref
                )
            elif placement.treatment not in asset.supported_treatments:
                _issue(
                    issues,
                    "asset_treatment_unsupported",
                    f"{path}.asset_placement",
                    placement.treatment.value,
                )
            if (
                slide.semantic_role == SemanticSlideRoleV4.FOUNDER_TEAM
                and asset is not None
                and asset.semantic_role != AssetSemanticRole.FOUNDER_PORTRAIT
            ):
                _issue(
                    issues,
                    "founder_asset_role_mismatch",
                    f"{path}.asset_placement",
                    asset.semantic_role.value,
                )

    if planner.slides and not planner.slides[-1].resolves_opening:
        _issue(issues, "weak_opening_closing_relationship", "slides[-1].resolves_opening", "false")
    close = envelope.investment_close
    if close.eligible and planner.slides:
        closing = planner.slides[-1]
        closing_text = " ".join(
            [
                closing.headline,
                closing.subhead or "",
                closing.audience_claim,
                closing.consequence,
                *(row.text for row in closing.body),
            ]
        ).casefold()
        decision = close.selected_decision
        if decision is None or not any(term in closing_text for term in _decision_terms(decision)):
            _issue(issues, "closing_decision_language_mismatch", "slides[-1]", str(decision))
        if not set(close.evidence_ids) & set(_slide_evidence(closing)):
            _issue(
                issues,
                "closing_without_source_backed_decision",
                "slides[-1]",
                str(close.evidence_ids),
            )

    if issues:
        raise PlannerV4_2ValidationError(issues)


def enrich_planner_deck_spec_v4_2(
    planner: PlannerDeckSpecV4_2,
    package: NormalizedSourcePackageV2,
    envelope: PlannerDeterministicEnvelopeV4_2,
    *,
    validate: bool = True,
) -> EnrichedPlannerDeckV4_2:
    """Derive application semantics without altering narrative, copy, or composition."""

    if (
        envelope.source_package_id != package.package_id
        or envelope.source_checksum != package.source_checksum
    ):
        raise PlannerV4_2ValidationError(
            [PlannerV4_2Issue("envelope_source_mismatch", "envelope", envelope.source_package_id)]
        )
    if validate:
        validate_planner_deck_spec_v4_2(planner, envelope)
    _, evidence_sources = _reference_maps(package)
    protected = {
        fact_id for row in package.protected_coverage for fact_id in row.protected_fact_ids
    }
    assets = {row.asset_id: row for row in envelope.assets}
    capabilities = {row.archetype: row for row in envelope.compiler.primitives}
    financial = {row.number_id: row for row in envelope.financial_metrics}
    enriched_slides: list[EnrichedSlideV4_2] = []
    generated_ids = [f"p{index:02d}" for index in range(1, len(planner.slides) + 1)]
    represented: dict[str, list[str]] = {row.source_slide_id: [] for row in package.source_slides}
    used_numbers: list[str] = []
    for index, slide in enumerate(planner.slides):
        evidence_ids = _slide_evidence(slide)
        source_slide_ids = sorted(
            {
                source
                for evidence_id in evidence_ids
                for source in evidence_sources.get(evidence_id, [])
            }
        )
        slide_id = generated_ids[index]
        for source_id in source_slide_ids:
            represented[source_id].append(slide_id)
        number_ids = [row.number_ref for row in slide.visual.metrics]
        used_numbers.extend(number_ids)
        capability = capabilities.get(slide.visual_archetype)
        compiler_supported = bool(
            capability
            and slide.composition_variant in capability.variants
            and slide.visual_type in capability.visual_types
        )
        edge_endpoints = [
            (f"v{row.from_item_ordinal:02d}", f"v{row.to_item_ordinal:02d}")
            for row in slide.visual.edges
        ]
        profile = _ROLE_BUDGETS_V4_2[slide.semantic_role][0]
        asset = assets.get(slide.asset_placement.asset_ref or "")
        enriched_slides.append(
            EnrichedSlideV4_2(
                slide_id=slide_id,
                position=index + 1,
                previous_argument_id=generated_ids[index - 1] if index else None,
                next_argument_id=(
                    generated_ids[index + 1] if index + 1 < len(generated_ids) else None
                ),
                resolves_argument_ids=(
                    [generated_ids[0]] if slide.resolves_opening and index else []
                ),
                evidence_ids=evidence_ids,
                protected_fact_ids=sorted(set(evidence_ids) & protected),
                source_slide_ids=source_slide_ids,
                copy_budget_profile=profile,
                audience_facing_words=_slide_word_count(slide),
                visual_item_ids=[
                    f"v{row_index:02d}" for row_index in range(1, len(slide.visual.items) + 1)
                ],
                visual_metric_ids=[
                    f"m{row_index:02d}" for row_index in range(1, len(slide.visual.metrics) + 1)
                ],
                visual_step_ids=[
                    f"t{row_index:02d}" for row_index in range(1, len(slide.visual.steps) + 1)
                ],
                edge_endpoints=edge_endpoints,
                asset_role=asset.semantic_role if asset else None,
                compiler_supported=compiler_supported,
                creative=slide,
            )
        )

    argument = []
    for stage in InvestorArgumentStageV4_1:
        slide_ids = [
            row.slide_id
            for row in enriched_slides
            if _ARGUMENT_STAGE_BY_ROLE[row.creative.semantic_role] == stage
        ]
        argument.append(
            InvestorArgumentEnvelopeMoveV4_2(
                stage=stage,
                slide_ids=slide_ids,
                status="represented" if slide_ids else "evidence_gap",
            )
        )
    high_value = sorted(row.asset_id for row in envelope.assets if row.required_for_planner)
    return EnrichedPlannerDeckV4_2(
        enricher_version=PLANNER_ENRICHER_VERSION_V4_2,
        source_package_id=package.package_id,
        source_checksum=package.source_checksum,
        deck_title=planner.deck_title,
        narrative_arc=[row.semantic_role for row in planner.slides],
        investor_argument=argument,
        evaluation_criteria=envelope.evaluation_criteria,
        source_coverage=[
            SourceCoverageLedgerV4_2(
                source_slide_id=source_id,
                status="represented" if slide_ids else "not_selected",
                generated_slide_ids=slide_ids,
            )
            for source_id, slide_ids in represented.items()
        ],
        financial_evidence=[
            financial[number_id]
            for number_id in dict.fromkeys(used_numbers)
            if number_id in financial
        ],
        high_value_asset_ids=high_value,
        slides=enriched_slides,
    )


def project_frozen_planner_v4_1_to_v4_2(planner: PlannerDeckSpecV4_1) -> PlannerDeckSpecV4_2:
    """Project only creative judgments; discard and rederive v4.1 application fields."""

    sections = []
    for row in planner.deck_strategy.investor_argument:
        ordinals = []
        for value in row.slide_ids:
            match = re.search(r"([0-9]{1,2})$", value)
            if match:
                ordinals.append(int(match.group(1)))
        sections.append(
            PlannerSectionV4_2(
                stage=row.stage,
                purpose=f"{row.stage.value.replace('_', ' ')} section",
                slide_ordinals=ordinals,
            )
        )

    item_index_by_slide = [
        {row.item_id: index for index, row in enumerate(slide.visual.items, start=1)}
        for slide in planner.slides
    ]
    slides = []
    rhythm = planner.deck_strategy.visual_rhythm
    for index, slide in enumerate(planner.slides):
        position = index + 1
        if position == 1:
            pacing = SlidePacingV4_2.OPEN
        elif position == len(planner.slides):
            pacing = SlidePacingV4_2.CLOSE
        elif position in rhythm.breathing_space_positions:
            pacing = SlidePacingV4_2.BREATHE
        elif position in rhythm.evidence_rich_positions:
            pacing = SlidePacingV4_2.PROVE
        else:
            pacing = SlidePacingV4_2.BUILD
        asset_ref = slide.asset_intent.asset_ref
        slides.append(
            PlannerSlideV4_2(
                semantic_role=slide.semantic_role,
                narrative_job=slide.narrative_job,
                audience_claim=slide.audience_claim,
                consequence=slide.consequence,
                headline=slide.headline,
                subhead=slide.subhead,
                body=slide.body,
                selected_evidence_ids=slide.evidence_ids,
                visual_archetype=slide.visual_archetype,
                composition_variant=slide.composition_variant,
                composition_silhouette=slide.composition_silhouette,
                visual_type=slide.visual_type,
                visual=PlannerVisualV4_2(
                    metric_encoding=slide.visual.metric_encoding.value,
                    items=[
                        PlannerVisualItemV4_2(
                            label=row.label,
                            detail=row.detail,
                            value=row.value,
                            group=row.group,
                            evidence_ids=row.evidence_ids,
                            asset_ref=row.asset_ref,
                        )
                        for row in slide.visual.items
                    ],
                    metrics=[
                        PlannerMetricV4_2(
                            number_ref=row.number_ref,
                            value=row.value,
                            label=row.label,
                            context=row.context,
                        )
                        for row in slide.visual.metrics
                    ],
                    steps=[
                        PlannerStepV4_2(
                            label=row.label,
                            detail=row.detail,
                            evidence_ids=row.evidence_ids,
                        )
                        for row in slide.visual.steps
                    ],
                    people=[
                        PlannerPersonV4_2(
                            name=row.name,
                            role=row.role,
                            proof=row.proof,
                            evidence_ids=row.evidence_ids,
                            asset_ref=row.asset_ref,
                        )
                        for row in slide.visual.people
                    ],
                    edges=[
                        PlannerEdgeV4_2(
                            from_item_ordinal=item_index_by_slide[index].get(row.from_item_id, 99),
                            to_item_ordinal=item_index_by_slide[index].get(row.to_item_id, 99),
                            label=row.label,
                            evidence_ids=row.evidence_ids,
                        )
                        for row in slide.visual.edges
                    ],
                ),
                asset_placement=PlannerAssetPlacementV4_2(
                    asset_ref=asset_ref,
                    treatment=slide.asset_intent.treatment if asset_ref else AssetTreatmentV4.NONE,
                    rationale=slide.asset_intent.rationale if asset_ref else None,
                ),
                resolves_opening=planner.slides[0].slide_id in slide.resolves_argument_ids,
                opens_question=slide.opens_question,
                tonal_mode=rhythm.tonal_sequence[index],
                pacing=pacing,
            )
        )
    return PlannerDeckSpecV4_2(
        schema_version=PLANNER_SCHEMA_VERSION_V4_2,
        deck_title=planner.deck_title,
        deck_strategy=PlannerCreativeStrategyV4_2(
            central_thesis=planner.deck_strategy.central_thesis,
            narrative_tension=planner.deck_strategy.narrative_tension,
            opening_promise=planner.deck_strategy.opening_promise,
            closing_resolution=planner.deck_strategy.closing_resolution,
            sections=sections,
            brand_direction=planner.deck_strategy.brand_direction,
        ),
        slides=slides,
    )


def source_bound_planner_schema_v4_2(
    package: NormalizedSourcePackageV2,
) -> dict[str, Any]:
    """Return the narrow model-output schema with request-scoped enums only."""

    schema = PlannerDeckSpecV4_2.model_json_schema()
    evidence = sorted(
        _identifier(row) for row in [*package.facts, *package.claims, *package.numbers]
    )
    numbers = sorted(row.number_id for row in package.numbers)
    assets = sorted(row.asset_id for row in package.assets)
    definitions = schema.setdefault("$defs", {})
    definitions.update(
        {
            "AllowedEvidenceIdV4_2": {"type": "string", "enum": evidence},
            "AllowedNumberIdV4_2": {"type": "string", "enum": numbers},
            "AllowedAssetIdV4_2": {"type": "string", "enum": assets},
        }
    )

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("discriminator", None)
            if "oneOf" in value:
                value["anyOf"] = value.pop("oneOf")
            properties = value.get("properties")
            if isinstance(properties, dict):
                for key, child in list(properties.items()):
                    if key in {"evidence_ids", "selected_evidence_ids"}:
                        child["items"] = {"$ref": "#/$defs/AllowedEvidenceIdV4_2"}
                    elif key == "number_ref":
                        properties[key] = {"$ref": "#/$defs/AllowedNumberIdV4_2"}
                    elif key == "asset_ref":
                        properties[key] = {
                            "anyOf": [
                                {"$ref": "#/$defs/AllowedAssetIdV4_2"},
                                {"type": "null"},
                            ]
                        }
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://deck.aistack.codes/schemas/planner-deck-spec.v4.2.json"
    return schema


def parse_planner_deck_spec_v4_2(raw_json: str) -> PlannerDeckSpecV4_2:
    try:
        return PlannerDeckSpecV4_2.model_validate_json(raw_json, strict=True)
    except ValidationError as exc:
        raise PlannerV4_2ValidationError(
            PlannerV4_2Issue(
                code="planner_schema_invalid",
                path=".".join(str(part) for part in row["loc"]),
                message=row["msg"],
            )
            for row in exc.errors(include_url=False)
        ) from exc


def canonical_v4_2_bytes(value: PlannerV4Model) -> bytes:
    return json.dumps(
        value.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _policy(
    ownership: ViolationOwnershipV4_2,
    current_owner: str,
    proposed_owner: str,
    derivation: str,
    required_input: str,
    failure: str,
    replay: Literal["disappears", "remains", "redesigned"],
) -> ViolationPolicyV4_2:
    return ViolationPolicyV4_2(
        ownership=ownership,
        current_owner=current_owner,
        proposed_owner=proposed_owner,
        derivation=derivation,
        required_input=required_input,
        failure=failure,
        replay_disposition=replay,
    )


_D = ViolationOwnershipV4_2.DETERMINISTIC
_P = ViolationOwnershipV4_2.PRE_GENERATION
_C = ViolationOwnershipV4_2.CREATIVE
_O = ViolationOwnershipV4_2.OBSOLETE


VIOLATION_POLICIES_V4_2: dict[str, ViolationPolicyV4_2] = {
    "investor_argument_slide_unknown": _policy(
        _D,
        "model",
        "enricher",
        "Map ordered semantic roles to generated IDs and argument stages.",
        "ordered slides",
        "fail if a role has no stage mapping",
        "disappears",
    ),
    "investor_evaluation_criteria_invalid": _policy(
        _D,
        "model",
        "envelope",
        "Emit the fixed ordered investor rubric.",
        "planner contract version",
        "fail envelope construction",
        "disappears",
    ),
    "financial_evidence_semantics_mismatch": _policy(
        _D,
        "model",
        "fact envelope",
        "Classify each exact number from local source context.",
        "number plus source references",
        "fail on ambiguous protected financial fact",
        "disappears",
    ),
    "financial_evidence_not_source_bound": _policy(
        _D,
        "model",
        "fact envelope",
        "Attach number identity and request-scoped provenance directly.",
        "source package number record",
        "fail on dangling provenance",
        "disappears",
    ),
    "investor_decision_not_source_supported": _policy(
        _P,
        "model",
        "pre-generation close gate",
        "Derive permitted decisions only from funding/next-step evidence.",
        "source-backed close evidence",
        "stop before generation",
        "disappears",
    ),
    "closing_decision_language_mismatch": _policy(
        _P,
        "model",
        "envelope plus creative validator",
        "Compare unchanged closing copy with the selected source-backed decision.",
        "derived decision and closing copy",
        "reject candidate; never rewrite copy",
        "disappears",
    ),
    "duplicate_slide_id": _policy(
        _D,
        "model",
        "enricher",
        "Assign contiguous p01..pNN identities.",
        "ordered slide list",
        "fail on impossible ordering",
        "disappears",
    ),
    "duplicate_semantic_role": _policy(
        _O,
        "validator",
        "removed",
        "Allow repeated roles when narrative jobs remain distinct.",
        "semantic roles and narrative jobs",
        "reject duplicate narrative jobs, not repeated roles",
        "redesigned",
    ),
    "narrative_arc_sequence_mismatch": _policy(
        _D,
        "model",
        "enricher",
        "Derive arc from ordered slide roles.",
        "ordered slides",
        "fail if role is unsupported",
        "disappears",
    ),
    "previous_argument_relationship_invalid": _policy(
        _D,
        "model",
        "enricher",
        "Derive previous ID from list position.",
        "ordered slides",
        "fail on non-list input",
        "disappears",
    ),
    "next_argument_relationship_invalid": _policy(
        _D,
        "model",
        "enricher",
        "Derive next ID from list position.",
        "ordered slides",
        "fail on non-list input",
        "disappears",
    ),
    "copy_budget_count_mismatch": _policy(
        _D,
        "model",
        "enricher",
        "Count audience-facing words from unchanged copy and visual labels.",
        "creative slide copy",
        "reject actual over/under-capacity copy",
        "disappears",
    ),
    "compiler_support_misdeclared": _policy(
        _D,
        "model",
        "compiler capability envelope",
        "Look up the selected composition in versioned Compiler v3 capabilities.",
        "archetype, variant, visual type",
        "reject unsupported combination",
        "disappears",
    ),
    "compiler_v2_grammar_missing": _policy(
        _D,
        "model",
        "compiler capability envelope",
        "Declare Compiler v3 primitives from code-owned capabilities.",
        "compiler version",
        "reject unsupported archetype",
        "disappears",
    ),
    "metric_number_not_in_slide_evidence": _policy(
        _D,
        "model",
        "enricher",
        "Union metric number refs into slide provenance.",
        "visual metrics",
        "fail on unknown number",
        "disappears",
    ),
    "nested_evidence_not_declared": _policy(
        _D,
        "model",
        "enricher",
        "Stable-union all nested evidence into the slide manifest.",
        "creative body and visual evidence",
        "fail on unknown evidence",
        "disappears",
    ),
    "incomplete_source_coverage": _policy(
        _O,
        "validator",
        "source coverage ledger",
        "Account for every source slide as represented or not selected without forcing irrelevant use.",
        "evidence-to-source map",
        "fail only on unknown provenance",
        "redesigned",
    ),
    "high_value_asset_manifest_mismatch": _policy(
        _D,
        "model",
        "asset envelope",
        "Derive high-value asset IDs from request-scoped asset records.",
        "source assets",
        "fail on cross-source or invalid asset",
        "disappears",
    ),
    "empty_asset_intent_inconsistent": _policy(
        _D,
        "model",
        "enricher",
        "An absent asset deterministically has no role, treatment, or rationale.",
        "nullable asset selection",
        "reject contradictory selected-asset intent",
        "disappears",
    ),
    "mixed_unit_shared_scale": _policy(
        _P,
        "model",
        "creative validator",
        "Compare units before accepting proportional encoding.",
        "selected metric IDs",
        "reject candidate; never change encoding",
        "remains",
    ),
    "metric_encoding_missing": _policy(
        _C,
        "model",
        "model",
        "Model must choose a truthful encoding for selected metrics.",
        "verified metrics",
        "reject candidate",
        "remains",
    ),
    "metric_proof_cardinality_invalid": _policy(
        _C,
        "model",
        "model",
        "Model must select one to four metrics for the primitive.",
        "verified metrics",
        "reject candidate",
        "remains",
    ),
    "ordinal_stage_contract_invalid": _policy(
        _C,
        "model",
        "model",
        "Model must not mix ordinal stages with quantitative metrics.",
        "steps and metrics",
        "reject candidate",
        "remains",
    ),
    "problem_landscape_cardinality_invalid": _policy(
        _C,
        "model",
        "model",
        "Model must express three to six evidenced problem-system items.",
        "verified problem evidence",
        "reject candidate",
        "remains",
    ),
    "unsupported_compiler_v2_variant": _policy(
        _O,
        "v2 validator",
        "Compiler v3 capability validator",
        "Replace v2 naming with exact v3 composition capability.",
        "v3 capability envelope",
        "reject unsupported v3 combination",
        "redesigned",
    ),
    "unsupported_compiler_v2_visual_type": _policy(
        _O,
        "v2 validator",
        "Compiler v3 capability validator",
        "Replace v2 naming with exact v3 visual capability.",
        "v3 capability envelope",
        "reject unsupported v3 combination",
        "redesigned",
    ),
    "weak_opening_closing_relationship": _policy(
        _C,
        "model",
        "model",
        "Model must explicitly resolve the opening in its closing move.",
        "whole-deck narrative",
        "reject candidate",
        "remains",
    ),
}


def classify_recorded_violations_v4_2(validation_report: dict[str, Any]) -> dict[str, Any]:
    issues = list(validation_report.get("issues") or [])
    rows = []
    for ordinal, issue in enumerate(issues, start=1):
        policy = VIOLATION_POLICIES_V4_2.get(issue["code"])
        if policy is None:
            raise ValueError(f"unclassified_violation:{issue['code']}")
        rows.append(
            {
                "ordinal": ordinal,
                "code": issue["code"],
                "path": issue["path"],
                "message": issue["message"],
                "ownership": policy.ownership.value,
                "currentOwner": policy.current_owner,
                "proposedOwner": policy.proposed_owner,
                "deterministicDerivation": policy.derivation,
                "requiredInput": policy.required_input,
                "failureBehaviour": policy.failure,
                "replayDisposition": policy.replay_disposition,
            }
        )
    counts = Counter(row["ownership"] for row in rows)
    dispositions = Counter(row["replayDisposition"] for row in rows)
    return {
        "contractVersion": PLANNER_SCHEMA_VERSION_V4_2,
        "inputViolationCount": len(rows),
        "ownershipCounts": dict(sorted(counts.items())),
        "replayDispositionCounts": dict(sorted(dispositions.items())),
        "allViolationsClassified": len(rows) == 122,
        "violations": rows,
    }
