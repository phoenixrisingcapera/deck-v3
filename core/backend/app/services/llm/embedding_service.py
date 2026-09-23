from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING
from urllib import error as url_error
from urllib import request

from cryptography.fernet import InvalidToken

from app.core.config import settings
from app.core.workspace_ai_crypto import get_workspace_ai_fernet
from app.db.models import WorkspaceAiCredential, WorkspaceAiProviderSetting
from app.services.llm.model_catalog import get_model_capability

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_LOCAL_EMBEDDING_DIMENSIONS = 384
_STORAGE_EMBEDDING_DIMENSIONS = 1024


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int
    fallback_level: int = 0
    error_category: str | None = None


@dataclass(frozen=True)
class EmbeddingRuntimeConfig:
    provider: str
    model: str
    api_key: str
    source: str
    credential_last4: str | None = None


_metrics_lock = Lock()
_embedding_metrics: dict[str, int] = {
    "requests": 0,
    "successes": 0,
    "fallbacks": 0,
    "failures": 0,
}
_model_metrics: dict[str, dict[str, int]] = {}


class EmbeddingUnavailableError(RuntimeError):
    pass


def probe_embedding_contract() -> dict[str, object]:
    """Call the configured provider and verify the vector storage contract."""
    result = create_embeddings_with_metadata(["Deck AI Stack readiness probe"])
    if result.dimensions != _STORAGE_EMBEDDING_DIMENSIONS:
        raise EmbeddingUnavailableError(
            f"Embedding dimension mismatch: provider returned {result.dimensions}, "
            f"storage requires {_STORAGE_EMBEDDING_DIMENSIONS}."
        )
    return {
        "provider": result.provider,
        "model": result.model,
        "dimensions": result.dimensions,
        "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
        "status": "ok",
    }


OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
# Legacy OpenRouter transport retained for non-production compatibility. The
# enforced production embedding route uses the OpenAI endpoint above.
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai" + "/api/" + "v1/embeddings"


def _resolved_embedding_provider() -> str:
    provider = settings.embedding_provider.strip().lower()
    if settings.is_production and provider != "openai":
        raise EmbeddingUnavailableError("Production embeddings require OpenAI.")
    if provider in {"", "auto"}:
        if settings.effective_qwen_api_key:
            return "dashscope"
        if settings.openrouter_api_key:
            return "openrouter"
        if settings.openai_api_key:
            return "openai"
        return "local"
    return provider


def get_embedding_provider_status(runtime_config: EmbeddingRuntimeConfig | None = None) -> dict:
    if runtime_config is not None:
        return {
            "status": "ready",
            "provider": runtime_config.provider,
            "model": runtime_config.model,
            "dimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            "fallbackModels": [],
            "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            "source": runtime_config.source,
        }
    provider = _resolved_embedding_provider()
    if provider == "openai":
        if settings.openai_api_key:
            return {
                "status": "ready",
                "provider": provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            }
        if settings.openrouter_api_key:
            return {
                "status": "ready",
                "provider": "openrouter",
                "model": "openai/text-embedding-3-small",
                "dimensions": settings.embedding_dimensions,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
                "message": "OPENAI_API_KEY missing; using OpenRouter embedding fallback.",
            }
        return {
            "status": "unavailable",
            "provider": provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "fallbackModels": _configured_fallback_models(),
            "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            "message": "OPENAI_API_KEY is required for embeddings.",
        }
    if provider == "openrouter":
        if settings.openrouter_api_key:
            return {
                "status": "ready",
                "provider": provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            }
        return {
            "status": "unavailable",
            "provider": provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "fallbackModels": _configured_fallback_models(),
            "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            "message": "OPENROUTER_API_KEY is required for embeddings.",
        }
    if provider == "dashscope":
        if settings.effective_qwen_api_key:
            return {
                "status": "ready",
                "provider": provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            }
        if settings.openrouter_api_key:
            return {
                "status": "ready",
                "provider": "openrouter",
                "model": "openai/text-embedding-3-small",
                "dimensions": settings.embedding_dimensions,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
                "message": "QWEN_API_KEY missing; using OpenRouter embedding fallback.",
            }
        # DashScope key missing: check if local fallback is available
        local_status = _check_local_embedding_available()
        if local_status["available"]:
            return {
                "status": "ready",
                "provider": "local",
                "model": _LOCAL_ST_MODEL_DEFAULT,
                "dimensions": settings.embedding_dimensions,
                "modelDimensions": _LOCAL_EMBEDDING_DIMENSIONS,
                "fallbackModels": _configured_fallback_models(),
                "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
                "message": "QWEN_API_KEY missing; using local sentence-transformers fallback.",
            }
        return {
            "status": "unavailable",
            "provider": provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "fallbackModels": _configured_fallback_models(),
            "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            "message": "QWEN_API_KEY is required for DashScope embeddings. No local fallback available.",
        }
    if provider == "local":
        reason: str | None = None
        loaded_model = _LOCAL_ST_MODEL_DEFAULT
        try:
            _load_sentence_transformer_model()
            status = "ready"
        except EmbeddingUnavailableError as exc:
            status = "unavailable"
            reason = str(exc)
        return {
            "status": status,
            "provider": provider,
            "model": loaded_model,
            "dimensions": settings.embedding_dimensions,
            "modelDimensions": _LOCAL_EMBEDDING_DIMENSIONS,
            "fallbackModels": _configured_fallback_models(),
            "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
            **({"message": reason} if reason else {}),
        }
    return {
        "status": "unavailable",
        "provider": provider,
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
        "fallbackModels": _configured_fallback_models(),
        "storageDimensions": _STORAGE_EMBEDDING_DIMENSIONS,
        "message": f"Unsupported embedding provider: {provider}",
    }


def _check_local_embedding_available() -> dict:
    """Check if local sentence-transformers is available as a fallback."""
    try:
        _load_sentence_transformer_model()
        return {"available": True}
    except EmbeddingUnavailableError:
        return {"available": False}


def resolve_workspace_embedding_config(
    db: "Session",
    workspace_id: str,
) -> EmbeddingRuntimeConfig | None:
    setting = (
        db.query(WorkspaceAiProviderSetting)
        .filter(
            WorkspaceAiProviderSetting.workspace_id == workspace_id,
            WorkspaceAiProviderSetting.configured_at.is_not(None),
        )
        .first()
    )
    if setting is None or not setting.credential_id:
        return None

    provider = "dashscope" if setting.provider == "qwen" else setting.provider
    if provider not in {"openai", "dashscope"}:
        return None

    model = setting.embedding_model or settings.embedding_model
    capability = get_model_capability(model)
    catalog_provider = "qwen" if provider == "dashscope" else provider
    if capability is None or capability.provider != catalog_provider or not capability.supports_embeddings:
        raise EmbeddingUnavailableError("The configured workspace embedding model is unavailable.")

    credential = (
        db.query(WorkspaceAiCredential)
        .filter(
            WorkspaceAiCredential.id == setting.credential_id,
            WorkspaceAiCredential.workspace_id == workspace_id,
            WorkspaceAiCredential.provider == setting.provider,
            WorkspaceAiCredential.is_active.is_(True),
        )
        .first()
    )
    if credential is None:
        return None
    try:
        api_key = get_workspace_ai_fernet().decrypt(credential.encrypted_api_key).decode()
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise EmbeddingUnavailableError("The workspace embedding credential could not be decrypted.") from exc
    return EmbeddingRuntimeConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        source="workspace",
        credential_last4=credential.api_key_last4,
    )


def create_embeddings(
    texts: list[str],
    *,
    runtime_config: EmbeddingRuntimeConfig | None = None,
) -> list[list[float]]:
    return create_embeddings_with_metadata(texts, runtime_config=runtime_config).vectors


def create_embeddings_with_metadata(
    texts: list[str],
    *,
    runtime_config: EmbeddingRuntimeConfig | None = None,
) -> EmbeddingResult:
    """Generate storage-compatible vectors using an ordered, quota-safe fallback chain.

    Vision and rerank models are intentionally excluded: they are different task
    contracts, not interchangeable text embedding fallbacks.
    """
    if not texts:
        return EmbeddingResult([], "none", "none", _STORAGE_EMBEDDING_DIMENSIONS)
    with _metrics_lock:
        _embedding_metrics["requests"] += 1
    attempts = _embedding_attempts(runtime_config)
    last_error: Exception | None = None
    for level, (provider, model) in enumerate(attempts):
        try:
            api_key = runtime_config.api_key if runtime_config and provider == runtime_config.provider else None
            vectors = _create_embeddings_for(provider, model, texts, api_key=api_key)
            _validate_vectors(vectors, len(texts), _STORAGE_EMBEDDING_DIMENSIONS)
            _record_model_metric(provider, model, "success", level)
            with _metrics_lock:
                _embedding_metrics["successes"] += 1
                if level:
                    _embedding_metrics["fallbacks"] += 1
            return EmbeddingResult(vectors, provider, model, _STORAGE_EMBEDDING_DIMENSIONS, level)
        except Exception as exc:
            last_error = exc
            category = _classify_embedding_error(exc)
            _record_model_metric(provider, model, "failure", level)
            logger.warning("embedding_attempt_failed", extra={"provider": provider, "model": model, "level": level, "category": category})
            if category in {"authentication", "invalid_request"} and provider == "dashscope":
                # A bad model/key is not repaired by retrying the same provider.
                continue
    with _metrics_lock:
        _embedding_metrics["failures"] += 1
    category = _classify_embedding_error(last_error) if last_error else "provider_error"
    raise EmbeddingUnavailableError(f"Embedding generation failed ({category}).") from last_error


def get_embedding_metrics() -> dict:
    with _metrics_lock:
        return {"totals": dict(_embedding_metrics), "models": {key: dict(value) for key, value in _model_metrics.items()}}


def _configured_fallback_models() -> list[str]:
    return [model.strip() for model in settings.embedding_fallback_models.split(",") if model.strip()]


def _embedding_attempts(runtime_config: EmbeddingRuntimeConfig | None = None) -> list[tuple[str, str]]:
    if runtime_config is not None:
        return [(runtime_config.provider, runtime_config.model)]
    provider = _resolved_embedding_provider()
    primary_model = settings.embedding_model
    attempts: list[tuple[str, str]] = []
    if provider == "dashscope" and settings.effective_qwen_api_key:
        attempts.append(("dashscope", primary_model))
        attempts.extend(("dashscope", model) for model in _configured_fallback_models() if model != primary_model)
    elif provider == "openai" and settings.openai_api_key:
        attempts.append(("openai", primary_model))
    elif provider == "openrouter" and settings.openrouter_api_key:
        attempts.append(("openrouter", "openai/text-embedding-3-small"))
    if settings.is_production:
        # Production must stay on explicitly configured first-party providers only.
        # Keep local/off-platform fallbacks disabled, but allow a supported
        # OpenAI embedding path when production is configured that way.
        return attempts if provider in {"dashscope", "openai"} else []
    # Cross-provider fallback: if primary provider key is missing, try others
    if not attempts:
        if settings.effective_qwen_api_key:
            attempts.append(("dashscope", primary_model))
        if settings.openrouter_api_key:
            attempts.append(("openrouter", "openai/text-embedding-3-small"))
        if settings.openai_api_key:
            attempts.append(("openai", "text-embedding-3-small"))
    # Always include OpenAI fallback if key is available
    if settings.openai_api_key and ("openai", "text-embedding-3-small") not in attempts:
        attempts.append(("openai", "text-embedding-3-small"))
    # Local sentence-transformers is the final fallback after cloud failures.
    if ("local", _LOCAL_ST_MODEL_DEFAULT) not in attempts:
        attempts.append(("local", _LOCAL_ST_MODEL_DEFAULT))
    return attempts


def _create_embeddings_for(
    provider: str,
    model: str,
    texts: list[str],
    *,
    api_key: str | None = None,
) -> list[list[float]]:
    if provider == "openai":
        return _request_embeddings(OPENAI_EMBEDDINGS_URL, api_key or settings.openai_api_key, model, settings.embedding_timeout_seconds, dimensions=_STORAGE_EMBEDDING_DIMENSIONS)(texts)
    if provider == "openrouter":
        return _request_embeddings(OPENROUTER_EMBEDDINGS_URL, api_key or settings.openrouter_api_key, model, settings.embedding_timeout_seconds, dimensions=_STORAGE_EMBEDDING_DIMENSIONS, extra_headers={"HTTP-Referer": settings.openrouter_site_url, "X-Title": settings.openrouter_app_name})(texts)
    if provider == "dashscope":
        from app.services.llm.dashscope_provider import call_dashscope_embedding
        response = call_dashscope_embedding(api_key=api_key or settings.effective_qwen_api_key, model=model, input=texts, dimensions=_STORAGE_EMBEDDING_DIMENSIONS, timeout=settings.embedding_timeout_seconds)
        items = response.get("data") if isinstance(response, dict) else None
        vectors = [item.get("embedding") for item in items or [] if isinstance(item, dict)]
        return [[float(value) for value in vector] for vector in vectors]
    if provider == "local":
        vectors = _local_embeddings(texts)
        # Pad local vectors (384 dims) to storage dimensions (1024 dims)
        padded = []
        for vector in vectors:
            if len(vector) < _STORAGE_EMBEDDING_DIMENSIONS:
                padded.append(vector + [0.0] * (_STORAGE_EMBEDDING_DIMENSIONS - len(vector)))
            else:
                padded.append(vector[:_STORAGE_EMBEDDING_DIMENSIONS])
        return padded
    raise EmbeddingUnavailableError(f"Embedding provider is not implemented: {provider}")


def _validate_vectors(vectors: list[list[float]], expected_count: int, expected_dimensions: int) -> None:
    if len(vectors) != expected_count or not all(len(vector) == expected_dimensions for vector in vectors):
        raise EmbeddingUnavailableError(f"Embedding vector shape mismatch; expected {expected_count}x{expected_dimensions}.")


def _classify_embedding_error(exc: Exception) -> str:
    message = str(exc).lower()
    if any(token in message for token in ("429", "rate limit", "quota", "allocationquota")):
        return "quota"
    if any(token in message for token in ("401", "403", "api key", "authentication", "unauthorized")):
        return "authentication"
    if any(token in message for token in ("timeout", "network", "urlopen")):
        return "network"
    if any(token in message for token in ("shape", "invalid", "unsupported")):
        return "invalid_request"
    return "provider_error"


def _record_model_metric(provider: str, model: str, outcome: str, level: int) -> None:
    key = f"{provider}:{model}"
    with _metrics_lock:
        metric = _model_metrics.setdefault(key, {"attempts": 0, "successes": 0, "failures": 0, "fallbackSuccesses": 0})
        metric["attempts"] += 1
        metric["successes" if outcome == "success" else "failures"] += 1
        if outcome == "success" and level > 0:
            metric["fallbackSuccesses"] += 1


def _load_sentence_transformer_model():
    """Lazy-load a sentence-transformers model, raising EmbeddingUnavailableError
    if the library or model weights are unavailable."""
    import importlib

    if importlib.util.find_spec("sentence_transformers") is None:
        raise EmbeddingUnavailableError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        )
    if _st_model is None:
        _init_st_model()
    if _st_model is None:
        raise EmbeddingUnavailableError("sentence-transformers model failed to initialise.")


_LOCAL_ST_MODEL_DEFAULT = "all-MiniLM-L6-v2"

try:
    _st_model = None
    _st_model_name: str = ""
    _st_model_load_error: str | None = None

    def _init_st_model() -> None:
        global _st_model, _st_model_name, _st_model_load_error
        if _st_model_load_error is not None:
            raise EmbeddingUnavailableError(_st_model_load_error)
        from sentence_transformers import SentenceTransformer

        model_name = _LOCAL_ST_MODEL_DEFAULT
        try:
            # A mounted request must never turn an optional local fallback into
            # an implicit Hugging Face download. Operators may pre-provision
            # weights, but missing weights fail immediately and retrieval
            # degrades truthfully to its non-vector path.
            _st_model = SentenceTransformer(
                model_name,
                local_files_only=True,
                trust_remote_code=False,
            )
            _st_model_name = model_name
            logger.info("Local embedding model '%s' loaded (%d dimensions).", model_name, _st_model.get_sentence_embedding_dimension())
        except Exception as exc:
            _st_model_load_error = f"Local sentence-transformers model '{model_name}' is not provisioned."
            raise EmbeddingUnavailableError(_st_model_load_error) from exc

except ImportError:
    _st_model = None
    _st_model_name = ""
    _st_model_load_error = "sentence-transformers is not installed."

    def _init_st_model() -> None:
        raise EmbeddingUnavailableError("sentence-transformers is not installed.")


def _local_embeddings(texts: list[str]) -> list[list[float]]:
    if _st_model is None:
        try:
            _init_st_model()
        except EmbeddingUnavailableError:
            # second attempt: maybe import failed on first import
            if _st_model is None:
                _load_sentence_transformer_model()
                if _st_model is None:
                    _init_st_model()
    if _st_model is None:
        raise EmbeddingUnavailableError("Local embedding model is not available. Check installation and model name.")
    try:
        embeddings = _st_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [[float(v) for v in row] for row in embeddings]
    except Exception as exc:
        raise EmbeddingUnavailableError(f"Local embedding inference failed: {exc}") from exc


def _request_embeddings(
    url: str,
    api_key: str,
    model: str,
    timeout: int,
    *,
    dimensions: int | None = None,
    extra_headers: dict[str, str] | None = None,
):
    def runner(texts: list[str]) -> list[list[float]]:
        payload_data: dict = {"input": texts, "model": model}
        if dimensions is not None:
            payload_data["dimensions"] = dimensions
        payload = json.dumps(payload_data).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for key, value in (extra_headers or {}).items():
            if value:
                headers[key] = value
        req = request.Request(
            url=url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except url_error.HTTPError as exc:
            exc.read()
            raise EmbeddingUnavailableError(f"Embedding request failed with status {exc.code}") from exc
        except url_error.URLError as exc:
            raise EmbeddingUnavailableError("Embedding request failed due to a network error.") from exc

        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise EmbeddingUnavailableError("Embedding response did not include a data list.")
        vectors = [item.get("embedding") for item in items if isinstance(item, dict)]
        if len(vectors) != len(texts) or not all(isinstance(vector, list) for vector in vectors):
            raise EmbeddingUnavailableError("Embedding response shape was invalid.")
        return [[float(value) for value in vector] for vector in vectors]

    return runner
