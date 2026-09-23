"""Durable handlers for the canonical Deck Map and Market Research services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import WorkflowJob
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    record_workflow_artifact,
    set_workflow_job_status,
)
from app.services.llm.deck_map_analysis_service import (
    DECK_MAP_ANALYSIS_ARTIFACT_TYPE,
    analyze_deck_map,
)
from app.services.llm.market_research_service import (
    MARKET_RESEARCH_ARTIFACT_TYPE,
    generate_market_research,
)


def _complete_intelligence_job(
    db: Session,
    job: WorkflowJob,
    *,
    worker_id: str,
    result: dict,
    result_key: str,
    artifact_type: str,
    ready_phase: str,
) -> None:
    payload = result.get(result_key)
    artifact_id = str(result.get("runId") or "").strip()
    if result.get("status") != "completed" or not isinstance(payload, dict) or not artifact_id:
        raise RuntimeError(f"{job.job_type.replace('_', ' ').title()} did not persist a result")
    record_workflow_artifact(
        db,
        job=job,
        artifact_type=artifact_type,
        storage_key=f"deck-llm-artifact:{artifact_id}",
        metadata={"deckId": job.deck_id, "artifactId": artifact_id, "cached": bool(result.get("cached"))},
    )
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message=f"{job.job_type.replace('_', ' ').title()} persisted.",
        output_payload={
            "phase": ready_phase,
            "runId": artifact_id,
            "deckId": job.deck_id,
            "status": "completed",
            "cached": bool(result.get("cached")),
            result_key: payload,
            "artifactType": artifact_type,
        },
    )
    db.commit()


def handle_deck_map_analysis(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    result = analyze_deck_map(db, job.deck_id)
    _complete_intelligence_job(
        db,
        job,
        worker_id=worker_id,
        result=result,
        result_key="analysis",
        artifact_type=DECK_MAP_ANALYSIS_ARTIFACT_TYPE,
        ready_phase="deck_map_analysis_ready",
    )


def handle_market_research(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    public_request = (job.input_json or {}).get("publicResearch")
    paid_request = (job.input_json or {}).get("paidPublicResearch")
    if paid_request is not None:
        from app.services.llm.investor_public_research import discover_public_research
        result = discover_public_research(db, job.deck_id, paid_request)
    elif public_request is not None:
        from app.services.llm.investor_public_research import collect_public_research
        result = collect_public_research(db, job.deck_id, public_request)
    else:
        result = generate_market_research(db, job.deck_id)
    _complete_intelligence_job(
        db,
        job,
        worker_id=worker_id,
        result=result,
        result_key="research",
        artifact_type="instant_deck_verified_public_research" if public_request is not None or paid_request is not None else MARKET_RESEARCH_ARTIFACT_TYPE,
        ready_phase="market_research_ready",
    )
