"""Durable, bounded pre-generation investment analysis for VC redesigns.

The source deck remains company evidence. Verified public research remains an
external evidence lane. This module creates strategic VC inferences that cite
one or both lanes but can never promote themselves to company facts.
"""
from __future__ import annotations

import json
import re
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.ai_vc.models import (
    DeckArchitecture, DeckSlidePlan, InvestmentCommitteeReview, PublicCompanyDescriptor,
)

ARTIFACT_TYPE = "instant_deck_vc_strategy"
ATTEMPT_TYPE = "instant_deck_vc_strategy_attempt"
SCHEMA_VERSION = "instant-deck-vc-strategy.v2"

_META = re.compile(
    r"\b(concept test deck|use this deck to test|test deck v?2|does the redesign|"
    r"key test|concept only|not a production claim|author note|design instruction)\b",
    re.IGNORECASE,
)


class StrategyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companyIntelligence: dict = Field(default_factory=dict)
    researchQuestions: list[str] = Field(min_length=1, max_length=12)
    investmentMemo: dict
    financialAnalysis: dict
    vcInferences: list[dict] = Field(default_factory=list, max_length=20)
    narrativeStrategy: dict
    deckArchitecture: list[dict] = Field(min_length=1, max_length=24)
    evidenceGaps: list[str] = Field(default_factory=list, max_length=20)
    investmentCommitteeReview: InvestmentCommitteeReview


def _classify_business_models(company: dict) -> list[dict]:
    text = " ".join(item.get("text", "") for item in company.get("businessEvidence", [])).lower()
    signals = {
        "biotech": ("clinical", "biotech", "therapeutic", "drug", "trial"),
        "fintech": ("fintech", "payment", "banking", "lending", "insurance"),
        "marketplace": ("marketplace", "buyers and sellers", "take rate"),
        "consumer": ("consumer", "retail", "ecommerce", "e-commerce"),
        "saas": ("software", "saas", "platform", "subscription", "workflow"),
    }
    # Whole-token matching matters: substring matching classified "industrial"
    # as biotech because it contains "trial".  Hyphenated signals remain
    # supported without allowing one industry word to hide inside another.
    words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text))
    scores = {
        sector: sum(
            (token in words) if " " not in token else bool(re.search(r"\b" + re.escape(token) + r"\b", text))
            for token in tokens
        )
        for sector, tokens in signals.items()
    }
    ranked = sorted(((sector, score) for sector, score in scores.items() if score), key=lambda item: (-item[1], item[0]))
    return ([{"model": sector, "confidence": min(1.0, 0.35 + score * 0.2), "method": "keyword_fallback"}
             for sector, score in ranked[:3]] or
            [{"model": "general", "confidence": 0.2, "method": "insufficient_evidence"}])


def _infer_sector(company: dict) -> str:
    return _classify_business_models(company)[0]["model"]


def build_universal_research_plan(company: dict) -> dict:
    from app.core.config import settings
    from app.services.ai_vc.models import ResearchBudget
    from app.services.ai_vc.ontology import VC_DIMENSIONS, plan_research_tasks
    from app.services.ai_vc.skills.resolver import (
        resolve_skill_plan,
        skill_plan_trace,
        skill_research_priorities,
    )
    evidence = company.get("businessEvidence", [])
    summary = "; ".join(item.get("text", "") for item in evidence[:4]) or "the uploaded company"
    normalized = {**company, "summary": summary}
    budget = ResearchBudget(
        max_searches=1,
        max_sources=min(3, settings.instant_html_vc_research_max_sources),
        max_tokens=settings.ai_vc_research_max_tokens,
        max_cost_cents=(
            settings.instant_html_vc_research_max_cost_cents
            / max(1, settings.ai_vc_research_max_searches)
            if settings.instant_html_vc_research_max_cost_cents is not None
            else None
        ),
        max_runtime_seconds=settings.instant_html_vc_research_timeout_seconds,
    )
    skill_plan = resolve_skill_plan(company)
    tasks = plan_research_tasks(
        normalized,
        sector=skill_plan.inferred_sector,
        max_tasks=8,
        budget=budget,
        preferred_purposes=[
            purpose for purpose in skill_research_priorities(skill_plan)
            if purpose in VC_DIMENSIONS
        ],
    )
    return {"schemaVersion": "ai-vc-research-plan.v2", "sector": skill_plan.inferred_sector,
            "businessModelClassifications": _classify_business_models(company),
            "skillSelection": skill_plan_trace(skill_plan),
            "tasks": [task.model_dump() for task in tasks]}


def _clean(value: str, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


_FINANCIAL_SIGNAL = re.compile(
    r"(?:[$£€]\s?\d|\d(?:[\d,.]*\d)?\s?%|\b(?:arr|mrr|revenue|sales|bookings|gmv|"
    r"gross margin|margin|profit|loss|burn|runway|cash|price|pricing|subscription|contract value|"
    r"acv|ltv|cac|churn|retention|growth|customer count|customers|units|funding|raise|valuation)\b)",
    re.IGNORECASE,
)
_PROJECTION_SIGNAL = re.compile(
    r"\b(?:forecast|project(?:ed|ion)?|target(?:s|ed|ing)?|plan(?:ned)?|expect(?:ed)?|could|may|roadmap|future|"
    r"illustrative|scenario|assum(?:e|ed|ption))\b",
    re.IGNORECASE,
)


def _financial_evidence_record(record: dict, text: str) -> dict | None:
    """Preserve financially relevant source claims without upgrading their status."""
    if not _FINANCIAL_SIGNAL.search(text):
        return None
    status = "management_projection" if _PROJECTION_SIGNAL.search(text) else "company_supplied_unspecified"
    return {
        "text": text,
        "evidenceRefs": list(record.get("evidenceRefs") or []),
        "status": status,
        "evidenceClass": "MANAGEMENT_PROJECTION" if status == "management_projection" else "COMPANY_SOURCE",
    }


def build_company_intelligence(source_facts: list[dict], source_slides: list[dict]) -> dict:
    """Deterministically classify source content before any narrative call."""
    evidence, hypotheses, editorial, financial = [], [], [], []
    for fact in source_facts:
        text = _clean(fact.get("text", ""))
        if not text:
            continue
        record = {"text": text, "evidenceRefs": [fact.get("factId")], "classification": "FACT"}
        if _META.search(text):
            record["classification"] = "META_EDITORIAL"
            editorial.append(record)
        elif re.search(r"\b(plan(?:ned)?|intend|could|may|hypothesis|target|roadmap|future)\b", text, re.I):
            record["classification"] = "HYPOTHESIS"
            hypotheses.append(record)
        else:
            evidence.append(record)
        financial_record = _financial_evidence_record(record, text)
        if financial_record is not None and record["classification"] != "META_EDITORIAL":
            financial.append(financial_record)
    for slide in source_slides:
        text = _clean(slide.get("text", ""))
        if text and _META.search(text):
            editorial.append({"text": text, "evidenceRefs": [slide.get("sourceSlideId")], "classification": "META_EDITORIAL"})
    return {
        "schemaVersion": "company-intelligence.v1",
        "businessEvidence": evidence[:80],
        "financialEvidence": financial[:40],
        "hypotheses": hypotheses[:30],
        "metaEditorial": editorial[:30],
        "unknowns": [],
    }


def build_research_questions(company: dict) -> list[str]:
    return [task["question"] for task in build_universal_research_plan(company)["tasks"]]


_PUBLIC_INDUSTRY_TAXONOMY = {
    "healthcare": ("healthcare", "clinic", "hospital", "patient", "medical", "provider"),
    "financial services": ("fintech", "banking", "payment", "lending", "insurance"),
    "manufacturing": ("manufacturing", "factory", "industrial", "plant", "production line"),
    "field services": ("field service", "technician", "work order", "maintenance", "repair"),
    "logistics and supply chain": ("logistics", "warehouse", "freight", "supply chain", "delivery"),
    "construction": ("construction", "contractor", "jobsite", "building project"),
    "energy and utilities": ("energy", "utility", "renewable", "oil and gas", "power grid"),
    "education": ("education", "school", "student", "teacher", "learning"),
    "agriculture": ("agriculture", "farm", "farms", "farmer", "farmers", "crop", "agtech"),
    "retail and commerce": ("retail", "ecommerce", "e-commerce", "merchant", "shopper"),
    "hospitality": ("hospitality", "hotel", "restaurant", "guest"),
    "real estate": ("real estate", "property", "tenant", "landlord"),
    "cybersecurity": ("cybersecurity", "security operations", "threat", "breach"),
    "telecommunications": ("telecom", "telecommunications", "network operator"),
    "life sciences": ("biotech", "therapeutic", "clinical trial", "drug discovery"),
}
_PUBLIC_WORKFLOW_TAXONOMY = {
    "operations workflow": ("workflow", "workflows", "operations", "process"),
    "scheduling and dispatch": ("scheduling", "dispatch", "appointment"),
    "customer acquisition": ("lead", "marketing", "acquisition", "sales funnel"),
    "customer retention": ("retention", "renewal", "rebooking", "churn"),
    "automation": ("automation", "automate", "orchestration"),
    "analytics and reporting": ("analytics", "reporting", "dashboard", "insight"),
    "compliance": ("compliance", "regulatory", "audit"),
    "collaboration": ("collaboration", "handoff", "team communication"),
}
_PUBLIC_GEOGRAPHIES = {
    "United Kingdom": ("United Kingdom", "UK", "British"),
    "United States": ("United States", "US", "American"),
    "Canada": ("Canada", "Canadian"),
    "Europe": ("Europe", "European Union", "EU", "European"),
    "Australia": ("Australia", "Australian"),
    "New Zealand": ("New Zealand",),
    "Latin America": ("Latin America",),
    "Middle East": ("Middle East",),
    "Africa": ("Africa", "African"),
    "Asia Pacific": ("Asia Pacific", "APAC"),
}


def _taxonomy_matches(text: str, taxonomy: dict[str, tuple[str, ...]]) -> list[str]:
    return [
        label for label, signals in taxonomy.items()
        if any(re.search(r"\b" + re.escape(signal) + r"\b", text, re.IGNORECASE) for signal in signals)
    ]


def build_public_company_descriptor(company: dict) -> PublicCompanyDescriptor:
    """Reduce private evidence to general, non-identifying research dimensions.

    The vocabulary is a cross-industry taxonomy, not a narrative or fixture
    mapping. It deliberately excludes names, source sentences and metrics. The
    research model remains responsible for choosing the actual question/query.
    """
    # Reuse the same skill-resolution boundary as the research plan.  A second
    # divergent classifier previously produced a biotech search brief while
    # the canonical plan correctly selected SaaS.
    from app.services.ai_vc.skills.resolver import resolve_skill_plan
    sector = resolve_skill_plan(company).inferred_sector
    evidence = " ".join(
        str(item.get("text") or "").lower()
        for item in company.get("businessEvidence", [])[:20]
        if isinstance(item, dict)
    )
    customer_signals = []
    if re.search(r"\b(?:enterprise|large compan(?:y|ies)|corporate)\b", evidence):
        customer_signals.append("enterprise buyers")
    if re.search(r"\b(?:small business|smb|sme|independent operator)\b", evidence):
        customer_signals.append("small and midsize businesses")
    if re.search(r"\b(?:consumer|shopper|patient|guest|student|homeowner)\b", evidence):
        customer_signals.append("individual end users")
    if re.search(r"\b(?:government|public sector|municipal)\b", evidence):
        customer_signals.append("public-sector buyers")
    customer = " and ".join(customer_signals[:2]) or "business operators and their customers"
    product = {
        "saas": "business workflow software",
        "fintech": "financial technology platform",
        "biotech": "life-sciences product",
        "consumer": "consumer product or service",
        "marketplace": "two-sided marketplace",
    }.get(sector, "business product or service")
    industries = _taxonomy_matches(evidence, _PUBLIC_INDUSTRY_TAXONOMY)
    workflows = _taxonomy_matches(evidence, _PUBLIC_WORKFLOW_TAXONOMY)
    geography = next((
        label for label, signals in _PUBLIC_GEOGRAPHIES.items()
        if any(re.search(r"\b" + re.escape(signal) + r"\b", evidence, re.I) for signal in signals)
    ), "unknown")
    periods = list(dict.fromkeys(re.findall(r"\b(?:19|20)\d{2}\b", evidence)))[:8]
    context_terms = industries[:4] + workflows[:4]
    return PublicCompanyDescriptor(
        category=sector + " category" if sector != "general" else "business technology category",
        customer_type=customer,
        product_type=product,
        industry_context=", ".join(context_terms) or "business operations and category adoption",
        geography=geography,
        industry_dimensions=industries,
        workflow_dimensions=workflows,
        reporting_periods=periods,
    )


def build_evidence_graph(source_facts: list[dict], external_research: dict) -> dict:
    from app.services.ai_vc.models import EvidenceEdge, EvidenceNode
    nodes, edges = [], []
    for fact in source_facts:
        if fact.get("factId") and fact.get("text"):
            nodes.append(EvidenceNode(
                id=str(fact["factId"]), evidence_class="COMPANY_SOURCE", claim=str(fact["text"]),
                source_ids=[str(value) for value in fact.get("sourceSlideIds") or []],
                provenance={"sourceType": fact.get("sourceType"), "field": fact.get("field")},
                confidence="high" if fact.get("confidence") == "high" else "low",
            ).model_dump())
            for source_id in fact.get("sourceSlideIds") or []:
                edges.append(EvidenceEdge(source_id=str(fact["factId"]), target_id=str(source_id), relation="SUPPORTED_BY").model_dump())
    for claim in external_research.get("claims", []):
        if claim.get("id") and claim.get("text"):
            nodes.append(EvidenceNode(
                id=str(claim["id"]), evidence_class="EXTERNAL_RESEARCH", claim=str(claim["text"]),
                source_ids=[str(claim.get("url") or "")],
                provenance={"publisher": claim.get("publisher"), "publicationDate": claim.get("publicationDate"),
                            "retrievalDate": claim.get("retrievalDate"), "evidenceSha256": claim.get("evidenceSha256")},
                confidence="high",
            ).model_dump())
            if claim.get("url"):
                edges.append(EvidenceEdge(source_id=str(claim["id"]), target_id=str(claim["url"]), relation="SUPPORTED_BY").model_dump())
    return {"schemaVersion": "ai-vc-evidence-graph.v1", "nodes": nodes, "edges": edges}


def public_research_brief(
    company: dict, questions: list[str], website: str | None = None,
    descriptor: PublicCompanyDescriptor | None = None,
) -> str:
    descriptor = descriptor or build_public_company_descriptor(company)
    website_context = (
        " A confirmed public company website is available as an optional orientation source."
        if website and website.startswith("https://") else ""
    )
    return _clean(
        "Research current investor-relevant evidence for a " + descriptor.product_type +
        " serving " + descriptor.customer_type + " in the " + descriptor.category +
        ", with relevant industry context: " + descriptor.industry_context + "." +
        website_context +
        " Cover category structure, why now, competitors, customer economics, business-model benchmarks, "
        "regulation and comparable outcomes where relevant. Do not search for the private company by name or "
        "infer its metrics, traction, customers, partnerships or capabilities.",
        700,
    )


def _validate_item_refs(
    items: object,
    *,
    allowed: set[str],
    label: str,
    evidence_class: str | None = None,
) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise ValueError(f"{label} must be a list")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} entries must be objects")
        refs = item.get("evidenceRefs") or item.get("inputEvidenceRefs") or []
        if not isinstance(refs, list) or not refs or any(str(ref) not in allowed for ref in refs):
            raise ValueError(f"{label} cites unknown or disallowed evidence")
        if evidence_class is not None:
            item["evidenceClass"] = evidence_class


def _financial_reference_ids(financial: dict) -> list[str]:
    refs: set[str] = set()
    for key in (
        "verifiedCompanyMetrics", "managementProjections", "externalBenchmarks",
        "derivedCalculations", "investorImplications", "narrativeSelections",
    ):
        for item in financial.get(key) or []:
            if isinstance(item, dict):
                refs.update(str(ref) for ref in (item.get("evidenceRefs") or item.get("inputEvidenceRefs") or []))
    return sorted(refs)


def _validate_financial_analysis(financial: object, source_ids: set[str], external_ids: set[str]) -> dict:
    if not isinstance(financial, dict):
        raise ValueError("Financial analysis must be an object")
    valid = source_ids | external_ids
    _validate_item_refs(
        financial.get("verifiedCompanyMetrics"), allowed=source_ids,
        label="Verified company metric", evidence_class="COMPANY_SOURCE",
    )
    _validate_item_refs(
        financial.get("managementProjections"), allowed=source_ids,
        label="Management projection", evidence_class="MANAGEMENT_PROJECTION",
    )
    _validate_item_refs(
        financial.get("externalBenchmarks"), allowed=external_ids,
        label="External financial benchmark", evidence_class="EXTERNAL_RESEARCH",
    )
    _validate_item_refs(
        financial.get("derivedCalculations"), allowed=valid,
        label="Derived calculation", evidence_class="DERIVED_CALCULATION",
    )
    _validate_item_refs(
        financial.get("investorImplications"), allowed=valid,
        label="Financial investor implication", evidence_class="VC_INFERENCE",
    )
    _validate_item_refs(
        financial.get("narrativeSelections"), allowed=valid,
        label="Financial narrative selection",
    )
    if not isinstance(financial.get("missingFinancialProof", []), list):
        raise ValueError("Missing financial proof must be a list")
    financial["policy"] = {
        "companyMetrics": "COMPANY_SOURCE only; preserve value, currency, unit, period and qualifier",
        "managementProjections": "source-backed and visibly labelled as projections",
        "externalBenchmarks": "EXTERNAL_RESEARCH with citation; never company performance",
        "derivedCalculations": "illustrative only with explicit formula and cited inputs",
        "productKnowledge": "selects what matters but supplies no figures",
    }
    return financial


def _validate_evidence_boundaries(payload: dict, source_ids: set[str], external_ids: set[str]) -> dict:
    valid = source_ids | external_ids
    for item in payload.get("vcInferences", []):
        item["evidenceClass"] = "VC_INFERENCE"
        refs = item.get("evidenceRefs") or []
        if any(ref not in valid for ref in refs):
            raise ValueError("VC inference cites unknown evidence")
    for slide in payload.get("deckArchitecture", []):
        refs = slide.get("evidenceRefs") or []
        if any(ref not in valid for ref in refs):
            raise ValueError("Deck architecture cites unknown evidence")
    synthesis = payload.get("researchSynthesis") or {}
    if not isinstance(synthesis, dict):
        raise ValueError("Research synthesis must be an object")
    for impact in synthesis.get("finding_impacts", []):
        refs = impact.get("evidence_ids") or []
        if not refs or any(str(ref) not in external_ids for ref in refs):
            raise ValueError("Research finding impact cites unknown or non-external evidence")
    payload["financialAnalysis"] = _validate_financial_analysis(
        payload.get("financialAnalysis"), source_ids, external_ids,
    )
    payload["evidencePolicy"] = {
        "companyFacts": "COMPANY_SOURCE only",
        "externalClaims": "EXTERNAL_RESEARCH with citation",
        "strategicInterpretation": "VC_INFERENCE, never company fact",
        "managementProjections": "COMPANY_SOURCE with explicit projection status",
        "productKnowledge": "advisory methodology only, never factual or numerical authority",
        "researchSelection": "model-authored use/reject decisions must cite EXTERNAL_RESEARCH IDs",
    }
    return payload


_INVESTOR_ARCHITECTURE_ROLES = (
    {
        "role": "investment_thesis",
        "title": "The investment thesis",
        "purpose": "State the strongest source-grounded reason this company could matter.",
        "keywords": ("company", "platform", "product", "solution", "system", "software"),
    },
    {
        "role": "customer_problem",
        "title": "The customer and structural problem",
        "purpose": "Explain the customer, their workflow, and the economically meaningful problem.",
        "keywords": ("customer", "buyer", "user", "problem", "pain", "manual"),
    },
    {
        "role": "workflow_economics",
        "title": "Why the current workflow breaks",
        "purpose": "Show the supported operational friction, fragmentation, or consequence.",
        "keywords": ("workflow", "fragment", "process", "time", "cost", "loss", "retain", "conversion"),
    },
    {
        "role": "product_wedge",
        "title": "The product and initial wedge",
        "purpose": "Show what the product does and where it first enters the customer workflow.",
        "keywords": ("product", "feature", "workflow", "integrat", "connect", "autom", "timeline"),
    },
    {
        "role": "category_position",
        "title": "Category position and differentiation",
        "purpose": "Clarify the supported boundary between this offering, substitutes, and adjacent tools.",
        "keywords": ("compet", "alternative", "different", "category", "market", "existing", "stack"),
    },
    {
        "role": "proof_and_business_model",
        "title": "Proof and business model",
        "purpose": "Present only supplied validation, commercial evidence, and business-model facts.",
        "keywords": ("revenue", "pricing", "price", "customer", "pilot", "traction", "growth", "subscription"),
    },
    {
        "role": "expansion_and_defensibility",
        "title": "Expansion and defensibility",
        "purpose": "Explain supported expansion paths and why the position may compound over time.",
        "keywords": ("expand", "roadmap", "future", "data", "network", "defens", "scale"),
    },
    {
        "role": "investor_case",
        "title": "The credible investor case",
        "purpose": "Synthesize the strongest supported opportunity without inventing an ask or missing proof.",
        "keywords": ("vision", "opportunity", "mission", "impact", "scale", "growth"),
    },
)

_CORE_INVESTOR_ROLES = {
    "investment_thesis",
    "customer_problem",
    "product_wedge",
    "investor_case",
}

def _fallback_deck_architecture(
    *, source_facts: list[dict], external_ids: set[str]
) -> list[dict]:
    """Build a narrative fallback from supported investor arguments, not page count."""
    source_records = [
        (str(fact["factId"]), _clean(fact.get("text", ""), 800).lower())
        for fact in source_facts
        if fact.get("factId") and _clean(fact.get("text", ""))
    ]
    source_ids = [fact_id for fact_id, _ in source_records]
    slides: list[dict] = []
    for template in _INVESTOR_ARCHITECTURE_ROLES:
        matched = [
            fact_id for fact_id, text in source_records
            if any(keyword in text for keyword in template["keywords"])
        ][:5]
        role = str(template["role"])
        externally_supported = role == "category_position" and bool(external_ids)
        if role not in _CORE_INVESTOR_ROLES and not matched and not externally_supported:
            continue
        if not matched and source_ids:
            matched = [source_ids[len(slides) % len(source_ids)]]
        # Current cited research may support category positioning, but never
        # replaces company-source lineage for what the company has achieved.
        if role == "category_position":
            matched.extend(sorted(external_ids)[:3])
        index = len(slides) + 1
        slides.append({
            "id": f"planned-slide-{index:02d}",
            "role": role,
            "title": template["title"],
            "purpose": template["purpose"],
            "evidenceRefs": list(dict.fromkeys(matched)),
        })
    return slides


def _typed_deck_architecture(payload: dict) -> dict:
    raw_slides = payload.get("deckArchitecture") or []
    slides = [
        DeckSlidePlan(
            id=str(slide.get("id") or f"planned-slide-{index:02d}"),
            index=index,
            role=str(slide.get("role") or slide.get("type") or "investment_argument"),
            objective=str(slide.get("objective") or slide.get("purpose") or slide.get("title") or f"Slide {index}"),
            headline_direction=str(slide.get("headlineDirection") or slide.get("headline") or slide.get("title") or ""),
            key_message=str(slide.get("keyMessage") or ""),
            evidence_ids=[str(value) for value in slide.get("evidenceRefs") or slide.get("evidence_ids") or []],
            calculation_ids=[str(value) for value in slide.get("calculationIds") or slide.get("calculation_ids") or []],
            visual_primitive=str(slide.get("visualPrimitive") or slide.get("visual_primitive") or ""),
            visual_intent=str(slide.get("visualIntent") or ""),
            investor_belief=str(slide.get("investorBelief") or slide.get("investor_belief") or slide.get("keyMessage") or ""),
            evidence_shape=str(slide.get("evidenceShape") or slide.get("evidence_shape") or ""),
            copy_budget_words=max(5, min(180, int(slide.get("copyBudgetWords") or 55))),
        )
        for index, slide in enumerate(raw_slides, 1)
        if isinstance(slide, dict)
    ]
    architecture = DeckArchitecture(
        core_thesis=str((payload.get("narrativeStrategy") or {}).get("thesis") or "Source-grounded investment case"),
        recommended_slide_count=len(slides),
        rationale=str((payload.get("narrativeStrategy") or {}).get("slideCountRationale") or "Slide count follows the reconstructed investor argument, not the uploaded deck."),
        slides=slides,
    )
    return architecture.model_dump(mode="json")


def load_vc_strategy(db: Session, deck_id: str, operation_id: str) -> dict:
    row = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_type=ARTIFACT_TYPE, artifact_key="vc-strategy:" + operation_id,
    ).one_or_none()
    return row.payload_json if row and row.status == "ready" else {}


def _ensure_vc_strategy_v2(
    db: Session, *, deck, operation_id: str, source_facts: list[dict], source_slides: list[dict], external_research: dict,
    design_guidance: dict | None = None,
) -> dict:
    """Historical v2 implementation retained for persisted-source archaeology."""
    key = "vc-strategy:" + operation_id
    existing = db.query(DeckLlmArtifact).filter_by(deck_id=deck.id, artifact_key=key).one_or_none()
    if existing is not None:
        if existing.status != "ready":
            raise ValueError("Existing VC strategy attempt is not safe to replay")
        return existing.payload_json or {}

    company = build_company_intelligence(source_facts, source_slides)
    questions = build_research_questions(company)
    research_plan = build_universal_research_plan(company)
    evidence_graph = build_evidence_graph(source_facts, external_research)
    from app.services.llm.ai_vc_retrieval import build_ai_vc_evidence_pack
    evidence_pack = build_ai_vc_evidence_pack(
        company_facts=source_facts, external_research=external_research, questions=questions,
        research_tasks=research_plan["tasks"], db=db, deck_id=deck.id,
        design_guidance=design_guidance,
    )
    source_ids = {str(f.get("factId")) for f in source_facts if f.get("factId")}
    external_ids = {str(c.get("id")) for c in external_research.get("claims", []) if c.get("id")}
    max_cents = settings.instant_html_vc_memo_max_cost_cents

    from app.services.llm.generation_service import get_generation_provider_config
    from app.services.llm.openai_provider import call_openai_response, parse_openai_structured_response
    model = settings.openai_model
    config = get_generation_provider_config(db, deck, preferred_model=model, strict=True, use_case="analysis")
    if config["provider"] != "openai" or config["model"] != model:
        raise ValueError("The bounded VC strategy provider/model is unavailable")
    attempt = DeckLlmArtifact(
        id=generate_id("vcstrategyattempt"), deck_id=deck.id, artifact_type=ATTEMPT_TYPE,
        artifact_key=key, schema_version=SCHEMA_VERSION, status="running",
        summary="One bounded pre-generation AI-VC strategy request.",
        payload_json={"companyIntelligence": company, "researchQuestions": questions,
                      "researchPlan": research_plan, "evidenceGraph": evidence_graph,
                      "retrievalEvidencePack": evidence_pack,
                      "providerStarts": 1, "clientRequestId": str(uuid4()), "model": model,
                      "maxCostCents": max_cents}, metrics_json={"costKnown": False},
    )
    db.add(attempt)
    db.commit()
    system = """Act as a skeptical venture investor and narrative strategist. Return JSON only with exactly:
companyIntelligence (object), researchQuestions (array), investmentMemo (object), financialAnalysis (object), vcInferences (array of objects),
narrativeStrategy (object), deckArchitecture (array of objects), evidenceGaps (array), and investmentCommitteeReview
with strengths, concerns, missing_proof, investor_objections, recommended_changes, advisory, important,
critical_for_fundraising, publication_blocking (always false), and next_action.
Reconstruct the investment story from first principles. Identify the wedge, buyer, workflow, why-now, category,
competition, business model, GTM, expansion, defensibility, strongest reason to care, strongest reason not to invest,
objections and missing proof. Improve positioning, but never invent company functionality, traction, economics or
relationships. Every inference and proposed factual slide must include evidenceRefs using only supplied IDs.
Use all three intelligence lanes before choosing the narrative: COMPANY_SOURCE establishes what the company is and
has proved; EXTERNAL_RESEARCH establishes cited current category context; PRODUCT_KNOWLEDGE supplies retrieved VC
methodology for evaluating investability. First synthesize the investmentMemo from those lanes. Then derive
narrativeStrategy and every deckArchitecture slide directly from that memo. Do not independently restyle the upload.
FinancialAnalysis must contain exactly verifiedCompanyMetrics, managementProjections, externalBenchmarks,
derivedCalculations, investorImplications, narrativeSelections, and missingFinancialProof arrays. Select the figures
that most improve an investor's understanding of traction, pricing, revenue quality, retention, unit economics,
margins, growth, burn/runway, capital needs, milestones, and venture-scale potential. Relevance is not permission to
invent: verifiedCompanyMetrics and managementProjections may cite COMPANY_SOURCE IDs only; externalBenchmarks may
cite EXTERNAL_RESEARCH IDs only and must never be presented as company performance; investorImplications are
VC_INFERENCE. Preserve every amount, currency, unit, period, qualifier, and actual/projected status. Leave unsupported
categories empty and record them in missingFinancialProof. Do not manufacture TAM, revenue, customers, pricing,
growth, margins, retention, an investment ask, or a financial forecast. derivedCalculations must remain empty unless
the supplied context contains an application-owned calculation with an explicit formula and input evidence IDs.
When a selected financial item contains an exact source-backed number, return its structured metric, numeric value,
unit, period or category, status (actual, forecast, projected, scenario, or target), evidenceRefs, and calculationId
only when derived. For a comparable series, repeat those fields as points under one metric. Omit structured numeric
fields when the exact value cannot be established; never parse or complete a series from remembered facts.
PRODUCT_KNOWLEDGE may help decide which economics matter, but it supplies no company or market figure. Inspire through
economic clarity and evidence selection, never exaggeration. Use financialAnalysis.narrativeSelections to decide
which supported figures deserve prominence, and omit low-value numbers that do not strengthen the investment case.
Use visualDesignGuidance as advisory design knowledge retrieved by embeddings. For every proposed slide, choose a
visualPrimitive and visualIntent that best communicates that slide's investor argument. The guidance must improve the
model's judgment, not force a template, fixed layout family, or repeated composition. The LLM owns the final narrative,
slide count, slide roles, visual direction, hierarchy, and composition intent.
For each architecture slide also return investorBelief, evidenceShape, and copyBudgetWords. evidenceShape describes
the supported structure (for example time_series, actual_vs_forecast, category_comparison, cumulative_funnel,
financial_bridge, historical_income_statement, relationship_map, source_image, or qualitative); it does not create
evidence. The application validates the proposed primitive against that structure before authoring.
Choose visualPrimitive from: hero, editorial_statement, big_number, data_chart, market_size, market_map,
competitive_matrix, comparison, workflow, lifecycle, timeline, flywheel, funnel, ecosystem,
platform_architecture, technology_stack, value_chain, wedge_expansion, financial_bridge, business_model,
product_ui, process, team, photography, mixed, or composition.
Company claims may cite company source IDs only. External claims must cite external IDs and retain citations.
Label every strategic interpretation evidenceClass VC_INFERENCE. Exclude all META_EDITORIAL material. Do not impose
a fixed slide count or funding ask. First decide the investor questions the deck must answer, then choose the output
slide count required to make that specific capital-raising argument. Record the reasoning in
narrativeStrategy.slideCountRationale. Never copy, preserve, or mathematically derive the output count from the input
slide count. Consolidate, split, reorder, replace, or omit source presentation sections as the investment narrative
requires. A one-slide poster is not an investor deck. Do not pad the narrative or invent facts to create slides. The
source deck is evidence, not a manuscript, outline, required slide order, or slide-count target.
Use vcMethodologyByPurpose only as internal investment reasoning methodology. It is historical PRODUCT_KNOWLEDGE,
not company proof or current market evidence. Never copy its abstracts or citations into the deck, and never use its
document IDs as evidenceRefs. Current market, competitor, pricing, regulation, funding, exit and why-now claims must
still use supplied EXTERNAL_RESEARCH IDs.
The investment committee critique is advisory. Even critical_for_fundraising observations must never refuse,
block, or suppress the redesign, publication, or export."""
    user = json.dumps({"companyIntelligence": company, "researchQuestions": questions,
                       "researchPlan": research_plan, "evidenceGraph": evidence_graph,
                       "retrievalEvidencePack": evidence_pack,
                       "allowedCompanyEvidenceIds": sorted(source_ids),
                       "allowedExternalEvidenceIds": sorted(external_ids)}, separators=(",", ":"))
    transport = getattr(call_openai_response, "__wrapped__", call_openai_response)
    try:
        response = transport(api_key=config["apiKey"], model=model, system=system, user=user,
                             max_output_tokens=settings.ai_vc_analysis_max_tokens,
                             timeout=settings.ai_vc_max_runtime_seconds,
                             timeout_ceiling=settings.ai_vc_max_runtime_seconds,
                             client_request_id=attempt.payload_json["clientRequestId"])
        usage = response.get("usage") or {}
        # Conservative configured gate; actual request usage is recorded and the
        # provider invoice remains authoritative.
        from app.services.llm.instant_html_operation_service import estimate_model_cost_cents
        estimated_cents = estimate_model_cost_cents(
            "openai", model, input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
        if max_cents is not None and (
            estimated_cents is None or float(estimated_cents) > max_cents
        ):
            raise ValueError("VC memo exceeded its configured cost allowance")
        parsed = StrategyPayload.model_validate(json.loads(parse_openai_structured_response(response))).model_dump()
        parsed["companyIntelligence"] = company
        parsed["researchQuestions"] = questions
        parsed = _validate_evidence_boundaries(parsed, source_ids, external_ids)
        parsed["methodologyRetrievalTrace"] = evidence_pack["methodologyRetrievalTrace"]
        parsed["architectureIntelligenceTrace"] = {
            "decisionBasis": "investment_memo_synthesis",
            "companyEvidenceIds": [item["source_id"] for item in evidence_pack["companyEvidence"]],
            "externalEvidenceIds": sorted(external_ids),
            "productKnowledge": evidence_pack["methodologyRetrievalTrace"],
            "designKnowledge": evidence_pack["designKnowledgeTrace"],
        }
        parsed["financialIntelligenceTrace"] = {
            "decisionBasis": "evidence_classed_financial_selection",
            "selectedEvidenceIds": _financial_reference_ids(parsed["financialAnalysis"]),
            "companyFinancialEvidenceIds": [
                item["source_id"] for item in evidence_pack["companyFinancialEvidence"]
            ],
            "externalPurposes": sorted(evidence_pack["externalEvidenceByPurpose"]),
            "productKnowledgeIsNumericalAuthority": False,
        }
        parsed["typedDeckArchitecture"] = _typed_deck_architecture(parsed)
    except Exception as exc:
        fallback = {
            "companyIntelligence": company, "researchQuestions": questions,
            "investmentMemo": {"status": "unavailable", "limitation": "Investment analysis could not be completed."},
            "financialAnalysis": {
                "verifiedCompanyMetrics": [
                    item for item in company.get("financialEvidence", [])
                    if item.get("evidenceClass") == "COMPANY_SOURCE"
                ],
                "managementProjections": [
                    item for item in company.get("financialEvidence", [])
                    if item.get("evidenceClass") == "MANAGEMENT_PROJECTION"
                ],
                "externalBenchmarks": [],
                "derivedCalculations": [],
                "investorImplications": [],
                "narrativeSelections": [],
                "missingFinancialProof": [
                    "AI-VC financial selection was unavailable; use only exact source-backed figures."
                ],
                "policy": {
                    "companyMetrics": "COMPANY_SOURCE only",
                    "externalBenchmarks": "EXTERNAL_RESEARCH only",
                    "productKnowledge": "advisory only",
                },
            },
            "vcInferences": [],
            "narrativeStrategy": {"status": "conservative_source_grounded", "thesis": ""},
            # A failed strategy call must not substitute an application-owned
            # universal slide sequence. The final designer can still author a
            # source-grounded deck, and the degraded state remains explicit.
            "deckArchitecture": [],
            "evidenceGaps": ["AI-VC analysis unavailable; no strategic inference may be presented as fact."],
            "investmentCommitteeReview": InvestmentCommitteeReview(
                concerns=["Investment analysis was unavailable."],
                missing_proof=["Review source evidence and add the strongest missing investor proof."],
            ).model_dump(),
            "evidencePolicy": {"companyFacts": "COMPANY_SOURCE only", "externalClaims": "EXTERNAL_RESEARCH with citation", "strategicInterpretation": "VC_INFERENCE, never company fact"},
            "analysisStatus": "unavailable",
            "architectureIntelligenceTrace": {
                "decisionBasis": "final_designer_source_only",
                "companyEvidenceIds": sorted(source_ids),
                "externalEvidenceIds": sorted(external_ids),
                "productKnowledge": evidence_pack["methodologyRetrievalTrace"],
                "designKnowledge": evidence_pack["designKnowledgeTrace"],
            },
            "financialIntelligenceTrace": {
                "decisionBasis": "source_only_fallback",
                "selectedEvidenceIds": sorted({
                    str(ref)
                    for item in company.get("financialEvidence", [])
                    for ref in item.get("evidenceRefs", [])
                }),
                "companyFinancialEvidenceIds": [
                    item["source_id"] for item in evidence_pack["companyFinancialEvidence"]
                ],
                "externalPurposes": sorted(evidence_pack["externalEvidenceByPurpose"]),
                "productKnowledgeIsNumericalAuthority": False,
            },
        }
        fallback["typedDeckArchitecture"] = _typed_deck_architecture(fallback)
        attempt.artifact_type = ARTIFACT_TYPE
        attempt.status = "ready"
        attempt.payload_json = fallback
        attempt.metrics_json = {"costKnown": False, "errorType": type(exc).__name__, "providerStarts": 1}
        attempt.summary = "Conservative source-grounded fallback; AI-VC analysis unavailable."
        from app.services.ai_vc.advisory import persist_investment_critique
        persist_investment_critique(
            db, deck_id=deck.id, operation_id=operation_id,
            review=fallback["investmentCommitteeReview"],
        )
        db.commit()
        return fallback
    attempt.artifact_type = ARTIFACT_TYPE
    attempt.status = "ready"
    attempt.payload_json = parsed
    attempt.metrics_json = {"costKnown": bool(usage), "estimatedCostCents": estimated_cents,
                            "inputTokens": usage.get("input_tokens"), "outputTokens": usage.get("output_tokens"),
                            "providerStarts": 1}
    attempt.summary = "Persisted evidence-referenced AI-VC memo and narrative strategy."
    from app.services.ai_vc.advisory import persist_investment_critique
    persist_investment_critique(
        db, deck_id=deck.id, operation_id=operation_id,
        review=parsed["investmentCommitteeReview"],
    )
    db.commit()
    return parsed


def ensure_vc_strategy(
    db: Session, *, deck, operation_id: str, source_facts: list[dict],
    source_slides: list[dict], external_research: dict,
    design_guidance: dict | None = None,
) -> dict:
    """Run the mounted, staged AI-VC graph behind the existing entrypoint."""
    from app.services.ai_vc.runtime import execute_ai_vc_runtime

    return execute_ai_vc_runtime(
        db,
        deck=deck,
        operation_id=operation_id,
        source_facts=source_facts,
        source_slides=source_slides,
        external_research=external_research,
        design_guidance=design_guidance,
    )
