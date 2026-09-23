from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DeckLlmArtifact
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.workflow_jobs import list_workflow_jobs_for_deck

DEFAULT_ARTIFACT_LIMIT = 100
MAX_ARTIFACT_LIMIT = 250


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()  # type: ignore[no-any-return]
        except TypeError:
            return str(value)
    return str(value)


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _storage_pointer(payload_json: dict, bucket_payload_key: str | None) -> dict[str, str | None]:
    storage_path = (
        bucket_payload_key
        or payload_json.get("storagePath")
        or payload_json.get("bucketPayloadKey")
        or payload_json.get("bucketRenderSchemaKey")
        or payload_json.get("bucketCodeJsonKey")
        or payload_json.get("bucketManifestKey")
        or payload_json.get("canonicalStoragePath")
    )
    storage_provider = (
        payload_json.get("storageProvider")
        or payload_json.get("renderSchemaStorageProvider")
        or payload_json.get("codeJsonStorageProvider")
    )
    content_type = payload_json.get("contentType")
    return {
        "provider": storage_provider if isinstance(storage_provider, str) else None,
        "path": storage_path if isinstance(storage_path, str) else None,
        "contentType": content_type if isinstance(content_type, str) else None,
    }


def _latest_workflow_job_ref(db: Session, deck_id: str) -> tuple[str | None, str | None]:
    jobs = list_workflow_jobs_for_deck(db, deck_id)
    if not jobs:
        return None, None
    latest = jobs[0]
    return latest.id, latest.job_type


def _workflow_job_refs_by_extraction_run(db: Session, deck_id: str) -> dict[str, dict[str, str | None]]:
    jobs = list_workflow_jobs_for_deck(db, deck_id)
    mapping: dict[str, dict[str, str | None]] = {}
    for job in jobs:
        if job.extraction_run_id and job.extraction_run_id not in mapping:
            mapping[job.extraction_run_id] = {
                "workflowJobId": job.id,
                "workflowJobType": job.job_type,
            }
    return mapping


def _map_artifact(artifact: DeckLlmArtifact, workflow_ref: dict[str, str | None] | None = None) -> dict:
    payload_json = _as_dict(artifact.payload_json)
    metrics_json = _as_dict(artifact.metrics_json)
    storage = _storage_pointer(payload_json, artifact.bucket_payload_key)
    mapped = {
        "id": artifact.id,
        "deckId": artifact.deck_id,
        "deck_id": artifact.deck_id,
        "extractionRunId": artifact.extraction_run_id,
        "extraction_run_id": artifact.extraction_run_id,
        "workflowJobId": (workflow_ref or {}).get("workflowJobId"),
        "workflowJobType": (workflow_ref or {}).get("workflowJobType"),
        "artifactType": artifact.artifact_type,
        "artifact_type": artifact.artifact_type,
        "artifactKey": artifact.artifact_key,
        "artifact_key": artifact.artifact_key,
        "schemaVersion": artifact.schema_version,
        "schema_version": artifact.schema_version,
        "status": artifact.status,
        "summary": artifact.summary,
        "payloadJson": payload_json,
        "payload_json": payload_json,
        "bucketPayloadKey": artifact.bucket_payload_key,
        "bucket_payload_key": artifact.bucket_payload_key,
        "metrics": metrics_json,
        "metricsJson": metrics_json,
        "metrics_json": metrics_json,
        "storage": storage,
        "createdAt": _iso(artifact.created_at),
        "created_at": _iso(artifact.created_at),
        "updatedAt": _iso(artifact.updated_at),
        "updated_at": _iso(artifact.updated_at),
    }
    # Backwards-compatible fields used by diagnostic panels. The list endpoint does not sign
    # bucket URLs so it remains safe during storage outages and cannot turn page load into a 500.
    mapped["artifactUrl"] = None
    mapped["artifact_url"] = None
    mapped["artifactUrlStatus"] = "not_signed"
    return mapped


def list_deck_llm_artifacts(
    db: Session,
    deck_id: str,
    *,
    artifact_type: str | None = None,
    limit: int = DEFAULT_ARTIFACT_LIMIT,
) -> dict:
    bounded_limit = max(1, min(int(limit or DEFAULT_ARTIFACT_LIMIT), MAX_ARTIFACT_LIMIT))
    query = db.query(DeckLlmArtifact).filter(DeckLlmArtifact.deck_id == deck_id)
    if artifact_type:
        query = query.filter(DeckLlmArtifact.artifact_type == artifact_type)

    artifacts = (
        query.order_by(DeckLlmArtifact.created_at.desc(), DeckLlmArtifact.id.desc())
        .limit(bounded_limit)
        .all()
    )
    workflow_refs = _workflow_job_refs_by_extraction_run(db, deck_id)
    mapped_artifacts = [
        _map_artifact(artifact, workflow_refs.get(artifact.extraction_run_id or ""))
        for artifact in artifacts
    ]
    latest_by_type: dict[str, dict] = {}
    for artifact in mapped_artifacts:
        latest_by_type.setdefault(artifact["artifactType"], artifact)
    latest_workflow_job_id, latest_workflow_job_type = _latest_workflow_job_ref(db, deck_id)
    workflow = get_deck_workflow_state(db, deck_id) or {}

    effective_status = workflow.get("status") or "pending"

    return {
        "deckId": deck_id,
        "deck_id": deck_id,
        "workflowId": workflow.get("workflowId"),
        "workflowPhase": workflow.get("phase"),
        "workflowStatus": workflow.get("status"),
        "workflowJobId": latest_workflow_job_id,
        "workflowJobType": latest_workflow_job_type,
        # Artifact availability is independent from workflow readiness.
        "status": effective_status,
        "artifactsAvailable": bool(mapped_artifacts),
        "degraded": False,
        "artifacts": mapped_artifacts,
        "latestArtifacts": latest_by_type,
        "latest_artifacts": latest_by_type,
        "counts": {
            "total": len(mapped_artifacts),
            "byType": dict(Counter(artifact["artifactType"] for artifact in mapped_artifacts)),
            "byStatus": dict(Counter(artifact["status"] for artifact in mapped_artifacts)),
        },
        "limit": bounded_limit,
        "artifactType": artifact_type,
        "artifact_type": artifact_type,
    }
