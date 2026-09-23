from __future__ import annotations

import json

from app.services.llm.dashscope_provider import call_dashscope_chat_completion, extract_dashscope_text
from app.ai_orchestration.schemas import LlmGenerationOutput
from app.core.config import settings


class DashScopeLlmProvider:
    name = "dashscope"

    def __init__(self, *, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("QWEN_API_KEY is required for Qwen generation.")
        self.api_key = api_key
        self.model = model or settings.effective_qwen_model

    def generate_slide_versions(self, context: dict) -> LlmGenerationOutput:
        response = call_dashscope_chat_completion(
            api_key=self.api_key,
            model=self.model,
            system=_system_prompt(),
            user=json.dumps(context, default=str),
        )
        return LlmGenerationOutput.model_validate(json.loads(extract_dashscope_text(response)))


def _system_prompt() -> str:
    return (
        "You generate investor-ready pitch deck slide variations. "
        "Return only JSON with keys batchTitle and generatedSlides. "
        "Each generated slide must include sourceSlideId, title, headline, summary, rationale, "
        "and sceneGraph. sceneGraph must use schemaVersion smart-deck-scene-graph.v1, width 1280, "
        "height 720, and 1-48 positioned text/shape/image/chart_placeholder elements."
    )
