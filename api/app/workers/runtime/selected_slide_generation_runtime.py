"""Selected-slide generation workflow handler.

Groups selected source slides into deterministic batches for a targeted
generation request, with bounded concurrency and per-slide validation.

Audit note: the paired service now calls the configured LLM provider when
available and normalizes source_fact_ids. It still writes a workflow manifest,
not final SmartDeckSuggestion rows; persistence of accept/reject suggestions is
handled by the Smart Edit path until a canonical SmartDeckContext endpoint lands.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Deck
from app.services.llm.generation_service import get_generation_provider_config
from app.services.llm.selected_slide_generation_service import (
    build_selected_slide_batches,
    summarize_slide_generation_manifest,
    summarize_slide_generation_result,
)
from app.services.deck_processing.workflow_jobs import JOB_STATUS_COMPLETED, record_workflow_artifact, set_workflow_job_status
from app.services.storage.signed_urls import get_bucket_artifact_service


def handle_selected_slide_generation(db: Session, job, *, worker_id: str) -> None:
    """Create and persist a selected-slide generation manifest for diagnostics."""
    payload = dict(job.input_json or {})
    prompt = str(payload.get("prompt") or "").strip()
    selected_source_slide_ids = list(payload.get("selectedSourceSlideIds") or [])
    partition_count = int(payload.get("partitionCount") or 1)
    batch_size = int(payload.get("batchSize") or 8)
    preferred_model = str(payload.get("preferredModel") or "").strip() or None

    deck = db.query(Deck).filter(Deck.id == job.deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    if not prompt:
        raise ValueError("Selected-slide generation requires a prompt.")
    if not selected_source_slide_ids:
        raise ValueError("Selected-slide generation requires at least one selected source slide.")

    plan = build_selected_slide_batches(
        db,
        deck=deck,
        selected_source_slide_ids=selected_source_slide_ids,
        prompt=prompt,
        partition_count=partition_count,
        batch_size=batch_size,
    )
    tasks = plan["tasks"]
    if not tasks:
        raise ValueError("Selected-slide generation did not build any tasks.")

    provider_config = get_generation_provider_config(
        db,
        deck,
        preferred_model=preferred_model,
        strict=False,
        use_case="selected_slide_generation",
    )
    max_workers = max(1, min(settings.max_concurrent_slide_generations, len(tasks)))
    results_by_index: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="selected-slide") as executor:
        futures = {
            executor.submit(
                summarize_slide_generation_result,
                task,
                prompt=plan["prompt"],
                provider_config=provider_config,
            ): index
            for index, task in enumerate(tasks)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results_by_index[index] = future.result()
            except Exception:
                if not settings.allow_partial_batch_success:
                    raise
                task = tasks[index]
                results_by_index[index] = {
                    "taskId": task.get("taskId"),
                    "batchIndex": task.get("batchIndex"),
                    "slideIds": task.get("slideIds", []),
                    "slideTitles": [slide.get("title") for slide in task.get("slides", []) if isinstance(slide, dict)],
                    "slideCount": len(task.get("slides", [])),
                    "summary": "This selected-slide batch could not be analyzed.",
                    "status": "failed",
                    "errorCode": "selected_slide_batch_failed",
                }
    results = [results_by_index[index] for index in range(len(tasks))]

    manifest = summarize_slide_generation_manifest(tasks, results)
    artifact_payload = {
        "schemaVersion": "selected-slide-generation.v1",
        "deckId": deck.id,
        "jobId": job.id,
        "plan": {key: value for key, value in plan.items() if key != "tasks"},
        "tasks": tasks,
        "results": results,
        "summary": manifest,
    }
    artifact_content = json.dumps(artifact_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    artifact_hash = hashlib.sha256(artifact_content).hexdigest()
    bucket_service = get_bucket_artifact_service()
    artifact_key = bucket_service.make_llm_artifact_key(
        user_id=deck.user_id or "unknown-user",
        deck_id=deck.id,
        artifact_id=f"selected-slide-generation-{job.id}",
    )
    bucket_service.put_json_sync(key=artifact_key, data=artifact_payload)
    record_workflow_artifact(
        db,
        job=job,
        artifact_type="selected_slide_generation_manifest",
        storage_key=artifact_key,
        content_hash=artifact_hash,
        metadata={
            "deckId": deck.id,
            "partitionCount": plan["partitionCount"],
            "batchSize": plan["batchSize"],
            "taskCount": manifest["taskCount"],
            "resultCount": manifest["resultCount"],
            "failedTaskCount": manifest["failedTaskCount"],
            "contentType": "application/json",
        },
    )
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Selected-slide generation completed.",
        published_phase=None,
        output_payload={
            "phase": "selected_slide_generation_ready",
            "selectedSlideGeneration": {
                "deckId": deck.id,
                "deckTitle": deck.title,
                "prompt": plan["prompt"],
                "partitionCount": plan["partitionCount"],
                "batchSize": plan["batchSize"],
                "selectedSourceSlideIds": plan["selectedSourceSlideIds"],
                "taskCount": manifest["taskCount"],
                "resultCount": manifest["resultCount"],
                "failedTaskCount": manifest["failedTaskCount"],
                "artifactStorageKey": artifact_key,
            },
            "tasks": tasks,
            "results": results,
            "summary": manifest,
        },
    )
    db.commit()
