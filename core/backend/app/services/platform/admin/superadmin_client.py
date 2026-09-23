from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from app.core.config import settings
from app.core.utils import safe_read_json


def _base_url() -> str:
    return (settings.superadmin_aistack_url or "").strip().rstrip("/")


def _request_json(method: str, path: str) -> tuple[bool, dict[str, Any] | None, str | None]:
    base = _base_url()
    if not base:
        return False, None, "Super-admin service URL is not configured."

    try:
        request = Request(f"{base}{path}", headers={"accept": "application/json"}, method=method.upper())
        timeout_seconds = max(0.5, float(settings.superadmin_aistack_timeout_seconds))
        with urlopen(request, timeout=timeout_seconds) as response:
            return True, safe_read_json(response.read()), None
    except HTTPError as exc:
        body = exc.read()
        details = ""
        try:
            parsed = safe_read_json(body)
            if isinstance(parsed, dict) and "detail" in parsed:
                details = f" {parsed.get('detail')}"
        except Exception:
            details = ""
        return False, None, f"Super-admin HTTP {exc.code}.{details}"
    except (URLError, TimeoutError, socket.timeout) as exc:
        return False, None, f"Super-admin request failed: {exc}"
    except Exception as exc:  # pragma: no cover
        return False, None, f"Super-admin request failed: {exc}"


def get_superadmin_aistack_snapshot() -> dict[str, Any]:
    base_url = _base_url()
    if not base_url:
        return {
            "configured": False,
            "status": "unconfigured",
            "health": None,
            "error": None,
            "baseUrl": None,
        }

    health_ok, health, health_error = _request_json("GET", "/health")
    return {
        "configured": True,
        "status": "healthy" if health_ok else "unhealthy",
        "health": health if isinstance(health, dict) else None,
        "error": health_error,
        "baseUrl": base_url,
    }
