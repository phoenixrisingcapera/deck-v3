"""Typed contracts for application-owned AI-VC capabilities."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai_vc.models import RetrievalPurpose


SkillPhase = Literal["understanding", "research", "analysis", "narrative", "visual"]


class AIVCSkill(BaseModel):
    """One trusted product capability loaded from the checked-in skill catalog."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    description: str = Field(min_length=10, max_length=1024)
    phases: list[SkillPhase] = Field(min_length=1)
    retrieval_purposes: list[RetrievalPurpose] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    sector_signals: list[str] = Field(default_factory=list)
    instructions: str = Field(min_length=20, max_length=12000)
    path: str
    content_hash: str


class SkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    priority: Literal["critical", "high", "medium"]
    reason: str


class AIVCSkillPlan(BaseModel):
    """Resolved capabilities for one company, before research begins."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai-vc-skill-plan.v1"] = "ai-vc-skill-plan.v1"
    catalog_version: Literal["ai-vc-product-skills.v1"] = "ai-vc-product-skills.v1"
    inferred_sector: str
    selected: list[SkillSelection]
    research_purposes: list[RetrievalPurpose]
    skills: list[AIVCSkill]
