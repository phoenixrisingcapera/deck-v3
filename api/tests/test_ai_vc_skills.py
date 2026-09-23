from app.services.ai_vc.skills.registry import load_builtin_skill_catalog
from app.services.ai_vc.skills.resolver import (
    resolve_model_skill_plan,
    resolve_skill_plan,
    stage_skill_context,
)
from app.services.llm.instant_vc_strategy import build_universal_research_plan


def _company(text: str) -> dict:
    return {
        "businessEvidence": [{"text": text, "evidenceRefs": ["fact_1"]}],
        "hypotheses": [],
    }


def test_builtin_skill_catalog_is_bounded_and_uses_only_product_tools():
    catalog = load_builtin_skill_catalog()
    assert {
        "company-understanding", "market-structure", "investment-memo",
        "narrative-architecture", "visual-storytelling", "saas-economics",
    } <= set(catalog)
    allowed = {
        "public_research", "evidence_search", "methodology_retrieval",
        "company_memory", "financial_calculation",
    }
    assert all(set(skill.allowed_tools) <= allowed for skill in catalog.values())
    assert all("shell" not in skill.allowed_tools for skill in catalog.values())


def test_skill_resolver_selects_sector_capability_and_discloses_by_phase():
    plan = resolve_skill_plan(_company(
        "Subscription workflow software for specialist clinics with recurring revenue."
    ))
    names = [selection.name for selection in plan.selected]
    assert plan.inferred_sector == "saas"
    assert "saas-economics" in names

    analysis = stage_skill_context(plan, "analysis")
    narrative = stage_skill_context(plan, "narrative")
    analysis_names = {skill["name"] for skill in analysis["skills"]}
    narrative_names = {skill["name"] for skill in narrative["skills"]}
    assert "saas-economics" in analysis_names
    assert "narrative-architecture" not in analysis_names
    assert "narrative-architecture" in narrative_names
    assert "company-understanding" not in narrative_names
    assert all(skill["instructions"] for skill in analysis["skills"])


def test_skills_drive_research_priorities_without_turning_methodology_into_search_evidence():
    plan = build_universal_research_plan(_company(
        "SaaS platform that coordinates clinic acquisition, booking, follow-up and retention."
    ))
    purposes = [task["purpose"] for task in plan["tasks"]]
    assert plan["schemaVersion"] == "ai-vc-research-plan.v2"
    assert plan["skillSelection"]["catalogVersion"] == "ai-vc-product-skills.v1"
    assert purposes[0] == "market_context"
    assert "customer_economics" in purposes
    assert "investment_screening" not in purposes
    assert "design_guidance" not in purposes


def test_active_model_plan_selects_methodology_without_sector_keyword_routing():
    plan = resolve_model_skill_plan({
        "companyUnderstanding": {
            "industryContexts":[{"statement":"industrial diagnostics sold to manufacturers"}],
        },
        "methodologySelections":[
            {"name":"company-understanding", "priority":"critical", "reason":"Interpret mixed evidence"},
            {"name":"saas-economics", "priority":"high", "reason":"The model identified recurring software economics"},
        ],
    })
    assert plan.inferred_sector == "industrial diagnostics sold to manufacturers"
    assert [item.name for item in plan.selected] == ["company-understanding", "saas-economics"]
    assert "biotech-analysis" not in {item.name for item in plan.selected}
    assert "hardware-economics" not in {item.name for item in plan.selected}
