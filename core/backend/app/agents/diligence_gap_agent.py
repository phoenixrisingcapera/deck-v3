"""Diligence gap detection agent.

Uses deck_context when available. Provider failure returns no findings so the
product can expose an explicit degraded run without fabricating deck evidence.
"""

from __future__ import annotations


import json
import logging
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded

from app.agents.llm_agent_utils import complete_json_with_ai_provider


logger = logging.getLogger(__name__)


def run(deck_id: str, *, deck_context: dict | None = None, provider_config: dict | None = None, deadline: OperationDeadline | None = None, usage_sink: dict | None = None) -> list[dict[str, str]] | None:
    """Return investor diligence gaps from the provided deck context."""
    if deck_context:
        try:
            raw = complete_json_with_ai_provider(
                provider_config=provider_config,
                system="You detect investor diligence gaps in pitch decks. Return JSON only.",
                user=(
                    "Return a JSON array of 1 to 8 findings. Each item must include "
                    "slide_id, block_id, title, detail, severity, and category. "
                    "severity must be low, medium, or high. Use only provided deck context.\n\n"
                    f"Deck context:\n{json.dumps(deck_context, ensure_ascii=True)}"
                ),
            deadline=deadline,
            usage_sink=usage_sink,
            )
        except OperationDeadlineExceeded:
            raise
        except Exception as exc:
            logger.warning("diligence_gap_provider_unavailable", extra={"errorType": type(exc).__name__})
            # DISABLED: Provider outages used to become persisted deck findings.
            # Reason: transport failure is run state, not diligence evidence.
            return None
        if isinstance(raw, list):
            findings = [_normalize_finding(item, deck_id) for item in raw if isinstance(item, dict)]
            valid_findings = [finding for finding in findings if finding is not None][:8]
            return valid_findings or None

    # DISABLED: A hard-coded sample finding was previously returned here.
    # Reason: sample content must never be persisted as analysis of a user deck.
    return None


def _normalize_finding(item: dict, deck_id: str) -> dict[str, str] | None:
    title = str(item.get("title") or "").strip()
    detail = str(item.get("detail") or "").strip()
    if not title or not detail:
        return None
    severity = str(item.get("severity") or "medium").lower()
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    return {
        "id": str(item.get("id") or ""),
        "deck_id": deck_id,
        "slide_id": str(item.get("slide_id") or ""),
        "block_id": str(item.get("block_id") or ""),
        "title": title[:180],
        "detail": detail[:1200],
        "severity": severity,
        "category": str(item.get("category") or "missing evidence")[:120],
    }
