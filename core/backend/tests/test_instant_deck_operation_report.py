from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import (
    Deck, DeckLlmArtifact, InstantDeckOperation, InstantDeckProviderAttempt, User, WorkflowJob, Workspace,
)
from app.services.admin.instant_deck_operation_report import build_instant_deck_operation_report


def test_internal_operation_report_is_durable_structured_and_excludes_source_prose(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setenv("DECK_BUILD_COMMIT", "release-sha")
    try:
        user = User(id="user", email="owner@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="workspace", name="Workspace", user_id=user.id)
        deck = Deck(
            id="deck", workspace_id=workspace.id, user_id=user.id, title="Deck",
            audience="Investors", purpose="Fundraising", status="ready",
        )
        job = WorkflowJob(id="job", deck_id=deck.id, user_id=user.id, job_type="instant_deck_generation", status="completed")
        operation = InstantDeckOperation(
            id="operation", deck_id=deck.id, user_id=user.id, workflow_job_id=job.id,
            idempotency_key="key", request_hash="a" * 64, status="completed", checkpoint_stage="published",
            provider_request_starts=1, actual_input_tokens=100, actual_output_tokens=50,
            actual_provider_cost_cents=1.25,
        )
        attempt = InstantDeckProviderAttempt(
            id="attempt", operation_id=operation.id, attempt_number=1, provider="openai", model="model",
            response_state="completed", outcome_known=True, actual_input_tokens=100,
            actual_output_tokens=50, actual_cost_cents=1.25, cost_source="provider_usage",
        )
        artifact = DeckLlmArtifact(
            id="visual", deck_id=deck.id, artifact_type="instant_deck_visual_intelligence",
            artifact_key="visual-intelligence:operation", schema_version="visual-intelligence.v2", status="ready",
            payload_json={
                "knowledge_version": "investor-visual-design.2026-09-22.v2",
                "selected_knowledge_modules": ["chart_selection"],
                "knowledge_trace": {
                    "consideredModuleIds": ["chart_selection", "deck_rhythm"],
                    "selectedModuleIds": ["chart_selection"],
                    "injectedModuleIds": ["chart_selection"],
                    "usedRuleIds": ["chart.series"],
                    "droppedModuleIds": ["deck_rhythm"],
                },
                "chart_specs": [{"privateSourceProse": "must not escape"}],
                "compliance_diagnostics": [{"code": "required_executable_chart_missing", "slideId": "slide-2"}],
                "visual_rhythm": {"repeated_layout_warnings": ["Slides 1-3 repeat a layout."]},
            },
            metrics_json={"chartSpecCount": 1, "renderedAssetCount": 1},
        )
        db.add_all([user, workspace, deck, job, operation, attempt, artifact])
        db.commit()

        report = build_instant_deck_operation_report(db, deck_id=deck.id, operation_id=operation.id)

        assert report["release"]["buildCommit"] == "release-sha"
        assert report["providerAccounting"]["actualCostCents"] == 1.25
        assert report["visualAuthoring"]["chartSpecCount"] == 1
        assert report["visualAuthoring"]["complianceDiagnostics"][0]["code"] == "required_executable_chart_missing"
        assert report["visualAuthoring"]["knowledgeTrace"]["usedRuleIds"] == ["chart.series"]
        assert "must not escape" not in str(report)
    finally:
        db.close()
        engine.dispose()
