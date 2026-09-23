from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Deck, DeckExtractionRun, DeckFile, DesignVersion, SmartDeckWorkspace
from app.services.admin.workflow_observability import get_admin_deck_workflow_processing
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state


def get_smart_deck_readiness(db: Session, deck_id: str) -> dict[str, Any] | None:
    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        return None

    source = workflow.get("source") if isinstance(workflow.get("source"), dict) else {}
    smart_deck = workflow.get("smartDeck") if isinstance(workflow.get("smartDeck"), dict) else {}
    worker_heartbeat = workflow.get("workerHeartbeat") if isinstance(workflow.get("workerHeartbeat"), dict) else {}

    source_file_saved = bool(workflow.get("sourceFileSaved"))
    slides_read = int(source.get("slideCount") or 0) > 0 or bool(source.get("extractionReady"))
    previews_created = int(source.get("thumbnailCount") or 0) > 0
    workspace_prepared = bool(smart_deck.get("workspaceId")) or bool(smart_deck.get("sourceContextReady"))
    smart_deck_openable = bool(workflow.get("canOpenSmartDeck"))

    steps = {
        "sourceFileSaved": source_file_saved,
        "slidesRead": slides_read,
        "previewsCreated": previews_created,
        "previewsRequired": source.get("thumbnailsRequired", True),
        "workspacePrepared": workspace_prepared,
        "smartDeckOpenable": smart_deck_openable,
    }
    current_step = _current_step(steps)
    blocking_reason = _blocking_reason(workflow=workflow, steps=steps, worker_heartbeat=worker_heartbeat)
    retry_allowed = bool(workflow.get("canRetry")) or (
        source_file_saved and not smart_deck_openable and blocking_reason not in {None, "provider_not_configured"}
    )

    return {
        "deckId": deck_id,
        "ready": smart_deck_openable,
        "status": workflow.get("lifecycleStatus") or workflow.get("status") or "unknown",
        "currentStep": current_step,
        "canOpenSmartDeck": smart_deck_openable,
        "retryAllowed": retry_allowed,
        "blockingReason": blocking_reason,
        "steps": steps,
        "adminDebugUrl": f"/api/admin/decks/{deck_id}/debug",
        "processingUrl": f"/decks/{deck_id}/processing",
        "smartDeckUrl": ((workflow.get("links") or {}).get("smartDeckUrl")) or f"/decks/{deck_id}/smart-deck",
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "updatedAt": workflow.get("updatedAt"),
        "message": _readiness_message(current_step=current_step, blocking_reason=blocking_reason),
        "repairActions": {
            "retryProcessingUrl": f"/api/admin/decks/{deck_id}/retry-processing",
            "requeueStaleJobsUrl": f"/api/admin/decks/{deck_id}/requeue-stale-jobs",
            "prepareSmartDeckUrl": f"/api/admin/decks/{deck_id}/prepare-smart-deck",
            "repairMissingArtifactsUrl": f"/api/admin/decks/{deck_id}/repair-missing-artifacts",
        },
    }


def get_admin_deck_debug(db: Session, deck_id: str) -> dict[str, Any] | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None

    workflow = get_deck_workflow_state(db, deck_id)
    readiness = get_smart_deck_readiness(db, deck_id)
    processing = get_admin_deck_workflow_processing(db, deck_id)
    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck_id).one_or_none()
    latest_extraction = (
        db.query(DeckExtractionRun)
        .filter(DeckExtractionRun.deck_id == deck_id)
        .order_by(DeckExtractionRun.created_at.desc())
        .first()
    )
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).one_or_none()
    design_version = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.status != "discarded")
        .order_by(DesignVersion.created_at.desc())
        .first()
    )

    source = workflow.get("source") if isinstance((workflow or {}).get("source"), dict) else {}
    smart_deck = workflow.get("smartDeck") if isinstance((workflow or {}).get("smartDeck"), dict) else {}
    artifact_checklist = {
        "sourceFileSaved": bool((readiness or {}).get("steps", {}).get("sourceFileSaved")),
        "slidesRead": bool((readiness or {}).get("steps", {}).get("slidesRead")),
        "previewsCreated": bool((readiness or {}).get("steps", {}).get("previewsCreated")),
        "workspacePrepared": bool((readiness or {}).get("steps", {}).get("workspacePrepared")),
        "smartDeckOpenable": bool((readiness or {}).get("steps", {}).get("smartDeckOpenable")),
        "slideCount": int(source.get("slideCount") or 0),
        "thumbnailCount": int(source.get("thumbnailCount") or 0),
        "generatedSlideCount": int(smart_deck.get("generatedSlideCount") or 0),
        "missingArtifacts": list(workflow.get("missingArtifacts") or []) if isinstance(workflow, dict) else [],
    }

    return {
        "deckId": deck.id,
        "deckStatus": deck.status,
        "deckSummary": deck.summary,
        "deckFile": {
            "id": deck_file.id if deck_file is not None else None,
            "filename": deck_file.original_filename or deck_file.filename if deck_file is not None else None,
            "checksumSha256": deck_file.checksum_sha256 if deck_file is not None else None,
            "storagePath": deck_file.storage_path if deck_file is not None else None,
            "storageProvider": deck_file.storage_provider if deck_file is not None else None,
        },
        "latestExtractionRun": {
            "id": latest_extraction.id if latest_extraction is not None else None,
            "status": latest_extraction.status if latest_extraction is not None else None,
            "sourceFileId": latest_extraction.source_file_id if latest_extraction is not None else None,
            "errorMessage": latest_extraction.error_message if latest_extraction is not None else None,
            "createdAt": latest_extraction.created_at.isoformat() if latest_extraction and latest_extraction.created_at else None,
            "updatedAt": latest_extraction.updated_at.isoformat() if latest_extraction and latest_extraction.updated_at else None,
        },
        "workerHeartbeat": (workflow or {}).get("workerHeartbeat") if isinstance(workflow, dict) else None,
        "currentStage": (workflow or {}).get("activeStage") if isinstance(workflow, dict) else None,
        "artifactChecklist": artifact_checklist,
        "workspace": {
            "id": workspace.id if workspace is not None else None,
            "status": workspace.status if workspace is not None else None,
        },
        "designVersion": {
            "id": design_version.id if design_version is not None else None,
            "status": design_version.status if design_version is not None else None,
        },
        "failureTickets": list((workflow or {}).get("failures") or []) if isinstance(workflow, dict) else [],
        "recommendedRepairAction": _recommended_repair_action(readiness),
        "repairActions": {
            "retryProcessingUrl": f"/api/admin/decks/{deck_id}/retry-processing",
            "requeueStaleJobsUrl": f"/api/admin/decks/{deck_id}/requeue-stale-jobs",
            "prepareSmartDeckUrl": f"/api/admin/decks/{deck_id}/prepare-smart-deck",
            "repairMissingArtifactsUrl": f"/api/admin/decks/{deck_id}/repair-missing-artifacts",
        },
        "readiness": readiness,
        "workflowState": workflow,
        "processing": processing,
    }


def _smart_deck_debug_payload(db: Session, deck: Deck) -> dict[str, Any]:
    """Compatibility payload for older product-runtime imports.

    Some deployed revisions imported this private helper directly. Keep the
    symbol available so route imports do not crash while the richer
    get_admin_deck_debug payload remains the canonical implementation.
    """

    debug = get_admin_deck_debug(db, deck.id) or {}
    workflow = debug.get("workflowState") if isinstance(debug.get("workflowState"), dict) else {}
    smart_deck = workflow.get("smartDeck") if isinstance(workflow.get("smartDeck"), dict) else {}
    workspace = debug.get("workspace") if isinstance(debug.get("workspace"), dict) else {}
    design_version = debug.get("designVersion") if isinstance(debug.get("designVersion"), dict) else {}

    generated_slide_count = int(smart_deck.get("generatedSlideCount") or 0)
    render_schema_element_count = int(smart_deck.get("renderSchemaElementCount") or 0)
    active_generated_slide_id = smart_deck.get("activeGeneratedSlideId")

    return {
        "workspaceId": workspace.get("id"),
        "workspaceStatus": workspace.get("status"),
        "activeDesignVersionId": design_version.get("id"),
        "designVersionStatus": design_version.get("status"),
        "generatedSlideCount": generated_slide_count,
        "activeGeneratedSlideId": active_generated_slide_id,
        "renderSchemaElementCount": render_schema_element_count,
        "hasRenderableSchema": bool(active_generated_slide_id and render_schema_element_count > 0),
        "readiness": debug.get("readiness"),
        "recommendedRepairAction": debug.get("recommendedRepairAction"),
    }


def _current_step(steps: dict[str, bool]) -> str:
    if not steps["sourceFileSaved"]:
        return "checking_smart_deck_readiness"
    if not steps["slidesRead"]:
        return "reading_uploaded_slides"
    if steps.get("previewsRequired", True) and not steps["previewsCreated"]:
        return "creating_slide_previews"
    if not steps["workspacePrepared"]:
        return "preparing_smart_deck_workspace"
    if not steps["smartDeckOpenable"]:
        return "opening_smart_deck"
    return "ready"


def _blocking_reason(*, workflow: dict[str, Any], steps: dict[str, bool], worker_heartbeat: dict[str, Any]) -> str | None:
    if steps["smartDeckOpenable"]:
        return None
    explicit = workflow.get("blockingReason")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    heartbeat_state = worker_heartbeat.get("state")
    stale_reason = worker_heartbeat.get("staleReason")
    if isinstance(stale_reason, str) and stale_reason.strip():
        return stale_reason.strip()
    if heartbeat_state == "worker_stalled":
        return "worker_stalled"
    if heartbeat_state == "worker_not_running":
        return "worker_not_running"
    if not steps["sourceFileSaved"]:
        return "source_file_missing"
    if not steps["slidesRead"]:
        return "slides_not_read"
    if steps.get("previewsRequired", True) and not steps["previewsCreated"]:
        return "slide_previews_missing"
    if not steps["workspacePrepared"]:
        return "workspace_not_prepared"
    return "smart_deck_not_openable"


def _readiness_message(*, current_step: str, blocking_reason: str | None) -> str:
    if blocking_reason == "worker_stalled":
        return "Processing is stuck because the worker heartbeat is stale."
    if blocking_reason == "worker_not_running":
        return "Processing is waiting for a worker to claim the job."
    if blocking_reason:
        return f"Smart Deck is blocked at {current_step.replace('_', ' ')}."
    return f"Smart Deck is currently {current_step.replace('_', ' ')}."


def _recommended_repair_action(readiness: dict[str, Any] | None) -> str:
    if not isinstance(readiness, dict):
        return "inspect_workflow_state"
    blocking_reason = readiness.get("blockingReason")
    if blocking_reason in {"worker_stalled", "worker_not_running", "queued_too_long", "heartbeat_stale"}:
        return "requeue_stale_jobs"
    if blocking_reason in {"slides_not_read", "slide_previews_missing", "workspace_not_prepared"}:
        return "retry_processing"
    if blocking_reason == "provider_not_configured":
        return "configure_provider"
    if readiness.get("canOpenSmartDeck"):
        return "open_smart_deck"
    return "inspect_workflow_state"
