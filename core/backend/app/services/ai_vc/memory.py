"""Workspace-isolated, provenance-aware memory for the AI-VC runtime.

This is deliberately a product-memory layer over ``AgentLearningMemory``.  It
does not promote prior deck copy into current company truth and it never mixes
workspace memory with the global VC methodology corpus.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import AgentLearningMemory
from app.services.ai_vc.models import AIVCMemoryRecord


SCHEMA_VERSION = "ai-vc-memory.v1"
_METRIC = re.compile(
    r"(?:[$£€]\s?\d|\d(?:[\d,.]*\d)?\s?%|\b(?:arr|mrr|revenue|customers?|margin|"
    r"retention|churn|cac|ltv|burn|runway|pricing|price|valuation)\b)",
    re.IGNORECASE,
)


def company_identity(*, workspace_id: str, company_name: str | None, website_url: str | None) -> str:
    normalized = "|".join(
        [workspace_id.strip().casefold(), (website_url or "").strip().casefold().rstrip("/"),
         (company_name or "").strip().casefold()]
    )
    return "company_" + sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _metadata(memory: AgentLearningMemory) -> dict[str, Any]:
    return memory.metadata_json if isinstance(memory.metadata_json, dict) else {}


def _is_fresh(memory: AgentLearningMemory, *, today: date) -> bool:
    metadata = _metadata(memory)
    expires = metadata.get("expiresAt")
    if isinstance(expires, str):
        try:
            return date.fromisoformat(expires) >= today
        except ValueError:
            return False
    return True


def load_memory_context(
    ai_db: Session,
    *,
    workspace_id: str,
    company_identity_value: str,
    user_id: str | None,
    limit: int = 80,
) -> dict[str, Any]:
    """Return typed advisory memory without upgrading historical claims.

    Company and research memories always retain their effective period and are
    labelled historical.  Only explicit preferences/accepted decisions may
    directly influence a future narrative or visual choice.
    """
    rows = (
        ai_db.query(AgentLearningMemory)
        .filter(
            AgentLearningMemory.workspace_id == workspace_id,
            AgentLearningMemory.status == "active",
            AgentLearningMemory.memory_type.in_([
                "company_fact", "company_positioning", "accepted_strategy",
                "rejected_positioning", "investor_objection", "fundraising_goal",
                "brand_preference", "visual_preference", "research_fact",
            ]),
        )
        .order_by(AgentLearningMemory.updated_at.desc(), AgentLearningMemory.created_at.desc())
        .limit(limit * 3)
        .all()
    )
    today = date.today()
    memories: list[dict[str, Any]] = []
    for row in rows:
        metadata = _metadata(row)
        if metadata.get("companyIdentity") != company_identity_value:
            # User presentation preferences may apply across companies, but
            # company/research/fundraising claims may not cross identities.
            if row.memory_type not in {"brand_preference", "visual_preference"} or row.user_id != user_id:
                continue
        if metadata.get("supersededBy") or not _is_fresh(row, today=today):
            continue
        effective_period = metadata.get("effectivePeriod")
        if row.memory_type == "company_fact" and _METRIC.search(row.content) and not effective_period:
            # Unversioned remembered metrics are never eligible even as context.
            continue
        memories.append({
            "id": row.id,
            "memoryType": row.memory_type,
            "content": row.content,
            "confidence": row.confidence,
            "effectivePeriod": effective_period,
            "sourceArtifactId": metadata.get("sourceArtifactId") or row.source_run_id,
            "authority": (
                "preference" if row.memory_type in {"brand_preference", "visual_preference"}
                else "accepted_decision" if row.memory_type in {"accepted_strategy", "rejected_positioning"}
                else "historical_context_only"
            ),
            "freshness": "fresh" if row.memory_type == "research_fact" else "not_applicable",
        })
        if len(memories) >= limit:
            break
    return {
        "schemaVersion": SCHEMA_VERSION,
        "companyIdentity": company_identity_value,
        "memories": memories,
        "policy": {
            "companyClaims": "historical context only until supported by current source evidence",
            "researchClaims": "must be fresh and reverified before use as external evidence",
            "preferences": "may influence style and positioning but never establish facts",
            "workspaceIsolation": True,
        },
    }


def persist_memory_record(ai_db: Session, record: AIVCMemoryRecord, *, user_id: str | None = None) -> AgentLearningMemory:
    content_hash = sha256(record.content.encode("utf-8")).hexdigest()
    existing = (
        ai_db.query(AgentLearningMemory)
        .filter(
            AgentLearningMemory.workspace_id == record.workspace_id,
            AgentLearningMemory.memory_type == record.memory_type,
            AgentLearningMemory.source_run_id == record.source_artifact_id,
        )
        .all()
    )
    for row in existing:
        if _metadata(row).get("contentHash") == content_hash:
            return row
    row = AgentLearningMemory(
        id=generate_id("aivcmemory"),
        workspace_id=record.workspace_id,
        deck_id=record.deck_id,
        user_id=user_id,
        memory_type=record.memory_type,
        content=record.content,
        confidence=record.confidence,
        source_run_id=record.source_artifact_id,
        source_run_type="instant_deck_ai_vc",
        status="active",
        title=record.memory_type.replace("_", " ").title(),
        tags_json=["ai_vc", record.memory_type],
        evidence_json={"sourceArtifactId": record.source_artifact_id},
        metadata_json={
            "schemaVersion": SCHEMA_VERSION,
            "companyIdentity": record.company_identity,
            "contentHash": content_hash,
            "effectivePeriod": record.effective_period,
            "supersededBy": record.superseded_by,
            "expiresAt": record.expires_at.isoformat() if record.expires_at else None,
            "factualAuthority": False,
        },
        created_at=record.created_at or datetime.utcnow(),
    )
    ai_db.add(row)
    ai_db.flush()
    return row


def persist_company_snapshot(
    ai_db: Session,
    *,
    workspace_id: str,
    company_identity_value: str,
    deck_id: str,
    user_id: str | None,
    source_artifact_id: str,
    company_intelligence: dict[str, Any],
    narrative_strategy: dict[str, Any],
) -> list[str]:
    """Persist historical, source-versioned context after a successful run."""
    created: list[str] = []
    effective_period = f"source-artifact:{source_artifact_id}"
    for item in (company_intelligence.get("businessEvidence") or [])[:30]:
        content = " ".join(str(item.get("text") or "").split())
        if not content:
            continue
        row = persist_memory_record(ai_db, AIVCMemoryRecord(
            workspace_id=workspace_id,
            company_identity=company_identity_value,
            deck_id=deck_id,
            memory_type="company_fact",
            content=content,
            source_artifact_id=source_artifact_id,
            effective_period=effective_period,
            confidence=0.8,
        ), user_id=user_id)
        created.append(row.id)
    positioning = " ".join(str(narrative_strategy.get("thesis") or "").split())
    if positioning:
        row = persist_memory_record(ai_db, AIVCMemoryRecord(
            workspace_id=workspace_id,
            company_identity=company_identity_value,
            deck_id=deck_id,
            memory_type="company_positioning",
            content=positioning,
            source_artifact_id=source_artifact_id,
            effective_period=effective_period,
            confidence=0.65,
        ), user_id=user_id)
        created.append(row.id)
    ai_db.flush()
    return created


def memory_context_hash(context: dict[str, Any]) -> str:
    return sha256(json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
