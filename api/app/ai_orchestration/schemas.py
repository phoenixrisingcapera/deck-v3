from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AiOrchestrationRequest(BaseModel):
    deck_id: str = Field(alias="deckId")
    selected_slide_ids: list[str] = Field(alias="selectedSlideIds", min_length=1, max_length=8)
    user_instruction: str = Field(alias="userInstruction", min_length=1, max_length=4000)
    audience: str | None = None
    mode: Literal["redesign_selected_slides"] = "redesign_selected_slides"
    preferred_model: str | None = Field(default=None, alias="preferredModel")

    model_config = ConfigDict(populate_by_name=True)


class SceneGraphElement(BaseModel):
    id: str
    type: Literal["text", "shape", "image", "chart_placeholder"]
    x: float
    y: float
    width: float
    height: float
    text: str | None = None
    style: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)


class SlideSceneGraph(BaseModel):
    schema_version: Literal["smart-deck-scene-graph.v1"] = Field(alias="schemaVersion")
    width: int
    height: int
    background: dict[str, Any] = Field(default_factory=lambda: {"type": "color", "value": "#ffffff"})
    elements: list[SceneGraphElement] = Field(min_length=1, max_length=48)

    model_config = ConfigDict(populate_by_name=True)


class GeneratedSlideVersion(BaseModel):
    source_slide_id: str = Field(alias="sourceSlideId")
    title: str
    headline: str
    summary: str
    rationale: str
    scene_graph: SlideSceneGraph = Field(alias="sceneGraph")

    model_config = ConfigDict(populate_by_name=True)


class LlmGenerationOutput(BaseModel):
    batch_title: str = Field(alias="batchTitle")
    generated_slides: list[GeneratedSlideVersion] = Field(alias="generatedSlides", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class AiRunResponse(BaseModel):
    id: str
    deckId: str
    workspaceId: str
    status: str
    mode: str
    selectedSlideIds: list[str]
    provider: str
    model: str | None = None
    createdAt: str
    completedAt: str | None = None


class AiOrchestrationResponse(BaseModel):
    runId: str
    deckId: str
    status: str
    batchId: str
    batch: dict
    generatedSlideVersions: list[dict]
    aiRun: AiRunResponse

