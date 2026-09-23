from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.dashscope_provider import DashScopeProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.openrouter_provider import OpenRouterProvider
from app.services.llm.provider_base import LLMProvider
from app.services.llm.provider_registry import ProviderRegistry
from app.services.llm.response_models import LlmGenerationConfig, LlmResponse

default_registry = ProviderRegistry()
default_registry.register(AnthropicProvider())
default_registry.register(OpenAIProvider())
default_registry.register(OpenRouterProvider())
default_registry.register(DashScopeProvider())

__all__ = [
    "LLMProvider",
    "LlmGenerationConfig",
    "LlmResponse",
    "ProviderRegistry",
    "default_registry",
]
