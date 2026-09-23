"""Universal investment dimensions; questions remain company-specific."""
from __future__ import annotations

from collections.abc import Sequence

from app.services.ai_vc.models import ResearchBudget, ResearchTask, RetrievalPurpose

VC_DIMENSIONS = (
    "problem_severity", "customer_buyer", "market_context", "market_size",
    "why_now", "competitor_landscape", "substitutes",
    "differentiation", "business_model_benchmark", "pricing", "customer_economics",
    "acquisition_dynamics", "sales_motion", "retention", "margins", "scalability",
    "capital_intensity", "regulatory_context", "defensibility", "comparable_outcomes",
    "funding_outcomes", "major_risks", "milestones", "investor_objections",
    "financial_potential",
)

SECTOR_EMPHASIS = {
    "saas": ("retention", "customer_economics", "competitor_landscape", "sales_motion", "margins", "scalability"),
    "consumer": ("retention", "acquisition_dynamics", "pricing", "margins", "market_size"),
    "fintech": ("regulatory_context", "customer_economics", "capital_intensity", "margins", "major_risks"),
    "biotech": ("regulatory_context", "capital_intensity", "milestones", "defensibility", "major_risks"),
    "marketplace": ("customer_buyer", "acquisition_dynamics", "retention", "margins", "scalability"),
}


def plan_research_tasks(
    company: dict,
    *,
    sector: str = "general",
    max_tasks: int = 8,
    budget: ResearchBudget | None = None,
    preferred_purposes: Sequence[RetrievalPurpose] | None = None,
) -> list[ResearchTask]:
    descriptor = str(company.get("summary") or company.get("whatCompanySells") or "this company")[:220]
    priority = list(preferred_purposes or ())
    for dimension in SECTOR_EMPHASIS.get(sector.lower(), ()):
        if dimension not in priority:
            priority.append(dimension)
    for dimension in VC_DIMENSIONS:
        if dimension not in priority:
            priority.append(dimension)
    allocation = budget or ResearchBudget()
    tasks = []
    question_templates = {
        "competitor_landscape": "Which incumbents, substitutes and adjacent products compete with {company}, and where do they stop?",
        "why_now": "Which credible market, technology, behavior or regulatory changes make {company} timely now?",
        "customer_economics": "What credible evidence explains customer pain, willingness to pay and retention economics for {company}?",
        "regulatory_context": "Which regulatory constraints, approvals or compliance risks materially affect {company}?",
        "financial_potential": "Which externally supportable assumptions can frame an illustrative financial scenario for {company}?",
    }
    for index, dimension in enumerate(priority[:max_tasks]):
        question = question_templates.get(
            dimension,
            "What credible evidence should an investor use to assess " + dimension.replace("_", " ") + " for {company}?",
        ).format(company=descriptor)
        tasks.append(ResearchTask(
            id=f"research_{index + 1:02d}", purpose=dimension,
            question=question,
            importance="critical" if index < 3 else "high" if index < 5 else "medium",
            required_evidence_types=["credible_primary_source"],
            preferred_sources=["government", "regulator", "company_primary", "industry_association"],
            budget=allocation.model_copy(),
        ))
    return tasks
