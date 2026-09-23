from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

WORKFLOW_READY_PHASES: list[str] = []


def open_smart_deck(db: Session, deck_id: str) -> dict[str, Any]:
    return {
        "nextAction": None,
        "canOpenSmartDeck": True,
        "canGenerate": False,
        "canRetry": False,
        "degradedMode": False,
        "missingArtifacts": [],
        "failures": [],
        "activeJob": None,
        "failedJob": None,
        "latestJobs": [],
    }


def view_processing(db: Session, deck_id: str) -> dict[str, Any]:
    return {
        "nextAction": None,
        "canOpenSmartDeck": True,
        "canGenerate": False,
        "canRetry": False,
        "degradedMode": False,
        "missingArtifacts": [],
        "failures": [],
        "activeJob": None,
        "failedJob": None,
        "latestJobs": [],
    }
