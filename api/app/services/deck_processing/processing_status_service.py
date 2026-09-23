from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state


PHASE_STAGE_MAP: dict[str, tuple[str, int]] = {
    "upload_accepted": ("file_received", 8),
    "source_file_saved": ("file_received", 12),
    "source_extraction_queued": ("reading_slides", 18),
    "source_extraction_running": ("reading_slides", 28),
    "miniatures_queued": ("creating_previews", 40),
    "miniatures_running": ("creating_previews", 52),
    "brand_extraction_queued": ("extracting_brand", 62),
    "brand_extraction_running": ("extracting_brand", 70),
    "smart_deck_context_queued": ("building_context", 80),
    "smart_deck_context_running": ("building_context", 88),
    "db_publisher_queued": ("preparing_workspace", 94),
    "db_publisher_running": ("preparing_workspace", 97),
    "smart_deck_ready": ("ready", 100),
    "preview_ready": ("ready", 100),
    "applied": ("ready", 100),
    "export_ready": ("ready", 100),
}

FAILURE_STATUSES = {"failed", "failed_retryable", "failed_final", "blocked", "timed_out"}


def get_deck_processing_status(db: Session, deck_id: str) -> dict | None:
    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        return None

    phase = str(workflow.get("phase") or workflow.get("activeStage") or "upload_accepted")
    lifecycle_status = str(workflow.get("lifecycleStatus") or workflow.get("status") or "processing")
    error_message = str(workflow.get("message") or workflow.get("errorMessage") or "").strip() or None

    if bool(workflow.get("canOpenSmartDeck")):
        return {
            "deckId": deck_id,
            "status": "ready",
            "stage": "ready",
            "progress": 100,
            "readyForSmartDeck": True,
            "errorMessage": None,
        }

    if lifecycle_status in FAILURE_STATUSES:
        return {
            "deckId": deck_id,
            "status": "failed",
            "stage": "failed",
            "progress": max(_progress_for_phase(phase), 12),
            "readyForSmartDeck": False,
            "errorMessage": error_message or "Smart Deck processing failed.",
        }

    return {
        "deckId": deck_id,
        "status": "processing",
        "stage": _stage_for_phase(phase),
        "progress": _progress_for_phase(phase),
        "readyForSmartDeck": False,
        "errorMessage": None,
    }


def get_deck_processing_health(db: Session, deck_id: str) -> dict | None:
    """Admin-facing processing health with raw workflow diagnostics."""

    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        return None
    status = get_deck_processing_status(db, deck_id)
    phase = str(workflow.get("phase") or workflow.get("activeStage") or "upload_accepted")
    lifecycle_status = str(workflow.get("lifecycleStatus") or workflow.get("status") or "processing")
    error_message = str(workflow.get("message") or workflow.get("errorMessage") or "").strip() or None
    workflow_jobs = workflow.get("workflowJobs") if isinstance(workflow.get("workflowJobs"), list) else []

    return {
        **(status or {}),
        "deckId": deck_id,
        "phase": phase,
        "lifecycleStatus": lifecycle_status,
        "canOpenSmartDeck": bool(workflow.get("canOpenSmartDeck")),
        "canRetry": bool(workflow.get("canRetry")),
        "degraded": bool(workflow.get("degraded") or workflow.get("isDegraded")),
        "degradedReason": workflow.get("degradedReason") or workflow.get("degraded_reason"),
        "activeStage": workflow.get("activeStage") or _stage_for_phase(phase),
        "errorMessage": error_message,
        "workflowJobCount": len(workflow_jobs),
        "latestWorkflowJob": workflow_jobs[0] if workflow_jobs else None,
        "workflow": workflow,
    }


def _stage_for_phase(phase: str) -> str:
    return PHASE_STAGE_MAP.get(phase, ("preparing_workspace", 92))[0]


def _progress_for_phase(phase: str) -> int:
    return PHASE_STAGE_MAP.get(phase, ("preparing_workspace", 92))[1]
