from __future__ import annotations

import os

from app.core.instant_html_renderer_security import forbidden_render_environment_variables


def validate_render_worker_secret_contract() -> None:
    normalize = lambda value: str(value or "").strip().lower().replace("-", "_")
    job_types = {normalize(item) for item in str(os.getenv("DECK_WORKER_JOB_TYPES") or "").split(",") if item.strip()}
    kind = normalize(os.getenv("WORKER_KIND"))
    role = normalize(os.getenv("APP_ROLE"))
    is_preview_role = role == "worker_preview_render" or kind == "preview_render" or "preview_render" in job_types
    if not is_preview_role:
        return
    if job_types - {"preview_render"}:
        raise RuntimeError("Instant HTML preview rendering requires a dedicated single-purpose worker")
    present = forbidden_render_environment_variables()
    if present:
        raise RuntimeError("Preview-render worker must not receive provider, billing, session, or workspace credential secrets: " + ", ".join(present))
    if not os.getenv("INSTANT_HTML_RENDER_FERNET_KEY") or not os.getenv("INSTANT_HTML_RENDER_KEY_VERSION"):
        raise RuntimeError("Preview-render worker requires a versioned purpose-specific render key")
