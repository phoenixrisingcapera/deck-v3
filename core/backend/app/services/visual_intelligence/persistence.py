from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.visual_intelligence.models import VisualIntelligenceBundle

ARTIFACT_TYPE = "instant_deck_visual_intelligence"
SCHEMA_VERSION = "visual-intelligence.v2"


def persist_visual_intelligence(db: Session, *, deck_id: str, operation_id: str,
                                bundle: VisualIntelligenceBundle) -> dict:
    key = f"visual-intelligence:{operation_id}"
    row = db.query(DeckLlmArtifact).filter_by(deck_id=deck_id, artifact_key=key).one_or_none()
    payload = bundle.model_dump(mode="json")
    if row is None:
        row = DeckLlmArtifact(
            id=generate_id("visualintelligence"), deck_id=deck_id,
            artifact_type=ARTIFACT_TYPE, artifact_key=key,
            schema_version=SCHEMA_VERSION, status="ready",
            summary="Versioned visual direction and slide briefs; no factual authority.",
        )
        db.add(row)
    row.payload_json = payload
    row.metrics_json = {
        "providerStarts": 0,
        "publicationBlocking": False,
        "chartSpecCount": len(bundle.chart_specs),
        "diagramSpecCount": len(bundle.diagram_specs),
        "renderedAssetCount": len(bundle.rendered_assets),
        "complianceFailureCount": len(bundle.compliance_diagnostics),
        "selectedKnowledgeModules": bundle.selected_knowledge_modules,
        "usedVisualRuleCount": len((bundle.knowledge_trace or {}).get("usedRuleIds") or []),
    }
    db.flush()
    return payload


def load_visual_intelligence(db: Session, *, deck_id: str, operation_id: str) -> dict:
    row = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_key=f"visual-intelligence:{operation_id}",
        artifact_type=ARTIFACT_TYPE, status="ready",
    ).one_or_none()
    return row.payload_json if row and isinstance(row.payload_json, dict) else {}


def visual_intelligence_status(db: Session, deck_id: str) -> dict | None:
    row = (
        db.query(DeckLlmArtifact)
        .filter_by(deck_id=deck_id, artifact_type=ARTIFACT_TYPE, status="ready")
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if row is None or not isinstance(row.payload_json, dict):
        return None
    try:
        bundle = VisualIntelligenceBundle.model_validate(row.payload_json)
    except ValueError:
        return None
    return {
        "status": "ready",
        "schemaVersion": bundle.schema_version,
        "internalProductOnly": True,
        "publicationBlocking": False,
        "visualDirection": bundle.visual_direction.model_dump(mode="json"),
        "visualRhythm": bundle.visual_rhythm.model_dump(mode="json") if bundle.visual_rhythm else None,
        "slideVisualBriefs": [item.model_dump(mode="json") for item in bundle.slide_visual_briefs],
        "chartSpecCount": len(bundle.chart_specs),
        "diagramSpecCount": len(bundle.diagram_specs),
        "visionReviewStatus": bundle.vision_review_status,
        "knowledgeVersion": bundle.knowledge_version,
        "complianceDiagnostics": bundle.compliance_diagnostics,
    }
