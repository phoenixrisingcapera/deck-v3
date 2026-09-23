"""Resolve a small, company-relevant capability set before research."""
from __future__ import annotations

from app.services.ai_vc.skills.models import AIVCSkillPlan, SkillPhase, SkillSelection
from app.services.ai_vc.skills.registry import load_builtin_skill_catalog

_CORE = (
    "company-understanding", "market-structure", "customer-economics",
    "competitor-landscape", "why-now", "business-model", "financial-scenario",
    "investment-memo", "ic-critique", "narrative-architecture", "visual-storytelling",
)
_SECTOR_SKILLS = {
    "saas": "saas-economics", "marketplace": "marketplace-economics",
    "fintech": "fintech-economics", "hardware": "hardware-economics",
    "biotech": "biotech-analysis",
}
_SECTOR_SIGNALS = {
    "biotech": ("biotech", "therapeutic", "clinical trial", "drug discovery", "diagnostic"),
    "fintech": ("fintech", "payments", "banking", "lending", "insurance", "financial platform"),
    "marketplace": ("marketplace", "buyers and sellers", "take rate", "two-sided"),
    "hardware": ("hardware", "device", "manufacturing", "bill of materials", "supply chain"),
    "saas": ("software", "saas", "subscription", "workflow", "crm", "operating system", "platform"),
}
_RESEARCH_PRIORITY = {
    "general": (
        "market_context", "competitor_landscape", "customer_economics", "why_now",
        "business_model_benchmark", "regulatory_context", "acquisition_dynamics", "comparable_outcomes",
    ),
    "saas": (
        "market_context", "competitor_landscape", "customer_economics", "why_now",
        "business_model_benchmark", "retention", "sales_motion", "pricing",
    ),
    "marketplace": (
        "market_context", "customer_economics", "acquisition_dynamics", "competitor_landscape",
        "retention", "margins", "why_now", "business_model_benchmark",
    ),
    "fintech": (
        "regulatory_context", "customer_economics", "competitor_landscape", "capital_intensity",
        "market_context", "major_risks", "margins", "why_now",
    ),
    "hardware": (
        "capital_intensity", "margins", "regulatory_context", "milestones",
        "market_context", "competitor_landscape", "scalability", "why_now",
    ),
    "biotech": (
        "regulatory_context", "milestones", "capital_intensity", "market_context",
        "major_risks", "defensibility", "comparable_outcomes", "why_now",
    ),
}


def _company_text(company: dict) -> str:
    return " ".join(
        str(item.get("text") or "")
        for lane in ("businessEvidence", "hypotheses")
        for item in company.get(lane, [])
        if isinstance(item, dict)
    ).lower()


def _infer_sector(company: dict) -> str:
    text = _company_text(company)
    scores = {
        sector: sum(signal in text for signal in signals)
        for sector, signals in _SECTOR_SIGNALS.items()
    }
    sector, score = max(scores.items(), key=lambda item: (item[1], item[0]))
    return sector if score else "general"


def resolve_skill_plan(company: dict) -> AIVCSkillPlan:
    """Compatibility resolver for historical artifacts and non-Instant callers.

    The active Instant Deck path uses ``resolve_model_skill_plan``. Keyword
    matches here must never regain authority over live research scheduling.
    """
    catalog = load_builtin_skill_catalog()
    sector = _infer_sector(company)
    names = list(_CORE)
    sector_skill = _SECTOR_SKILLS.get(sector)
    if sector_skill:
        names.insert(4, sector_skill)
    selected = []
    skills = []
    for name in names:
        skill = catalog[name]
        skills.append(skill)
        selected.append(SkillSelection(
            name=name,
            priority=(
                "critical"
                if name in {"company-understanding", "investment-memo", "narrative-architecture"}
                else "high"
            ),
            reason=(
                f"Detected {sector} investment model"
                if name == sector_skill
                else "Core capital-raising capability"
            ),
        ))
    purposes = []
    for skill in skills:
        for purpose in skill.retrieval_purposes:
            if purpose not in purposes:
                purposes.append(purpose)
    return AIVCSkillPlan(
        inferred_sector=sector, selected=selected,
        research_purposes=purposes, skills=skills,
    )


def resolve_model_skill_plan(model_plan: dict) -> AIVCSkillPlan:
    """Load only checked-in methodology selected by the evidence-grounded model."""
    catalog = load_builtin_skill_catalog()
    raw_selections = model_plan.get("methodologySelections") or model_plan.get("methodology_selections") or []
    selected: list[SkillSelection] = []
    skills = []
    seen: set[str] = set()
    for raw in raw_selections:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if name in seen:
            continue
        if name not in catalog:
            raise ValueError("Model selected unknown AI-VC methodology")
        seen.add(name)
        skill = catalog[name]
        skills.append(skill)
        selected.append(SkillSelection(
            name=name,
            priority=str(raw.get("priority") or "high"),
            reason=str(raw.get("reason") or "Selected by evidence-grounded research planning"),
        ))
    if not skills:
        raise ValueError("Model research plan selected no valid methodology")
    purposes: list[str] = []
    for skill in skills:
        for purpose in skill.retrieval_purposes:
            if purpose not in purposes:
                purposes.append(purpose)
    contexts = model_plan.get("companyUnderstanding", {}).get("industryContexts", [])
    industry = " / ".join(
        str(item.get("statement") or "") for item in contexts[:3] if isinstance(item, dict)
    ) or "unknown or mixed"
    return AIVCSkillPlan(
        inferred_sector=industry[:240], selected=selected,
        research_purposes=purposes, skills=skills,
    )


def resolve_core_skill_plan() -> AIVCSkillPlan:
    """Sector-neutral compatibility plan when model planning is unavailable."""
    catalog = load_builtin_skill_catalog()
    skills = [catalog[name] for name in _CORE]
    purposes: list[str] = []
    for skill in skills:
        for purpose in skill.retrieval_purposes:
            if purpose not in purposes:
                purposes.append(purpose)
    return AIVCSkillPlan(
        inferred_sector="unknown or mixed",
        selected=[SkillSelection(
            name=skill.name,
            priority="critical" if skill.name in {"company-understanding", "investment-memo", "narrative-architecture"} else "high",
            reason="Sector-neutral product methodology; no model research plan was available",
        ) for skill in skills],
        research_purposes=purposes,
        skills=skills,
    )


def stage_skill_context(plan: AIVCSkillPlan, phase: SkillPhase) -> dict:
    """Expose full instructions only for capabilities active in this phase."""
    active = [skill for skill in plan.skills if phase in skill.phases]
    return {
        "schemaVersion": "ai-vc-active-skills.v1",
        "phase": phase,
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "instructions": skill.instructions,
                "retrievalPurposes": skill.retrieval_purposes,
                "allowedTools": skill.allowed_tools,
                "contentHash": skill.content_hash,
            }
            for skill in active
        ],
        "policy": {
            "skillsAreMethodologyNotEvidence": True,
            "toolsAreApplicationServicesOnly": True,
            "unselectedSkillInstructionsAreNotLoaded": True,
        },
    }


def skill_research_priorities(plan: AIVCSkillPlan) -> list[str]:
    """Order only purposes declared by selected skills for the bounded research run."""
    declared = set(plan.research_purposes)
    preferred = _RESEARCH_PRIORITY.get(plan.inferred_sector, _RESEARCH_PRIORITY["general"])
    return [purpose for purpose in preferred if purpose in declared]


def skill_plan_trace(plan: AIVCSkillPlan) -> dict:
    """Persist selection/provenance without copying internal instructions to authoring."""
    return {
        "schemaVersion": plan.schema_version,
        "catalogVersion": plan.catalog_version,
        "inferredSector": plan.inferred_sector,
        "selectedSkills": [selection.model_dump(mode="json") for selection in plan.selected],
        "researchPurposes": plan.research_purposes,
        "skillHashes": {skill.name: skill.content_hash for skill in plan.skills},
    }
