from __future__ import annotations

import json

from app.services.llm.anthropic_provider import call_anthropic_message, extract_anthropic_text
from app.ai_orchestration.schemas import LlmGenerationOutput
from app.core.config import settings


class AnthropicLlmProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude generation.")
        self.api_key = api_key
        self.model = model or settings.anthropic_model

    def generate_slide_versions(self, context: dict) -> LlmGenerationOutput:
        response = call_anthropic_message(
            api_key=self.api_key,
            model=self.model,
            system=_system_prompt(),
            user=json.dumps(context, default=str),
        )
        return LlmGenerationOutput.model_validate(json.loads(extract_anthropic_text(response)))


def _system_prompt() -> str:
    return (
        "You generate investor-ready pitch deck slide variations. "
        "Return only JSON with keys batchTitle and generatedSlides. "
        "Each generated slide must include sourceSlideId, title, headline, summary, rationale, "
        "and sceneGraph. sceneGraph must use schemaVersion smart-deck-scene-graph.v1, width 1280, "
        "height 720, and 1-48 positioned text/shape/image/chart_placeholder elements."
    )
