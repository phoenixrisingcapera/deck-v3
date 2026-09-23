from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import settings


def get_workspace_ai_fernet() -> Fernet:
    if not settings.workspace_ai_fernet_key:
        raise RuntimeError("WORKSPACE_AI_FERNET_KEY is required for workspace AI provider credentials")
    return Fernet(settings.workspace_ai_fernet_key.encode())
