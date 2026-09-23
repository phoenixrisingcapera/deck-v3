from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import Deck, DeckFile, DeckSlide, DeckSlideAsset, DeckSlideBlock
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state
from app.services.admin.worker_health import get_latest_worker_heartbeat

PROCESSING_QUEUED_STALE_SECONDS = 120
PROCESSING_HEARTBEAT_STALE_SECONDS = 300

PHASES = [
    {
        "key": "source_saved",
        "label": "Source file saved",
        "description": "The uploaded deck file is persisted and available to the workflow.",
    },
    {
        "key": "source_extraction",
        "label": "Source extraction",
        "description": "Slides, text blocks, and assets are being extracted from the source deck.",
    },
    {
        "key": "miniatures",
        "label": "Miniatures",
        "description": "Slide previews and thumbnails are being rendered.",
    },
    {
        "key": "smart_deck_ready",
        "label": "Smart Deck ready",
        "description": "The backend workflow has published Smart Deck readiness.",
    },
    {
        "key": "brand_extraction",
        "label": "Brand extraction",
        "description": "Optional palette, logo, and brand provenance are being extracted.",
    },
]


def get_deck_processing_visibility(db: Session, deck_id: str) -> dict | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None

    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        return None

    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck_id).one_or_none()
    upload = _upload_payload(deck_file)
    outputs = _output_counts(db, deck_id)
    processing = _processing_payload(workflow, deck_id, deck_file.id if deck_file is not None else None)
    worker = _worker_payload(processing)
    worker["latestHeartbeat"] = get_latest_worker_heartbeat(db)
    phases = _phases(workflow, outputs)
    persisted_deck_status = canonical_deck_state(deck.status).value
    lifecycle_status = str(
        workflow.get("status")
        or ((processing or {}).get("workflowJobStatus") if isinstance(processing, dict) else None)
        or "queued"
    )
    if persisted_deck_status == DeckState.READY.value and lifecycle_status in {"completed", "ready"}:
        lifecycle_status = DeckState.READY.value
        if isinstance(processing, dict):
            processing["status"] = DeckState.READY.value
            processing["state"] = DeckState.READY.value
            processing["runStatus"] = DeckState.READY.value
            processing["workflowJobStatus"] = DeckState.READY.value
        else:
            processing = {
                "id": workflow.get("workflowId") or f"deckwf_{deck.id}",
                "runId": workflow.get("workflowId") or f"deckwf_{deck.id}",
                "workflowJobId": None,
                "workflowJobType": None,
                "workflowJobStatus": "completed",
                "workflowPhase": workflow.get("phase") or "smart_deck_context_ready",
                "deckId": deck.id,
                "sourceFileId": deck_file.id if deck_file is not None else None,
                "runType": "workflow_job",
                "status": "completed",
                "runStatus": "completed",
                "state": DeckState.READY.value,
                "stage": workflow.get("phase") or "smart_deck_context_ready",
                "stageLabel": str(workflow.get("phase") or "smart_deck_context_ready").replace("_", " ").title(),
                "nextAction": workflow.get("nextAction"),
                "attemptCount": 1,
                "maxAttempts": 1,
                "recoveryCount": 0,
                "lockedBy": None,
                "lockedAt": None,
                "heartbeatAt": None,
                "lastRecoveredAt": None,
                "lastRecoveredBy": None,
                "publishedPhase": workflow.get("phase"),
                "publishedAt": None,
                "requiresManualReview": False,
                "finalFailureReason": None,
                "slideCount": workflow.get("source", {}).get("slideCount"),
                "blockCount": None,
                "assetCount": workflow.get("source", {}).get("assetCount"),
                "errorMessage": None,
                "errorJson": None,
                "metadataJson": {
                    "workflowId": workflow.get("workflowId"),
                    "jobType": None,
                    "phase": workflow.get("phase"),
                    "terminalReason": None,
                },
                "metricsJson": {
                    "provider": workflow.get("provider") or {},
                    "smartDeck": workflow.get("smartDeck") or {},
                },
                "createdAt": deck.updated_at.isoformat() if deck.updated_at else None,
                "startedAt": None,
                "completedAt": deck.updated_at.isoformat() if deck.updated_at else None,
            }
    next_action = str(workflow.get("nextAction") or "view_processing")
    can_remove = bool(workflow.get("canOpenSmartDeck")) or lifecycle_status in {
        "failed_retryable",
        "failed_final",
        "blocked",
        "timed_out",
        DeckState.FAILED.value,
    }
    return {
        "deckId": deck.id,
        "workflowId": workflow.get("workflowId"),
        "workflowPhase": workflow.get("phase"),
        "workflowStatus": workflow.get("status"),
        "status": lifecycle_status,
        "state": lifecycle_status,
        "deckStatus": lifecycle_status,
        "deckSummary": deck.summary,
        "upload": upload,
        "processing": processing,
        "outputs": outputs,
        "worker": worker,
        "nextAction": next_action,
        "canOpenSmartDeck": bool(workflow.get("canOpenSmartDeck")),
        "canRetry": bool(workflow.get("canRetry")),
        "canRemove": can_remove,
        "phases": phases,
        "processingStatusUrl": f"/api/products/deck-aistack-codes/decks/{deck.id}/workflow-state",
        "smartDeckUrl": str(((workflow.get("links") or {}).get("smartDeckUrl")) or f"/decks/{deck.id}/smart-deck"),
        "retryUrl": f"/api/products/deck-aistack-codes/decks/{deck.id}/workflows/source-extraction",
        "persistedDeckStatus": persisted_deck_status,
    }


def _upload_payload(deck_file: DeckFile | None) -> dict:
    if deck_file is None:
        return {
            "sourceSaved": False,
            "fileId": None,
            "filename": None,
            "storagePath": None,
            "storageProvider": None,
            "sizeBytes": None,
            "checksumSha256": None,
            "uploadedAt": None,
        }

    return {
        "sourceSaved": True,
        "fileId": deck_file.id,
        "filename": deck_file.original_filename or deck_file.filename,
        "mimeType": deck_file.mime_type,
        "fileExtension": deck_file.file_extension,
        "storagePath": deck_file.storage_path,
        "storageProvider": deck_file.storage_provider,
        "sizeBytes": deck_file.size,
        "checksumSha256": deck_file.checksum_sha256,
        "uploadedAt": deck_file.uploaded_at.isoformat() if deck_file.uploaded_at else None,
    }


def _processing_payload(workflow: dict, deck_id: str, source_file_id: str | None) -> dict | None:
    active_job = workflow.get("activeJob") or None
    latest_jobs = workflow.get("latestJobs") or []
    selected_job = active_job or (latest_jobs[0] if latest_jobs else None)
    if selected_job is None:
        return None

    error_payload = selected_job.get("error") if isinstance(selected_job.get("error"), dict) else None
    source = workflow.get("source") or {}
    smart_deck = workflow.get("smartDeck") or {}
    provider = workflow.get("provider") or {}
    phase = str(selected_job.get("phase") or workflow.get("phase") or "upload_accepted")
    status = str(selected_job.get("status") or workflow.get("status") or "queued")

    return {
        "id": selected_job.get("jobId"),
        "runId": selected_job.get("jobId"),
        "workflowJobId": selected_job.get("jobId"),
        "workflowJobType": selected_job.get("jobType"),
        "workflowJobStatus": status,
        "workflowPhase": phase,
        "deckId": deck_id,
        "sourceFileId": source_file_id,
        "runType": "workflow_job",
        "status": status,
        "runStatus": status,
        "state": status,
        "stage": phase,
        "stageLabel": phase.replace("_", " ").title(),
        "nextAction": workflow.get("nextAction"),
        "attemptCount": selected_job.get("attemptCount"),
        "maxAttempts": selected_job.get("maxAttempts"),
        "recoveryCount": selected_job.get("recoveryCount"),
        "lockedBy": selected_job.get("workerId"),
        "lockedAt": selected_job.get("startedAt"),
        "heartbeatAt": selected_job.get("heartbeatAt"),
        "lastRecoveredAt": selected_job.get("lastRecoveredAt"),
        "lastRecoveredBy": selected_job.get("lastRecoveredBy"),
        "publishedPhase": selected_job.get("publishedPhase"),
        "publishedAt": selected_job.get("publishedAt"),
        "requiresManualReview": str(workflow.get("blockingReason") or "") not in {"", "provider_not_configured"} and not bool(workflow.get("canRetry")),
        "finalFailureReason": workflow.get("blockingReason") or selected_job.get("terminalReason"),
        "slideCount": source.get("slideCount"),
        "blockCount": None,
        "assetCount": source.get("assetCount"),
        "errorMessage": (error_payload or {}).get("message"),
        "errorJson": error_payload,
        "metadataJson": {
            "workflowId": workflow.get("workflowId"),
            "jobType": selected_job.get("jobType"),
            "phase": phase,
            "terminalReason": selected_job.get("terminalReason"),
        },
        "metricsJson": {
            "provider": provider,
            "smartDeck": smart_deck,
        },
        "createdAt": selected_job.get("queuedAt"),
        "startedAt": selected_job.get("startedAt"),
        "completedAt": selected_job.get("completedAt") or selected_job.get("failedAt"),
    }


def _worker_payload(processing: dict | None) -> dict:
    if processing is None:
        return {
            "workerRequired": False,
            "state": "not_started",
            "queueState": "not_queued",
            "runId": None,
            "workflowJobId": None,
            "workflowJobType": None,
            "workflowJobStatus": None,
            "queuedTooLong": False,
            "heartbeatStale": False,
            "staleReason": None,
            "message": "Workflow processing has not been started yet.",
            "oldestQueuedAt": None,
            "lastHeartbeatAt": None,
            "queuedAgeSeconds": None,
            "heartbeatAgeSeconds": None,
        }

    run_status = str(processing.get("runStatus") or processing.get("status") or "")
    queued_at = processing.get("createdAt")
    heartbeat_at = processing.get("heartbeatAt") or processing.get("startedAt") or queued_at
    queued_age_seconds = _age_seconds(queued_at)
    heartbeat_age_seconds = _age_seconds(heartbeat_at)
    queued_too_long = run_status == "queued" and (queued_age_seconds or 0) >= PROCESSING_QUEUED_STALE_SECONDS
    heartbeat_stale = run_status == "running" and heartbeat_age_seconds is not None and heartbeat_age_seconds >= PROCESSING_HEARTBEAT_STALE_SECONDS
    stale_reason = "queued_too_long" if queued_too_long else "heartbeat_stale" if heartbeat_stale else None

    if queued_too_long:
        state = "worker_not_running"
        message = "Workflow job is queued, but no worker has claimed it yet."
    elif heartbeat_stale:
        state = "worker_stalled"
        message = "Workflow job was claimed, but the worker heartbeat is stale."
    elif run_status == "queued":
        state = "queued"
        message = "Workflow job is queued and waiting for a worker."
    elif run_status == "running":
        state = "running"
        message = "Workflow job is running."
    elif run_status == "completed":
        state = "completed"
        message = "Workflow job completed."
    elif run_status in {"failed_retryable", "failed_final", "blocked", "timed_out"}:
        state = "failed"
        message = "Workflow job did not complete successfully."
    else:
        state = "review_status"
        message = "Workflow job status needs review."

    return {
        "workerRequired": run_status in {"queued", "running"},
        "state": state,
        "queueState": run_status,
        "runId": processing.get("workflowJobId") or processing.get("runId") or processing.get("id"),
        "workflowJobId": processing.get("workflowJobId") or processing.get("runId") or processing.get("id"),
        "workflowJobType": processing.get("workflowJobType")
        or ((processing.get("metadataJson") or {}).get("jobType") if isinstance(processing.get("metadataJson"), dict) else None),
        "workflowJobStatus": run_status,
        "recoveryCount": processing.get("recoveryCount"),
        "queuedTooLong": queued_too_long,
        "heartbeatStale": heartbeat_stale,
        "staleReason": stale_reason,
        "message": message,
        "oldestQueuedAt": queued_at if run_status == "queued" else None,
        "lastHeartbeatAt": heartbeat_at,
        "lastRecoveredAt": processing.get("lastRecoveredAt"),
        "lastRecoveredBy": processing.get("lastRecoveredBy"),
        "queuedAgeSeconds": queued_age_seconds,
        "heartbeatAgeSeconds": heartbeat_age_seconds,
    }


def _age_seconds(value: object) -> int | None:
    timestamp = _parse_datetime(value)
    if timestamp is None:
        return None
    return max(0, int((datetime.utcnow() - timestamp).total_seconds()))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is None else parsed.astimezone().replace(tzinfo=None)


def _output_counts(db: Session, deck_id: str) -> dict:
    return {
        "slideCount": db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id).count(),
        "blockCount": db.query(DeckSlideBlock).filter(DeckSlideBlock.deck_id == deck_id).count(),
        "assetCount": db.query(DeckSlideAsset).filter(DeckSlideAsset.deck_id == deck_id).count(),
        "previewCount": db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id, DeckSlide.thumbnail_path.isnot(None)).count(),
    }


def _phases(workflow: dict, outputs: dict) -> list[dict]:
    source = workflow.get("source") or {}
    phase = str(workflow.get("phase") or "upload_accepted")
    latest_jobs = workflow.get("latestJobs") or []
    completed_job_types = {
        str(job.get("jobType"))
        for job in latest_jobs
        if str(job.get("status") or "") == "completed"
    }
    downstream_source_completion = {"source_extraction", "miniatures", "brand_extraction", "smart_deck_context", "db_publisher"}
    phase_status = {
        "source_saved": "completed" if bool(source.get("fileSaved")) or "source_ingestion" in completed_job_types else "pending",
        "source_extraction": "completed" if bool(downstream_source_completion & completed_job_types) else "active" if phase in {"source_extraction_queued", "source_extraction_running"} else "pending",
        "miniatures": "completed" if int(source.get("thumbnailCount") or 0) > 0 or "miniatures" in completed_job_types else "active" if phase in {"miniatures_queued", "miniatures_running"} else "pending",
        "smart_deck_ready": "completed" if bool((workflow.get("smartDeck") or {}).get("ready")) else "active" if phase in {"smart_deck_context_queued", "smart_deck_context_running", "db_publisher_queued", "db_publisher_running"} else "pending",
        "brand_extraction": "completed" if "brand_extraction" in completed_job_types else "active" if phase in {"brand_extraction_queued", "brand_extraction_running"} else "pending",
    }

    counts = {
        "source_saved": int(source.get("fileSaved") or 0),
        "source_extraction": int(outputs.get("slideCount") or 0),
        "miniatures": int(source.get("thumbnailCount") or 0),
        "brand_extraction": int(bool(source.get("brandExtractionReady"))),
        "smart_deck_ready": int(bool((workflow.get("smartDeck") or {}).get("ready"))),
    }

    return [
        {
            "key": item["key"],
            "label": item["label"],
            "description": item.get("description"),
            "status": phase_status[item["key"]],
            "active": phase_status[item["key"]] == "active",
            "completed": phase_status[item["key"]] == "completed",
            "count": counts[item["key"]],
        }
        for item in PHASES
        if item["key"] != "miniatures" or source.get("thumbnailsRequired", True)
    ]
