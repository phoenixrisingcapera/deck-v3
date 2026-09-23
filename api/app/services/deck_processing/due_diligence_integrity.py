"""Shared Due Diligence persistence invariants.

This module does not own execution. It centralizes canonical values used by the
existing mutation and read-model paths so persisted reports remain queryable.
"""

from __future__ import annotations

import re


def normalize_diligence_audience(value: str | None) -> str:
    """Return the stable storage/query key for a human-readable audience."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized or "seed_vc"


__all__ = ["normalize_diligence_audience"]
