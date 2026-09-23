from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AgentExecutionMode = Literal["workflow", "variation_job", "analysis_run"]


@dataclass(frozen=True)
class AgentCapability:
    agent_key: str
    label: str
    description: str
    execution: AgentExecutionMode
    allowed_user_roles: tuple[str, ...]
    input_schema: str
    output_schema: str
    provider_use_case: str
    persistence_target: str
    review_surface: str
    user_route: str
    command_route: str
    required_input_fields: tuple[str, ...]
    job_chain: tuple[str, ...] = ()
    workflow_job_type: str | None = None
    artifact_types: tuple[str, ...] = ()
    debug_fields: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, object]:
        return {
            "agentKey": self.agent_key,
            "label": self.label,
            "description": self.description,
            "execution": self.execution,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "reviewSurface": self.review_surface,
            "userRoute": self.user_route,
            "commandRoute": self.command_route,
            "requiredInputFields": list(self.required_input_fields),
        }

    def to_super_admin_dict(self) -> dict[str, object]:
        payload = self.to_public_dict()
        payload.update(
            {
                "allowedUserRoles": list(self.allowed_user_roles),
                "workflowJobType": self.workflow_job_type,
                "jobChain": list(self.job_chain),
                "providerUseCase": self.provider_use_case,
                "persistenceTarget": self.persistence_target,
                "artifactTypes": list(self.artifact_types),
                "debugFields": list(self.debug_fields),
                "notes": list(self.notes),
            }
        )
        return payload


@dataclass(frozen=True)
class AgentRegistry:
    capabilities: tuple[AgentCapability, ...] = field(default_factory=tuple)

    def list(self) -> tuple[AgentCapability, ...]:
        return self.capabilities

    def get(self, agent_key: str) -> AgentCapability | None:
        normalized = agent_key.strip().lower().replace("-", "_")
        return next((item for item in self.capabilities if item.agent_key == normalized), None)
