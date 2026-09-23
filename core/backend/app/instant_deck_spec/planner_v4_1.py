"""Investor-only PlannerDeckSpec v4.1 contract.

This additive, offline-only minor version preserves ``planner_deck_spec.v4``
unchanged while replacing its open-ended audience strategy with a bounded
investor contract.  It performs no provider, compiler, network, persistence,
worker, or publication operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Annotated, Any, Iterable, Literal

from pydantic import Field, StringConstraints, ValidationError

from .planner_v4 import (
    CommercialCoverageStatusV4,
    PLANNER_NORMALIZER_VERSION_V4,
    PLANNER_SCHEMA_VERSION_V4,
    PlannerCommercialCategoryV4,
    PlannerAssetStrategyV4,
    PlannerBrandDirectionV4,
    PlannerDeckSpecV4,
    PlannerDeckStrategyV4,
    PlannerSlideV4,
    PlannerVisualRhythmV4,
    PlannerV4Issue,
    PlannerV4Model,
    PlannerV4ValidationError,
    SemanticSlideRoleV4,
    planner_v4_slide_bounds,
    normalize_planner_deck_spec_v4,
    validate_planner_deck_spec_v4,
)
from .models import DeckSpec, NormalizedSourcePackage
from .source_package_v2 import NormalizedSourcePackageV2, ProtectedCoverageCategory


PLANNER_SCHEMA_VERSION_V4_1 = "planner_deck_spec.v4.1"
PLANNER_NORMALIZER_VERSION_V4_1 = "instant-deck-planner-normalizer.v4.1"


class InvestorSubtypeV4_1(str, Enum):
    ANGEL = "angel"
    VENTURE_CAPITAL = "venture_capital"
    FAMILY_OFFICE = "family_office"
    STRATEGIC = "strategic"
    IMPACT = "impact"
    INVESTMENT_COMMITTEE = "investment_committee"
    INSTITUTIONAL_FUND = "institutional_fund"
    UNSPECIFIED_INVESTOR = "unspecified_investor"


class FundraisingStageV4_1(str, Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B_OR_LATER = "series_b_or_later"
    GROWTH = "growth"
    PROGRAMME = "programme"
    UNSPECIFIED = "unspecified"


class InvestmentContextV4_1(str, Enum):
    NEW_INVESTMENT = "new_investment"
    FOLLOW_ON = "follow_on"
    STRATEGIC_INVESTMENT = "strategic_investment"
    PROGRAMME_FUNDING = "programme_funding"
    INVESTMENT_COMMITTEE_REVIEW = "investment_committee_review"
    UNSPECIFIED = "unspecified"


class InvestorSophisticationV4_1(str, Enum):
    GENERALIST = "generalist"
    EXPERIENCED = "experienced"
    SECTOR_SPECIALIST = "sector_specialist"
    INSTITUTIONAL = "institutional"
    UNSPECIFIED = "unspecified"


class DiligencePriorityV4_1(str, Enum):
    TRACTION = "traction"
    BUSINESS_MODEL = "business_model"
    MARKET = "market"
    TEAM = "team"
    DEFENSIBILITY = "defensibility"
    FINANCIALS = "financials"
    USE_OF_FUNDS = "use_of_funds"
    IMPACT = "impact"
    GOVERNANCE = "governance"


class DesiredInvestorDecisionV4_1(str, Enum):
    REQUEST_MEETING = "request_meeting"
    ADVANCE_TO_DILIGENCE = "advance_to_diligence"
    APPROVE_INVESTMENT = "approve_investment"
    PARTICIPATE_IN_ROUND = "participate_in_round"
    FUND_PROGRAMME = "fund_programme"
    APPROVE_NEXT_INVESTMENT_STAGE = "approve_next_investment_stage"


class InvestorCoverageCategoryV4_1(str, Enum):
    OPPORTUNITY_THESIS = "opportunity_thesis"
    PROBLEM = "problem"
    SOLUTION_PRODUCT = "solution_product"
    WHY_NOW = "why_now"
    TRACTION = "traction"
    BUSINESS_MODEL = "business_model"
    MARKET = "market"
    TEAM_FOUNDER = "team_founder"
    DEFENSIBILITY = "defensibility"
    FINANCIAL_EVIDENCE = "financial_evidence"
    FUNDING_ASK = "funding_ask"
    USE_OF_FUNDS = "use_of_funds"
    INVESTOR_NEXT_STEP = "investor_next_step"


class InvestorCoverageStatusV4_1(str, Enum):
    PRESENT_AND_USED = "evidence_present_and_used"
    PRESENT_BUT_EXCLUDED = "evidence_present_but_excluded"
    ABSENT_FROM_SOURCE = "evidence_absent_from_source"
    AMBIGUOUS_OR_UNSUPPORTED = "evidence_ambiguous_or_unsupported"


class EvidenceGapTypeV4_1(str, Enum):
    ABSENT = "evidence_absent"
    AMBIGUOUS = "evidence_ambiguous"


class InvestorArgumentStageV4_1(str, Enum):
    OPPORTUNITY = "opportunity"
    PROBLEM_CHANGE = "problem_change"
    SOLUTION = "solution"
    EVIDENCE = "evidence"
    ECONOMICS = "economics"
    SCALE = "scale"
    RIGHT_TO_WIN = "right_to_win"
    CAPITAL_PROPOSITION = "capital_proposition"
    INVESTOR_DECISION = "investor_decision"


class InvestorEvaluationCriterionV4_1(str, Enum):
    INVESTMENT_THESIS_CLARITY = "investment_thesis_clarity"
    COMMERCIAL_COMPLETENESS = "commercial_completeness"
    CREDIBILITY = "credibility"
    TRACTION_INTERPRETATION = "traction_interpretation"
    ECONOMIC_CLARITY = "economic_clarity"
    MARKET_LOGIC = "market_logic"
    FOUNDER_MARKET_FIT = "founder_market_fit"
    DEFENSIBILITY = "defensibility"
    ASK_CLARITY = "ask_clarity"
    CAPITAL_TO_MILESTONE_LOGIC = "capital_to_milestone_logic"
    DILIGENCE_READINESS = "diligence_readiness"
    CLOSING_STRENGTH = "closing_strength"


class InvestorFinancialKindV4_1(str, Enum):
    REVENUE = "revenue"
    VALUATION = "valuation"
    FUNDING_REQUEST = "funding_request"
    ASSETS_UNDER_MANAGEMENT = "assets_under_management"
    MARKET_SIZE = "market_size"
    TRANSACTION_FEE = "transaction_fee"
    TRACTION_METRIC = "traction_metric"
    OTHER = "other"


class InvestorProfileV4_1(PlannerV4Model):
    investor_subtype: InvestorSubtypeV4_1
    investor_subtype_evidence_ids: list[str] = Field(min_length=0, max_length=4)
    company_stage: FundraisingStageV4_1
    company_stage_evidence_ids: list[str] = Field(min_length=0, max_length=4)
    investment_context: InvestmentContextV4_1
    investment_context_evidence_ids: list[str] = Field(min_length=0, max_length=4)
    sophistication_level: InvestorSophisticationV4_1
    likely_diligence_priorities: list[DiligencePriorityV4_1] = Field(
        min_length=1,
        max_length=9,
    )
    desired_investor_decision: DesiredInvestorDecisionV4_1
    decision_evidence_ids: list[str] = Field(min_length=1, max_length=6)


class InvestorEvidenceGapV4_1(PlannerV4Model):
    gap_type: EvidenceGapTypeV4_1
    explanation: Annotated[str, StringConstraints(min_length=12, max_length=180)]
    candidate_evidence_ids: list[str] = Field(min_length=0, max_length=6)


class InvestorCoverageExclusionV4_1(PlannerV4Model):
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    reason: Annotated[str, StringConstraints(min_length=12, max_length=180)]


class InvestorCoverageV4_1(PlannerV4Model):
    category: InvestorCoverageCategoryV4_1
    status: InvestorCoverageStatusV4_1
    used_evidence_ids: list[str] = Field(min_length=0, max_length=10)
    exclusion: InvestorCoverageExclusionV4_1 | None
    evidence_gap: InvestorEvidenceGapV4_1 | None


class InvestorArgumentMoveV4_1(PlannerV4Model):
    stage: InvestorArgumentStageV4_1
    slide_ids: list[str] = Field(min_length=1, max_length=4)


class InvestorFinancialEvidenceV4_1(PlannerV4Model):
    number_id: str
    kind: InvestorFinancialKindV4_1
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class PlannerDeckStrategyV4_1(PlannerV4Model):
    product_purpose: Literal["investor_presentation"]
    investor_profile: InvestorProfileV4_1
    central_thesis: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    narrative_tension: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    narrative_arc: list[SemanticSlideRoleV4] = Field(min_length=8, max_length=14)
    opening_promise: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    closing_resolution: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    mandatory_fact_ids: list[str] = Field(min_length=0, max_length=24)
    investor_coverage: list[InvestorCoverageV4_1] = Field(min_length=13, max_length=13)
    investor_argument: list[InvestorArgumentMoveV4_1] = Field(min_length=9, max_length=9)
    financial_evidence: list[InvestorFinancialEvidenceV4_1] = Field(
        min_length=0,
        max_length=16,
    )
    evaluation_criteria: list[InvestorEvaluationCriterionV4_1] = Field(
        min_length=12,
        max_length=12,
    )
    brand_direction: PlannerBrandDirectionV4
    visual_rhythm: PlannerVisualRhythmV4
    asset_strategy: PlannerAssetStrategyV4


class PlannerDeckSpecV4_1(PlannerV4Model):
    schema_version: Literal["planner_deck_spec.v4.1"]
    normalizer_version: Literal["instant-deck-planner-normalizer.v4.1"]
    source_package_id: str
    source_checksum: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    deck_title: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    deck_strategy: PlannerDeckStrategyV4_1
    slides: list[PlannerSlideV4] = Field(min_length=8, max_length=14)


@dataclass(frozen=True, slots=True)
class PlannerV4_1Issue:
    code: str
    path: str
    message: str


class PlannerV4_1ValidationError(ValueError):
    def __init__(self, issues: Iterable[PlannerV4_1Issue]):
        self.issues = tuple(issues)
        summary = "; ".join(f"{row.code}@{row.path}" for row in self.issues)
        super().__init__(summary or "planner_v4_1_validation_failed")


_ARGUMENT_ORDER = list(InvestorArgumentStageV4_1)
_EVALUATION_ORDER = list(InvestorEvaluationCriterionV4_1)

_ARGUMENT_ROLES = {
    InvestorArgumentStageV4_1.OPPORTUNITY: {"cover", "thesis"},
    InvestorArgumentStageV4_1.PROBLEM_CHANGE: {"problem"},
    InvestorArgumentStageV4_1.SOLUTION: {"solution", "process"},
    InvestorArgumentStageV4_1.EVIDENCE: {"traction"},
    InvestorArgumentStageV4_1.ECONOMICS: {"business_model"},
    InvestorArgumentStageV4_1.SCALE: {"market_opportunity"},
    InvestorArgumentStageV4_1.RIGHT_TO_WIN: {
        "founder_team",
        "ecosystem",
        "network_defensibility",
    },
    InvestorArgumentStageV4_1.CAPITAL_PROPOSITION: {"investment_proposition"},
    InvestorArgumentStageV4_1.INVESTOR_DECISION: {"closing"},
}


def _identifier(row: Any) -> str:
    return getattr(row, "fact_id", getattr(row, "claim_id", getattr(row, "number_id", "")))


def _source_text(package: NormalizedSourcePackageV2, evidence_ids: Iterable[str]) -> str:
    requested = set(evidence_ids)
    rows = [*package.facts, *package.claims, *package.numbers]
    values = []
    for row in rows:
        if _identifier(row) not in requested:
            continue
        values.extend(
            str(value)
            for value in (
                getattr(row, "text", None),
                getattr(row, "qualifier", None),
                getattr(row, "unit", None),
            )
            if value
        )
    return " ".join(values).casefold()


def classify_investor_number_v4_1(qualifier: str) -> InvestorFinancialKindV4_1:
    """Classify financial meanings without collapsing unlike monetary values."""

    text = " ".join(re.findall(r"[a-z0-9]+", qualifier.casefold()))
    if "assets under management" in text or re.search(r"\baum\b", text):
        return InvestorFinancialKindV4_1.ASSETS_UNDER_MANAGEMENT
    if "valuation" in text or "post money" in text or "pre money" in text:
        return InvestorFinancialKindV4_1.VALUATION
    if any(term in text for term in ("funding sought", "funding request", "capital raise")):
        return InvestorFinancialKindV4_1.FUNDING_REQUEST
    if "transaction fee" in text or "take rate" in text:
        return InvestorFinancialKindV4_1.TRANSACTION_FEE
    if any(term in text for term in ("market size", "transaction value", "addressable market")):
        return InvestorFinancialKindV4_1.MARKET_SIZE
    if any(term in text for term in ("revenue", "arr", "mrr", "sales")):
        return InvestorFinancialKindV4_1.REVENUE
    if any(term in text for term in ("buyer", "user", "order", "customer")):
        return InvestorFinancialKindV4_1.TRACTION_METRIC
    return InvestorFinancialKindV4_1.OTHER


def _coverage_candidates(
    package: NormalizedSourcePackageV2,
) -> dict[InvestorCoverageCategoryV4_1, set[str]]:
    facts = list(package.facts)
    result = {category: set() for category in InvestorCoverageCategoryV4_1}
    protected = {row.category: set(row.protected_fact_ids) for row in package.protected_coverage}
    result[InvestorCoverageCategoryV4_1.TRACTION] |= protected.get(
        ProtectedCoverageCategory.TRACTION,
        set(),
    )
    result[InvestorCoverageCategoryV4_1.FINANCIAL_EVIDENCE] |= protected.get(
        ProtectedCoverageCategory.FINANCIAL,
        set(),
    )
    result[InvestorCoverageCategoryV4_1.FUNDING_ASK] |= protected.get(
        ProtectedCoverageCategory.ASK,
        set(),
    )
    result[InvestorCoverageCategoryV4_1.TEAM_FOUNDER] |= protected.get(
        ProtectedCoverageCategory.FOUNDER,
        set(),
    )
    for fact in facts:
        text = fact.text.casefold()
        identifier = fact.fact_id
        if fact.kind in {"identity", "product"}:
            result[InvestorCoverageCategoryV4_1.OPPORTUNITY_THESIS].add(identifier)
        if fact.kind == "general" and any(
            term in text for term in ("problem", "fragment", "prevent", "block", "manual")
        ):
            result[InvestorCoverageCategoryV4_1.PROBLEM].add(identifier)
        if fact.kind in {"product", "process"}:
            result[InvestorCoverageCategoryV4_1.SOLUTION_PRODUCT].add(identifier)
        if any(term in text for term in ("why now", "timing", "window", "regulatory shift")):
            result[InvestorCoverageCategoryV4_1.WHY_NOW].add(identifier)
        if fact.kind == "metric":
            result[InvestorCoverageCategoryV4_1.TRACTION].add(identifier)
        if fact.kind == "financial" and any(
            term in text for term in ("fee", "revenue", "margin", "business model")
        ):
            result[InvestorCoverageCategoryV4_1.BUSINESS_MODEL].add(identifier)
        if any(
            term in text
            for term in (
                "serviceable market",
                "addressable market",
                "market size",
                "transaction value",
            )
        ) or re.search(r"\b(?:tam|sam|som)\b", text):
            result[InvestorCoverageCategoryV4_1.MARKET].add(identifier)
        if fact.kind == "team":
            result[InvestorCoverageCategoryV4_1.TEAM_FOUNDER].add(identifier)
        if fact.kind == "partnership" or any(
            term in text for term in ("defens", "network", "proprietary", "moat")
        ):
            result[InvestorCoverageCategoryV4_1.DEFENSIBILITY].add(identifier)
        if fact.kind == "financial":
            result[InvestorCoverageCategoryV4_1.FINANCIAL_EVIDENCE].add(identifier)
        if any(term in text for term in ("seeking", "funding request", "capital raise")):
            result[InvestorCoverageCategoryV4_1.FUNDING_ASK].add(identifier)
        if any(term in text for term in ("to expand", "use of funds", "launch", "milestone")):
            result[InvestorCoverageCategoryV4_1.USE_OF_FUNDS].add(identifier)
        if any(term in text for term in ("next decision", "next step", "meeting", "diligence")):
            result[InvestorCoverageCategoryV4_1.INVESTOR_NEXT_STEP].add(identifier)
    return result


def derive_investor_coverage_v4_1(
    package: NormalizedSourcePackageV2,
    *, coverage_model: type[InvestorCoverageV4_1] = InvestorCoverageV4_1,
) -> tuple[InvestorCoverageV4_1, ...]:
    """Derive source presence only; the planner still chooses use or exclusion."""

    candidates = _coverage_candidates(package)
    rows = []
    for category in InvestorCoverageCategoryV4_1:
        evidence = sorted(candidates[category])
        if evidence:
            rows.append(
                coverage_model(
                    category=category,
                    status=InvestorCoverageStatusV4_1.PRESENT_AND_USED,
                    used_evidence_ids=evidence,
                    exclusion=None,
                    evidence_gap=None,
                )
            )
        else:
            rows.append(
                coverage_model(
                    category=category,
                    status=InvestorCoverageStatusV4_1.ABSENT_FROM_SOURCE,
                    used_evidence_ids=[],
                    exclusion=None,
                    evidence_gap=InvestorEvidenceGapV4_1(
                        gap_type=EvidenceGapTypeV4_1.ABSENT,
                        explanation=f"The source package contains no supported {category.value} evidence.",
                        candidate_evidence_ids=[],
                    ),
                )
            )
    return tuple(rows)


def _issue(
    issues: list[PlannerV4_1Issue],
    code: str,
    path: str,
    message: str,
) -> None:
    issues.append(PlannerV4_1Issue(code=code, path=path, message=message))


def _legacy_projection(planner: PlannerDeckSpecV4_1, package: NormalizedSourcePackageV2) -> PlannerDeckSpecV4:
    used_by_slides = {fact_id for slide in planner.slides for fact_id in slide.protected_fact_ids}
    commercial = []
    for source in package.protected_coverage:
        protected = set(source.protected_fact_ids)
        commercial.append(
            PlannerCommercialCategoryV4(
                category=source.category,
                source_status=CommercialCoverageStatusV4(source.status),
                used_fact_ids=sorted(protected & used_by_slides),
                exclusions=[],
            )
        )
    strategy = planner.deck_strategy
    legacy_strategy = PlannerDeckStrategyV4(
        audience="Investors",
        purpose="Secure a source-backed investor decision.",
        desired_decision=strategy.investor_profile.desired_investor_decision.value,
        central_thesis=strategy.central_thesis,
        narrative_tension=strategy.narrative_tension,
        narrative_arc=strategy.narrative_arc,
        opening_promise=strategy.opening_promise,
        closing_resolution=strategy.closing_resolution,
        mandatory_fact_ids=strategy.mandatory_fact_ids,
        commercial_coverage=commercial,
        brand_direction=strategy.brand_direction,
        visual_rhythm=strategy.visual_rhythm,
        asset_strategy=strategy.asset_strategy,
    )
    return PlannerDeckSpecV4(
        schema_version=PLANNER_SCHEMA_VERSION_V4,
        normalizer_version=PLANNER_NORMALIZER_VERSION_V4,
        source_package_id=planner.source_package_id,
        source_checksum=planner.source_checksum,
        deck_title=planner.deck_title,
        deck_strategy=legacy_strategy,
        slides=planner.slides,
    )


def validate_planner_deck_spec_v4_1(
    planner: PlannerDeckSpecV4_1,
    package: NormalizedSourcePackageV2,
) -> None:
    issues: list[PlannerV4_1Issue] = []
    if planner.source_package_id != package.package_id:
        _issue(issues, "source_package_mismatch", "source_package_id", planner.source_package_id)
    if planner.source_checksum != package.source_checksum:
        _issue(issues, "source_checksum_mismatch", "source_checksum", planner.source_checksum)

    evidence_ids = {
        _identifier(row) for row in [*package.facts, *package.claims, *package.numbers]
    }
    profile = planner.deck_strategy.investor_profile
    profile_refs = [
        *profile.investor_subtype_evidence_ids,
        *profile.company_stage_evidence_ids,
        *profile.investment_context_evidence_ids,
        *profile.decision_evidence_ids,
    ]
    if not set(profile_refs) <= evidence_ids:
        _issue(issues, "investor_profile_evidence_unknown", "deck_strategy.investor_profile", "unknown evidence ID")

    subtype_unspecified = profile.investor_subtype == InvestorSubtypeV4_1.UNSPECIFIED_INVESTOR
    if subtype_unspecified != (not profile.investor_subtype_evidence_ids):
        _issue(
            issues,
            "investor_subtype_evidence_mismatch",
            "deck_strategy.investor_profile.investor_subtype",
            "A specific subtype requires direct source evidence; unspecified must have none.",
        )
    if not subtype_unspecified:
        subtype_text = _source_text(package, profile.investor_subtype_evidence_ids)
        expected = profile.investor_subtype.value.replace("_", " ")
        if expected not in subtype_text:
            _issue(issues, "unsupported_investor_subtype_inference", "deck_strategy.investor_profile.investor_subtype", expected)

    stage_unspecified = profile.company_stage == FundraisingStageV4_1.UNSPECIFIED
    if stage_unspecified != (not profile.company_stage_evidence_ids):
        _issue(
            issues,
            "company_stage_evidence_mismatch",
            "deck_strategy.investor_profile.company_stage",
            "A specific stage requires direct source evidence; unspecified must have none.",
        )
    if not stage_unspecified:
        stage_text = _source_text(package, profile.company_stage_evidence_ids)
        expected = profile.company_stage.value.replace("_", " ")
        if expected not in stage_text:
            _issue(issues, "unsupported_company_stage_inference", "deck_strategy.investor_profile.company_stage", expected)

    context_unspecified = profile.investment_context == InvestmentContextV4_1.UNSPECIFIED
    if context_unspecified != (not profile.investment_context_evidence_ids):
        _issue(
            issues,
            "investment_context_evidence_mismatch",
            "deck_strategy.investor_profile.investment_context",
            "A specific investment context requires direct source evidence; unspecified must have none.",
        )

    coverage = planner.deck_strategy.investor_coverage
    coverage_by_category = {row.category: row for row in coverage}
    if len(coverage_by_category) != len(InvestorCoverageCategoryV4_1) or set(coverage_by_category) != set(InvestorCoverageCategoryV4_1):
        _issue(issues, "investor_coverage_categories_invalid", "deck_strategy.investor_coverage", "Every investor category must appear once.")
    candidates = _coverage_candidates(package)
    for category in InvestorCoverageCategoryV4_1:
        row = coverage_by_category.get(category)
        if row is None:
            continue
        source_candidates = candidates[category]
        path = f"deck_strategy.investor_coverage.{category.value}"
        used = set(row.used_evidence_ids)
        if row.evidence_gap is not None and not set(
            row.evidence_gap.candidate_evidence_ids
        ) <= evidence_ids:
            _issue(
                issues,
                "evidence_gap_candidate_unknown",
                path,
                "A typed gap may only cite request-scoped source evidence.",
            )
        if not used <= source_candidates:
            _issue(issues, "investor_coverage_not_source_bound", path, ",".join(sorted(used - source_candidates)))
        if row.status == InvestorCoverageStatusV4_1.PRESENT_AND_USED:
            if not source_candidates or not used or row.exclusion is not None or row.evidence_gap is not None:
                _issue(issues, "present_used_coverage_invalid", path, "Present-and-used coverage requires source evidence and no gap/exclusion.")
        elif row.status == InvestorCoverageStatusV4_1.PRESENT_BUT_EXCLUDED:
            if not source_candidates or used or row.exclusion is None or row.evidence_gap is not None:
                _issue(issues, "present_excluded_coverage_invalid", path, "Present-but-excluded coverage requires a reason and no used evidence.")
            elif not set(row.exclusion.evidence_ids) <= source_candidates:
                _issue(issues, "excluded_coverage_not_source_bound", path, "Excluded evidence is not source-bound.")
        elif row.status == InvestorCoverageStatusV4_1.ABSENT_FROM_SOURCE:
            if source_candidates or used or row.exclusion is not None or row.evidence_gap is None or row.evidence_gap.gap_type != EvidenceGapTypeV4_1.ABSENT:
                _issue(issues, "absent_coverage_gap_invalid", path, "Absent evidence requires a typed absent gap and no content.")
        else:
            if used or row.exclusion is not None or row.evidence_gap is None or row.evidence_gap.gap_type != EvidenceGapTypeV4_1.AMBIGUOUS:
                _issue(issues, "ambiguous_coverage_gap_invalid", path, "Ambiguous evidence requires a typed ambiguity gap.")

    argument = planner.deck_strategy.investor_argument
    stages = [row.stage for row in argument]
    if stages != _ARGUMENT_ORDER:
        _issue(issues, "investor_argument_incomplete", "deck_strategy.investor_argument", "The cumulative investor reasoning stages must appear once in canonical argument order.")
    slides_by_id = {slide.slide_id: slide for slide in planner.slides}
    previous_min = 0
    for index, move in enumerate(argument):
        referenced = [slides_by_id.get(slide_id) for slide_id in move.slide_ids]
        if any(slide is None for slide in referenced):
            _issue(issues, "investor_argument_slide_unknown", f"deck_strategy.investor_argument[{index}]", "unknown slide")
            continue
        roles = {slide.semantic_role.value for slide in referenced if slide is not None}
        if not roles <= _ARGUMENT_ROLES[move.stage]:
            _issue(issues, "investor_argument_role_mismatch", f"deck_strategy.investor_argument[{index}]", ",".join(sorted(roles)))
        current_min = min(slide.position for slide in referenced if slide is not None)
        if current_min < previous_min:
            _issue(issues, "investor_argument_not_cumulative", f"deck_strategy.investor_argument[{index}]", str(current_min))
        previous_min = current_min

    if planner.deck_strategy.evaluation_criteria != _EVALUATION_ORDER:
        _issue(issues, "investor_evaluation_criteria_invalid", "deck_strategy.evaluation_criteria", "Investor-specific evaluation criteria must be complete and ordered.")

    numbers = {row.number_id: row for row in package.numbers}
    financial_rows = planner.deck_strategy.financial_evidence
    if len({row.number_id for row in financial_rows}) != len(financial_rows):
        _issue(issues, "duplicate_financial_evidence", "deck_strategy.financial_evidence", "number IDs must be unique")
    for index, row in enumerate(financial_rows):
        source = numbers.get(row.number_id)
        path = f"deck_strategy.financial_evidence[{index}]"
        if source is None:
            _issue(issues, "financial_evidence_number_unknown", path, row.number_id)
            continue
        expected = classify_investor_number_v4_1(source.qualifier or "")
        if row.kind != expected:
            _issue(issues, "financial_evidence_semantics_mismatch", path, f"{row.kind.value}!={expected.value}")
        if row.number_id not in row.evidence_ids or not set(row.evidence_ids) <= evidence_ids:
            _issue(issues, "financial_evidence_not_source_bound", path, row.number_id)

    funding = coverage_by_category.get(InvestorCoverageCategoryV4_1.FUNDING_ASK)
    if profile.desired_investor_decision in {
        DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT,
        DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND,
        DesiredInvestorDecisionV4_1.FUND_PROGRAMME,
        DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE,
    } and (
        funding is None
        or funding.status != InvestorCoverageStatusV4_1.PRESENT_AND_USED
        or not candidates[InvestorCoverageCategoryV4_1.FUNDING_ASK]
    ):
        _issue(issues, "funding_ask_fabricated", "deck_strategy.investor_profile.desired_investor_decision", profile.desired_investor_decision.value)
    decision_text = _source_text(package, profile.decision_evidence_ids)
    decision_terms = {
        DesiredInvestorDecisionV4_1.REQUEST_MEETING: ("meeting", "next step"),
        DesiredInvestorDecisionV4_1.ADVANCE_TO_DILIGENCE: ("diligence",),
        DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT: ("seeking", "funded", "investment"),
        DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND: ("round",),
        DesiredInvestorDecisionV4_1.FUND_PROGRAMME: ("programme", "program"),
        DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE: ("stage",),
    }[profile.desired_investor_decision]
    if not any(term in decision_text for term in decision_terms):
        _issue(issues, "investor_decision_not_source_supported", "deck_strategy.investor_profile.decision_evidence_ids", profile.desired_investor_decision.value)
    closing = planner.slides[-1]
    if closing.semantic_role.value != "closing" or not set(profile.decision_evidence_ids) <= set(closing.evidence_ids):
        _issue(issues, "closing_decision_not_source_supported", "slides[-1]", closing.slide_id)
    closing_text = " ".join(
        [
            closing.headline,
            closing.subhead or "",
            closing.audience_claim,
            closing.consequence,
            *(row.text for row in closing.body),
        ]
    ).casefold()
    closing_terms = {
        DesiredInvestorDecisionV4_1.REQUEST_MEETING: ("meeting", "meet"),
        DesiredInvestorDecisionV4_1.ADVANCE_TO_DILIGENCE: ("diligence",),
        DesiredInvestorDecisionV4_1.APPROVE_INVESTMENT: ("fund", "back", "invest"),
        DesiredInvestorDecisionV4_1.PARTICIPATE_IN_ROUND: ("round", "participate"),
        DesiredInvestorDecisionV4_1.FUND_PROGRAMME: ("fund", "programme", "program"),
        DesiredInvestorDecisionV4_1.APPROVE_NEXT_INVESTMENT_STAGE: ("approve", "stage"),
    }[profile.desired_investor_decision]
    if not any(term in closing_text for term in closing_terms):
        _issue(
            issues,
            "closing_decision_language_mismatch",
            "slides[-1]",
            profile.desired_investor_decision.value,
        )

    try:
        validate_planner_deck_spec_v4(_legacy_projection(planner, package), package)
    except PlannerV4ValidationError as exc:
        issues.extend(
            PlannerV4_1Issue(code=row.code, path=row.path, message=row.message)
            for row in exc.issues
        )
    if issues:
        raise PlannerV4_1ValidationError(issues)


def parse_and_validate_planner_v4_1(raw_json: str, package: NormalizedSourcePackageV2) -> PlannerDeckSpecV4_1:
    try:
        planner = PlannerDeckSpecV4_1.model_validate_json(raw_json, strict=True)
    except ValidationError as exc:
        raise PlannerV4_1ValidationError(
            PlannerV4_1Issue(
                code="planner_schema_invalid",
                path=".".join(str(part) for part in row["loc"]),
                message=row["msg"],
            )
            for row in exc.errors(include_url=False)
        ) from exc
    validate_planner_deck_spec_v4_1(planner, package)
    return planner


def normalize_planner_deck_spec_v4_1(
    planner: PlannerDeckSpecV4_1,
    package_v2: NormalizedSourcePackageV2,
    canonical_package_v1: NormalizedSourcePackage,
) -> DeckSpec:
    """Normalize through the unchanged v4 bridge after investor validation."""

    validate_planner_deck_spec_v4_1(planner, package_v2)
    from .compiler_source_bridge_v4_1 import (
        alias_planner_payload_v4_1,
        build_compiler_source_bridge_v4_1,
    )

    bridge = build_compiler_source_bridge_v4_1(package_v2, canonical_package_v1)
    legacy = _legacy_projection(planner, package_v2)
    aliased_legacy = PlannerDeckSpecV4.model_validate_json(
        json.dumps(
            alias_planner_payload_v4_1(
                legacy.model_dump(mode="json"), bridge.manifest
            ),
            sort_keys=True,
            separators=(",", ":"),
        ),
        strict=True,
    )
    canonical = normalize_planner_deck_spec_v4(
        aliased_legacy,
        bridge.aliased_package_v2,
        bridge.compiler_package_v1,
    )
    return canonical.model_copy(
        update={
            "audience": "Investors",
            "narrative": canonical.narrative.model_copy(
                update={
                    "audience_need": planner.deck_strategy.investor_profile.desired_investor_decision.value,
                }
            ),
        }
    )


def normalize_planner_deck_spec_v4_1_with_source_bridge(
    planner: PlannerDeckSpecV4_1,
    package_v2: NormalizedSourcePackageV2,
    canonical_package_v1: NormalizedSourcePackage,
) -> tuple[DeckSpec, "CompilerSourceBridgeBundleV4_1"]:
    """Return the canonical DeckSpec and the exact compiler source package."""

    from .compiler_source_bridge_v4_1 import (
        CompilerSourceBridgeBundleV4_1,
        build_compiler_source_bridge_v4_1,
    )

    canonical = normalize_planner_deck_spec_v4_1(
        planner, package_v2, canonical_package_v1
    )
    bridge: CompilerSourceBridgeBundleV4_1 = build_compiler_source_bridge_v4_1(
        package_v2, canonical_package_v1
    )
    return canonical, bridge


def source_bound_planner_schema_v4_1(package: NormalizedSourcePackageV2) -> dict[str, Any]:
    schema = PlannerDeckSpecV4_1.model_json_schema()
    evidence = sorted(
        {_identifier(row) for row in [*package.facts, *package.claims, *package.numbers]}
    )
    protected = sorted(
        {fact_id for row in package.protected_coverage for fact_id in row.protected_fact_ids}
    )
    definitions = schema.setdefault("$defs", {})
    definitions.update(
        {
            "AllowedEvidenceId": {"type": "string", "enum": evidence},
            "AllowedProtectedFactId": {"type": "string", "enum": protected},
            "AllowedSourceSlideId": {"type": "string", "enum": [row.source_slide_id for row in package.source_slides]},
            "AllowedAssetId": {"type": "string", "enum": [row.asset_id for row in package.assets]},
            "AllowedNumberId": {"type": "string", "enum": [row.number_id for row in package.numbers]},
        }
    )
    evidence_arrays = {
        "evidence_ids",
        "used_evidence_ids",
        "candidate_evidence_ids",
        "investor_subtype_evidence_ids",
        "company_stage_evidence_ids",
        "investment_context_evidence_ids",
        "decision_evidence_ids",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("discriminator", None)
            if "oneOf" in value:
                value["anyOf"] = value.pop("oneOf")
            properties = value.get("properties")
            if isinstance(properties, dict):
                for key, child in list(properties.items()):
                    if key in evidence_arrays:
                        child["items"] = {"$ref": "#/$defs/AllowedEvidenceId"}
                    elif key in {"mandatory_fact_ids", "protected_fact_ids"}:
                        child["items"] = {"$ref": "#/$defs/AllowedProtectedFactId"}
                    elif key == "source_slide_ids":
                        child["items"] = {"$ref": "#/$defs/AllowedSourceSlideId"}
                    elif key in {"asset_id", "asset_ref"}:
                        properties[key] = {
                            "anyOf": [
                                {"$ref": "#/$defs/AllowedAssetId"},
                                {"type": "null"},
                            ]
                        } if key == "asset_ref" else {"$ref": "#/$defs/AllowedAssetId"}
                    elif key in {"number_id", "number_ref"}:
                        properties[key] = {"$ref": "#/$defs/AllowedNumberId"}
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
    schema["$id"] = "https://deck.aistack.codes/schemas/planner-deck-spec.v4.1.json"
    return schema


def canonical_planner_v4_1_bytes(planner: PlannerDeckSpecV4_1) -> bytes:
    return json.dumps(
        planner.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
