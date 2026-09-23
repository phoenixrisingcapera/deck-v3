from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import AgentLearningMemory, AgentRegressionCase, AgentTelemetryEvent, User, WorkflowJob
from app.db.session import AiSessionLocal
from app.observability import current_trace_context

SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "generated_output",
    "output",
    "password",
    "prompt",
    "provider_api_key",
    "raw_slide_text",
    "raw_text",
    "secret",
    "token",
    "user_email",
    "user_instruction",
}

MAX_REDACTED_ERROR_LENGTH = 500
MAX_STRING_METADATA_LENGTH = 500
MAX_OPERATOR_NOTE_LENGTH = 500


def redact_telemetry_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_KEYS:
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = redact_telemetry_value(nested)
        return redacted
    if isinstance(value, list):
        return [redact_telemetry_value(item) for item in value[:50]]
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_METADATA_LENGTH else f"{value[:MAX_STRING_METADATA_LENGTH]}..."
    return value


def redact_error_message(message: str | None) -> str | None:
    if not message:
        return None
    cleaned = " ".join(str(message).split())
    return cleaned if len(cleaned) <= MAX_REDACTED_ERROR_LENGTH else f"{cleaned[:MAX_REDACTED_ERROR_LENGTH]}..."


def record_agent_event(
    db: Session,
    *,
    event_name: str,
    run_type: str,
    workspace_id: str | None = None,
    deck_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    event_level: str = "info",
    status: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_cents: float | None = None,
    error_category: str | None = None,
    error_message: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> AgentTelemetryEvent | None:
    telemetry_db = db
    owns_telemetry_session = False
    if str(settings.ai_database_url or "").strip() and db.get_bind().dialect.name != "sqlite":
        telemetry_db = AiSessionLocal()
        owns_telemetry_session = True
    try:
        trace_context = current_trace_context()
        event = AgentTelemetryEvent(
            id=generate_id("telemetry"),
            workspace_id=workspace_id,
            deck_id=deck_id,
            user_id=user_id,
            run_id=run_id,
            run_type=run_type,
            step_id=step_id,
            event_name=event_name,
            event_level=event_level,
            status=status,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_cents=estimated_cost_cents,
            error_category=error_category,
            error_message_redacted=redact_error_message(error_message),
            trace_id=trace_id or trace_context.get("trace_id"),
            span_id=span_id or trace_context.get("span_id"),
            request_id=request_id,
            metadata_json=redact_telemetry_value(metadata or {}),
            created_at=datetime.utcnow(),
        )
        telemetry_db.add(event)
        if commit or owns_telemetry_session:
            telemetry_db.commit()
            telemetry_db.refresh(event)
        return event
    except Exception:
        telemetry_db.rollback()
        return None
    finally:
        if owns_telemetry_session:
            telemetry_db.close()


def record_run_started(db: Session, *, run_id: str, run_type: str, workspace_id: str | None, deck_id: str | None, user_id: str | None, provider: str | None = None, model: str | None = None, metadata: dict[str, Any] | None = None) -> AgentTelemetryEvent | None:
    return record_agent_event(
        db,
        event_name="ai.run.started",
        run_type=run_type,
        workspace_id=workspace_id,
        deck_id=deck_id,
        user_id=user_id,
        run_id=run_id,
        status="running",
        provider=provider,
        model=model,
        metadata=metadata,
    )


def record_run_failed(db: Session, *, run_id: str, run_type: str, workspace_id: str | None, deck_id: str | None, user_id: str | None, provider: str | None = None, model: str | None = None, error_category: str = "unknown_error", error_message: str | None = None, metadata: dict[str, Any] | None = None) -> AgentTelemetryEvent | None:
    return record_agent_event(
        db,
        event_name="ai.run.failed",
        run_type=run_type,
        workspace_id=workspace_id,
        deck_id=deck_id,
        user_id=user_id,
        run_id=run_id,
        event_level="error",
        status="failed",
        provider=provider,
        model=model,
        error_category=error_category,
        error_message=error_message,
        metadata=metadata,
    )


def list_agent_telemetry_events(
    db: Session,
    *,
    limit: int = 100,
    run_id: str | None = None,
    deck_id: str | None = None,
    run_type: str | None = None,
    status: str | None = None,
    event_name: str | None = None,
) -> dict[str, Any]:
    query = db.query(AgentTelemetryEvent).order_by(AgentTelemetryEvent.created_at.desc())
    if run_id:
        query = query.filter(AgentTelemetryEvent.run_id == run_id)
    if deck_id:
        query = query.filter(AgentTelemetryEvent.deck_id == deck_id)
    if run_type:
        query = query.filter(AgentTelemetryEvent.run_type == run_type)
    if status:
        query = query.filter(AgentTelemetryEvent.status == status)
    if event_name:
        query = query.filter(AgentTelemetryEvent.event_name == event_name)

    events = query.limit(limit).all()
    status_counts = dict(db.query(AgentTelemetryEvent.status, func.count(AgentTelemetryEvent.id)).group_by(AgentTelemetryEvent.status).all())
    event_counts = dict(db.query(AgentTelemetryEvent.event_name, func.count(AgentTelemetryEvent.id)).group_by(AgentTelemetryEvent.event_name).all())
    return {
        "summary": {
            "total": db.query(AgentTelemetryEvent).count(),
            "returned": len(events),
            "statusCounts": {str(key or "unknown"): value for key, value in status_counts.items()},
            "eventCounts": {str(key): value for key, value in event_counts.items()},
        },
        "events": [_serialize_event(event) for event in events],
        "redaction": {
            "detailPolicy": "Agent telemetry stores IDs, statuses, counts, timings, and redacted metadata only. Raw prompts, raw slide text, and generated outputs are not stored here.",
        },
    }


def get_agent_telemetry_run_detail(db: Session, run_id: str) -> dict[str, Any] | None:
    events = (
        db.query(AgentTelemetryEvent)
        .filter(AgentTelemetryEvent.run_id == run_id)
        .order_by(AgentTelemetryEvent.created_at.asc())
        .all()
    )
    if not events:
        return None

    first = events[0]
    failed_events = [event for event in events if _is_failure_event(event)]
    return {
        "run": {
            "runId": run_id,
            "runType": first.run_type,
            "workspaceId": first.workspace_id,
            "deckId": first.deck_id,
            "userId": first.user_id,
            "status": events[-1].status,
            "provider": first.provider,
            "model": first.model,
            "eventCount": len(events),
            "failureCount": len(failed_events),
            "startedAt": events[0].created_at.isoformat(),
            "lastEventAt": events[-1].created_at.isoformat(),
        },
        "events": [_serialize_event(event) for event in events],
        "redaction": {
            "detailPolicy": "Run telemetry detail is assembled from the redacted AgentTelemetryEvent stream only.",
        },
    }


def get_agent_telemetry_metrics(db: Session) -> dict[str, Any]:
    total = db.query(AgentTelemetryEvent).count()
    failure_count = _failure_query(db).count()
    completed_count = db.query(AgentTelemetryEvent).filter(AgentTelemetryEvent.status == "completed").count()
    running_count = db.query(AgentTelemetryEvent).filter(AgentTelemetryEvent.status == "running").count()
    avg_latency = db.query(func.avg(AgentTelemetryEvent.latency_ms)).filter(AgentTelemetryEvent.latency_ms.isnot(None)).scalar()

    return {
        "summary": {
            "totalEvents": total,
            "failedEvents": failure_count,
            "completedEvents": completed_count,
            "runningEvents": running_count,
            "averageLatencyMs": round(float(avg_latency)) if avg_latency is not None else None,
        },
        "runTypeCounts": _count_by(db, AgentTelemetryEvent.run_type),
        "providerCounts": _count_by(db, AgentTelemetryEvent.provider),
        "statusCounts": _count_by(db, AgentTelemetryEvent.status),
        "eventCounts": _count_by(db, AgentTelemetryEvent.event_name),
        "failureCategoryCounts": _count_by(_failure_query(db), AgentTelemetryEvent.error_category),
        "extraction": _deck_extraction_metrics(db),
    }


def _deck_extraction_metrics(db: Session) -> dict[str, Any]:
    source_job_types = {
        "source_ingestion",
        "source_extraction",
        "miniatures",
        "brand_extraction",
        "smart_deck_context",
        "db_publisher",
    }
    jobs = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.job_type.in_(tuple(source_job_types)))
        .all()
    )
    source_runs = [job for job in jobs if job.job_type == "source_extraction"]
    failed_runs = [job for job in source_runs if job.status in {"failed_retryable", "failed_final", "blocked", "timed_out"} or job.error_message]
    active_runs = [job for job in source_runs if job.status in {"queued", "running", "failed_retryable"}]
    partial_error_count = 0
    slides_with_partial_errors = 0
    text_source_counts: dict[str, int] = {}
    asset_type_counts: dict[str, int] = {}
    worker_counts: dict[str, int] = {}
    source_format_counts: dict[str, int] = {}

    for job in jobs:
        output = job.output_json if isinstance(job.output_json, dict) else {}
        input_payload = job.input_json if isinstance(job.input_json, dict) else {}
        partial_error_count += _safe_int(output.get("partialErrorCount"))
        slides_with_partial_errors += _safe_int(output.get("slidesWithPartialErrors"))
        _merge_counts(text_source_counts, output.get("textSourceCounts"))
        _merge_counts(asset_type_counts, output.get("assetTypeCounts"))
        worker_id = str(job.locked_by or "").strip()
        if worker_id:
            worker_counts[worker_id] = worker_counts.get(worker_id, 0) + 1
        source_format = str(output.get("sourceFormat") or input_payload.get("sourceFormat") or "").strip()
        if source_format:
            source_format_counts[source_format] = source_format_counts.get(source_format, 0) + 1

    return {
        "summary": {
            "totalRuns": len(source_runs),
            "completedRuns": sum(1 for job in source_runs if job.status == "completed"),
            "failedRuns": len(failed_runs),
            "activeRuns": len(active_runs),
            "totalSlides": sum(_safe_int((job.output_json or {}).get("slideCount")) for job in source_runs),
            "totalBlocks": sum(_safe_int((job.output_json or {}).get("blockCount")) for job in source_runs),
            "totalAssets": sum(_safe_int((job.output_json or {}).get("assetCount")) for job in source_runs),
            "partialErrorCount": partial_error_count,
            "slidesWithPartialErrors": slides_with_partial_errors,
        },
        "statusCounts": _count_model_by(db, WorkflowJob, WorkflowJob.status),
        "runTypeCounts": _count_model_by(db, WorkflowJob, WorkflowJob.job_type),
        "extractorCounts": dict(sorted(worker_counts.items())),
        "sourceFormatCounts": dict(sorted(source_format_counts.items())),
        "textSourceCounts": dict(sorted(text_source_counts.items())),
        "assetTypeCounts": dict(sorted(asset_type_counts.items())),
    }


def list_agent_telemetry_failures(
    db: Session,
    *,
    limit: int = 100,
    run_type: str | None = None,
    deck_id: str | None = None,
) -> dict[str, Any]:
    query = _failure_query(db)
    if run_type:
        query = query.filter(AgentTelemetryEvent.run_type == run_type)
    if deck_id:
        query = query.filter(AgentTelemetryEvent.deck_id == deck_id)
    events = query.order_by(AgentTelemetryEvent.created_at.desc()).limit(limit).all()
    return {
        "summary": {
            "totalFailures": _failure_query(db).count(),
            "returned": len(events),
        },
        "failures": [_serialize_event(event) for event in events],
        "redaction": {
            "detailPolicy": "Failure telemetry includes redacted error categories/messages and safe metadata only.",
        },
    }


def promote_telemetry_failure_to_learning_memory(
    db: Session,
    *,
    event_id: str,
    actor: User | None = None,
    note: str | None = None,
    commit: bool = True,
) -> dict[str, Any] | None:
    event = db.get(AgentTelemetryEvent, event_id)
    if event is None:
        return None
    if not _is_failure_event(event):
        raise ValueError("Only failed telemetry events can be promoted to learning memory.")

    existing = (
        db.query(AgentLearningMemory)
        .filter(
            AgentLearningMemory.source_run_id == event.id,
            AgentLearningMemory.memory_type == "reflection",
        )
        .one_or_none()
    )
    title, content, evidence = _learning_memory_from_event(event, note=note)
    if existing is not None:
        existing.title = title
        existing.content = content
        existing.evidence_json = evidence
        existing.feedback_label = "failure"
        existing.score = min(existing.score, -1)
        existing.updated_at = datetime.utcnow()
        memory = existing
    else:
        memory = AgentLearningMemory(
            id=generate_id("learn"),
            workspace_id=event.workspace_id,
            deck_id=event.deck_id,
            user_id=event.user_id,
            source_run_id=event.id,
            source_run_type=event.run_type,
            memory_type="reflection",
            status="active",
            feedback_label="failure",
            score=-1,
            title=title,
            content=content,
            tags_json=["telemetry", "failure", event.run_type],
            evidence_json=evidence,
            created_by_user_id=actor.id if actor is not None else None,
        )
        db.add(memory)

    if commit:
        db.commit()
        db.refresh(memory)
    return {"memory": _serialize_learning_memory(memory)}


def promote_telemetry_failure_to_regression_case(
    db: Session,
    *,
    event_id: str,
    actor: User | None = None,
    note: str | None = None,
    commit: bool = True,
) -> dict[str, Any] | None:
    event = db.get(AgentTelemetryEvent, event_id)
    if event is None:
        return None
    if not _is_failure_event(event):
        raise ValueError("Only failed telemetry events can be promoted to regression cases.")

    existing = db.query(AgentRegressionCase).filter(AgentRegressionCase.source_event_id == event.id).one_or_none()
    title = _regression_case_title(event)
    fixture = _regression_fixture_from_event(event)
    clean_note = _clean_operator_note(note)
    if existing is not None:
        existing.title = title
        existing.fixture_json = fixture
        existing.notes = clean_note
        existing.updated_at = datetime.utcnow()
        case = existing
    else:
        case = AgentRegressionCase(
            id=generate_id("regress"),
            source_event_id=event.id,
            workspace_id=event.workspace_id,
            deck_id=event.deck_id,
            user_id=event.user_id,
            run_id=event.run_id,
            run_type=event.run_type,
            event_name=event.event_name,
            case_name=title,
            case_type="failure_reproduction",
            status="active",
            failure_category=event.error_category,
            title=title,
            fixture_json=fixture,
            notes=clean_note,
            created_by_user_id=actor.id if actor is not None else None,
        )
        db.add(case)

    if commit:
        db.commit()
        db.refresh(case)
    return {"regressionCase": _serialize_regression_case(case)}


def _failure_query(db: Session):
    return db.query(AgentTelemetryEvent).filter(
        or_(
            AgentTelemetryEvent.status == "failed",
            AgentTelemetryEvent.event_level == "error",
            AgentTelemetryEvent.event_name.like("%.failed"),
        )
    )


def _is_failure_event(event: AgentTelemetryEvent) -> bool:
    return event.status == "failed" or event.event_level == "error" or event.event_name.endswith(".failed")


def _count_by(query_or_db: Session | Any, column: Any) -> dict[str, int]:
    query = query_or_db.query(column, func.count(AgentTelemetryEvent.id)) if isinstance(query_or_db, Session) else query_or_db.with_entities(column, func.count(AgentTelemetryEvent.id))
    rows = query.group_by(column).all()
    return {str(key or "unknown"): value for key, value in rows}


def _count_model_by(db: Session, model: Any, column: Any) -> dict[str, int]:
    rows = db.query(column, func.count(model.id)).group_by(column).all()
    return {str(key or "unknown"): value for key, value in rows}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _merge_counts(target: dict[str, int], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        target[str(key or "unknown")] = target.get(str(key or "unknown"), 0) + _safe_int(value)


def _clean_operator_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = " ".join(str(note).split())
    if not cleaned:
        return None
    return cleaned[:MAX_OPERATOR_NOTE_LENGTH]


def _learning_memory_from_event(event: AgentTelemetryEvent, *, note: str | None = None) -> tuple[str, str, dict[str, Any]]:
    category = event.error_category or "unknown_error"
    title = f"Review {event.run_type} failure: {category}"
    note_text = _clean_operator_note(note)
    content_parts = [
        f"Telemetry event {event.event_name} failed for run type {event.run_type}.",
        f"Failure category: {category}.",
    ]
    if event.error_message_redacted:
        content_parts.append(f"Redacted error: {event.error_message_redacted}")
    if note_text:
        content_parts.append(f"Operator note: {note_text}")
    content_parts.append("Before repeating this workflow, inspect the run timeline, confirm the failure category, and add a regression case if the issue is systematic.")
    evidence = {
        "telemetryEventId": event.id,
        "runId": event.run_id,
        "runType": event.run_type,
        "eventName": event.event_name,
        "status": event.status,
        "errorCategory": event.error_category,
        "errorMessage": event.error_message_redacted,
        "provider": event.provider,
        "model": event.model,
        "metadata": event.metadata_json or {},
    }
    if note_text:
        evidence["operatorNote"] = note_text
    return title, " ".join(content_parts), redact_telemetry_value(evidence)


def _regression_case_title(event: AgentTelemetryEvent) -> str:
    category = event.error_category or "unknown_error"
    return f"{event.run_type} {event.event_name} regression: {category}"[:255]


def _regression_fixture_from_event(event: AgentTelemetryEvent) -> dict[str, Any]:
    return redact_telemetry_value(
        {
            "schemaVersion": "agent-regression-case.v1",
            "sourceTelemetryEventId": event.id,
            "runId": event.run_id,
            "runType": event.run_type,
            "eventName": event.event_name,
            "status": event.status,
            "eventLevel": event.event_level,
            "provider": event.provider,
            "model": event.model,
            "errorCategory": event.error_category,
            "errorMessage": event.error_message_redacted,
            "metadata": event.metadata_json or {},
            "expected": {
                "shouldReproduceFailureCategory": event.error_category,
                "shouldNotExposeRawPromptOrSlideText": True,
            },
        }
    )


def _serialize_learning_memory(memory: AgentLearningMemory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "workspaceId": memory.workspace_id,
        "deckId": memory.deck_id,
        "userId": memory.user_id,
        "sourceRunId": memory.source_run_id,
        "sourceRunType": memory.source_run_type,
        "memoryType": memory.memory_type,
        "status": memory.status,
        "feedbackLabel": memory.feedback_label,
        "score": memory.score,
        "title": memory.title,
        "content": memory.content,
        "tags": memory.tags_json or [],
        "evidence": memory.evidence_json or {},
        "createdByUserId": memory.created_by_user_id,
        "createdAt": memory.created_at.isoformat() if memory.created_at else None,
        "updatedAt": memory.updated_at.isoformat() if memory.updated_at else None,
    }


def _serialize_regression_case(case: AgentRegressionCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "sourceEventId": case.source_event_id,
        "workspaceId": case.workspace_id,
        "deckId": case.deck_id,
        "userId": case.user_id,
        "runId": case.run_id,
        "runType": case.run_type,
        "eventName": case.event_name,
        "status": case.status,
        "failureCategory": case.failure_category,
        "title": case.title,
        "fixture": case.fixture_json,
        "notes": case.notes,
        "createdByUserId": case.created_by_user_id,
        "createdAt": case.created_at.isoformat() if case.created_at else None,
        "updatedAt": case.updated_at.isoformat() if case.updated_at else None,
    }


def _serialize_event(event: AgentTelemetryEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "workspaceId": event.workspace_id,
        "deckId": event.deck_id,
        "userId": event.user_id,
        "runId": event.run_id,
        "runType": event.run_type,
        "stepId": event.step_id,
        "eventName": event.event_name,
        "eventLevel": event.event_level,
        "status": event.status,
        "provider": event.provider,
        "model": event.model,
        "latencyMs": event.latency_ms,
        "inputTokens": event.input_tokens,
        "outputTokens": event.output_tokens,
        "estimatedCostCents": event.estimated_cost_cents,
        "errorCategory": event.error_category,
        "errorMessage": event.error_message_redacted,
        "traceId": event.trace_id,
        "spanId": event.span_id,
        "requestId": event.request_id,
        "metadata": event.metadata_json or {},
        "createdAt": event.created_at.isoformat(),
    }
