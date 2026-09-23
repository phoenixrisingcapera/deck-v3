from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    DeckExport, DeckLlmArtifact, DesignVersion, InstantDeckCompilation, InstantDeckOperation,
    InstantDeckProviderAttempt, InstantDeckRenderProof, WorkflowJob,
)
from app.services.ai_vc.observability import operation_observability_read_model


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def build_instant_deck_operation_report(db: Session, *, deck_id: str, operation_id: str) -> dict[str, Any]:
    operation = db.query(InstantDeckOperation).filter_by(id=operation_id, deck_id=deck_id).one_or_none()
    if operation is None:
        raise ValueError("instant_deck_operation_not_found")
    job = db.query(WorkflowJob).filter_by(id=operation.workflow_job_id).one_or_none() if operation.workflow_job_id else None
    attempts = (
        db.query(InstantDeckProviderAttempt)
        .filter_by(operation_id=operation.id)
        .order_by(InstantDeckProviderAttempt.attempt_number.asc())
        .all()
    )
    artifacts = (
        db.query(DeckLlmArtifact)
        .filter(DeckLlmArtifact.deck_id == deck_id)
        .filter(DeckLlmArtifact.artifact_key.contains(operation_id))
        .order_by(DeckLlmArtifact.created_at.asc())
        .all()
    )
    visual = next((row for row in artifacts if row.artifact_type == "instant_deck_visual_intelligence"), None)
    vision_review = next((row for row in artifacts if row.artifact_type == "instant_deck_vision_review"), None)
    repair_plan = next((row for row in artifacts if row.artifact_type == "instant_deck_visual_repair_plan"), None)
    visual_payload = visual.payload_json if visual and isinstance(visual.payload_json, dict) else {}
    visual_metrics = visual.metrics_json if visual and isinstance(visual.metrics_json, dict) else {}
    visual_briefs = visual_payload.get("slide_visual_briefs") or []
    primitive_counts: dict[str, int] = {}
    for brief in visual_briefs:
        if isinstance(brief, dict):
            primitive = str(brief.get("visual_primitive") or "unknown")
            primitive_counts[primitive] = primitive_counts.get(primitive, 0) + 1
    design = db.query(DesignVersion).filter_by(id=operation.design_version_id).one_or_none() if operation.design_version_id else None
    compilation = db.query(InstantDeckCompilation).filter_by(
        design_version_id=operation.design_version_id,
    ).one_or_none() if operation.design_version_id else None
    render_proofs = db.query(InstantDeckRenderProof).filter_by(
        compilation_id=compilation.id,
    ).all() if compilation is not None else []
    exports = db.query(DeckExport).filter(
        DeckExport.deck_id == deck_id,
        DeckExport.created_at >= operation.created_at,
    ).order_by(DeckExport.created_at.asc()).all()
    ai_vc_observability = operation_observability_read_model(
        db, deck_id=deck_id, operation_id=operation_id,
    )
    elapsed_seconds = None
    if operation.completed_at is not None and operation.created_at is not None:
        elapsed_seconds = round((operation.completed_at - operation.created_at).total_seconds(), 3)
    return {
        "schemaVersion": "instant-deck-operation-report.v1",
        "operation": {
            "id": operation.id, "deckId": deck_id, "status": operation.status,
            "checkpointStage": operation.checkpoint_stage, "terminalReason": operation.terminal_reason,
            "createdAt": _iso(operation.created_at), "completedAt": _iso(operation.completed_at),
        },
        "release": {
            "buildCommit": os.getenv("DECK_BUILD_COMMIT") or os.getenv("RAILWAY_GIT_COMMIT_SHA"),
            "workerRole": os.getenv("APP_ROLE"),
        },
        "workflow": None if job is None else {
            "id": job.id, "type": job.job_type, "status": job.status,
            "phase": job.published_phase or (job.output_json or {}).get("publishedPhase"),
            "errorCode": job.error_code, "terminalReason": job.terminal_reason,
            "attemptCount": job.attempt_count, "recoveryCount": job.recovery_count,
            "queuedAt": _iso(job.queued_at), "startedAt": _iso(job.started_at),
            "completedAt": _iso(job.completed_at), "failedAt": _iso(job.failed_at),
        },
        "providerAccounting": {
            "starts": operation.provider_request_starts,
            "inputTokens": operation.actual_input_tokens,
            "outputTokens": operation.actual_output_tokens,
            "actualCostCents": operation.actual_provider_cost_cents,
            "costCapCents": operation.max_cost_cents,
            "attempts": [{
                "attemptNumber": row.attempt_number, "requestKind": row.request_kind,
                "provider": row.provider, "model": row.model, "responseState": row.response_state,
                "outcomeKnown": row.outcome_known, "inputTokens": row.actual_input_tokens,
                "outputTokens": row.actual_output_tokens, "actualCostCents": row.actual_cost_cents,
                "costSource": row.cost_source, "providerErrorCode": row.provider_error_code,
                "requestStartedAt": _iso(row.request_started_at),
                "responseReceivedAt": _iso(row.response_received_at),
            } for row in attempts],
        },
        "durableArtifacts": [{
            "type": row.artifact_type, "key": row.artifact_key, "schemaVersion": row.schema_version,
            "status": row.status, "metrics": row.metrics_json or {},
        } for row in artifacts],
        "aiVC": ai_vc_observability,
        "visualAuthoring": {
            "knowledgeVersion": visual_payload.get("knowledge_version"),
            "selectedModules": visual_payload.get("selected_knowledge_modules") or [],
            "knowledgeTrace": visual_payload.get("knowledge_trace") or {},
            "visualBriefCount": len(visual_briefs),
            "chartSpecCount": visual_metrics.get("chartSpecCount", len(visual_payload.get("chart_specs") or [])),
            "diagramSpecCount": visual_metrics.get("diagramSpecCount", len(visual_payload.get("diagram_specs") or [])),
            "imageBriefCount": len((visual_payload.get("asset_plan") or {}).get("images") or []),
            "primitivesByType": primitive_counts,
            "renderedAssetCount": visual_metrics.get("renderedAssetCount", len(visual_payload.get("rendered_assets") or [])),
            "complianceDiagnostics": visual_payload.get("compliance_diagnostics") or [],
            "rhythmDiagnostics": (visual_payload.get("visual_rhythm") or {}).get("repeated_layout_warnings") or [],
        },
        "qualityReview": {
            "vision": (vision_review.payload_json or {}) if vision_review is not None else None,
            "repair": (repair_plan.payload_json or {}) if repair_plan is not None else None,
        },
        "result": None if design is None else {
            "designVersionId": design.id, "status": design.status, "artifactType": design.artifact_type,
            "renderMode": design.render_mode,
            "visualPlanCompliance": (design.validation_report_json or {}).get("visualPlanCompliance"),
            "requestedSlides": len(visual_briefs),
            "returnedSlides": len(design.generated_slides),
        },
        "render": {
            "compilationStatus": compilation.status if compilation is not None else None,
            "renderProofStatus": compilation.render_proof_status if compilation is not None else None,
            "passed": sum(row.status == "passed" for row in render_proofs),
            "failed": sum(row.status != "passed" for row in render_proofs),
        },
        "final": {
            "publicationStatus": design.status if design is not None else None,
            "exports": [{"id": row.id, "type": row.type, "handoffStatus": row.handoff_status} for row in exports],
            "status": operation.status,
        },
        "total": {
            "knownCostCents": ((ai_vc_observability or {}).get("metrics") or {}).get(
                "knownMeasuredCostCents", operation.actual_provider_cost_cents,
            ),
            "unknownProviderOutcomes": ((ai_vc_observability or {}).get("metrics") or {}).get(
                "unknownProviderOutcomeCount", sum(not row.outcome_known for row in attempts),
            ),
            "endToEndDurationSeconds": elapsed_seconds,
        },
    }
