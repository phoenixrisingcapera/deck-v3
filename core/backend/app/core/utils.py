"""Shared utility functions used across the backend.

Consolidated from duplicate implementations in:
- app/services/admin/guardrail_client.py
- app/services/platform/admin/superadmin_client.py
- app/ai/market_research_knowledge_context.py
- app/ai/vc_finance_knowledge_context.py
- app/api/routes/upload_rescue.py
- app/services/deck_processing/upload_service.py
- app/api/routes/deck_retry_rescue.py
- app/api/routes/products.py
- app/services/admin/failure_tickets.py
- app/services/admin/operations.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9.\-_]")


def safe_read_json(payload: bytes | str | None) -> dict[str, Any]:
    """Parse JSON payload safely, returning empty dict on failure."""
    if not payload:
        return {}
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    text = payload.strip()
    if not text:
        return {}
    return json.loads(text)


def read_json_payload(raw: str) -> dict | list | None:
    """Parse JSON string, returning None on decode error."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def safe_filename(filename: str) -> str:
    """Sanitize a filename for safe storage, using pre-compiled regex."""
    name = Path(filename).name.strip() or "deck.bin"
    cleaned = SAFE_FILENAME_RE.sub("-", name).strip(".-")
    return cleaned[:180] or "deck.bin"


def request_id(request: Any | None) -> str | None:
    """Extract request ID from a FastAPI request object."""
    if request is None:
        return None
    state = getattr(request, "state", None)
    state_request_id = getattr(state, "request_id", None)
    if state_request_id:
        return str(state_request_id)
    headers = getattr(request, "headers", None)
    if headers and headers.get("x-request-id"):
        return str(headers.get("x-request-id"))
    return None
