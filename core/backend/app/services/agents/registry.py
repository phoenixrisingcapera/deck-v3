from __future__ import annotations

from app.services.agents.base import AgentCapability, AgentRegistry
from app.services.agents.due_diligence_agent import DUE_DILIGENCE_AGENT
from app.services.agents.smart_deck_agent import SMART_DECK_AGENT
from app.services.agents.smart_edit_agent import SMART_EDIT_AGENT


_REGISTRY = AgentRegistry(
    capabilities=(
        SMART_DECK_AGENT,
        SMART_EDIT_AGENT,
        DUE_DILIGENCE_AGENT,
    )
)


def list_agent_capabilities() -> tuple[AgentCapability, ...]:
    return _REGISTRY.list()


def get_agent_capability(agent_key: str) -> AgentCapability | None:
    return _REGISTRY.get(agent_key)
