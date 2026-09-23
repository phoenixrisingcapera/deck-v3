from __future__ import annotations

import json

from app.services.llm.openrouter_provider import call_openrouter_chat_completion, extract_openrouter_text
from app.ai_orchestration.schemas import LlmGenerationOutput
from app.core.config import settings


class OpenRouterLlmProvider:
    name = "openrouter"

    def __init__(self, *, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter generation.")
        self.api_key = api_key
        self.model = model or settings.openrouter_model

    def generate_slide_versions(self, context: dict) -> LlmGenerationOutput:
        response_payload = call_openrouter_chat_completion(
            api_key=self.api_key,
            model=self.model,
            system=_system_prompt(),
            user=json.dumps(context, default=str),
            response_format={"type": "json_object"},
        )
        return LlmGenerationOutput.model_validate(json.loads(extract_openrouter_text(response_payload)))


def _system_prompt() -> str:
    return (
        "You generate investor-ready pitch deck slide variations. "
        "Return only JSON with keys batchTitle and generatedSlides. "
        "Each generated slide must include sourceSlideId, title, headline, summary, rationale, "
        "and sceneGraph. sceneGraph must use schemaVersion smart-deck-scene-graph.v1, width 1280, "
        "height 720, and 1-48 positioned text/shape/image/chart_placeholder elements."
    )
