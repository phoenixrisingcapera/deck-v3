from __future__ import annotations

from app.core.security import generate_id
from sqlalchemy.orm import Session

from app.db.models import DeckLlmArtifact


CANONICAL_DECK_INTELLIGENCE_ARTIFACT_TYPE = "canonical_deck_intelligence"


def build_canonical_deck_intelligence(db: Session, deck_id: str) -> dict:
    deck_map_artifact = _latest_artifact(db, deck_id, "smart_deck_deck_map_analysis")
    audience_diligence_artifact = _latest_artifact(db, deck_id, "audience_diligence_conversion_plan")
    audience_conversion_artifact = audience_diligence_artifact or _latest_artifact(db, deck_id, "audience_conversion_generated") or _latest_artifact(db, deck_id, "audience_conversion_plan")
    market_research_artifact = _latest_artifact(db, deck_id, "smart_deck_market_research")
    deck_map = deck_map_artifact.payload_json if deck_map_artifact and deck_map_artifact.payload_json else {}
    audience_conversion = audience_conversion_artifact.payload_json if audience_conversion_artifact and audience_conversion_artifact.payload_json else {}
    audience_diligence = audience_diligence_artifact.payload_json if audience_diligence_artifact and audience_diligence_artifact.payload_json else audience_conversion
    market_research = market_research_artifact.payload_json if market_research_artifact and market_research_artifact.payload_json else {}
    payload = {
        "schemaVersion": "canonical-deck-intelligence.v1",
        "deckId": deck_id,
        "canonicalArtifactTypes": {
            "deckMap": "smart_deck_deck_map_analysis",
            "audienceConversion": "audience_diligence_conversion_plan",
            "audienceDiligence": "audience_diligence_conversion_plan",
            "marketResearch": "smart_deck_market_research",
        },
        "canonicalArtifactRefs": {
            "deckMap": _artifact_ref(deck_map_artifact),
            "audienceConversion": _artifact_ref(audience_conversion_artifact),
            "audienceDiligence": _artifact_ref(audience_diligence_artifact),
            "marketResearch": _artifact_ref(market_research_artifact),
        },
        "deckMap": deck_map,
        "audienceConversion": audience_conversion,
        "audienceDiligence": audience_diligence,
        "marketResearch": market_research,
    }
    return payload


def get_latest_canonical_deck_intelligence(db: Session, deck_id: str) -> dict | None:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == CANONICAL_DECK_INTELLIGENCE_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    return artifact.payload_json if artifact and artifact.payload_json else None


def persist_canonical_deck_intelligence(db: Session, deck_id: str) -> dict:
    payload = build_canonical_deck_intelligence(db, deck_id)
    existing = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == CANONICAL_DECK_INTELLIGENCE_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key == f"canonical:{deck_id}",
        )
        .one_or_none()
    )
    if existing is not None:
        existing.payload_json = payload
        existing.summary = "Canonical deck intelligence snapshot."
        existing.status = "ready"
        db.flush()
        return payload
    db.add(
        DeckLlmArtifact(
            id=generate_id("artifact"),
            deck_id=deck_id,
            artifact_type=CANONICAL_DECK_INTELLIGENCE_ARTIFACT_TYPE,
            artifact_key=f"canonical:{deck_id}",
            schema_version="canonical-deck-intelligence.v1",
            status="ready",
            summary="Canonical deck intelligence snapshot.",
            payload_json=payload,
        )
    )
    db.flush()
    return payload


def _latest_payload(db: Session, deck_id: str, artifact_type: str) -> dict | None:
    artifact = _latest_artifact(db, deck_id, artifact_type)
    return artifact.payload_json if artifact and artifact.payload_json else None


def _latest_artifact(db: Session, deck_id: str, artifact_type: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == artifact_type,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _artifact_ref(artifact: DeckLlmArtifact | None) -> dict | None:
    if artifact is None:
        return None
    return {
        "artifactId": artifact.id,
        "artifactKey": artifact.artifact_key,
        "artifactType": artifact.artifact_type,
        "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
        "summary": artifact.summary,
    }
