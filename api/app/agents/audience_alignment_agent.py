"""Deterministic audience alignment helper.

Returns the default tone/priority for a target audience. This is intentionally
small and should not duplicate Smart Edit or adaptation suggestion generation.
"""

from __future__ import annotations


def run(audience_type: str, purpose: str) -> dict[str, str]:
    """Describe the writing posture Smart Deck should use for an audience."""
    return {
        "audience_type": audience_type,
        "purpose": purpose,
        "priority": "evidence density and decision readiness",
        "tone": "precise and risk-aware",
    }
