from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import AgentLearningMemory, Deck, GenerationJob, User, Workspace


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _preview(value: str | None, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _memory_summary(memory: AgentLearningMemory, deck_context: dict[str, dict[str, Any]]) -> dict[str, Any]:
    context = deck_context.get(memory.deck_id or "", {})
    return {
        "id": memory.id,
        "workspaceId": memory.workspace_id,
        "workspaceName": context.get("workspaceName"),
        "deckId": memory.deck_id,
        "deckTitle": context.get("deckTitle"),
        "userId": memory.user_id,
        "userEmail": context.get("userEmail"),
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
        "createdAt": _iso(memory.created_at),
        "updatedAt": _iso(memory.updated_at),
        "lastUsedAt": _iso(memory.last_used_at),
    }


def _deck_context(db: Session) -> dict[str, dict[str, Any]]:
    rows = (
        db.query(
            Deck.id,
            Deck.title,
            Deck.user_id,
            Deck.workspace_id,
            User.email.label("user_email"),
            Workspace.name.label("workspace_name"),
        )
        .outerjoin(User, User.id == Deck.user_id)
        .outerjoin(Workspace, Workspace.id == Deck.workspace_id)
        .all()
    )
    return {
        row.id: {
            "deckTitle": row.title,
            "userId": row.user_id,
            "userEmail": row.user_email,
            "workspaceId": row.workspace_id,
            "workspaceName": row.workspace_name,
        }
        for row in rows
    }


def _failed_generation_candidate(job: GenerationJob, deck_context: dict[str, dict[str, Any]]) -> dict[str, Any]:
    context = deck_context.get(job.deck_id, {})
    return {
        "id": job.id,
        "runType": "generation_job",
        "status": job.status,
        "deckId": job.deck_id,
        "deckTitle": context.get("deckTitle"),
        "workspaceId": context.get("workspaceId"),
        "workspaceName": context.get("workspaceName"),
        "userId": context.get("userId"),
        "userEmail": context.get("userEmail"),
        "provider": job.provider,
        "model": job.model,
        "selectedSlideCount": len(job.selected_source_slide_ids_json or []),
        "errorPreview": _preview(job.error_message),
        "createdAt": _iso(job.created_at),
        "updatedAt": _iso(job.updated_at),
        "completedAt": _iso(job.completed_at),
    }


def _build_generation_failure_reflection(job: GenerationJob, *, reason: str | None = None) -> tuple[str, str, dict[str, Any]]:
    selected_count = len(job.selected_source_slide_ids_json or [])
    title = "Review failed Smart Deck generation before retry"
    cause = _preview(job.error_message, limit=180) or "The generation job was marked failed."
    reason_text = _preview(reason, limit=180)
    content_parts = [
        f"Before retrying a similar Smart Deck generation, verify provider availability and schema validation for the selected {selected_count} slide(s).",
        f"Failure signal: {cause}",
    ]
    if reason_text:
        content_parts.append(f"Operator note: {reason_text}")
    content_parts.append("Next run should keep the original deck context, reduce unnecessary scope, and confirm that generated slide JSON validates before surfacing the iteration.")
    evidence = {
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "selectedSlideCount": selected_count,
        "hasError": bool(job.error_message),
        "errorPreview": cause,
    }
    if reason_text:
        evidence["operatorReason"] = reason_text
    return title, " ".join(content_parts), evidence


def record_generation_failure_memory(
    core_db: Session,
    *,
    job: GenerationJob,
    actor: User | None = None,
    reason: str | None = None,
    ai_db: Session | None = None,
) -> AgentLearningMemory:
    memory_db = ai_db or core_db
    existing = (
        memory_db.query(AgentLearningMemory)
        .filter(
            AgentLearningMemory.source_run_id == job.id,
            AgentLearningMemory.memory_type == "reflection",
        )
        .one_or_none()
    )
    title, content, evidence = _build_generation_failure_reflection(job, reason=reason)
    context = _deck_context(core_db).get(job.deck_id, {})
    if existing is not None:
        existing.title = title
        existing.content = content
        existing.evidence_json = evidence
        existing.feedback_label = "failure"
        existing.score = min(existing.score, -1)
        existing.updated_at = datetime.utcnow()
        return existing

    memory = AgentLearningMemory(
        id=generate_id("learn"),
        workspace_id=context.get("workspaceId"),
        deck_id=job.deck_id,
        user_id=context.get("userId"),
        source_run_id=job.id,
        source_run_type="generation_job",
        memory_type="reflection",
        status="active",
        feedback_label="failure",
        score=-1,
        title=title,
        content=content,
        tags_json=["smart_deck", "generation", "reflexion"],
        evidence_json=evidence,
        created_by_user_id=actor.id if actor is not None else None,
    )
    memory_db.add(memory)
    return memory


def list_agent_learning_memories(
    ai_db: Session,
    *,
    core_db: Session | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    core_session = core_db or ai_db
    deck_context = _deck_context(core_session)
    memories = (
        ai_db.query(AgentLearningMemory)
        .order_by(AgentLearningMemory.created_at.desc())
        .limit(limit)
        .all()
    )
    memory_source_ids = {memory.source_run_id for memory in memories if memory.source_run_id}
    failed_candidates = (
        core_session.query(GenerationJob)
        .filter(GenerationJob.status.in_(["failed", "canceled"]))
        .order_by(GenerationJob.updated_at.desc(), GenerationJob.created_at.desc())
        .limit(limit)
        .all()
    )
    candidates = [
        _failed_generation_candidate(job, deck_context)
        for job in failed_candidates
        if job.id not in memory_source_ids
    ]
    type_counts = {
        row.memory_type: row.count
        for row in ai_db.query(AgentLearningMemory.memory_type, func.count(AgentLearningMemory.id).label("count"))
        .group_by(AgentLearningMemory.memory_type)
        .all()
    }
    status_counts = {
        row.status: row.count
        for row in ai_db.query(AgentLearningMemory.status, func.count(AgentLearningMemory.id).label("count"))
        .group_by(AgentLearningMemory.status)
        .all()
    }
    return {
        "summary": {
            "total": ai_db.query(AgentLearningMemory).count(),
            "returned": len(memories),
            "candidateRuns": len(candidates),
            "reflectionCount": type_counts.get("reflection", 0),
            "exemplarCount": type_counts.get("exemplar", 0),
            "insightCount": type_counts.get("insight", 0),
        },
        "typeCounts": type_counts,
        "statusCounts": status_counts,
        "memories": [_memory_summary(memory, deck_context) for memory in memories],
        "candidateRuns": candidates[:limit],
        "redaction": {
            "sensitiveFieldsRedacted": ["prompt", "additional_context", "llm_context_json", "result_json"],
            "detailPolicy": "Learning memory exposes operator-safe summaries only; raw prompts and provider payloads stay out of the admin learning feed.",
        },
    }
