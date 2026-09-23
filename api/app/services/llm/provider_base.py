from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.llm.response_models import LlmGenerationConfig, LlmResponse


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate_text(self, *, system: str | None = None, user: str, config: LlmGenerationConfig) -> LlmResponse:
        ...

    @abstractmethod
    def validate_connection(self, *, api_key: str, model: str | None = None) -> bool:
        ...
