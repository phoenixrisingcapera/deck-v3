from __future__ import annotations

import json

from app.services.llm.openai_provider import call_openai_response, extract_openai_text
from app.ai_orchestration.schemas import LlmGenerationOutput
from app.core.config import settings


class OpenAiLlmProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI generation.")
        self.api_key = api_key
        self.model = model or settings.openai_model

    def generate_slide_versions(self, context: dict) -> LlmGenerationOutput:
        response_payload = call_openai_response(
            api_key=self.api_key,
            model=self.model,
            system=_system_prompt(),
            user=json.dumps(context, default=str),
            response_format={"type": "json_object"},
        )

        return LlmGenerationOutput.model_validate(_extract_json_response(response_payload))


def _system_prompt() -> str:
    return (
        "You generate investor-ready pitch deck slide variations. "
        "Return only JSON with keys batchTitle and generatedSlides. "
        "Each generated slide must include sourceSlideId, title, headline, summary, rationale, "
        "and sceneGraph. sceneGraph must use schemaVersion smart-deck-scene-graph.v1, width 1280, "
        "height 720, and 1-48 positioned text/shape/image/chart_placeholder elements."
    )


def _extract_json_response(payload: dict) -> dict:
    return json.loads(extract_openai_text(payload))
