from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings


RAW_CHECKPOINT_ENCRYPTION_PURPOSE = "instant-html-raw-checkpoint.v2"
REQUEST_CONTEXT_ENCRYPTION_PURPOSE = "instant-html-request-context.v2"
LEGACY_REQUEST_CONTEXT_ENCRYPTION_PURPOSE = "instant-html-request-context"


def get_instant_html_raw_checkpoint_fernet() -> Fernet:
    """Derive a raw-checkpoint-only key from the workspace AI root key."""
    if not settings.workspace_ai_fernet_key:
        raise RuntimeError("WORKSPACE_AI_FERNET_KEY is required for Instant HTML raw checkpoints")
    root_key = base64.urlsafe_b64decode(settings.workspace_ai_fernet_key.encode("ascii"))
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"deck-aistack-instant-html",
        info=RAW_CHECKPOINT_ENCRYPTION_PURPOSE.encode("ascii"),
    ).derive(root_key)
    return Fernet(base64.urlsafe_b64encode(derived))


def get_instant_html_request_context_fernet() -> Fernet:
    """Derive a request-context-only key, distinct from raw checkpoints."""
    if not settings.workspace_ai_fernet_key:
        raise RuntimeError("WORKSPACE_AI_FERNET_KEY is required for Instant HTML request context")
    root_key = base64.urlsafe_b64decode(settings.workspace_ai_fernet_key.encode("ascii"))
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"deck-aistack-instant-html",
        info=REQUEST_CONTEXT_ENCRYPTION_PURPOSE.encode("ascii"),
    ).derive(root_key)
    return Fernet(base64.urlsafe_b64encode(derived))
