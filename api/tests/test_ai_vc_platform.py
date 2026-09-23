from app.services.ai_vc.finance import FinancialAssumption, calculate_saas_scenario
import pytest

from app.services.ai_vc.graph import build_ai_vc_graph, critique_publication_effect
from app.services.ai_vc.models import (
    DeckArchitecture, DeckSlidePlan, InvestmentCommitteeReview, ResearchBudget, RunResearchBudget,
)
from app.services.ai_vc.ontology import VC_DIMENSIONS, plan_research_tasks


def test_universal_ontology_creates_sector_specific_tasks_without_company_hardcoding():
    tasks = plan_research_tasks(
        {"summary": "workflow software for specialist clinics"}, sector="saas", max_tasks=6,
        budget=ResearchBudget(max_searches=1, max_sources=3, max_tokens=2000, max_cost_cents=80, max_runtime_seconds=60),
    )
    assert len(tasks) == 6
    assert tasks[0].purpose == "retention"
    assert all("specialist clinics" in task.question for task in tasks)
    assert "regulatory_context" in VC_DIMENSIONS
    assert all(task.budget.max_searches == 1 for task in tasks)


@pytest.mark.parametrize(
    ("sector", "expected_purpose"),
    [
        ("saas", "retention"),
        ("fintech", "regulatory_context"),
        ("consumer", "acquisition_dynamics"),
        ("biotech", "milestones"),
    ],
)
def test_research_ontology_adapts_across_investment_models(sector, expected_purpose):
    tasks = plan_research_tasks(
        {"summary": f"a private {sector} company"}, sector=sector, max_tasks=6,
    )
    assert expected_purpose in {task.purpose for task in tasks}
    assert all(task.budget.max_searches == 1 for task in tasks)


def test_financial_model_is_deterministic_and_explicitly_illustrative():
    model = calculate_saas_scenario([
        FinancialAssumption(id="a1", name="accounts", value=2000, unit="accounts", evidence_class="VC_INFERENCE", confidence="low"),
        FinancialAssumption(id="a2", name="monthly_price", value=350, unit="GBP", evidence_class="EXTERNAL_RESEARCH", source_evidence_ids=["ev1"], confidence="medium"),
        FinancialAssumption(id="a3", name="gross_margin", value=0.8, unit="ratio", evidence_class="VC_INFERENCE", confidence="low"),
    ])
    values = {item["id"]: item["value"] for item in model["calculations"]}
    assert values["calc_arr"] == 8_400_000
    assert values["calc_gross_profit"] == 6_720_000
    gross_profit = next(item for item in model["calculations"] if item["id"] == "calc_gross_profit")
    assert gross_profit["assumption_ids"] == ["a3"]
    assert gross_profit["calculation_ids"] == ["calc_arr"]
    assert model["presentationLabel"] == "Illustrative scenario"


def test_graph_allows_one_bounded_follow_up_then_completes():
    calls = []
    def node(name, output=None):
        def run(state):
            calls.append(name)
            return output(state) if callable(output) else (output or {})
        return run

    graph = build_ai_vc_graph(
        understand=node("understand"), plan=node("plan"), research=node("research"),
        analyze=node("analyze"), finance=node("finance"),
        committee=node("committee", lambda state: {
            "ic_review": {"criticalUnansweredQuestions": ["gap"] if state.get("research_iterations", 0) == 0 else []},
            "additional_reasoning_calls": state.get("additional_reasoning_calls", 0) + 1,
        }),
        follow_up=node("follow_up", lambda state: {"research_iterations": state.get("research_iterations", 0) + 1}),
        narrative=node("narrative", {"next_action": "design"}),
    )
    result = graph.invoke({
        "schema_version": "ai-vc-state.v1", "research_iterations": 0,
        "max_research_iterations": 2, "additional_reasoning_calls": 0,
        "max_additional_reasoning_calls": 3, "budget_remaining_cents": 100,
    })
    assert calls.count("follow_up") == 1
    # The critique is advisory; do not replay an identical paid analysis call
    # under the same durable identity when no new evidence was acquired.
    assert calls.count("analyze") == 1
    assert result["research_iterations"] == 1
    assert result["next_action"] == "design"


def test_run_budget_is_global_not_copied_as_fresh_allowance_per_task():
    run = RunResearchBudget(max_searches=2, max_sources=6, max_tokens=4000,
                            max_cost_cents=160, max_runtime_seconds=120)
    task = ResearchBudget(max_searches=1, max_sources=3, max_tokens=2000,
                          max_cost_cents=80, max_runtime_seconds=60)
    run = run.reserve(task).reserve(task)
    assert run.used_searches == 2 and run.used_cost_cents == 160
    with pytest.raises(ValueError, match="run-level budget"):
        run.reserve(task)


def test_ic_critique_is_structurally_advisory_and_never_blocks_export():
    review = InvestmentCommitteeReview(
        concerns=["No retention data supplied"],
        critical_for_fundraising=["Willingness to pay is unproven"],
    )
    assert review.publication_blocking is False
    effect = critique_publication_effect({"ic_review": review.model_dump()})
    assert effect == {"investmentCritiqueBlocksPublication": False, "next_action": "narrative"}


def test_deck_architecture_has_variable_count_and_typed_evidence_lineage():
    architecture = DeckArchitecture(
        core_thesis="A workflow layer for specialist clinics", recommended_slide_count=1,
        rationale="Only one source-backed idea is available in this fixture.",
        slides=[DeckSlidePlan(index=1, role="investment_thesis", objective="Explain the wedge",
                              evidence_ids=["fact_1"], calculation_ids=[], visual_intent="workflow diagram")],
    )
    assert architecture.recommended_slide_count == len(architecture.slides)


def test_graph_stops_when_budget_is_exhausted():
    graph = build_ai_vc_graph(
        understand=lambda state: {}, plan=lambda state: {}, research=lambda state: {},
        analyze=lambda state: {}, finance=lambda state: {},
        committee=lambda state: {"ic_review": {"criticalUnansweredQuestions": ["gap"]}},
        follow_up=lambda state: (_ for _ in ()).throw(AssertionError("follow-up must not run")),
        narrative=lambda state: {"next_action": "design"},
    )
    result = graph.invoke({"budget_remaining_cents": 0, "max_research_iterations": 2,
                           "max_additional_reasoning_calls": 3})
    assert result["next_action"] == "design"
