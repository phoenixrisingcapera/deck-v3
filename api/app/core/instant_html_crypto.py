from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import settings


def get_instant_html_render_fernet() -> Fernet:
    """Return the purpose-specific key that can decrypt sanitized render data only."""
    if not settings.instant_html_render_fernet_key:
        raise RuntimeError("INSTANT_HTML_RENDER_FERNET_KEY is required for Instant HTML artifacts")
    return Fernet(settings.instant_html_render_fernet_key.encode("utf-8"))
