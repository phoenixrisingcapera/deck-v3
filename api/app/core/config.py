import base64
import binascii
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, PrivateAttr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.openai_full_html_policy import FULL_HTML_OPENAI_MODEL
from app.core.instant_deck_request_policy import MAX_PROVIDER_REQUEST_STARTS
from app.core.railway_env import PLACEHOLDER_PHRASES, PLACEHOLDER_PREFIXES, apply_railway_env_aliases
from app.core.worker_startup_policy import (
    INSTANT_DECK_PIPELINE_JOB_TYPES,
    OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS,
    PROVIDER_CAPABLE_WORKER_KINDS,
    PROVIDER_CREDENTIAL_ENV_NAMES,
    PROVIDER_FREE_WORKER_KINDS,
    SOURCE_PIPELINE_JOB_TYPES,
    resolve_worker_identity,
)


SETTINGS_ENV_FILE = str(Path(__file__).resolve().parents[2] / ".env")


def _runtime_settings_env_file() -> str | None:
    """Load the repository dotenv only for local, non-production runtime."""

    app_env = str(os.getenv("APP_ENV") or "").strip().lower()
    app_role = str(os.getenv("APP_ROLE") or "").strip().lower().replace("_", "-")
    railway_env = str(os.getenv("RAILWAY_ENVIRONMENT") or "").strip().lower()
    # The cookieless renderer and preview-render worker have deliberately
    # narrow secret boundaries. A repository dotenv would silently import
    # product/provider credentials even when their explicit environments are
    # correctly scoped.
    if app_role in {"instant-html-renderer", "worker-preview-render"} or app_env == "production" or railway_env == "production":
        return None
    return SETTINGS_ENV_FILE


apply_railway_env_aliases()


DEFAULT_AUTH_SECRET = "change-me"
DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/deck_aistack_codes"
DEFAULT_AI_DATABASE_URL = ""
INSTANT_HTML_WHOLE_DECK_DEFAULT_BYTES = 800_000
# Render documents cross the child boundary as base64, whose fixed 4/3
# expansion leaves deterministic shell/envelope headroom at this ceiling below
# both the independent 1,000,000-byte document limit and 1,100,000-byte IPC
# limit. The production default matches the renderer-feasible ceiling so larger
# real decks are not rejected by an otherwise stale byte budget.
INSTANT_HTML_WHOLE_DECK_MAX_BYTES = 800_000
INSTANT_HTML_LEGACY_MAX_OUTPUT_BYTES = 1_000_000
DATABASE_URL_ENV_CANDIDATES = (
    "DATABASE_URL",
    "DATABASE_PRIVATE_URL",
    "DATABASE_PUBLIC_URL",
    "POSTGRES_URL",
    "POSTGRES_PRIVATE_URL",
    "POSTGRES_PUBLIC_URL",
    "RAILWAY_DATABASE_URL",
)

PROVIDER_CAPABLE_JOB_TYPES = set(PROVIDER_CAPABLE_WORKER_KINDS)
OPTIONAL_SOURCE_PROVIDER_JOB_TYPES = set(OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS)
PROVIDER_CONFIGURATION_ENV_NAMES = set(PROVIDER_CREDENTIAL_ENV_NAMES)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _is_valid_fernet_key(value: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
    except (binascii.Error, ValueError):
        return False
    return len(decoded) == 32


def is_valid_fernet_key(value: str) -> bool:
    """Public presence/shape check for readiness code; never returns key material."""

    return _is_valid_fernet_key(value)


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    return (
        stripped.startswith("<")
        and stripped.endswith(">")
    ) or stripped.upper().startswith(PLACEHOLDER_PREFIXES) or any(phrase in lowered for phrase in PLACEHOLDER_PHRASES)


def is_placeholder(value: str) -> bool:
    """Public placeholder check for sanitized startup/readiness validation."""

    return _is_placeholder(value)


def _with_postgres_sslmode(url: str) -> str:
    if not url.startswith(("postgresql+psycopg://", "postgresql://", "postgres://")):
        return url
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "sslmode" for key, _value in query_items):
        return url
    query_items.append(("sslmode", "require"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _normalize_database_url_scheme(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _is_parseable_database_url(value: str) -> bool:
    if _is_placeholder(value):
        return False
    candidate = _normalize_database_url_scheme(value.strip())
    if candidate.startswith("sqlite"):
        return True
    if not candidate.startswith(("postgresql+psycopg://", "postgresql://", "postgres://")):
        return False
    parsed = urlsplit(candidate)
    return bool(parsed.scheme and parsed.netloc)


def _resolve_database_url(value: str) -> str:
    """Resolve Railway database aliases and avoid deploying literal placeholders.

    Railway can expose both `DATABASE_URL` and `DATABASE_PUBLIC_URL` / `DATABASE_PRIVATE_URL`.
    During manual configuration it is easy to leave `DATABASE_URL` as a literal
    placeholder such as `<real Railway Postgres URL>`. Alembic then crashes with a
    low-level SQLAlchemy parse error. Resolve a valid Railway URL here before
    settings reach Alembic or the runtime engine.
    """

    candidates: list[tuple[str, str]] = [("DATABASE_URL", value)]
    for env_name in DATABASE_URL_ENV_CANDIDATES:
        env_value = os.getenv(env_name, "")
        if env_value:
            candidates.append((env_name, env_value))

    seen: set[str] = set()
    for _name, candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if _is_parseable_database_url(candidate):
            return _normalize_database_url_scheme(candidate)

    return value


def _env_truthy(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    _startup_validation_errors: list[str] = PrivateAttr(default_factory=list)

    app_name: str = "Deck AI Stack API"
    app_env: str = "development"
    port: int = 8080
    cors_origin: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("cors_origin", "CORS_ORIGIN", "FRONTEND_URL"),
    )
    allowed_origins: str = Field(
        default="",
        validation_alias=AliasChoices("allowed_origins", "ALLOWED_ORIGINS", "CORS_ALLOWED_ORIGINS"),
    )
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices(*DATABASE_URL_ENV_CANDIDATES, "database_url"),
    )
    # AI database with pgvector for vector chunks, telemetry, and AI-support data.
    # When set, AI-specific tables (vector_chunks, agent_telemetry_events, etc.)
    # are stored in this database instead of the core database.
    ai_database_url: str = Field(
        default=DEFAULT_AI_DATABASE_URL,
        validation_alias=AliasChoices("AI_DATABASE_URL", "ai_database_url"),
    )
    training_export_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("TRAINING_EXPORT_ENABLED", "training_export_enabled"),
    )
    training_export_batch_size: int = Field(
        default=50,
        validation_alias=AliasChoices("TRAINING_EXPORT_BATCH_SIZE", "training_export_batch_size"),
    )
    admin_export_handoff_dir: str = Field(
        default=str(Path(__file__).resolve().parents[3] / "deck.admins-main" / "export-release-queue"),
        validation_alias=AliasChoices("ADMIN_EXPORT_HANDOFF_DIR", "admin_export_handoff_dir"),
    )
    auth_secret_key: str = Field(
        default=DEFAULT_AUTH_SECRET,
        validation_alias=AliasChoices("BACKEND_JWT_SIGNING_SECRET", "AUTH_SECRET_KEY", "auth_secret_key"),
    )
    auth_secret_key_id: str = Field(
        default="local-dev",
        validation_alias=AliasChoices("BACKEND_JWT_SIGNING_KEY_ID", "AUTH_SECRET_KEY_ID", "auth_secret_key_id"),
    )
    frontend_session_cookie_secret: str = Field(
        default="",
        validation_alias=AliasChoices("FRONTEND_SESSION_COOKIE_SECRET", "frontend_session_cookie_secret"),
    )
    workspace_ai_fernet_key: str = Field(
        default="",
        validation_alias=AliasChoices("WORKSPACE_AI_FERNET_KEY", "workspace_ai_fernet_key"),
    )
    workspace_ai_fernet_key_version: str = Field(
        default="local-dev",
        validation_alias=AliasChoices("WORKSPACE_AI_FERNET_KEY_VERSION", "workspace_ai_fernet_key_version"),
    )
    auth_token_expiry_minutes: int = 60
    auth_token_issuer: str = "deck-aistack-codes-api"
    auth_token_audience: str = "deck-aistack-codes-web"
    public_signup_enabled: bool = False
    user_admin_bootstrap_token: str = ""
    # OpenAI is the default production text-generation provider. Railway must
    # supply OPENAI_API_KEY to the API and every worker that performs LLM work.
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("openai_api_key", "OPENAI_API_KEY", "OPENAI_API"),
    )
    openai_model: str = Field(
        default="gpt-5-2025-08-07",
        validation_alias=AliasChoices("openai_model", "OPENAI_MODEL"),
    )
    openai_vision_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices("openai_vision_model", "OPENAI_VISION_MODEL"),
    )
    openai_timeout_seconds: int = 120
    openai_render_max_output_tokens: int = Field(
        default=8000,
        ge=16,
        le=16000,
        validation_alias=AliasChoices(
            "openai_render_max_output_tokens",
            "OPENAI_RENDER_MAX_OUTPUT_TOKENS",
        ),
    )
    openai_render_min_interval_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=120.0,
        validation_alias=AliasChoices(
            "openai_render_min_interval_seconds",
            "OPENAI_RENDER_MIN_INTERVAL_SECONDS",
        ),
    )
    # DISABLED FOR NOW: OpenRouter is not part of the active production provider set.
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o"
    openrouter_timeout_seconds: int = 60
    openrouter_site_url: str = ""
    openrouter_app_name: str = "Deck AI Stack"
    # DISABLED FOR NOW: Anthropic / Claude is not part of the active production provider set.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 4096
    anthropic_timeout_seconds: int = 60
    anthropic_max_retries: int = 1
    anthropic_retry_delay_seconds: float = 0.25
    embedding_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("embedding_provider", "EMBEDDING_PROVIDER"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("embedding_model", "EMBEDDING_MODEL"),
    )
    embedding_dimensions: int = Field(
        default=1024,
        validation_alias=AliasChoices("embedding_dimensions", "EMBEDDING_DIMENSIONS"),
    )
    embedding_timeout_seconds: int = Field(
        default=45,
        validation_alias=AliasChoices("embedding_timeout_seconds", "EMBEDDING_TIMEOUT_SECONDS"),
    )
    embedding_fallback_models: str = Field(
        default="text-embedding-v4",
        validation_alias=AliasChoices("embedding_fallback_models", "EMBEDDING_FALLBACK_MODELS"),
    )
    # Qwen (Alibaba DashScope) remains an explicitly selectable provider and
    # retains the existing vision/OCR contracts; it is not the text default.
    qwen_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("qwen_api_key", "QWEN_API_KEY", "DASHSCOPE_API_KEY"),
    )
    qwen_model: str = Field(
        default="qwen3.7-plus",
        validation_alias=AliasChoices("qwen_model", "QWEN_MODEL", "DASHSCOPE_MODEL"),
    )
    qwen_max_tokens: int = 8192
    qwen_timeout_seconds: int = 90
    dashscope_base_url: str = Field(
        default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("dashscope_base_url", "DASHSCOPE_BASE_URL"),
    )
    # Legacy aliases — map old env vars to qwen_ fields
    dashscope_api_key: str = Field(default="", validation_alias=AliasChoices("DASHSCOPE_API_KEY"))
    dashscope_model: str = Field(default="", validation_alias=AliasChoices("DASHSCOPE_MODEL"))
    dashscope_max_tokens: int = Field(default=0, validation_alias=AliasChoices("DASHSCOPE_MAX_TOKENS"))
    dashscope_timeout_seconds: int = Field(default=0, validation_alias=AliasChoices("DASHSCOPE_TIMEOUT_SECONDS"))
    # Qwen strategy — separate model routing for generation/critique/repair/embedding/vision
    deck_llm_strategy: str = Field(
        default="qwen_native",
        validation_alias=AliasChoices("deck_llm_strategy", "DECK_LLM_STRATEGY"),
    )
    deck_llm_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("deck_llm_provider", "DECK_LLM_PROVIDER"),
    )
    # Qwen-specific critique and repair defaults are retained for explicitly
    # selected Qwen workflows; OpenAI generation does not consume these values.
    qwen_critique_model: str = Field(
        default="qwen-plus",
        validation_alias=AliasChoices("qwen_critique_model", "QWEN_CRITIQUE_MODEL"),
    )
    qwen_repair_model: str = Field(
        default="qwen-turbo",
        validation_alias=AliasChoices("qwen_repair_model", "QWEN_REPAIR_MODEL"),
    )
    qwen_embedding_model: str = Field(
        default="text-embedding-v3",
        validation_alias=AliasChoices("qwen_embedding_model", "QWEN_EMBEDDING_MODEL"),
    )
    qwen_vision_model: str = Field(
        default="qwen-vl-ocr-2025-11-20",
        validation_alias=AliasChoices("qwen_vision_model", "QWEN_VISION_MODEL"),
    )
    deck_preview_parallelism: int = Field(
        default=4,
        ge=1,
        le=16,
        validation_alias=AliasChoices("deck_preview_parallelism", "DECK_PREVIEW_PARALLELISM"),
    )
    qwen_temperature: float = Field(
        default=0.3,
        validation_alias=AliasChoices("qwen_temperature", "QWEN_TEMPERATURE"),
    )
    qwen_max_retries: int = Field(
        default=2,
        validation_alias=AliasChoices("qwen_max_retries", "QWEN_MAX_RETRIES"),
    )
    qwen_max_output_tokens: int = Field(
        default=8192,
        validation_alias=AliasChoices("qwen_max_output_tokens", "QWEN_MAX_OUTPUT_TOKENS"),
    )
    # Optional advanced fallback routing. Leave unset for the current
    # single-provider Qwen deployment.
    qwen_fallback_provider: str = Field(
        default="",
        validation_alias=AliasChoices("qwen_fallback_provider", "QWEN_FALLBACK_PROVIDER"),
    )
    qwen_fallback_model: str = Field(
        default="",
        validation_alias=AliasChoices("qwen_fallback_model", "QWEN_FALLBACK_MODEL"),
    )
    qwen_max_tokens_per_job: int = Field(
        default=1000000,
        validation_alias=AliasChoices("qwen_max_tokens_per_job", "QWEN_MAX_TOKENS_PER_JOB"),
    )
    qwen_max_tokens_per_workspace_day: int = Field(
        default=1000000,
        validation_alias=AliasChoices("qwen_max_tokens_per_workspace_day", "QWEN_MAX_TOKENS_PER_WORKSPACE_DAY"),
    )
    qwen_max_repair_attempts: int = Field(
        default=1,
        validation_alias=AliasChoices("qwen_max_repair_attempts", "QWEN_MAX_REPAIR_ATTEMPTS"),
    )
    dashscope_workspace_id: str = Field(
        default="",
        validation_alias=AliasChoices("dashscope_workspace_id", "DASHSCOPE_WORKSPACE_ID"),
    )
    superadmin_guardrails_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPERADMIN_GUARDRAILS_URL",
            "SUPERADMIN_GUARDRAILS_BASE_URL",
            "AISTACK_GUARDRAILS_URL",
        ),
    )
    superadmin_guardrails_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPERADMIN_GUARDRAILS_API_KEY",
            "SUPERADMIN_GUARDRAILS_KEY",
            "AISTACK_GUARDRAILS_API_KEY",
        ),
    )
    superadmin_guardrails_timeout_seconds: float = Field(
        default=2.5,
        validation_alias=AliasChoices(
            "SUPERADMIN_GUARDRAILS_TIMEOUT_SECONDS",
            "AISTACK_GUARDRAILS_TIMEOUT_SECONDS",
        ),
    )
    superadmin_guardrails_strict_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "SUPERADMIN_GUARDRAILS_STRICT_MODE",
            "AISTACK_GUARDRAILS_STRICT_MODE",
        ),
    )
    superadmin_aistack_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPERADMIN_AISTACK_URL",
            "SUPERADMIN_AISTACK_BASE_URL",
            "AISTACK_SUPERADMIN_URL",
        ),
    )
    superadmin_aistack_timeout_seconds: float = Field(
        default=2.5,
        validation_alias=AliasChoices(
            "SUPERADMIN_AISTACK_TIMEOUT_SECONDS",
            "AISTACK_SUPERADMIN_TIMEOUT_SECONDS",
        ),
    )
    deck_knowledge_index_path: str = ""
    deck_generation_mode: str = Field(
        default="openai",
        validation_alias=AliasChoices(
            "deck_generation_mode",
            "DECK_GENERATION_MODE",
            "DECK_AISTACK_GENERATION_MODE",
        ),
    )
    max_concurrent_slide_generations: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "max_concurrent_slide_generations",
            "MAX_CONCURRENT_SLIDE_GENERATIONS",
        ),
    )
    instant_deck_max_concurrent_slide_generations: int = Field(
        default=2,
        ge=1,
        validation_alias=AliasChoices(
            "instant_deck_max_concurrent_slide_generations",
            "INSTANT_DECK_MAX_CONCURRENT_SLIDE_GENERATIONS",
        ),
    )
    instant_deck_generation_deadline_seconds: int = Field(
        default=600,
        ge=60,
        validation_alias=AliasChoices(
            "instant_deck_generation_deadline_seconds",
            "INSTANT_DECK_GENERATION_DEADLINE_SECONDS",
        ),
    )
    instant_html_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("instant_html_enabled", "INSTANT_HTML_ENABLED"),
    )
    instant_html_legacy_recovery_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "instant_html_legacy_recovery_enabled",
            "INSTANT_HTML_LEGACY_RECOVERY_ENABLED",
        ),
    )
    instant_html_legacy_recovery_ticket_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "instant_html_legacy_recovery_ticket_id",
            "INSTANT_HTML_LEGACY_RECOVERY_TICKET_ID",
        ),
    )
    instant_html_renderer_origin: str = Field(
        default="",
        validation_alias=AliasChoices("instant_html_renderer_origin", "INSTANT_HTML_RENDERER_ORIGIN"),
    )
    instant_html_render_parent_origin: str = Field(
        default="",
        validation_alias=AliasChoices("instant_html_render_parent_origin", "INSTANT_HTML_RENDER_PARENT_ORIGIN"),
    )
    instant_html_storage_allowed_hosts: str = Field(
        default="",
        validation_alias=AliasChoices("instant_html_storage_allowed_hosts", "INSTANT_HTML_STORAGE_ALLOWED_HOSTS"),
    )
    instant_html_capability_ttl_seconds: int = Field(
        default=30,
        ge=5,
        le=30,
        validation_alias=AliasChoices("instant_html_capability_ttl_seconds", "INSTANT_HTML_CAPABILITY_TTL_SECONDS"),
    )
    instant_html_max_provider_starts: int = Field(
        default=MAX_PROVIDER_REQUEST_STARTS,
        ge=MAX_PROVIDER_REQUEST_STARTS,
        le=MAX_PROVIDER_REQUEST_STARTS,
    )
    # Cost limits are optional policy controls. ``None`` means uncapped but
    # fully metered; feature activation is never inferred from a zero budget.
    instant_html_llm_first_beta: bool = False
    # AI-VC pre-generation stages. Each stage is independently bounded and
    # recorded before the designer request is frozen.
    instant_html_vc_research_enabled: bool = True
    instant_html_vc_research_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    instant_html_vc_memo_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    instant_html_vc_research_max_sources: int = Field(default=15, ge=1, le=24)
    instant_html_vc_research_timeout_seconds: int = Field(default=120, ge=15, le=300)
    ai_vc_research_max_searches: int = Field(default=6, ge=1, le=6)
    ai_vc_research_max_tokens: int = Field(default=2200, ge=500, le=8000)
    ai_vc_analysis_max_tokens: int = Field(default=12000, ge=1000, le=16000)
    ai_vc_max_total_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    # One model-authored investment memo may legitimately take several minutes
    # on a large source context. Keep one finite start and no automatic replay,
    # but do not force the source-only fallback at the former 180-second bound.
    ai_vc_max_runtime_seconds: int = Field(default=420, ge=30, le=600)
    ai_vc_max_research_iterations: int = Field(default=2, ge=1, le=2)
    ai_vc_max_additional_reasoning_calls: int = Field(default=3, ge=0, le=3)
    ai_vc_visual_planning_enabled: bool = False
    ai_vc_visual_planning_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ai_vc_image_generation_enabled: bool = False
    ai_vc_image_generation_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ai_vc_vision_review_enabled: bool = False
    ai_vc_vision_review_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ai_vc_visual_repair_enabled: bool = False
    ai_vc_visual_repair_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ai_vc_max_visual_repair_passes: int = Field(default=1, ge=0, le=2)
    instant_html_factual_review_enabled: bool = True
    instant_html_factual_review_max_cost_cents: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    instant_html_max_operation_cost_cents: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    instant_html_max_output_tokens: int = Field(default=128000, ge=8000, le=128000)
    instant_html_whole_deck_max_bytes: int = Field(
        default=INSTANT_HTML_WHOLE_DECK_DEFAULT_BYTES,
        ge=64_000,
        le=INSTANT_HTML_WHOLE_DECK_MAX_BYTES,
        validation_alias=AliasChoices(
            "instant_html_whole_deck_max_bytes",
            "INSTANT_HTML_WHOLE_DECK_MAX_BYTES",
        ),
    )
    instant_html_legacy_max_output_bytes: int | None = Field(
        default=None,
        ge=64_000,
        le=INSTANT_HTML_LEGACY_MAX_OUTPUT_BYTES,
        exclude=True,
        repr=False,
        validation_alias=AliasChoices(
            # Deployment compatibility only. This legacy name is normalized
            # into the canonical safe whole-deck ceiling below.
            "instant_html_max_output_bytes",
            "INSTANT_HTML_MAX_OUTPUT_BYTES",
        ),
    )
    # A 14-25 source whole-deck HTML response can legitimately take longer
    # than ten minutes on the pinned GPT-5 snapshot. Keep the provider call
    # inside the durable worker lease, but do not cut off an otherwise healthy
    # single request at the former 600-second boundary.
    instant_html_max_wall_seconds: int = Field(default=1200, ge=60, le=1800)
    instant_html_openai_timeout_seconds: int = Field(
        default=1200,
        ge=60,
        le=1800,
        validation_alias=AliasChoices(
            "instant_html_openai_timeout_seconds", "INSTANT_HTML_OPENAI_TIMEOUT_SECONDS"
        ),
    )
    instant_html_render_fernet_key: str = Field(
        default="",
        validation_alias=AliasChoices("INSTANT_HTML_RENDER_FERNET_KEY", "instant_html_render_fernet_key"),
    )
    instant_html_render_key_version: str = Field(
        default="",
        validation_alias=AliasChoices("INSTANT_HTML_RENDER_KEY_VERSION", "instant_html_render_key_version"),
    )
    max_selected_slides_per_batch: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "max_selected_slides_per_batch",
            "MAX_SELECTED_SLIDES_PER_BATCH",
        ),
    )
    allow_partial_batch_success: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "allow_partial_batch_success",
            "ALLOW_PARTIAL_BATCH_SUCCESS",
        ),
    )
    max_repair_attempts_per_slide: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "max_repair_attempts_per_slide",
            "MAX_REPAIR_ATTEMPTS_PER_SLIDE",
        ),
    )
    upload_storage_backend: str = Field(
        default="local",
        validation_alias=AliasChoices("upload_storage_backend", "UPLOAD_STORAGE_BACKEND", "DECK_AISTACK_STORAGE_PROVIDER"),
    )
    uploads_root: str = "/tmp/deck_aistack_codes_uploads"
    upload_storage_s3_bucket: str = Field(
        default="",
        validation_alias=AliasChoices(
            "upload_storage_s3_bucket",
            "S3_BUCKET_NAME",
            "AWS_S3_BUCKET_NAME",
            "UPLOAD_STORAGE_S3_BUCKET",
            "RAILWAY_BUCKET_NAME",
        ),
    )
    upload_storage_s3_prefix: str = "deck-aistack-codes/uploads"
    upload_storage_s3_provider: str = Field(
        default="aws",
        validation_alias=AliasChoices(
            "upload_storage_s3_provider",
            "UPLOAD_STORAGE_S3_PROVIDER",
            "STORAGE_S3_PROVIDER",
        ),
    )
    upload_storage_s3_region: str = Field(
        default="",
        validation_alias=AliasChoices(
            "upload_storage_s3_region",
            "AWS_DEFAULT_REGION",
            "UPLOAD_STORAGE_S3_REGION",
            "RAILWAY_BUCKET_REGION",
        ),
    )
    upload_storage_s3_endpoint_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "upload_storage_s3_endpoint_url",
            "AWS_ENDPOINT_URL",
            "UPLOAD_STORAGE_S3_ENDPOINT",
            "RAILWAY_BUCKET_ENDPOINT",
        ),
    )
    deck_aistack_bucket_public: bool = False
    deck_aistack_signed_url_ttl_seconds: int = 900
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = ""
    railway_bucket_access_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AWS_ACCESS_KEY_ID",
            "UPLOAD_STORAGE_S3_ACCESS_KEY",
            "RAILWAY_BUCKET_ACCESS_KEY",
        ),
    )
    railway_bucket_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AWS_SECRET_ACCESS_KEY",
            "UPLOAD_STORAGE_S3_SECRET_KEY",
            "RAILWAY_BUCKET_SECRET_KEY",
        ),
    )
    aws_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "aws_access_key_id",
            "AWS_ACCESS_KEY_ID",
            "UPLOAD_STORAGE_S3_ACCESS_KEY",
            "RAILWAY_BUCKET_ACCESS_KEY",
        ),
    )
    aws_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "aws_secret_access_key",
            "AWS_SECRET_ACCESS_KEY",
            "UPLOAD_STORAGE_S3_SECRET_KEY",
            "RAILWAY_BUCKET_SECRET_KEY",
        ),
    )
    max_request_body_size_bytes: int = 210 * 1024 * 1024
    upload_security_scan_command: str = ""
    upload_security_scan_timeout_seconds: int = 30
    turnstile_secret_key: str = ""
    turnstile_verify_timeout_seconds: int = 5
    # Temporary test-access allowance: keep the quota accounting and audit
    # trail enabled while allowing a user to exercise the full AI workflow.
    ai_daily_generation_quota: int = 1_000_000
    app_role: str = Field(
        default="api",
        validation_alias=AliasChoices("app_role", "APP_ROLE"),
    )
    railway_environment: str = ""
    otel_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("otel_enabled", "OTEL_ENABLED"),
    )
    otel_service_name: str = Field(
        default="deck-aistack-backend",
        validation_alias=AliasChoices("otel_service_name", "OTEL_SERVICE_NAME"),
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("otel_exporter_otlp_endpoint", "OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    otel_exporter_otlp_headers: str = Field(
        default="",
        validation_alias=AliasChoices("otel_exporter_otlp_headers", "OTEL_EXPORTER_OTLP_HEADERS"),
    )
    otel_sample_rate: float = Field(
        default=1.0,
        validation_alias=AliasChoices("otel_sample_rate", "OTEL_SAMPLE_RATE"),
    )

    @field_validator("database_url")
    @classmethod
    def normalize_db_scheme(cls, v: str) -> str:
        return _resolve_database_url(v)

    @field_validator("ai_database_url")
    @classmethod
    def normalize_ai_db_scheme(cls, v: str) -> str:
        if not v:
            return v
        normalized = _normalize_database_url_scheme(v)
        return _with_postgres_sslmode(normalized)

    @field_validator("instant_html_renderer_origin")
    @classmethod
    def validate_renderer_origin_shape(cls, value: str, info: ValidationInfo) -> str:
        from app.core.instant_html_renderer_security import validate_origin

        return validate_origin(
            value,
            variable_name="INSTANT_HTML_RENDERER_ORIGIN",
            allow_http_loopback=str(info.data.get("app_env") or "").strip().lower() != "production",
        )

    @field_validator("instant_html_render_parent_origin")
    @classmethod
    def validate_render_parent_origin_shape(cls, value: str, info: ValidationInfo) -> str:
        from app.core.instant_html_renderer_security import validate_origin

        return validate_origin(
            value,
            variable_name="INSTANT_HTML_RENDER_PARENT_ORIGIN",
            allow_http_loopback=str(info.data.get("app_env") or "").strip().lower() != "production",
        )

    @field_validator("upload_storage_s3_provider")
    @classmethod
    def normalize_upload_storage_s3_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("upload_storage_s3_endpoint_url")
    @classmethod
    def validate_upload_storage_s3_endpoint(cls, value: str, info: ValidationInfo) -> str:
        endpoint = value.strip()
        if not endpoint:
            return ""
        backend = str(info.data.get("upload_storage_backend") or "").strip().lower()
        if backend != "s3":
            return endpoint
        provider = str(info.data.get("upload_storage_s3_provider") or "").strip().lower()
        if provider == "aws":
            raise ValueError("AWS S3 provider must not set a custom endpoint; use provider=compatible")
        if provider != "compatible":
            return endpoint

        from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

        return validate_renderer_storage_endpoint(
            endpoint,
            backend="s3",
            allowed_hosts=str(info.data.get("instant_html_storage_allowed_hosts") or ""),
            variable_name="UPLOAD_STORAGE_S3_ENDPOINT",
        )

    @model_validator(mode="before")
    @classmethod
    def _prefer_explicit_database_url(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        if "database_url" in values:
            for candidate in DATABASE_URL_ENV_CANDIDATES:
                if candidate != "database_url":
                    values.pop(candidate, None)
        provider_names = (
            "upload_storage_s3_provider",
            "UPLOAD_STORAGE_S3_PROVIDER",
            "STORAGE_S3_PROVIDER",
        )
        endpoint_names = (
            "upload_storage_s3_endpoint_url",
            "AWS_ENDPOINT_URL",
            "UPLOAD_STORAGE_S3_ENDPOINT",
            "RAILWAY_BUCKET_ENDPOINT",
        )
        provider_was_supplied = any(name in values for name in provider_names)
        endpoint = next((values[name] for name in endpoint_names if name in values), "")
        backend = str(
            values.get("upload_storage_backend")
            or values.get("UPLOAD_STORAGE_BACKEND")
            or values.get("DECK_AISTACK_STORAGE_PROVIDER")
            or ""
        ).strip().lower()
        if backend == "s3" and not provider_was_supplied and str(endpoint or "").strip():
            values["upload_storage_s3_provider"] = "compatible"
        return values

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production" or self.railway_environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.allowed_origins or self.cors_origin)

    @property
    def superadmin_guardrails_enabled(self) -> bool:
        return bool(self.superadmin_guardrails_url.strip())

    @property
    def superadmin_aistack_enabled(self) -> bool:
        return bool(self.superadmin_aistack_url.strip())

    @property
    def effective_qwen_api_key(self) -> str:
        """Resolve Qwen API key — prefer qwen_api_key, fall back to legacy dashscope_api_key."""
        return self.qwen_api_key or self.dashscope_api_key

    @property
    def effective_qwen_model(self) -> str:
        """Resolve Qwen model — prefer qwen_model, fall back to legacy dashscope_model."""
        return self.qwen_model or self.dashscope_model or "qwen3.7-plus"

    @property
    def effective_qwen_timeout(self) -> int:
        """Resolve Qwen timeout — prefer qwen_timeout_seconds, fall back to legacy."""
        return self.qwen_timeout_seconds or self.dashscope_timeout_seconds or 90

    @property
    def effective_qwen_critique_model(self) -> str:
        return self.qwen_critique_model or self.effective_qwen_model

    @property
    def effective_qwen_repair_model(self) -> str:
        return self.qwen_repair_model or self.effective_qwen_model

    @property
    def effective_qwen_strategy(self) -> str:
        return (self.deck_llm_strategy or "qwen_native").strip().lower()

    @property
    def qwen_fallback_enabled(self) -> bool:
        return bool(self.qwen_fallback_provider and self.qwen_fallback_model)

    # --- S3 / object-storage credential consolidation ---
    # Storage credentials can be supplied through Railway-specific aliases
    # (RAILWAY_BUCKET_ACCESS_KEY / RAILWAY_BUCKET_SECRET_KEY) or through
    # standard AWS env vars (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).
    # These properties resolve the effective credential set once, avoiding
    # callers needing to know the alias order.

    @property
    def effective_s3_access_key(self) -> str:
        """Resolve S3 access key — prefer railway_bucket, fall back to aws."""
        return self.railway_bucket_access_key or self.aws_access_key_id

    @property
    def effective_s3_secret_key(self) -> str:
        """Resolve S3 secret key — prefer railway_bucket, fall back to aws."""
        return self.railway_bucket_secret_key or self.aws_secret_access_key

    @property
    def effective_s3_bucket(self) -> str:
        """Canonical S3 bucket name."""
        return self.upload_storage_s3_bucket

    @property
    def effective_s3_region(self) -> str:
        """Canonical S3 region."""
        return self.upload_storage_s3_region

    @property
    def effective_s3_endpoint_url(self) -> str:
        """Canonical S3 endpoint URL."""
        return self.upload_storage_s3_endpoint_url

    def _validate_production_database_url(self, errors: list[str]) -> None:
        if self.database_url == DEFAULT_DATABASE_URL or "localhost" in self.database_url or not _is_parseable_database_url(self.database_url):
            errors.append("DATABASE_URL must point to a valid production database URL or Railway DATABASE_PRIVATE_URL/DATABASE_PUBLIC_URL reference")
        else:
            self.database_url = _with_postgres_sslmode(self.database_url)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        # Backward-compatible normalization for deployments that historically
        # used zero as a feature switch. Activation now has its own boolean;
        # zero means no dollar cap, exactly like an omitted value.
        for field_name in (
            "instant_html_vc_research_max_cost_cents",
            "instant_html_vc_memo_max_cost_cents",
            "ai_vc_max_total_cost_cents",
            "ai_vc_visual_planning_max_cost_cents",
            "ai_vc_image_generation_max_cost_cents",
            "ai_vc_vision_review_max_cost_cents",
            "ai_vc_visual_repair_max_cost_cents",
            "instant_html_factual_review_max_cost_cents",
        ):
            if getattr(self, field_name) == 0:
                setattr(self, field_name, None)
        if (
            self.instant_html_legacy_max_output_bytes is not None
            and "instant_html_whole_deck_max_bytes" not in self.model_fields_set
        ):
            self.instant_html_whole_deck_max_bytes = min(
                self.instant_html_legacy_max_output_bytes,
                INSTANT_HTML_WHOLE_DECK_MAX_BYTES,
            )
        configured_ai_vc_caps = [
            value for value in (
                self.instant_html_vc_research_max_cost_cents,
                self.instant_html_vc_memo_max_cost_cents,
            ) if value is not None
        ]
        if (
            self.ai_vc_max_total_cost_cents is not None
            and sum(configured_ai_vc_caps) > self.ai_vc_max_total_cost_cents
        ):
            raise ValueError("AI-VC research and analysis allowances exceed AI_VC_MAX_TOTAL_COST_CENTS")
        if self.instant_html_llm_first_beta and not self.instant_html_factual_review_enabled:
            raise ValueError("INSTANT_HTML_FACTUAL_REVIEW_ENABLED must remain enabled for the LLM-first beta")
        runtime_role = self.app_role.strip().lower()
        is_instant_html_renderer = runtime_role in {"instant-html-renderer", "instant_html_renderer"}
        if not self.is_production and not is_instant_html_renderer:
            return self

        is_worker = runtime_role == "worker" or runtime_role.startswith("worker-")
        worker_kind = str(os.getenv("WORKER_KIND") or "").strip().lower().replace("-", "_")
        configured_job_types = {
            item.strip().lower().replace("-", "_")
            for item in str(os.getenv("DECK_WORKER_JOB_TYPES") or "").split(",")
            if item.strip()
        }
        identity = resolve_worker_identity({**os.environ, "APP_ROLE": self.app_role})
        role_worker_kind = runtime_role.removeprefix("worker-").replace("-", "_") if runtime_role.startswith("worker-") else ""
        explicit_worker_kind = worker_kind or role_worker_kind
        is_recovery_worker = bool(
            explicit_worker_kind == "stale_job_rescuer"
            or _env_truthy("DECK_WORKER_RECOVERY_ONLY", default=False)
        )
        source_enrichment_enabled = _env_truthy("SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED", default=True)
        provider_capable_worker = bool(
            not is_recovery_worker
            and (
                explicit_worker_kind in PROVIDER_CAPABLE_WORKER_KINDS
                or configured_job_types.intersection(PROVIDER_CAPABLE_JOB_TYPES)
                or (
                    source_enrichment_enabled
                    and (
                        explicit_worker_kind in OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS
                        or configured_job_types.intersection(OPTIONAL_SOURCE_PROVIDER_JOB_TYPES)
                    )
                )
            )
        )
        provider_free_worker = bool(
            is_worker
            and not provider_capable_worker
            and (
                explicit_worker_kind in PROVIDER_FREE_WORKER_KINDS
                or is_recovery_worker
                or bool(configured_job_types)
            )
        )
        is_preview_render_worker = bool(
            runtime_role in {"worker-preview-render", "worker_preview_render"}
            or worker_kind == "preview_render"
            or (configured_job_types == {"preview_render"})
        )
        is_migration = runtime_role in {"migration", "core-migration", "ai-migration"}
        is_ai_migration = runtime_role == "ai-migration"
        is_training_export = runtime_role in {"training-export", "training_export"}
        errors: list[str] = []
        critical_errors: list[str] = []

        def add_critical_error(message: str) -> None:
            errors.append(message)
            critical_errors.append(message)

        if is_worker:
            if identity.health_only:
                add_critical_error("Audit policy is health-only and cannot initialize production worker settings")
            for identity_error in identity.violations:
                add_critical_error(identity_error)

        if worker_kind and role_worker_kind and worker_kind != role_worker_kind:
            add_critical_error("APP_ROLE worker kind conflicts with WORKER_KIND")
        if is_recovery_worker:
            if explicit_worker_kind and explicit_worker_kind != "stale_job_rescuer":
                add_critical_error("Recovery-only worker must use WORKER_KIND=stale_job_rescuer")
            if configured_job_types:
                add_critical_error("Recovery-only worker must not claim DECK_WORKER_JOB_TYPES")
        elif explicit_worker_kind and configured_job_types:
            if explicit_worker_kind in {"source_pipeline", "llm_generation", "instant_deck_pipeline"}:
                if explicit_worker_kind == "source_pipeline" and configured_job_types != set(SOURCE_PIPELINE_JOB_TYPES):
                    add_critical_error("source_pipeline requires the canonical composite DECK_WORKER_JOB_TYPES")
                if explicit_worker_kind == "instant_deck_pipeline" and configured_job_types != set(INSTANT_DECK_PIPELINE_JOB_TYPES):
                    add_critical_error("instant_deck_pipeline requires the canonical composite DECK_WORKER_JOB_TYPES")
            else:
                if explicit_worker_kind in PROVIDER_FREE_WORKER_KINDS and configured_job_types != {explicit_worker_kind}:
                    add_critical_error("Provider-free WORKER_KIND conflicts with DECK_WORKER_JOB_TYPES")
                kind_provider_capable = bool(
                    explicit_worker_kind in PROVIDER_CAPABLE_WORKER_KINDS
                    or (source_enrichment_enabled and explicit_worker_kind in OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS)
                )
                job_provider_capabilities = {
                    bool(
                        job_type in PROVIDER_CAPABLE_JOB_TYPES
                        or (source_enrichment_enabled and job_type in OPTIONAL_SOURCE_PROVIDER_JOB_TYPES)
                    )
                    for job_type in configured_job_types
                }
                if any(capability != kind_provider_capable for capability in job_provider_capabilities):
                    add_critical_error("WORKER_KIND capability conflicts with DECK_WORKER_JOB_TYPES")

        if self.instant_html_enabled:
            if not self.instant_html_renderer_origin:
                errors.append("INSTANT_HTML_RENDERER_ORIGIN is required when Instant HTML is enabled")
            elif self.instant_html_renderer_origin in {origin.rstrip("/") for origin in self.cors_origins}:
                errors.append("INSTANT_HTML_RENDERER_ORIGIN must be a dedicated origin distinct from application origins")
            if not _is_valid_fernet_key(self.instant_html_render_fernet_key):
                errors.append("INSTANT_HTML_RENDER_FERNET_KEY must be a valid dedicated Fernet key")
            if not self.instant_html_render_key_version:
                errors.append("INSTANT_HTML_RENDER_KEY_VERSION is required when Instant HTML is enabled")
            if self.openai_model != FULL_HTML_OPENAI_MODEL:
                errors.append(f"OPENAI_MODEL must be the audited Instant HTML snapshot {FULL_HTML_OPENAI_MODEL}")

        if is_migration:
            if is_ai_migration:
                if not _is_parseable_database_url(self.ai_database_url):
                    errors.append("AI_DATABASE_URL must point to a valid production AI database")
                else:
                    self.ai_database_url = _with_postgres_sslmode(_normalize_database_url_scheme(self.ai_database_url))
            else:
                self._validate_production_database_url(errors)
            if errors:
                raise ValueError("Unsafe production migration settings: " + "; ".join(errors))
            return self

        if is_training_export:
            if self.app_env.lower() != "production":
                errors.append("APP_ENV must be production for production deployments")
            self._validate_production_database_url(errors)
            if self.training_export_batch_size <= 0:
                errors.append("TRAINING_EXPORT_BATCH_SIZE must be greater than zero in production")
            if errors:
                raise ValueError("Unsafe production training export settings: " + "; ".join(errors))
            return self

        if is_instant_html_renderer:
            from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

            if self.app_env.lower() != "production":
                errors.append("APP_ENV must be production for the Instant HTML renderer")
            self._validate_production_database_url(errors)
            if self.ai_database_url:
                errors.append("AI_DATABASE_URL and its aliases are forbidden for the Instant HTML renderer")
            if not self.instant_html_enabled:
                errors.append("INSTANT_HTML_ENABLED must be true for the Instant HTML renderer")
            if not self.instant_html_renderer_origin:
                errors.append("INSTANT_HTML_RENDERER_ORIGIN is required for the Instant HTML renderer")
            elif self.instant_html_renderer_origin in {origin.rstrip("/") for origin in self.cors_origins}:
                errors.append("INSTANT_HTML_RENDERER_ORIGIN must be a dedicated origin distinct from application origins")
            if not self.instant_html_render_parent_origin:
                errors.append("INSTANT_HTML_RENDER_PARENT_ORIGIN is required for the Instant HTML renderer")
            elif self.instant_html_render_parent_origin not in {origin.rstrip("/") for origin in self.cors_origins}:
                errors.append("INSTANT_HTML_RENDER_PARENT_ORIGIN must identify an allowed application parent origin")
            if not self.cors_origins or any(
                urlsplit(origin).scheme != "https" or not urlsplit(origin).hostname
                for origin in self.cors_origins
            ):
                errors.append("CORS_ORIGIN must identify an HTTPS application parent for the Instant HTML renderer")
            if not _is_valid_fernet_key(self.instant_html_render_fernet_key):
                errors.append("INSTANT_HTML_RENDER_FERNET_KEY must be a valid dedicated Fernet key")
            if (
                not self.instant_html_render_key_version
                or self.instant_html_render_key_version == "local-dev"
                or _is_placeholder(self.instant_html_render_key_version)
            ):
                errors.append("INSTANT_HTML_RENDER_KEY_VERSION must identify the active render key")
            if self.upload_storage_backend not in {"s3", "supabase"}:
                errors.append("UPLOAD_STORAGE_BACKEND must be s3 or supabase for the Instant HTML renderer")
            elif self.upload_storage_backend == "s3":
                s3_access_key = self.effective_s3_access_key
                s3_secret_key = self.effective_s3_secret_key
                if not self.upload_storage_s3_bucket or _is_placeholder(self.upload_storage_s3_bucket):
                    errors.append("S3 bucket configuration is required for the Instant HTML renderer")
                if not self.upload_storage_s3_region or _is_placeholder(self.upload_storage_s3_region):
                    errors.append("S3 region configuration is required for the Instant HTML renderer")
                s3_provider = self.upload_storage_s3_provider
                if s3_provider not in {"aws", "compatible"}:
                    errors.append("UPLOAD_STORAGE_S3_PROVIDER must be aws or compatible")
                elif s3_provider == "compatible" and not self.upload_storage_s3_endpoint_url:
                    errors.append("S3 endpoint configuration is required for the Instant HTML renderer")
                elif s3_provider == "compatible":
                    try:
                        self.upload_storage_s3_endpoint_url = validate_renderer_storage_endpoint(
                            self.upload_storage_s3_endpoint_url,
                            backend="s3",
                            allowed_hosts=self.instant_html_storage_allowed_hosts,
                            variable_name="UPLOAD_STORAGE_S3_ENDPOINT",
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
                if not s3_access_key or not s3_secret_key or _is_placeholder(s3_access_key) or _is_placeholder(s3_secret_key):
                    errors.append("S3 credentials are required for the Instant HTML renderer")
            else:
                if not self.supabase_url or not self.supabase_service_role_key or not self.supabase_storage_bucket:
                    errors.append("Supabase storage configuration is required for the Instant HTML renderer")
                elif self.supabase_url:
                    try:
                        self.supabase_url = validate_renderer_storage_endpoint(
                            self.supabase_url,
                            backend="supabase",
                            allowed_hosts=self.instant_html_storage_allowed_hosts,
                            variable_name="SUPABASE_URL",
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
            forbidden_values = {
                "auth": self.auth_secret_key not in {"", DEFAULT_AUTH_SECRET} or self.auth_secret_key_id not in {"", "local-dev"},
                "provider": bool(self.openai_api_key or self.openrouter_api_key or self.anthropic_api_key or self.effective_qwen_api_key),
                "workspace": bool(self.workspace_ai_fernet_key) or self.workspace_ai_fernet_key_version not in {"", "local-dev"},
                "session": bool(self.frontend_session_cookie_secret or self.user_admin_bootstrap_token or self.turnstile_secret_key),
                "admin": bool(self.superadmin_guardrails_api_key),
            }
            present_groups = sorted(name for name, present in forbidden_values.items() if present)
            if present_groups:
                errors.append("Instant HTML renderer must not receive product credential settings: " + ", ".join(present_groups))
            if errors:
                raise ValueError("Unsafe production Instant HTML renderer settings: " + "; ".join(errors))
            return self

        if self.app_env.lower() != "production":
            errors.append("APP_ENV must be production for production deployments")
        self._validate_production_database_url(errors)
        if is_worker and not explicit_worker_kind and not configured_job_types and not is_recovery_worker:
            add_critical_error(
                "Production workers require explicit WORKER_KIND, APP_ROLE=worker-<kind>, "
                "or DECK_WORKER_JOB_TYPES; service-name inference is compatibility-only"
            )
        if is_preview_render_worker:
            if self.ai_database_url:
                errors.append("AI_DATABASE_URL and its aliases are forbidden for the preview-render worker")
        elif is_worker and not _is_parseable_database_url(self.ai_database_url):
            errors.append("AI_DATABASE_URL is required for production workers")
        if not is_worker:
            if self.auth_secret_key == DEFAULT_AUTH_SECRET or len(self.auth_secret_key) < 32 or _is_placeholder(self.auth_secret_key):
                errors.append("BACKEND_JWT_SIGNING_SECRET must be set to a real non-default value at least 32 characters long")
            if not self.auth_secret_key_id or self.auth_secret_key_id == "local-dev" or _is_placeholder(self.auth_secret_key_id):
                errors.append("BACKEND_JWT_SIGNING_KEY_ID must identify the active production signing key")
            if not self.workspace_ai_fernet_key or _is_placeholder(self.workspace_ai_fernet_key):
                errors.append("WORKSPACE_AI_FERNET_KEY is required in production")
            elif not _is_valid_fernet_key(self.workspace_ai_fernet_key):
                errors.append("WORKSPACE_AI_FERNET_KEY must be a valid Fernet key")
            if (
                not self.workspace_ai_fernet_key_version
                or self.workspace_ai_fernet_key_version == "local-dev"
                or _is_placeholder(self.workspace_ai_fernet_key_version)
            ):
                errors.append("WORKSPACE_AI_FERNET_KEY_VERSION must identify the active production key")
            if self.ai_daily_generation_quota <= 0:
                errors.append("AI_DAILY_GENERATION_QUOTA must be greater than zero in production")
            if self.deck_generation_mode.strip().lower() == "mock":
                errors.append("DECK_GENERATION_MODE=mock is only allowed in local testing")
            if self.embedding_provider.strip().lower() not in {"dashscope", "openai", "auto", "local"}:
                errors.append("EMBEDDING_PROVIDER must be dashscope, openai, auto, or local for the current production deployment")
            if self.embedding_dimensions <= 0:
                errors.append("EMBEDDING_DIMENSIONS must be greater than zero")
            if self.embedding_dimensions != 1024:
                errors.append("EMBEDDING_DIMENSIONS must be 1024 for the pgvector-backed embedding store")
            if self.openai_timeout_seconds <= 0 or self.openai_timeout_seconds > 120:
                errors.append("OPENAI_TIMEOUT_SECONDS must be between 1 and 120 in production")
            if self.instant_html_openai_timeout_seconds < 60 or self.instant_html_openai_timeout_seconds > 1800:
                errors.append("INSTANT_HTML_OPENAI_TIMEOUT_SECONDS must be between 60 and 1800 in production")
            if self.openrouter_timeout_seconds <= 0 or self.openrouter_timeout_seconds > 120:
                errors.append("OPENROUTER_TIMEOUT_SECONDS must be between 1 and 120 in production")
            if self.anthropic_timeout_seconds <= 0 or self.anthropic_timeout_seconds > 120:
                errors.append("ANTHROPIC_TIMEOUT_SECONDS must be between 1 and 120 in production")
            if self.effective_qwen_timeout <= 0 or self.effective_qwen_timeout > 120:
                errors.append("QWEN_TIMEOUT_SECONDS must be between 1 and 120 in production")
            if self.anthropic_max_retries < 0 or self.anthropic_max_retries > 3:
                errors.append("ANTHROPIC_MAX_RETRIES must be between 0 and 3 in production")
            if self.anthropic_retry_delay_seconds < 0 or self.anthropic_retry_delay_seconds > 10:
                errors.append("ANTHROPIC_RETRY_DELAY_SECONDS must be between 0 and 10")
            if self.turnstile_verify_timeout_seconds <= 0 or self.turnstile_verify_timeout_seconds > 15:
                errors.append("TURNSTILE_VERIFY_TIMEOUT_SECONDS must be between 1 and 15 in production")
            if self.max_request_body_size_bytes <= 0:
                errors.append("MAX_REQUEST_BODY_SIZE_BYTES must be greater than zero in production")
            if self.app_role == "api" and self.upload_storage_backend == "local" and "upload_storage_backend" in self.__pydantic_fields_set__:
                errors.append("UPLOAD_STORAGE_BACKEND=local is not allowed in production")
            if not self.upload_security_scan_command or _is_placeholder(self.upload_security_scan_command):
                errors.append("upload_security_scan_command is required in production")
            if self.upload_storage_backend == "local":
                if not self.uploads_root.startswith("/"):
                    errors.append("uploads_root must be an absolute path in production")
                if self.uploads_root.startswith("/tmp"):
                    errors.append("uploads_root must not use /tmp in production")
            for origin in self.cors_origins:
                lowered = origin.lower().strip()
                if lowered == "*" or "localhost" in lowered:
                    errors.append("CORS settings must not use wildcard or localhost origins in production")
                    break
            if self.otel_enabled and not self.otel_service_name:
                errors.append("OTEL_SERVICE_NAME is required when OTEL_ENABLED=true")
            if self.otel_sample_rate < 0 or self.otel_sample_rate > 1:
                errors.append("OTEL_SAMPLE_RATE must be between 0 and 1")

        if provider_free_worker:
            environment_names = {str(name).upper() for name in os.environ}
            present_provider_names = sorted(PROVIDER_CONFIGURATION_ENV_NAMES & environment_names)
            provider_secrets_present = bool(
                self.openai_api_key
                or self.openrouter_api_key
                or self.anthropic_api_key
                or self.effective_qwen_api_key
                or self.workspace_ai_fernet_key
                or self.workspace_ai_fernet_key_version not in {"", "local-dev"}
            )
            if present_provider_names or provider_secrets_present:
                names = ", ".join(present_provider_names) if present_provider_names else "provider credential fields"
                add_critical_error(f"Provider-free worker must not receive provider configuration: {names}")

        if is_recovery_worker:
            if self.upload_storage_backend not in {"s3", "supabase"}:
                add_critical_error("Stale recovery requires UPLOAD_STORAGE_BACKEND=s3 or supabase for cleanup and purge")
            elif self.upload_storage_backend == "s3":
                recovery_s3_access_key = self.effective_s3_access_key
                recovery_s3_secret_key = self.effective_s3_secret_key
                if not self.upload_storage_s3_bucket or _is_placeholder(self.upload_storage_s3_bucket):
                    add_critical_error("Stale recovery requires an S3 bucket")
                if not self.upload_storage_s3_region or _is_placeholder(self.upload_storage_s3_region):
                    add_critical_error("Stale recovery requires an S3 region")
                if not recovery_s3_access_key or _is_placeholder(recovery_s3_access_key):
                    add_critical_error("Stale recovery requires an S3 access key")
                if not recovery_s3_secret_key or _is_placeholder(recovery_s3_secret_key):
                    add_critical_error("Stale recovery requires an S3 secret key")
                s3_provider = self.upload_storage_s3_provider.strip().lower()
                if s3_provider not in {"aws", "compatible"}:
                    add_critical_error("UPLOAD_STORAGE_S3_PROVIDER must be aws or compatible")
                recovery_endpoint = self.upload_storage_s3_endpoint_url.strip()
                if s3_provider == "compatible":
                    try:
                        from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

                        self.upload_storage_s3_endpoint_url = validate_renderer_storage_endpoint(
                            recovery_endpoint,
                            backend="s3",
                            allowed_hosts=self.instant_html_storage_allowed_hosts,
                            variable_name="UPLOAD_STORAGE_S3_ENDPOINT",
                        )
                        if not self.upload_storage_s3_endpoint_url or _is_placeholder(recovery_endpoint):
                            raise ValueError("UPLOAD_STORAGE_S3_ENDPOINT is missing or placeholder")
                    except ValueError:
                        add_critical_error("S3-compatible stale recovery requires a canonical allowed HTTPS endpoint")
                elif recovery_endpoint:
                    add_critical_error("AWS stale recovery must not set a custom S3 endpoint; use provider=compatible")
            elif self.upload_storage_backend == "supabase" and (
                not self.supabase_url
                or _is_placeholder(self.supabase_url)
                or not self.supabase_service_role_key
                or _is_placeholder(self.supabase_service_role_key)
                or not self.supabase_storage_bucket
                or _is_placeholder(self.supabase_storage_bucket)
            ):
                add_critical_error("Stale recovery requires complete Supabase storage configuration")
            elif self.upload_storage_backend == "supabase":
                try:
                    from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

                    self.supabase_url = validate_renderer_storage_endpoint(
                        self.supabase_url,
                        backend="supabase",
                        allowed_hosts=self.instant_html_storage_allowed_hosts,
                        variable_name="SUPABASE_URL",
                    )
                except ValueError:
                    add_critical_error("Stale recovery requires a canonical allowed HTTPS Supabase endpoint")

        is_instant_generation_worker = bool(
            explicit_worker_kind == "instant_deck_generation"
            or "instant_deck_generation" in configured_job_types
        )
        if is_instant_generation_worker:
            if self.deck_generation_mode.strip().lower() != "openai":
                add_critical_error("Instant generation requires DECK_GENERATION_MODE=openai")
            if self.deck_llm_provider.strip().lower() != "openai":
                add_critical_error("Instant generation requires DECK_LLM_PROVIDER=openai")
            if not self.openai_api_key or _is_placeholder(self.openai_api_key):
                add_critical_error("OPENAI_API_KEY is required for Instant generation")
            if self.openai_model != FULL_HTML_OPENAI_MODEL:
                add_critical_error(f"OPENAI_MODEL must be the audited Instant HTML snapshot {FULL_HTML_OPENAI_MODEL}")
        elif provider_capable_worker:
            if self.deck_generation_mode.strip().lower() != "openai":
                add_critical_error("Provider-capable worker requires DECK_GENERATION_MODE=openai")
            if self.deck_llm_provider.strip().lower() != "openai":
                add_critical_error("Provider-capable worker requires DECK_LLM_PROVIDER=openai")
            if not self.openai_api_key or _is_placeholder(self.openai_api_key):
                add_critical_error("OPENAI_API_KEY is required for provider-capable workers")
            if not self.openai_model.strip():
                add_critical_error("OPENAI_MODEL is required for provider-capable workers")
            if self.embedding_provider.strip().lower() != "openai":
                add_critical_error("EMBEDDING_PROVIDER must be openai for provider-capable workers")

        # Provider validation follows the selected mode. The API and workers
        # that execute source enrichment, generation, or diligence must fail
        # fast instead of starting with only a model name and no usable key.
        provider_role = runtime_role == "api" or provider_capable_worker
        generation_provider = self.deck_generation_mode.strip().lower()
        if provider_role:
            # Production provider policy: critique is deterministic, while every
            # provider-backed generation, repair, and vision pass must use the
            # selected OpenAI contract. Legacy Qwen/DashScope settings remain in
            # this class for non-production compatibility and historical tests.
            if generation_provider != "openai":
                errors.append("DECK_GENERATION_MODE must be openai for production AI services")
            if self.deck_llm_provider.strip().lower() != "openai":
                errors.append("DECK_LLM_PROVIDER must be openai for production AI services")
            if generation_provider == "openai":
                if not self.openai_api_key:
                    errors.append("OPENAI_API_KEY is required when DECK_GENERATION_MODE=openai")
                if not self.openai_model.strip():
                    errors.append("OPENAI_MODEL is required when DECK_GENERATION_MODE=openai")
            elif generation_provider in {"qwen", "dashscope", "alibaba"}:
                if not self.effective_qwen_api_key:
                    errors.append("QWEN_API_KEY is required when DECK_GENERATION_MODE selects Qwen/DashScope")
            elif generation_provider not in {"openrouter", "claude", "anthropic"}:
                errors.append("DECK_GENERATION_MODE must select a supported production provider")
        if (runtime_role == "api" or provider_capable_worker) and self.embedding_provider.strip().lower() != "openai":
            errors.append("EMBEDDING_PROVIDER must be openai for production API and embedding workers")
        if self.upload_storage_backend not in {"local", "s3", "supabase"}:
            errors.append("UPLOAD_STORAGE_BACKEND must be a supported storage backend")
        if self.upload_storage_backend == "local":
            pass
        if self.upload_storage_backend == "s3":
            s3_access_key = self.effective_s3_access_key
            s3_secret_key = self.effective_s3_secret_key
            if not self.upload_storage_s3_bucket or _is_placeholder(self.upload_storage_s3_bucket):
                errors.append("S3_BUCKET_NAME, AWS_S3_BUCKET_NAME, UPLOAD_STORAGE_S3_BUCKET, or RAILWAY_BUCKET_NAME is required when UPLOAD_STORAGE_BACKEND=s3")
            if not self.upload_storage_s3_region or _is_placeholder(self.upload_storage_s3_region):
                errors.append("AWS_DEFAULT_REGION, UPLOAD_STORAGE_S3_REGION, or RAILWAY_BUCKET_REGION is required when UPLOAD_STORAGE_BACKEND=s3")
            if not s3_access_key or _is_placeholder(s3_access_key):
                errors.append("AWS_ACCESS_KEY_ID, UPLOAD_STORAGE_S3_ACCESS_KEY, or RAILWAY_BUCKET_ACCESS_KEY is required when UPLOAD_STORAGE_BACKEND=s3")
            if not s3_secret_key or _is_placeholder(s3_secret_key):
                errors.append("AWS_SECRET_ACCESS_KEY, UPLOAD_STORAGE_S3_SECRET_KEY, or RAILWAY_BUCKET_SECRET_KEY is required when UPLOAD_STORAGE_BACKEND=s3")
            endpoint = self.upload_storage_s3_endpoint_url.strip()
            s3_provider = self.upload_storage_s3_provider
            if s3_provider not in {"aws", "compatible"}:
                errors.append("UPLOAD_STORAGE_S3_PROVIDER must be aws or compatible")
            elif s3_provider == "compatible" and not endpoint:
                errors.append("S3-compatible storage requires a custom endpoint")
            elif s3_provider == "aws" and endpoint:
                errors.append("AWS S3 storage must not set a custom endpoint; use provider=compatible")
            if endpoint and _is_placeholder(endpoint):
                errors.append("AWS_ENDPOINT_URL, UPLOAD_STORAGE_S3_ENDPOINT, or RAILWAY_BUCKET_ENDPOINT must be a real endpoint when provided")
            if is_preview_render_worker and endpoint and not _is_placeholder(endpoint):
                from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

                try:
                    self.upload_storage_s3_endpoint_url = validate_renderer_storage_endpoint(
                        endpoint,
                        backend="s3",
                        allowed_hosts=self.instant_html_storage_allowed_hosts,
                        variable_name="UPLOAD_STORAGE_S3_ENDPOINT",
                    )
                except ValueError as exc:
                    errors.append(str(exc))
        if self.upload_storage_backend == "supabase" and is_preview_render_worker and self.supabase_url:
            from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

            try:
                self.supabase_url = validate_renderer_storage_endpoint(
                    self.supabase_url,
                    backend="supabase",
                    allowed_hosts=self.instant_html_storage_allowed_hosts,
                    variable_name="SUPABASE_URL",
                )
            except ValueError as exc:
                errors.append(str(exc))
        self._validate_production_database_url(errors)
        if errors:
            if critical_errors:
                raise ValueError("Unsafe production capability settings: " + "; ".join(critical_errors))
            if _env_truthy("ALLOW_UNSAFE_PRODUCTION_STARTUP", default=False):
                object.__setattr__(self, "_startup_validation_errors", list(errors))
                return self
            raise ValueError("Unsafe production settings: " + "; ".join(errors))
        return self

    @property
    def startup_validation_errors(self) -> list[str]:
        return list(getattr(self, "_startup_validation_errors", []))

    @property
    def startup_validation_ok(self) -> bool:
        return len(self.startup_validation_errors) == 0

    model_config = SettingsConfigDict(env_file=SETTINGS_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


settings = Settings(_env_file=_runtime_settings_env_file())
