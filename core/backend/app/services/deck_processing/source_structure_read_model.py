"""Source structure read model.

Owns the canonical deck-structure frontend-facing read surface.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.db.models import Deck, DeckFile, DeckSlide, DeckSlideAsset, DeckSlideBlock, WorkflowJob
from app.services.deck_processing.source_slide_payload import map_source_slide_payload
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state
from app.services.deck_processing.workflow_jobs import list_workflow_jobs_for_deck


WORKFLOW_FAILED_STATUSES = {"failed_retryable", "failed_final", "blocked", "timed_out"}
WORKFLOW_READY_PHASES = {"source_ready", "smart_deck_ready", "preview_ready", "applied", "export_ready"}


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.file),
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _job_output(job: WorkflowJob | None) -> dict | None:
    if job is None or not isinstance(job.output_json, dict):
        return None
    return dict(job.output_json)


def _workflow_backed_deck_state(db: Session, deck: Deck, workflow: dict | None = None) -> str:
    workflow = workflow or get_deck_workflow_state(db, deck.id)
    if workflow is None:
        return canonical_deck_state(deck.status).value

    workflow_status = str(workflow.get("status") or "")
    workflow_phase = str(workflow.get("phase") or "")

    if workflow.get("canOpenSmartDeck") or workflow_phase in WORKFLOW_READY_PHASES:
        return DeckState.READY.value
    if workflow_status in WORKFLOW_FAILED_STATUSES:
        return DeckState.FAILED.value
    if workflow_phase in {"upload_accepted", "source_file_saved"}:
        return DeckState.UPLOADED.value
    if workflow.get("activeJob") or workflow.get("latestJobs"):
        return DeckState.PROCESSING.value
    return canonical_deck_state(deck.status).value


def _latest_source_pipeline_job(db: Session, deck_id: str) -> WorkflowJob | None:
    job_types = {
        "source_ingestion",
        "source_extraction",
        "miniatures",
        "brand_extraction",
        "smart_deck_context",
        "db_publisher",
    }
    for job in list_workflow_jobs_for_deck(db, deck_id):
        if job.job_type in job_types:
            return job
    return None


def _source_workspace_from_workflow_jobs(db: Session, deck_id: str) -> dict | None:
    for job_type in ("smart_deck_context", "db_publisher"):
        for job in list_workflow_jobs_for_deck(db, deck_id):
            if job.job_type != job_type:
                continue
            output = _job_output(job) or {}
            source_workspace = output.get("sourceWorkspace")
            if isinstance(source_workspace, dict):
                return source_workspace
    return None


def _source_enrichment_from_workspace(source_workspace: dict | None) -> dict | None:
    if not source_workspace:
        return None
    return {
        "source": source_workspace.get("enrichmentSource"),
        "llmStatus": source_workspace.get("llmStatus"),
        "provider": source_workspace.get("llmProvider"),
        "model": source_workspace.get("llmModel"),
    }


def _workflow_job_refs_by_extraction_run(db: Session, extraction_run_ids: list[str]) -> dict[str, dict[str, str | None]]:
    run_ids = [run_id for run_id in extraction_run_ids if isinstance(run_id, str) and run_id]
    if not run_ids:
        return {}

    mapping: dict[str, dict[str, str | None]] = {}
    query_jobs = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.extraction_run_id.in_(run_ids))
        .order_by(WorkflowJob.created_at.desc())
        .all()
    )
    for job in query_jobs:
        if job.extraction_run_id and job.extraction_run_id not in mapping:
            mapping[job.extraction_run_id] = {
                "workflowJobId": job.id,
                "workflowJobType": job.job_type,
            }
    return mapping


def _legacy_extraction_run_from_workflow_jobs(db: Session, deck_id: str) -> dict | None:
    job = _latest_source_pipeline_job(db, deck_id)
    if job is None:
        return None
    output = _job_output(job) or {}
    source_workspace = output.get("sourceWorkspace")
    source_enrichment = _source_enrichment_from_workspace(source_workspace if isinstance(source_workspace, dict) else None)
    phase = output.get("publishedPhase") or output.get("phase")
    return {
        "id": job.id,
        "workflowId": f"deckwf_{deck_id}",
        "workflowJobId": job.id,
        "workflowJobType": job.job_type,
        "workflowJobStatus": job.status,
        "workflowPhase": phase if isinstance(phase, str) else None,
        "status": job.status,
        "sourceFormat": output.get("sourceFormat"),
        "slideCount": output.get("slideCount"),
        "blockCount": output.get("blockCount"),
        "assetCount": output.get("assetCount"),
        "errorMessage": job.error_message,
        "sourceWorkspace": source_workspace if isinstance(source_workspace, dict) else None,
        "sourceEnrichment": source_enrichment,
        "metricsJson": output or None,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
    }


def get_deck_structure(db: Session, deck_id: str) -> dict:
    deck = _load_deck(db, deck_id)
    if deck is None:
        raise ValueError("Deck not found")

    workflow = get_deck_workflow_state(db, deck.id) or {}
    source_workspace = _source_workspace_from_workflow_jobs(db, deck.id)
    source_enrichment = _source_enrichment_from_workspace(source_workspace)
    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    deck_state = _workflow_backed_deck_state(db, deck, workflow)
    extraction_run_ids = [
        run_id
        for run_id in {
            *[slide.extraction_run_id for slide in slides if slide.extraction_run_id],
            *[asset.extraction_run_id for slide in slides for asset in slide.assets if asset.extraction_run_id],
        }
    ]
    workflow_refs = _workflow_job_refs_by_extraction_run(db, extraction_run_ids)
    return {
        "deckId": deck.id,
        "title": deck.title,
        "workflowId": workflow.get("workflowId"),
        "workflowPhase": workflow.get("phase"),
        "workflowStatus": workflow.get("status"),
        "status": deck_state,
        "state": deck_state,
        "deckStatus": deck_state,
        "sourceWorkspace": source_workspace,
        "sourceEnrichment": source_enrichment,
        "sourceFile": {
            "id": deck.file.id if deck.file else None,
            "filename": deck.file.original_filename or deck.file.filename if deck.file else None,
            "mimeType": deck.file.mime_type if deck.file else None,
            "pageCount": deck.file.page_count if deck.file else None,
        },
        "extractionRun": _legacy_extraction_run_from_workflow_jobs(db, deck.id),
        "slides": [
            {
                "id": slide.id,
                "extractionRunId": slide.extraction_run_id,
                "workflowJobId": (workflow_refs.get(slide.extraction_run_id or "") or {}).get("workflowJobId"),
                "workflowJobType": (workflow_refs.get(slide.extraction_run_id or "") or {}).get("workflowJobType"),
                **map_source_slide_payload(slide),
                "assets": [
                    {
                        **asset_payload,
                        "workflowJobId": (workflow_refs.get(asset_payload.get("extractionRunId") or "") or {}).get("workflowJobId"),
                        "workflowJobType": (workflow_refs.get(asset_payload.get("extractionRunId") or "") or {}).get("workflowJobType"),
                    }
                    for asset_payload in map_source_slide_payload(slide)["assets"]
                ],
            }
            for slide in slides
        ],
    }


__all__ = ["get_deck_structure", "map_source_slide_payload"]
