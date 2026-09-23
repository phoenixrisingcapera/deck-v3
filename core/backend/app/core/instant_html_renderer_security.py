from __future__ import annotations

import os
from ipaddress import ip_address
from urllib.parse import urlsplit

from app.core.railway_env import AI_DATABASE_ENV_ALIASES


INSTANT_HTML_RENDERER_ROLE = "instant-html-renderer"
INSTANT_HTML_RENDERER_ROLE_ALIASES = frozenset({INSTANT_HTML_RENDERER_ROLE, "instant_html_renderer"})

# The renderer needs the core database, artifact-storage credentials, and its
# purpose-specific render key. Product credentials must never cross this
# service boundary, even if another Railway service exposes them as shared
# variables.
INSTANT_HTML_RENDERER_FORBIDDEN_VARIABLES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "AUTH_SECRET_KEY",
        "AUTH_SECRET_KEY_ID",
        "BACKEND_JWT_SIGNING_KEY_ID",
        "BACKEND_JWT_SIGNING_SECRET",
        "DASHSCOPE_API_KEY",
        "FRONTEND_SESSION_COOKIE_SECRET",
        "JWT_SECRET",
        "OPENAI_API",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "QWEN_API_KEY",
        "SECRET_KEY",
        "SESSION_SECRET",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "SUPERADMIN_GUARDRAILS_API_KEY",
        "TURNSTILE_SECRET_KEY",
        "USER_ADMIN_BOOTSTRAP_TOKEN",
        "WORKSPACE_AI_FERNET_KEY",
        "WORKSPACE_AI_FERNET_KEY_VERSION",
    }
) | frozenset(AI_DATABASE_ENV_ALIASES)

INSTANT_HTML_RENDERER_REQUIRED_VARIABLES = frozenset(
    {
        "APP_ENV",
        "APP_ROLE",
        "CORS_ORIGIN",
        "DATABASE_URL",
        "INSTANT_HTML_ENABLED",
        "INSTANT_HTML_RENDERER_ORIGIN",
        "INSTANT_HTML_RENDER_PARENT_ORIGIN",
        "INSTANT_HTML_RENDER_FERNET_KEY",
        "INSTANT_HTML_RENDER_KEY_VERSION",
        "UPLOAD_STORAGE_BACKEND",
    }
)

_S3_PROVIDER_HOST_SUFFIXES = (
    "amazonaws.com",
    "r2.cloudflarestorage.com",
    "storage.railway.app",
    "storageapi.dev",
)
_SUPABASE_PROVIDER_HOST_SUFFIXES = ("supabase.co", "supabase.in")

INSTANT_HTML_RENDERER_STORAGE_VARIABLE_ALTERNATIVES = {
    "s3": frozenset(
        {
            "UPLOAD_STORAGE_S3_BUCKET",
            "UPLOAD_STORAGE_S3_REGION",
            "UPLOAD_STORAGE_S3_ENDPOINT",
            "UPLOAD_STORAGE_S3_ACCESS_KEY",
            "UPLOAD_STORAGE_S3_SECRET_KEY",
        }
    ),
    "supabase": frozenset({"SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET"}),
}


def is_instant_html_renderer_role(role: str | None) -> bool:
    return str(role or "").strip().lower() in INSTANT_HTML_RENDERER_ROLE_ALIASES


def forbidden_render_environment_variables(environ: dict[str, str] | None = None) -> list[str]:
    """Return forbidden credential names without ever reading/logging values."""

    source = os.environ if environ is None else environ
    return sorted(name for name in INSTANT_HTML_RENDERER_FORBIDDEN_VARIABLES if name in source)


def validate_instant_html_renderer_environment(environ: dict[str, str] | None = None) -> None:
    """Reject product/provider credentials before the renderer app is imported."""

    source = os.environ if environ is None else environ
    present = forbidden_render_environment_variables(source)
    if present:
        raise RuntimeError(
            "Instant HTML renderer must not receive auth, provider, workspace, session, or billing variables: "
            + ", ".join(present)
        )


def validate_origin(
    value: str,
    *,
    variable_name: str,
    allow_http_loopback: bool = False,
) -> str:
    """Validate a production HTTPS origin or an explicit development loopback origin."""

    candidate = str(value or "").strip()
    if not candidate:
        return ""
    if any(character in candidate for character in (";", ",", "'", '"', "\\", "\n", "\r", "\t")):
        raise ValueError(f"{variable_name} must be a single HTTPS origin")
    parsed = urlsplit(candidate)
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{variable_name} contains an invalid port") from exc
    is_development_loopback = (
        allow_http_loopback
        and parsed.scheme == "http"
        and str(parsed.hostname or "").lower().rstrip(".") in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        parsed.scheme != "https"
        and not is_development_loopback
        or not parsed.hostname
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != ""
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{variable_name} must be an HTTPS origin without credentials, path, query, fragment, or CSP delimiters")
    normalized_host = parsed.hostname.lower().rstrip(".")
    normalized_netloc = normalized_host if parsed_port is None else f"{normalized_host}:{parsed_port}"
    if parsed.netloc.lower().rstrip(".") != normalized_netloc:
        raise ValueError(f"{variable_name} must contain only a canonical host and optional port")
    return f"{parsed.scheme}://{normalized_netloc}"


def validate_renderer_storage_endpoint(
    value: str,
    *,
    backend: str,
    allowed_hosts: str = "",
    variable_name: str,
) -> str:
    """Reject credential-bearing or unrelated storage endpoints before SDK use."""

    endpoint = validate_origin(value, variable_name=variable_name)
    if not endpoint:
        return ""
    host = str(urlsplit(endpoint).hostname or "").lower().rstrip(".")
    explicit_hosts = {
        item.strip().lower().rstrip(".")
        for item in str(allowed_hosts or "").split(",")
        if item.strip()
    }
    explicitly_allowed = any(host == item or host.endswith("." + item) for item in explicit_hosts)
    suffixes = _S3_PROVIDER_HOST_SUFFIXES if backend == "s3" else _SUPABASE_PROVIDER_HOST_SUFFIXES
    provider_allowed = any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)
    try:
        parsed_ip = ip_address(host)
        is_ip = True
    except ValueError:
        parsed_ip = None
        is_ip = False
    if is_ip and parsed_ip is not None and (
        not parsed_ip.is_global
        or parsed_ip.is_multicast
        or parsed_ip.is_unspecified
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_private
        or parsed_ip.is_reserved
    ):
        raise ValueError(f"{variable_name} must not use a non-global IP literal")
    if (is_ip and not explicitly_allowed) or not (explicitly_allowed or provider_allowed):
        raise ValueError(
            f"{variable_name} host is not valid for the configured storage provider or explicit renderer allowlist"
        )
    return endpoint
