"""Audience adaptation suggestion agent.

Produces reviewable suggestions for a target audience. Missing provider output
returns no suggestions rather than sample copy.
"""

from __future__ import annotations


import json
import logging
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded

from app.agents.llm_agent_utils import complete_json_with_ai_provider


logger = logging.getLogger(__name__)


def run(
    deck_id: str,
    audience_type: str,
    *,
    deck_context: dict | None = None,
    provider_config: dict | None = None,
    deadline: OperationDeadline | None = None,
    usage_sink: dict | None = None,
) -> list[dict[str, str]] | None:
    """Return audience-specific suggestions without directly modifying slides."""
    if deck_context:
        try:
            raw = complete_json_with_ai_provider(
                provider_config=provider_config,
                system="You create reviewable audience adaptation suggestions for pitch decks. Return JSON only.",
                user=(
                    "Return a JSON array of 1 to 8 suggestions. Each item must include "
                    "slide_id, block_id, title, reason, suggested_text, and audience. "
                    "Preserve source-backed facts and do not invent metrics.\n\n"
                    f"Target audience: {audience_type}\n"
                    f"Deck context:\n{json.dumps(deck_context, ensure_ascii=True)}"
                ),
                deadline=deadline,
                usage_sink=usage_sink,
            )
        except OperationDeadlineExceeded:
            raise
        except Exception as exc:
            logger.warning("adaptation_suggestion_provider_unavailable", extra={"errorType": type(exc).__name__})
            return None
        if isinstance(raw, list):
            suggestions = [_normalize_suggestion(item, deck_id, audience_type) for item in raw if isinstance(item, dict)]
            valid_suggestions = [suggestion for suggestion in suggestions if suggestion is not None][:8]
            return valid_suggestions or None

    # DISABLED: Hard-coded sample adaptation copy previously appeared here.
    # Reason: invented metrics cannot be shown as a deck-specific recommendation.
    return None


def _normalize_suggestion(item: dict, deck_id: str, audience_type: str) -> dict[str, str] | None:
    title = str(item.get("title") or "").strip()
    reason = str(item.get("reason") or "").strip()
    suggested_text = str(item.get("suggested_text") or "").strip()
    if not title or not reason or not suggested_text:
        return None
    return {
        "id": str(item.get("id") or ""),
        "deck_id": deck_id,
        "slide_id": str(item.get("slide_id") or ""),
        "block_id": str(item.get("block_id") or ""),
        "title": title[:180],
        "reason": reason[:1200],
        "suggested_text": suggested_text[:4000],
        "status": "pending",
        "audience": str(item.get("audience") or audience_type)[:120],
    }
