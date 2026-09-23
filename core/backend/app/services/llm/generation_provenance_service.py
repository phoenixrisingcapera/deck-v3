from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DeckLlmArtifact
from app.schemas.deck_workflow import WorkflowGenerationProvenance


AUDIENCE_ARTIFACT_TYPES = {"audience_profile", "due_diligence_audience", "audience_diligence_conversion_plan"}
DILIGENCE_ARTIFACT_TYPES = {"due_diligence_claims", "due_diligence_risks", "due_diligence_report"}


class GenerationProvenanceError(ValueError):
    pass


def validate_generation_provenance(
    db: Session,
    deck_id: str,
    provenance: WorkflowGenerationProvenance | dict[str, Any] | None,
) -> WorkflowGenerationProvenance | None:
    """Validate typed, deck-owned provenance at route/queue and worker boundaries."""
    if provenance is None:
        return None
    typed = provenance if isinstance(provenance, WorkflowGenerationProvenance) else WorkflowGenerationProvenance.model_validate(provenance)
    expected: dict[str, set[str]] = {}
    if typed.audienceArtifactId:
        expected[typed.audienceArtifactId] = AUDIENCE_ARTIFACT_TYPES
    for artifact_id in typed.diligenceArtifactIds:
        expected[artifact_id] = DILIGENCE_ARTIFACT_TYPES
    if not expected:
        return typed
    artifacts = db.query(DeckLlmArtifact).filter(DeckLlmArtifact.id.in_(expected)).all()
    by_id = {artifact.id: artifact for artifact in artifacts}
    for artifact_id, expected_types in expected.items():
        artifact = by_id.get(artifact_id)
        if artifact is None or artifact.deck_id != deck_id:
            raise GenerationProvenanceError("One or more provenance artifacts do not belong to this deck.")
        if artifact.artifact_type not in expected_types:
            raise GenerationProvenanceError("A provenance artifact has an unexpected artifact type.")
        if artifact.status != "ready":
            raise GenerationProvenanceError("All provenance artifacts must be ready.")
        payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
        artifact_audience = payload.get("audience") or payload.get("audienceLabel") or payload.get("selectedAudience")
        if artifact_audience and artifact_audience != typed.audience:
            raise GenerationProvenanceError("Provenance artifact audience does not match generation audience.")
    return typed
