"""LangGraph coordinator over Deck V2-owned AI-VC services."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.services.ai_vc.models import AIVCState

Node = Callable[[AIVCState], dict[str, Any]]


@dataclass(frozen=True)
class DurablePaidNode:
    """Enforce Deck V2 prestart -> transport -> settlement ordering."""
    create_attempt_and_reserve: Callable[[AIVCState], str]
    execute_existing_transport: Callable[[AIVCState, str], dict[str, Any]]
    validate_and_settle: Callable[[AIVCState, str, dict[str, Any]], dict[str, Any]]

    def __call__(self, state: AIVCState) -> dict[str, Any]:
        attempt_id = self.create_attempt_and_reserve(state)
        response = self.execute_existing_transport(state, attempt_id)
        return self.validate_and_settle(state, attempt_id, response)


def _route_after_ic(state: AIVCState) -> str:
    critical = bool((state.get("ic_review") or {}).get("criticalUnansweredQuestions"))
    iterations = int(state.get("research_iterations", 0))
    max_iterations = int(state.get("max_research_iterations", 1))
    calls = int(state.get("additional_reasoning_calls", 0))
    max_calls = int(state.get("max_additional_reasoning_calls", 3))
    budget = state.get("budget_remaining_cents")
    cost_policy_allows = budget is None or float(budget) > 0
    return "follow_up" if critical and iterations < max_iterations and calls < max_calls and cost_policy_allows else "narrative"


def critique_publication_effect(_state: AIVCState) -> dict[str, Any]:
    """Investment critique is advisory even at fundraising-critical severity."""
    return {"investmentCritiqueBlocksPublication": False, "next_action": "narrative"}


def build_ai_vc_graph(*, understand: Node, plan: Node, research: Node, analyze: Node,
                      finance: Node, committee: Node, follow_up: Node, narrative: Node):
    graph = StateGraph(AIVCState)
    graph.add_node("understand", understand)
    graph.add_node("plan", plan)
    graph.add_node("research", research)
    graph.add_node("analyze", analyze)
    graph.add_node("finance", finance)
    graph.add_node("committee", committee)
    graph.add_node("follow_up", follow_up)
    graph.add_node("narrative", narrative)
    graph.add_edge(START, "understand")
    graph.add_edge("understand", "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "analyze")
    graph.add_edge("analyze", "finance")
    graph.add_edge("finance", "committee")
    graph.add_conditional_edges("committee", _route_after_ic, {"follow_up": "follow_up", "narrative": "narrative"})
    # The current follow-up node records advisory unanswered questions; it does
    # not acquire new evidence. Replaying the identical paid analysis request
    # both wastes money and collides with its durable attempt key. Continue to
    # narrative with the critique attached; future evidence-acquiring follow-up
    # work must define its own durable request identity.
    graph.add_edge("follow_up", "narrative")
    graph.add_edge("narrative", END)
    return graph.compile()
