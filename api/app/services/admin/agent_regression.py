from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import AgentRegressionCase, AgentTelemetryEvent, DeckLlmArtifact, GenerationJob
from app.services.admin.agent_telemetry import record_agent_event, redact_telemetry_value
from app.services.storage.artifact_storage import get_upload_storage


SENSITIVE_FIXTURE_KEYS = {
    "additional_context",
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

REGRESSION_FIXTURE_SCHEMA_VERSION = "agent-regression-case.v1"
SMART_DECK_ARTIFACT_STORAGE_VERSION = "smart-deck-assistant-artifact.v1"
SMART_DECK_CRITIQUE_ARTIFACT_TYPE = "smart_deck_generation_critique"
SMART_DECK_SOURCE_FACTS_ARTIFACT_TYPE = "smart_deck_source_facts"
SMART_DECK_CRITIQUE_REGRESSION_EVENT = "ai.smart_deck_generation.critique_regression"


def replay_agent_regression_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []

    if fixture.get("schemaVersion") != REGRESSION_FIXTURE_SCHEMA_VERSION:
        failures.append("schemaVersion must be agent-regression-case.v1")
    for key in ("sourceTelemetryEventId", "runType", "eventName", "errorCategory", "expected"):
        if not fixture.get(key):
            failures.append(f"{key} is required")

    expected = fixture.get("expected") if isinstance(fixture.get("expected"), dict) else {}
    expected_category = expected.get("shouldReproduceFailureCategory")
    if expected_category and fixture.get("errorCategory") != expected_category:
        failures.append("errorCategory does not match expected.shouldReproduceFailureCategory")

    if expected.get("shouldNotExposeRawPromptOrSlideText", True):
        leaked_paths = find_sensitive_fixture_leaks(fixture)
        if leaked_paths:
            failures.append(f"sensitive fixture values are not redacted: {', '.join(leaked_paths[:10])}")
    if expected.get("shouldPreserveSourceFactIds"):
        critique = fixture.get("critique") if isinstance(fixture.get("critique"), dict) else {}
        source_facts = fixture.get("sourceFacts") if isinstance(fixture.get("sourceFacts"), dict) else {}
        allowed_ids = set(critique.get("allowedSourceFactIds") or [])
        fact_ids = {
            str(fact.get("id"))
            for fact in source_facts.get("facts", [])
            if isinstance(fact, dict) and fact.get("id")
        }
        cited_ids = {
            str(fact_id)
            for slide in critique.get("slides", [])
            if isinstance(slide, dict)
            for fact_id in (slide.get("sourceFactIds") or [])
        }
        if not allowed_ids and not fact_ids:
            failures.append("source fact IDs are required for this fixture")
        if cited_ids and fact_ids and not cited_ids.issubset(fact_ids):
            failures.append("critique sourceFactIds include IDs missing from sourceFacts.facts")

    return {
        "passed": not failures,
        "failures": failures,
        "runType": fixture.get("runType"),
        "eventName": fixture.get("eventName"),
        "errorCategory": fixture.get("errorCategory"),
    }


def replay_agent_regression_cases(db: Session, *, limit: int = 100) -> dict[str, Any]:
    cases = (
        db.query(AgentRegressionCase)
        .filter(AgentRegressionCase.status == "active")
        .order_by(AgentRegressionCase.created_at.desc())
        .limit(limit)
        .all()
    )
    results = [
        {
            "caseId": case.id,
            "title": case.title,
            **replay_agent_regression_fixture(case.fixture_json or {}),
        }
        for case in cases
    ]
    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["passed"]),
            "failed": sum(1 for result in results if not result["passed"]),
        },
        "results": results,
    }


def promote_smart_deck_critique_to_regression_case(
    db: Session,
    *,
    artifact_id: str,
    actor=None,
    note: str | None = None,
    commit: bool = True,
) -> dict[str, Any] | None:
    artifact = db.get(DeckLlmArtifact, artifact_id)
    if artifact is None:
        return None
    if artifact.artifact_type != SMART_DECK_CRITIQUE_ARTIFACT_TYPE:
        raise ValueError("Only Smart Deck generation critique artifacts can be promoted.")

    critique_payload = _load_llm_artifact_payload(artifact)
    if not _critique_requires_regression(critique_payload):
        raise ValueError("Only review-status critiques with warnings or missing inputs can be promoted.")

    source_facts_artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == artifact.deck_id,
            DeckLlmArtifact.artifact_key == artifact.artifact_key,
            DeckLlmArtifact.artifact_type == SMART_DECK_SOURCE_FACTS_ARTIFACT_TYPE,
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    source_facts_payload = _load_llm_artifact_payload(source_facts_artifact) if source_facts_artifact is not None else {}
    job = db.get(GenerationJob, artifact.artifact_key)
    existing = (
        db.query(AgentRegressionCase)
        .filter(
            AgentRegressionCase.run_id == artifact.artifact_key,
            AgentRegressionCase.event_name == SMART_DECK_CRITIQUE_REGRESSION_EVENT,
        )
        .one_or_none()
    )
    event = db.get(AgentTelemetryEvent, existing.source_event_id) if existing is not None else None
    if event is None:
        event = record_agent_event(
            db,
            event_name=SMART_DECK_CRITIQUE_REGRESSION_EVENT,
            run_type="smart_deck_generation",
            workspace_id=getattr(job, "deck", None).workspace_id if job is not None and getattr(job, "deck", None) is not None else None,
            deck_id=artifact.deck_id,
            user_id=getattr(job, "deck", None).user_id if job is not None and getattr(job, "deck", None) is not None else None,
            run_id=artifact.artifact_key,
            event_level="error",
            status="failed",
            provider=job.provider if job is not None else None,
            model=job.model if job is not None else None,
            error_category="smart_deck_source_fact_critique",
            error_message=_critique_error_message(critique_payload),
            metadata={
                "artifactId": artifact.id,
                "artifactType": artifact.artifact_type,
                "critiqueStatus": critique_payload.get("status"),
                "warningCount": critique_payload.get("warningCount"),
                "missingInputCount": critique_payload.get("missingInputCount"),
                "sourceFactCount": source_facts_payload.get("factCount"),
                "sourceFactIds": _source_fact_ids(source_facts_payload),
            },
            commit=False,
        )
        if event is None:
            raise ValueError("Could not create telemetry event for Smart Deck critique regression.")
        db.flush()

    fixture = _smart_deck_critique_fixture(
        event=event,
        artifact=artifact,
        critique_payload=critique_payload,
        source_facts_payload=source_facts_payload,
        job=job,
    )
    title = _smart_deck_critique_regression_title(critique_payload)
    clean_note = _clean_note(note)
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
            deck_id=artifact.deck_id,
            user_id=event.user_id,
            run_id=artifact.artifact_key,
            run_type="smart_deck_generation",
            event_name=SMART_DECK_CRITIQUE_REGRESSION_EVENT,
            status="active",
            failure_category="smart_deck_source_fact_critique",
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


def export_agent_regression_fixture(case: AgentRegressionCase) -> dict[str, Any]:
    return redact_telemetry_value(
        {
            "caseId": case.id,
            "title": case.title,
            "sourceEventId": case.source_event_id,
            "fixture": case.fixture_json or {},
        }
    )


def write_agent_regression_fixture(case: AgentRegressionCase, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{case.id}.json"
    path.write_text(json.dumps(export_agent_regression_fixture(case), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_agent_regression_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fixture = payload.get("fixture") if isinstance(payload, dict) else None
    if not isinstance(fixture, dict):
        raise ValueError("Regression fixture file must contain a fixture object.")
    return fixture


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


def _load_llm_artifact_payload(artifact: DeckLlmArtifact | None) -> dict[str, Any]:
    if artifact is None:
        return {}
    payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
    if payload.get("artifactStorageVersion") != SMART_DECK_ARTIFACT_STORAGE_VERSION:
        return payload
    storage_path = payload.get("storagePath")
    path = get_upload_storage().resolve_path(storage_path if isinstance(storage_path, str) else None)
    if path is None or not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _critique_requires_regression(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") == "review"
        or int(payload.get("warningCount") or 0) > 0
        or int(payload.get("missingInputCount") or 0) > 0
    )


def _critique_error_message(payload: dict[str, Any]) -> str:
    warning_count = int(payload.get("warningCount") or 0)
    missing_count = int(payload.get("missingInputCount") or 0)
    return f"Smart Deck critique requires review: warnings={warning_count}, missingInputs={missing_count}"


def _source_fact_ids(source_facts_payload: dict[str, Any]) -> list[str]:
    facts = source_facts_payload.get("facts") if isinstance(source_facts_payload, dict) else []
    return [str(fact.get("id")) for fact in facts if isinstance(fact, dict) and fact.get("id")]


def _sanitized_source_facts(source_facts_payload: dict[str, Any]) -> list[dict[str, Any]]:
    facts = source_facts_payload.get("facts") if isinstance(source_facts_payload, dict) else []
    sanitized = []
    for fact in facts[:80]:
        if not isinstance(fact, dict):
            continue
        sanitized.append(
            {
                "id": fact.get("id"),
                "sourceType": fact.get("sourceType"),
                "sourceId": fact.get("sourceId"),
                "field": fact.get("field"),
                "confidence": fact.get("confidence"),
                "scope": fact.get("scope"),
                "factType": fact.get("factType"),
                "evidenceStrength": fact.get("evidenceStrength"),
                "safetyFlags": fact.get("safetyFlags") or [],
            }
        )
    return sanitized


def _sanitized_critique_slides(critique_payload: dict[str, Any]) -> list[dict[str, Any]]:
    slides = critique_payload.get("slides") if isinstance(critique_payload, dict) else []
    sanitized = []
    for slide in slides[:50]:
        if not isinstance(slide, dict):
            continue
        sanitized.append(
            {
                "sourceSlideId": slide.get("sourceSlideId"),
                "status": slide.get("status"),
                "sourceFactIds": slide.get("sourceFactIds") or [],
                "unsupportedSourceFactIds": slide.get("unsupportedSourceFactIds") or [],
                "missingInputCount": len(slide.get("missingInputs") or []),
                "warnings": slide.get("warnings") or [],
                "confidence": slide.get("confidence"),
            }
        )
    return sanitized


def _smart_deck_critique_fixture(
    *,
    event: AgentTelemetryEvent,
    artifact: DeckLlmArtifact,
    critique_payload: dict[str, Any],
    source_facts_payload: dict[str, Any],
    job: GenerationJob | None,
) -> dict[str, Any]:
    return redact_telemetry_value(
        {
            "schemaVersion": REGRESSION_FIXTURE_SCHEMA_VERSION,
            "sourceTelemetryEventId": event.id,
            "sourceArtifactId": artifact.id,
            "sourceArtifacts": {
                "critique": artifact.id,
                "sourceFactsArtifactType": SMART_DECK_SOURCE_FACTS_ARTIFACT_TYPE,
            },
            "runId": artifact.artifact_key,
            "runType": "smart_deck_generation",
            "eventName": SMART_DECK_CRITIQUE_REGRESSION_EVENT,
            "status": "failed",
            "eventLevel": "error",
            "provider": job.provider if job is not None else None,
            "model": job.model if job is not None else None,
            "errorCategory": "smart_deck_source_fact_critique",
            "critique": {
                "schemaVersion": critique_payload.get("schemaVersion"),
                "status": critique_payload.get("status"),
                "warningCount": critique_payload.get("warningCount"),
                "missingInputCount": critique_payload.get("missingInputCount"),
                "allowedSourceFactIds": critique_payload.get("allowedSourceFactIds") or [],
                "slides": _sanitized_critique_slides(critique_payload),
            },
            "sourceFacts": {
                "schemaVersion": source_facts_payload.get("schemaVersion"),
                "factCount": source_facts_payload.get("factCount"),
                "facts": _sanitized_source_facts(source_facts_payload),
                "coverage": source_facts_payload.get("coverage") or {},
            },
            "expected": {
                "shouldReproduceFailureCategory": "smart_deck_source_fact_critique",
                "shouldNotExposeRawPromptOrSlideText": True,
                "shouldPreserveSourceFactIds": True,
            },
        }
    )


def _smart_deck_critique_regression_title(payload: dict[str, Any]) -> str:
    warning_count = int(payload.get("warningCount") or 0)
    missing_count = int(payload.get("missingInputCount") or 0)
    return f"Smart Deck source-fact critique regression: warnings={warning_count} missingInputs={missing_count}"[:255]


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = " ".join(str(note).split())
    return cleaned[:500] if cleaned else None


def find_sensitive_fixture_leaks(value: Any, *, path: str = "$") -> list[str]:
    leaks: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            if key_text.lower() in SENSITIVE_FIXTURE_KEYS and nested != "[redacted]" and nested not in (None, "", []):
                leaks.append(nested_path)
            leaks.extend(find_sensitive_fixture_leaks(nested, path=nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            leaks.extend(find_sensitive_fixture_leaks(nested, path=f"{path}[{index}]"))
    return leaks
