from __future__ import annotations

import os


PLACEHOLDER_PREFIXES = ("REPLACE_ME", "CHANGE_ME", "TODO")
PLACEHOLDER_PHRASES = (
    "real bucket",
    "real access key",
    "real secret key",
    "real railway postgres url",
    "your postgres",
)

DATABASE_ENV_ALIASES = (
    "DATABASE_URL",
    "DATABASE_PRIVATE_URL",
    "DATABASE_PUBLIC_URL",
    "POSTGRES_URL",
    "POSTGRES_PRIVATE_URL",
    "POSTGRES_PUBLIC_URL",
    "RAILWAY_DATABASE_URL",
)

AI_DATABASE_ENV_ALIASES = (
    "AI_DATABASE_URL",
    "AI_DATABASE_PRIVATE_URL",
    "AI_DATABASE_PUBLIC_URL",
    "AI_POSTGRES_URL",
    "AI_POSTGRES_PRIVATE_URL",
    "AI_POSTGRES_PUBLIC_URL",
    "RAILWAY_AI_DATABASE_URL",
)

STORAGE_BUCKET_ENV_ALIASES = (
    "UPLOAD_STORAGE_S3_BUCKET",
    "RAILWAY_BUCKET_NAME",
    "AWS_S3_BUCKET_NAME",
    "S3_BUCKET_NAME",
    "BUCKET",
)

STORAGE_REGION_ENV_ALIASES = (
    "UPLOAD_STORAGE_S3_REGION",
    "RAILWAY_BUCKET_REGION",
    "AWS_DEFAULT_REGION",
    "REGION",
)

STORAGE_ENDPOINT_ENV_ALIASES = (
    "UPLOAD_STORAGE_S3_ENDPOINT",
    "RAILWAY_BUCKET_ENDPOINT",
    "AWS_ENDPOINT_URL",
    "ENDPOINT",
)

STORAGE_ACCESS_KEY_ENV_ALIASES = (
    "UPLOAD_STORAGE_S3_ACCESS_KEY",
    "RAILWAY_BUCKET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "ACCESS_KEY_ID",
)

STORAGE_SECRET_KEY_ENV_ALIASES = (
    "UPLOAD_STORAGE_S3_SECRET_KEY",
    "RAILWAY_BUCKET_SECRET_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "SECRET_ACCESS_KEY",
)

RAILWAY_ENV_ALIAS_GROUPS = (
    DATABASE_ENV_ALIASES,
    AI_DATABASE_ENV_ALIASES,
    STORAGE_BUCKET_ENV_ALIASES,
    STORAGE_REGION_ENV_ALIASES,
    STORAGE_ENDPOINT_ENV_ALIASES,
    STORAGE_ACCESS_KEY_ENV_ALIASES,
    STORAGE_SECRET_KEY_ENV_ALIASES,
)


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip().strip('"').strip("'")
    if not stripped:
        return True
    upper = stripped.upper()
    lower = stripped.lower()
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    if upper.startswith(PLACEHOLDER_PREFIXES):
        return True
    return any(phrase in lower for phrase in PLACEHOLDER_PHRASES)


def _real_env_value(name: str) -> str | None:
    value = os.getenv(name)
    if _is_placeholder(value):
        return None
    return value


def _copy_first_available(target: str, sources: tuple[str, ...]) -> None:
    """Copy the first real Railway/source env var into target.

    Existing real target values win. Placeholder target values such as
    `<real bucket name>` do not win, because those placeholders can accidentally
    block the real Railway connector variables from being used.
    """

    if _real_env_value(target):
        return

    for source in sources:
        value = _real_env_value(source)
        if value:
            os.environ[target] = value
            return


def _copy_first_available_to_group(names: tuple[str, ...]) -> None:
    value = next((_real_env_value(name) for name in names if _real_env_value(name)), None)
    if not value:
        return
    for name in names:
        if not _real_env_value(name):
            os.environ[name] = value


def apply_railway_env_aliases() -> None:
    """Normalise Railway connector variable names before settings import."""

    for group in RAILWAY_ENV_ALIAS_GROUPS:
        _copy_first_available_to_group(group)

    if not _real_env_value("UPLOAD_STORAGE_BACKEND") and not _real_env_value("DECK_AISTACK_STORAGE_PROVIDER"):
        if _real_env_value("UPLOAD_STORAGE_S3_BUCKET") or _real_env_value("RAILWAY_BUCKET_NAME") or _real_env_value("AWS_S3_BUCKET_NAME"):
            os.environ["UPLOAD_STORAGE_BACKEND"] = "s3"
            os.environ["DECK_AISTACK_STORAGE_PROVIDER"] = "s3"
