"""Separate private audit evidence from the context given to the deck author.

The compiler retains the complete canonical context.  The provider receives a
purpose-built authoring view: classified company evidence, verified research,
AI-VC conclusions, brand and approved visual references.  Source presentation
notes and internal critique/diagnostics never become candidate deck copy.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


_EDITORIAL = re.compile(
    r"\b(?:concept test deck|use this deck to test|test deck v?2|does the redesign|"
    r"key test|concept only|not a production claim|author note|design instruction|"
    r"evaluation rubric|source slide numbering|quality question|editorial note)\b",
    re.IGNORECASE,
)

_PRIVATE_STRATEGY_FIELDS = {
    "companyIntelligence",
    "investmentCommitteeReview",
    "diagnostics",
    "failureDiagnostics",
    "methodologyRetrievalTrace",
    "architectureIntelligenceTrace",
    "financialIntelligenceTrace",
    "memoryTrace",
    "skillExecutionTrace",
    "skillSelection",
    "activeSkills",
}


def _clean_company_facts(facts: object, *, excluded_ids: set[str] | None = None) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for value in facts if isinstance(facts, list) else []:
        if not isinstance(value, dict):
            continue
        if str(value.get("factId") or "") in (excluded_ids or set()):
            continue
        text = " ".join(str(value.get("text") or "").split())
        if not text or _EDITORIAL.search(text):
            continue
        cleaned.append(deepcopy(value))
    return cleaned


def _authoring_strategy(strategy: object) -> dict[str, Any]:
    if not isinstance(strategy, dict):
        return {}
    return {
        key: deepcopy(value)
        for key, value in strategy.items()
        if key not in _PRIVATE_STRATEGY_FIELDS
    }


def _authoring_external_research(research: object, strategy: object = None) -> dict[str, Any]:
    """Expose verified evidence, never internal search diagnostics or budgets."""
    if not isinstance(research, dict):
        return {"claims": []}
    all_claims = {
        str(claim.get("id")): deepcopy(claim)
        for claim in research.get("claims", [])
        if isinstance(claim, dict) and claim.get("category") == "external_research" and claim.get("id")
    }
    synthesis = strategy.get("researchSynthesis") if isinstance(strategy, dict) else {}
    impacts = synthesis.get("finding_impacts", []) if isinstance(synthesis, dict) else []
    selected: dict[str, list[dict[str, Any]]] = {}
    rejected: set[str] = set()
    for impact in impacts if isinstance(impacts, list) else []:
        if not isinstance(impact, dict):
            continue
        for evidence_id in impact.get("evidence_ids") or []:
            evidence_id = str(evidence_id)
            if impact.get("disposition") == "use":
                selected.setdefault(evidence_id, []).append(deepcopy(impact))
            elif impact.get("disposition") == "reject":
                rejected.add(evidence_id)
    # A successful strategy controls research selection.  Source-only fallback
    # has no model decision, so verified claims remain available and explicitly
    # marked unassessed for the final author instead of disappearing.
    model_authored = isinstance(strategy, dict) and strategy.get("architectureSource") == "model_authored"
    chosen_ids = set(selected) if model_authored else set(all_claims) - rejected
    claims = []
    for evidence_id in chosen_ids:
        claim = all_claims.get(evidence_id)
        if not claim:
            continue
        claim["citationFactId"] = evidence_id + "_citation"
        claim["readableCitation"] = " | ".join([
            str(claim.get("publisher") or "publisher unavailable"),
            "Published: " + str(claim.get("publicationDate") or "date unavailable"),
            "Retrieved: " + str(claim.get("retrievalDate") or "")[:10],
            str(claim.get("url") or ""),
        ])
        claim["strategyImpacts"] = selected.get(evidence_id, [])
        claim["selectionStatus"] = "selected_by_ai_vc" if evidence_id in selected else "unassessed_source_only_fallback"
        claims.append(claim)
    return {
        "schemaVersion": research.get("schemaVersion"),
        "claims": claims,
        "selectedEvidenceIds": sorted(selected),
        "rejectedEvidenceIds": sorted(rejected),
        "policy": {
            "claimsRequireCitation": True,
            "companyFactsMayChange": False,
        },
    }


def _reference_only_approved_assets(assets: object) -> list[dict[str, Any]]:
    """Mount stable approved-asset references, never the base64 bytes.

    The compiler and exporter resolve ``data-asset-ref`` values from the
    authoritative encrypted context pack.  Placing ``resolvedDataUrl`` base64
    blobs in the provider view wastes the model input window by thousands of
    tokens per asset and can make an otherwise feasible deck exceed the
    272000-token input limit.
    """
    return _strip_inline_bytes(assets)


def _reference_only_visual_intelligence(visual_intelligence: object) -> dict[str, Any]:
    """Keep rendered visual assets as references, dropping inline bytes."""
    if not isinstance(visual_intelligence, dict):
        return {}
    reference_only = deepcopy(visual_intelligence)
    rendered_assets = reference_only.get("rendered_assets")
    if isinstance(rendered_assets, list):
        reference_only["rendered_assets"] = _strip_inline_bytes(rendered_assets)
    return reference_only


def _strip_inline_bytes(items: object) -> list[Any]:
    """Drop inline base64 payload keys from a list of reference objects."""
    reference_only: list[Any] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            reference_only.append(item)
            continue
        reference = deepcopy(item)
        reference.pop("resolvedDataUrl", None)
        reference.pop("data_url", None)
        reference_only.append(reference)
    return reference_only


def _validate_model_authored_handoff(strategy: object, visual_intelligence: object) -> None:
    """Require the successful AI-VC result to be the designer's actual plan.

    This is a structural handoff check, not an investment-quality publication
    gate. It prevents a ready memo from being mounted beside a source-shaped or
    generic visual plan while keeping source-only fallback explicitly separate.
    """
    if not isinstance(strategy, dict) or strategy.get("architectureSource") != "model_authored":
        return
    memo = strategy.get("investmentMemo")
    typed = strategy.get("typedDeckArchitecture")
    slides = typed.get("slides") if isinstance(typed, dict) else strategy.get("deckArchitecture")
    briefs = visual_intelligence.get("slide_visual_briefs") if isinstance(visual_intelligence, dict) else None
    if not isinstance(memo, dict) or not memo or not isinstance(slides, list) or not slides:
        raise ValueError("Model-authored AI-VC strategy is missing its memo or deck architecture.")
    if not isinstance(briefs, list) or len(briefs) != len(slides):
        raise ValueError("Model-authored deck architecture and visual briefs must have exact coverage.")
    slide_ids = [str(slide.get("id") or "") for slide in slides if isinstance(slide, dict)]
    brief_ids = [str(brief.get("slide_id") or brief.get("slideId") or "") for brief in briefs if isinstance(brief, dict)]
    if len(slide_ids) != len(slides) or slide_ids != brief_ids or any(not value for value in slide_ids):
        raise ValueError("Model-authored visual briefs must preserve architecture order and slide identity.")


def build_ai_vc_contexts(context_pack: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(audit_context, authoring_context)`` for one immutable run."""
    strategy = context_pack.get("vcStrategy") or {}
    _validate_model_authored_handoff(strategy, context_pack.get("visualIntelligence") or {})
    source_slides = context_pack.get("sourceSlides") or []
    source_registry = [
        str(slide.get("sourceSlideId"))
        for slide in source_slides
        if isinstance(slide, dict) and str(slide.get("sourceSlideId") or "").strip()
    ]
    company_intelligence = strategy.get("companyIntelligence") if isinstance(strategy, dict) else {}
    if not isinstance(company_intelligence, dict):
        company_intelligence = {}
    meta_fact_ids = {
        str(reference)
        for item in company_intelligence.get("metaEditorial", [])
        if isinstance(item, dict)
        for reference in item.get("evidenceRefs", [])
    }
    company_facts = _clean_company_facts(
        context_pack.get("sourceFacts"), excluded_ids=meta_fact_ids,
    )
    safe_company_intelligence = {
        key: deepcopy(value)
        for key, value in company_intelligence.items()
        if key != "metaEditorial"
    }

    audit = {
        "schemaVersion": "ai-vc-audit-context.v1",
        "sourceSlides": deepcopy(source_slides),
        "sourceFacts": deepcopy(context_pack.get("sourceFacts") or []),
        "companyIntelligence": deepcopy(company_intelligence),
        "externalResearch": deepcopy(context_pack.get("externalResearch") or {}),
        "vcStrategy": deepcopy(strategy),
        "requiredSourceCoverage": deepcopy(context_pack.get("requiredSourceCoverage") or []),
    }
    authoring = {
        "schemaVersion": "ai-vc-authoring-context.v1",
        "objective": context_pack.get("objective"),
        "audience": context_pack.get("audience"),
        "presentationIntent": context_pack.get("presentationIntent"),
        "canonicalSourceIdRegistry": source_registry,
        "companyIntelligence": safe_company_intelligence,
        "companyEvidence": company_facts,
        "verifiedExternalResearch": _authoring_external_research(
            context_pack.get("externalResearch"), strategy
        ),
        "strategy": _authoring_strategy(strategy),
        "brand": deepcopy(context_pack.get("brand") or {}),
        "approvedAssets": _reference_only_approved_assets(context_pack.get("approvedAssets")),
        "visualIntelligence": _reference_only_visual_intelligence(
            context_pack.get("visualIntelligence")
        ),
        "sourceCoverage": deepcopy(context_pack.get("requiredSourceCoverage") or []),
        "policy": {
            "sourceDeckIsEvidenceNotManuscript": True,
            "strategyAndVisualPlanAreAuthoringAuthority": True,
            "outputSlideCountIsDeterminedByInvestmentArgument": True,
            "internalCritiqueMayNotAppearInExport": True,
            "metaEditorialMayNotAppearInExport": True,
            "onlyVerifiedExternalResearchMayEstablishMarketFacts": True,
        },
    }
    return audit, authoring


def provider_safe_ai_vc_context(context_pack: dict[str, Any]) -> dict[str, Any]:
    """Build the deck-author view without changing compiler authority."""
    _audit, authoring = build_ai_vc_contexts(context_pack)
    runtime = deepcopy(context_pack)
    runtime["authoringContext"] = authoring
    runtime["sourceSlides"] = [
        {
            "sourceSlideId": source_id,
            "authoringPolicy": "lineage_only; source presentation is not an outline",
        }
        for source_id in authoring["canonicalSourceIdRegistry"]
    ]
    runtime["sourceFacts"] = authoring["companyEvidence"]
    runtime["vcStrategy"] = authoring["strategy"]
    runtime["externalResearch"] = authoring["verifiedExternalResearch"]
    runtime["evidenceLanes"] = {
        "companySource": authoring["companyEvidence"],
        "externalResearch": authoring["verifiedExternalResearch"],
        "vcInference": authoring["strategy"],
    }
    runtime.pop("acceptedDecisions", None)
    runtime.pop("conflicts", None)
    runtime.pop("missingInputs", None)
    runtime.pop("claimCatalog", None)
    return runtime


def contains_forbidden_internal_copy(value: str) -> bool:
    """Small defense-in-depth predicate used by tests and publication checks."""
    return bool(_EDITORIAL.search(value or ""))


def research_usage_observations(
    *, strategy: object, authoring_research: object, compilation_manifest: object,
) -> dict[str, Any]:
    """Keep research selection, provider injection, and artifact use distinct."""
    synthesis = strategy.get("researchSynthesis") if isinstance(strategy, dict) else {}
    impacts = synthesis.get("finding_impacts", []) if isinstance(synthesis, dict) else []
    selected = {
        str(evidence_id)
        for impact in impacts if isinstance(impact, dict) and impact.get("disposition") == "use"
        for evidence_id in impact.get("evidence_ids") or []
    }
    injected = {
        str(claim.get("id"))
        for claim in (authoring_research.get("claims", []) if isinstance(authoring_research, dict) else [])
        if isinstance(claim, dict) and claim.get("id")
    }
    used_fact_ids = {
        str(fact_id)
        for slide in (compilation_manifest.get("slides", []) if isinstance(compilation_manifest, dict) else [])
        if isinstance(slide, dict)
        for element in slide.get("elements", [])
        if isinstance(element, dict)
        for fact_id in element.get("sourceFactIds", [])
    }
    reflected = injected.intersection(used_fact_ids)
    cited = {evidence_id for evidence_id in reflected if evidence_id + "_citation" in used_fact_ids}
    return {
        "schemaVersion": "ai-vc-research-usage.v1",
        "selectedEvidenceIds": sorted(selected),
        "injectedEvidenceIds": sorted(injected),
        "reflectedEvidenceIds": sorted(reflected),
        "readablyCitedEvidenceIds": sorted(cited),
        "policy": {
            "selectionIsNotInjection": True,
            "injectionIsNotArtifactUse": True,
            "artifactUseRequiresClaimAndReadableCitation": True,
        },
    }
