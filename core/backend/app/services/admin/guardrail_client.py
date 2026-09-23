from __future__ import annotations

import json
import socket
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from app.core.config import settings
from app.core.utils import safe_read_json
from app.db.models import User
from app.services.admin.security_audit import record_security_event


def _guardrail_base_url() -> str:
    base = (settings.superadmin_guardrails_url or "").strip()
    return base.rstrip("/")


def _guardrail_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-guardrails-key": settings.superadmin_guardrails_api_key.strip(),
    }
    return {key: value for key, value in headers.items() if value}


def _request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    base = _guardrail_base_url()
    if not base:
        return False, None, "Guardrail service URL is not configured."

    request_data = None
    url = f"{base.rstrip('/')}{path}"
    if payload is not None:
        request_data = json.dumps(payload).encode("utf-8")
    try:
        request = Request(url, data=request_data, headers=_guardrail_headers(), method=method.upper())
        timeout_seconds = max(0.5, float(settings.superadmin_guardrails_timeout_seconds))
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            return True, safe_read_json(body), None
    except HTTPError as exc:
        body = exc.read()
        details = ""
        try:
            parsed = safe_read_json(body)
            if isinstance(parsed, dict) and "detail" in parsed:
                details = f" {parsed.get('detail')}"
        except Exception:
            details = ""
        return False, None, f"Guardrails HTTP {exc.code}.{details}"
    except (URLError, TimeoutError, socket.timeout) as exc:
        return False, None, f"Guardrails request failed: {exc}"
    except Exception as exc:  # pragma: no cover
        return False, None, f"Guardrails request failed: {exc}"


def _record_guardrail_event(
    db,
    *,
    request,
    actor: User | None,
    deck_id: str | None,
    task_type: str,
    source: str,
    allowed: bool,
    outcome: str,
    decision: dict[str, Any],
    commit: bool,
) -> None:
    record_security_event(
        db,
        action="guardrails.evaluate",
        result=outcome,
        actor=actor,
        resource_type="guardrail",
        resource_id=deck_id,
        request=request,
        details={
            "taskType": task_type,
            "source": source,
            "allowed": bool(allowed),
            "riskLevel": decision.get("riskLevel"),
            "policy": decision.get("policy"),
            "guardrailStatus": decision.get("status"),
            "reason": decision.get("reason"),
            "blockedReasons": decision.get("blockedReasons"),
            "auditId": decision.get("auditId"),
            "auditStored": bool(decision.get("auditId")),
        },
        commit=commit,
    )


def evaluate_deck_guardrail(
    *,
    db,
    request,
    actor: User | None,
    task_type: str,
    source: str,
    deck_id: str | None = None,
    workspace_id: str | None = None,
    user_instruction: str = "",
    user_id: str | None = None,
    prompt_preview: str | None = None,
    commit_events: bool = True,
) -> dict[str, Any]:
    base_url = _guardrail_base_url()
    if not base_url:
        return {
            "enabled": False,
            "status": "unconfigured",
            "allowed": True,
            "decision": "Guardrail service is not configured.",
            "riskLevel": "low",
            "policy": None,
            "reason": None,
            "blockedReasons": [],
            "auditId": None,
            "statusCode": None,
        }

    evaluation_payload = {
        "task_type": task_type,
        "trusted_context": {
            "case_id": deck_id or source,
            "tenant_id": workspace_id,
            "workflow_id": deck_id,
            "data_classification": "internal",
            "chains": [],
            "obligations": [],
            "source_email_ids": [],
        },
        "untrusted_evidence": [
            {"source_id": deck_id or source, "text": user_instruction[:1200]},
            {"source_id": "preview", "text": (prompt_preview or "")[:1200]},
        ],
        "user_instruction": user_instruction[:2000],
        "adapter_boundary": {
            "adapter": "deck-generation",
            "destination": "superadmin-guardrails",
            "operation": task_type,
            "external_transfer": False,
            "stores_customer_data": False,
            "zero_retention_supported": True,
            "human_review_required": False,
            "notes": [f"source={source}", f"deck_id={deck_id or ''}"],
        },
        "audit_record": {
            "request_id": getattr(request.state, "request_id", None) or f"deck-{datetime.utcnow().isoformat()}",
            "actor_id": actor.id if actor is not None else (user_id or "anonymous"),
            "purpose": f"Deck safety check for {task_type}",
            "trace_id": None,
            "retention_tag": "standard",
            "approved_by": None,
            "labels": ["deck_api", "safety_gate"],
        },
        "surface": source,
        "subject_type": "api",
        "subject_id": deck_id,
        "user_id": user_id or (actor.id if actor is not None else None),
        "workspace_id": workspace_id,
        "deck_id": deck_id,
        "product_key": "deck-aistack",
        "content_text": user_instruction[:1800],
    }

    success, response, error = _request_json("POST", "/api/v1/guardrails/evaluate", payload=evaluation_payload)
    if not success:
        decision = {
            "enabled": True,
            "status": "guardrail_unreachable",
            "allowed": True if not settings.superadmin_guardrails_strict_mode else False,
            "decision": error,
            "riskLevel": "medium" if settings.superadmin_guardrails_strict_mode else "low",
            "policy": None,
            "reason": error,
            "blockedReasons": [error],
            "auditId": None,
            "statusCode": None,
        }
        _record_guardrail_event(
            db,
            request=request,
            actor=actor,
            deck_id=deck_id,
            task_type=task_type,
            source=source,
            allowed=bool(decision["allowed"]),
            outcome="failed",
            decision=decision,
            commit=commit_events,
        )
        return decision

    allowed = bool(response.get("allowed", True))
    risk_level = str(response.get("risk_level", response.get("riskLevel", "low")))
    blocked_reasons = list(response.get("blocked_reasons", []) or [])
    decision = {
        "enabled": True,
        "status": "checked",
        "allowed": allowed,
        "decision": "allow" if allowed else "block",
        "riskLevel": risk_level,
        "policy": response.get("policy"),
        "reason": response.get("reason"),
        "blockedReasons": blocked_reasons,
        "auditId": (response.get("audit_record") or {}).get("audit_id") if isinstance(response, dict) else None,
        "statusCode": None,
        "railsExecuted": response.get("rails_executed", []),
        "policyPack": response.get("policy_pack"),
    }
    _record_guardrail_event(
        db,
        request=request,
        actor=actor,
        deck_id=deck_id,
        task_type=task_type,
        source=source,
        allowed=allowed,
        outcome="blocked" if not allowed else "allowed",
        decision=decision,
        commit=commit_events,
    )
    return decision


def get_guardrail_health_snapshot() -> dict[str, Any]:
    base_url = _guardrail_base_url()
    if not base_url:
        return {
            "configured": False,
            "status": "unconfigured",
            "health": None,
            "operatorSummary": None,
            "policyRegistry": None,
            "audits": [],
            "error": None,
        }

    health_ok, health, health_error = _request_json("GET", "/api/v1/guardrails/health")
    policy_ok, policy, policy_error = _request_json("GET", "/api/v1/guardrails/policy-registry")
    summary_ok, summary, summary_error = _request_json("GET", "/api/v1/guardrails/operator/summary")
    audits_ok, audits, audits_error = _request_json("GET", "/api/v1/guardrails/audits?limit=25")

    error = None
    status = "healthy" if health_ok else "unhealthy"
    if not all((health_ok, policy_ok, summary_ok, audits_ok)):
        error = "; ".join(
            value
            for value in (health_error, policy_error, summary_error, audits_error)
            if value
        ) or None
        if health_ok and not policy_ok and not summary_ok:
            status = "degraded"

    return {
        "configured": True,
        "status": status,
        "health": health if isinstance(health, dict) else None,
        "operatorSummary": summary if isinstance(summary, dict) else None,
        "policyRegistry": policy if isinstance(policy, dict) else None,
        "audits": audits if isinstance(audits, list) else [],
        "error": error,
        "baseUrl": base_url,
    }
