from __future__ import annotations

from app.services.llm.provider_base import LLMProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider:
        provider = self._providers.get(name)
        if provider is None:
            raise KeyError(f"Unknown LLM provider: {name!r}. Available: {sorted(self._providers)}")
        return provider

    def available(self) -> list[str]:
        return sorted(self._providers)


registry = ProviderRegistry()
