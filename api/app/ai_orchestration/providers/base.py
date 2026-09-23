from __future__ import annotations

from typing import Protocol

from app.ai_orchestration.schemas import LlmGenerationOutput


class BaseLlmProvider(Protocol):
    name: str
    model: str | None

    def generate_slide_versions(self, context: dict) -> LlmGenerationOutput:
        ...

