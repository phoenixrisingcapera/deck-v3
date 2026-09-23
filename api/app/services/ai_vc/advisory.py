"""Durable, product-facing AI-VC advice that never controls publication.

The investment committee record is intentionally separate from factual review
and render validation. Even fundraising-critical observations are advice for the
founder; they are not workflow, publication, or export gates.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.ai_vc.models import InvestmentCommitteeReview


CRITIQUE_ARTIFACT_TYPE = "instant_deck_investment_critique"
CRITIQUE_SCHEMA_VERSION = "ai-vc-investment-critique.v1"
PUBLIC_RESEARCH_ARTIFACT_TYPE = "instant_deck_verified_public_research"


def persist_investment_critique(
    db: Session,
    *,
    deck_id: str,
    operation_id: str,
    review: InvestmentCommitteeReview | dict[str, Any],
) -> dict[str, Any]:
    """Upsert one operation-bound advisory record without touching job state."""
    validated = review if isinstance(review, InvestmentCommitteeReview) else InvestmentCommitteeReview.model_validate(review)
    payload = validated.model_dump()
    key = f"investment-critique:{operation_id}"
    row = db.query(DeckLlmArtifact).filter_by(deck_id=deck_id, artifact_key=key).one_or_none()
    if row is None:
        row = DeckLlmArtifact(
            id=generate_id("investmentcritique"),
            deck_id=deck_id,
            artifact_type=CRITIQUE_ARTIFACT_TYPE,
            artifact_key=key,
            schema_version=CRITIQUE_SCHEMA_VERSION,
            status="ready",
            summary="Advisory investment critique; never a publication or export gate.",
        )
        db.add(row)
    row.payload_json = payload
    row.metrics_json = {"publicationBlocking": False, "advisory": True}
    db.flush()
    return investment_critique_payload(payload)


def investment_critique_payload(raw: dict[str, Any]) -> dict[str, Any]:
    review = InvestmentCommitteeReview.model_validate(raw)
    return {
        "status": "ready",
        "advisory": True,
        "internalProductOnly": True,
        "publicationBlocking": False,
        "strengths": review.strengths,
        "concerns": review.concerns,
        "missingProof": review.missing_proof,
        "investorObjections": review.investor_objections,
        "recommendedChanges": review.recommended_changes,
        "severity": {
            "advisory": review.advisory,
            "important": review.important,
            "criticalForFundraising": review.critical_for_fundraising,
        },
        "nextAction": review.next_action,
    }


def investment_critique_status(db: Session, deck_id: str) -> dict[str, Any] | None:
    row = (
        db.query(DeckLlmArtifact)
        .filter_by(deck_id=deck_id, artifact_type=CRITIQUE_ARTIFACT_TYPE, status="ready")
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if row is None or not isinstance(row.payload_json, dict):
        return None
    try:
        return investment_critique_payload(row.payload_json)
    except ValueError:
        return None


def source_summary(db: Session, deck_id: str, *, limit: int = 20) -> dict[str, Any]:
    """Return UI-only provenance summaries from verified public evidence."""
    rows = (
        db.query(DeckLlmArtifact)
        .filter_by(deck_id=deck_id, artifact_type=PUBLIC_RESEARCH_ARTIFACT_TYPE, status="ready")
        .order_by(DeckLlmArtifact.created_at.desc())
        .all()
    )
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        payload = row.payload_json if isinstance(row.payload_json, dict) else {}
        for claim in payload.get("claims", []):
            if not isinstance(claim, dict) or claim.get("category") != "external_research":
                continue
            url = str(claim.get("url") or "")
            evidence_id = str(claim.get("id") or "")
            identity = (url, evidence_id)
            if not url or identity in seen:
                continue
            seen.add(identity)
            sources.append({
                "evidenceId": evidence_id,
                "topic": claim.get("topic"),
                "publisher": claim.get("publisher"),
                "url": url,
                "publicationDate": claim.get("publicationDate"),
                "retrievalDate": claim.get("retrievalDate"),
                "summary": claim.get("text"),
            })
            if len(sources) >= limit:
                break
        if len(sources) >= limit:
            break
    return {
        "status": "verified" if sources else "no_verified_sources",
        "internalProductOnly": True,
        "exportedWithDeck": False,
        "sources": sources,
    }
