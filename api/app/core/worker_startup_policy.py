"""Pure, names-only worker startup policy.

This module intentionally imports no settings, database, queue, or provider
code so Railway worker identity and secret boundaries can fail first.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


SOURCE_PIPELINE_JOB_TYPES = (
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "brand_extraction",
    "smart_deck_context",
    "db_publisher",
)
LLM_GENERATION_JOB_TYPES = (
    "llm_generation",
    "due_diligence",
    "deck_map_analysis",
    "market_research",
    "media_processing",
    "smart_edit",
)
INSTANT_DECK_PIPELINE_JOB_TYPES = (
    "source_ingestion",
    "source_extraction",
    "brand_extraction",
    "instant_deck_generation",
    "schema_validation",
    "db_publisher",
    "export",
)

SERVICE_WORKER_KINDS = {
    "worker-source-ingestion": "source_ingestion",
    "worker-source-extraction": "source_extraction",
    "worker-miniatures": "miniatures",
    "worker-brand-extraction": "brand_extraction",
    "worker-smart-deck-context": "smart_deck_context",
    "worker-db-publisher": "db_publisher",
    "worker-llm-generation": "llm_generation",
    "worker-instant-deck-generation": "instant_deck_generation",
    "worker-schema-validation": "schema_validation",
    "worker-preview-render": "preview_render",
    "worker-apply-version": "apply_version",
    "worker-compile-final-deck": "compile_final_deck",
    "worker-export": "export",
    "worker-due-diligence": "due_diligence",
    "worker-deck-map-analysis": "deck_map_analysis",
    "worker-market-research": "market_research",
    "worker-media-processing": "media_processing",
    "worker-smart-edit": "smart_edit",
    "worker-stale-job-rescuer": "stale_job_rescuer",
    "worker-source-pipeline": "source_pipeline",
    "deck-worker": "instant_deck_pipeline",
    "deck-processing-worker": "stale_job_rescuer",
    "deck-processing-worker-service": "stale_job_rescuer",
}

PROVIDER_CAPABLE_WORKER_KINDS = frozenset(
    {
        "instant_deck_generation",
        "instant_deck_pipeline",
        "llm_generation",
        "selected_slide_generation",
        "due_diligence",
        "deck_map_analysis",
        "market_research",
        "smart_edit",
    }
)
OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS = frozenset(
    {"smart_deck_context", "source_pipeline"}
)
PROVIDER_FREE_WORKER_KINDS = frozenset(
    {
        "schema_validation",
        "preview_render",
        "db_publisher",
        "stale_job_rescuer",
        "miniatures",
        "apply_version",
        "compile_final_deck",
        "export",
        "media_processing",
        "source_ingestion",
        "source_extraction",
        "brand_extraction",
    }
)

# Names accepted by settings/provider credential resolution. Matching is
# case-insensitive and values are never read or serialized by this policy.
PROVIDER_CREDENTIAL_ENV_NAMES = frozenset(
    {
        "OPENAI_API_KEY",
        "OPENAI_API",
        "OPENAI_MODEL",
        "DECK_LLM_PROVIDER",
        "DECK_GENERATION_MODE",
        "DECK_AISTACK_GENERATION_MODE",
        "EMBEDDING_PROVIDER",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "WORKSPACE_AI_FERNET_KEY",
        "WORKSPACE_AI_FERNET_KEY_VERSION",
    }
)


def normalize_name(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def parse_job_types(value: str | None) -> tuple[str, ...]:
    return tuple(sorted({normalize_name(item) for item in str(value or "").split(",") if item.strip()}))


def expected_job_types(kind: str | None) -> tuple[str, ...]:
    if kind == "source_pipeline":
        return tuple(sorted(SOURCE_PIPELINE_JOB_TYPES))
    if kind == "llm_generation":
        return tuple(sorted(LLM_GENERATION_JOB_TYPES))
    if kind == "instant_deck_pipeline":
        return tuple(sorted(INSTANT_DECK_PIPELINE_JOB_TYPES))
    if kind == "stale_job_rescuer" or not kind:
        return ()
    return (kind,)


def apply_worker_identity_defaults(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Apply canonical names before settings/runtime imports and validation."""
    source = os.environ if environ is None else environ
    service_name = str(source.get("RAILWAY_SERVICE_NAME") or "").strip().lower()
    service_kind = SERVICE_WORKER_KINDS.get(service_name)
    role = normalize_name(source.get("APP_ROLE") or "worker")
    role_kind = role.removeprefix("worker_") if role.startswith("worker_") else ""
    kind = normalize_name(source.get("WORKER_KIND")) or normalize_name(source.get("DECK_WORKER_KIND")) or service_kind or role_kind

    if service_kind:
        source.setdefault("APP_ROLE", f"worker-{service_kind.replace('_', '-')}")
    if kind:
        source.setdefault("WORKER_KIND", kind)
    jobs = expected_job_types(kind)
    if jobs:
        source.setdefault("DECK_WORKER_JOB_TYPES", ",".join(jobs))
    if kind == "source_pipeline":
        source.setdefault("DECK_WORKER_ALLOW_MULTI_JOB_TYPES", "true")
    if kind == "stale_job_rescuer":
        source.setdefault("DECK_WORKER_RECOVERY_ONLY", "true")
    return source


@dataclass(frozen=True)
class WorkerIdentity:
    role: str
    kind: str | None
    job_types: tuple[str, ...]
    service_name: str | None
    provider_capable: bool
    provider_free: bool
    policy: str
    health_only: bool
    violations: tuple[str, ...]
    forbidden_names: tuple[str, ...]


def resolve_worker_identity(environ: dict[str, str] | None = None) -> WorkerIdentity:
    source = os.environ if environ is None else environ
    role = normalize_name(source.get("APP_ROLE") or "worker")
    service_name = str(source.get("RAILWAY_SERVICE_NAME") or "").strip().lower() or None
    service_kind = SERVICE_WORKER_KINDS.get(service_name or "")
    role_kind = role.removeprefix("worker_") if role.startswith("worker_") else None
    kind = normalize_name(source.get("WORKER_KIND")) or normalize_name(source.get("DECK_WORKER_KIND")) or service_kind or role_kind
    jobs = parse_job_types(source.get("DECK_WORKER_JOB_TYPES")) or expected_job_types(kind)
    source_provider_enabled = normalize_name(source.get("SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED") or "true") not in {
        "0", "false", "no", "off"
    }
    provider_capable = bool(
        kind in PROVIDER_CAPABLE_WORKER_KINDS
        or (source_provider_enabled and kind in OPTIONAL_SOURCE_PROVIDER_WORKER_KINDS)
    )
    provider_free = bool(kind and not provider_capable)
    violations: list[str] = []

    is_worker_role = role == "worker" or role.startswith("worker_") or bool(service_kind)
    if is_worker_role and not kind:
        violations.append("worker identity requires WORKER_KIND")
    if service_kind:
        expected_role = f"worker_{service_kind}"
        if role not in {"worker", expected_role}:
            violations.append("APP_ROLE conflicts with the known Railway service identity")
        if kind != service_kind:
            violations.append("WORKER_KIND conflicts with the known Railway service identity")
        if jobs != expected_job_types(service_kind):
            violations.append("DECK_WORKER_JOB_TYPES conflicts with the known Railway service identity")
    elif role.startswith("worker_") and kind and role.removeprefix("worker_") != kind:
        violations.append("APP_ROLE conflicts with WORKER_KIND")

    expected_jobs = expected_job_types(kind)
    if kind and jobs != expected_jobs:
        violations.append("DECK_WORKER_JOB_TYPES does not match the exact worker capability")
    if kind == "stale_job_rescuer" and normalize_name(source.get("DECK_WORKER_RECOVERY_ONLY")) not in {
        "1", "true", "yes", "on"
    }:
        violations.append("stale_job_rescuer requires recovery-only mode")

    policy = normalize_name(source.get("WORKER_FORBIDDEN_SECRET_POLICY") or "enforce")
    if policy not in {"enforce", "audit"}:
        violations.append("worker secret policy must be enforce or audit")
    health_only = policy == "audit"

    present_names = {str(name).upper() for name in source}
    forbidden_names = tuple(sorted(PROVIDER_CREDENTIAL_ENV_NAMES & present_names)) if provider_free else ()
    if forbidden_names:
        violations.append("provider-free worker received provider credential or decryption variable names")

    return WorkerIdentity(
        role=role,
        kind=kind,
        job_types=jobs,
        service_name=service_name,
        provider_capable=provider_capable,
        provider_free=provider_free,
        policy=policy,
        health_only=health_only,
        violations=tuple(violations),
        forbidden_names=forbidden_names,
    )


def validate_worker_environment_before_import(
    environ: dict[str, str] | None = None, *, allow_health_only: bool = False
) -> WorkerIdentity:
    source = os.environ if environ is None else environ
    identity = resolve_worker_identity(source)
    explicit_worker_context = any(
        name in source
        for name in (
            "APP_ROLE",
            "WORKER_KIND",
            "DECK_WORKER_JOB_TYPES",
            "RAILWAY_SERVICE_NAME",
            "WORKER_FORBIDDEN_SECRET_POLICY",
        )
    )
    if not explicit_worker_context and normalize_name(source.get("APP_ENV")) != "production":
        return identity
    if identity.health_only:
        if allow_health_only:
            return identity
        raise RuntimeError("Unsafe worker startup policy: audit is health-only and cannot import worker runtime")
    if identity.violations:
        names = f"; forbidden names: {', '.join(identity.forbidden_names)}" if identity.forbidden_names else ""
        raise RuntimeError("Unsafe worker startup policy: " + "; ".join(identity.violations) + names)
    return identity
