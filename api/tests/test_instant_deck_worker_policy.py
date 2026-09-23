from app.core.worker_startup_policy import (
    INSTANT_DECK_PIPELINE_JOB_TYPES,
    expected_job_types,
)
import app.services.deck_processing
from app.services.deck_processing import workflow_jobs
from app.services.deck_processing.workflow_jobs import source_pipeline_stage_order
from app.db.base import CoreBase
from app.db.models import Deck, User, WorkflowJob, Workspace
from app.workers.dispatch.worker_runtime_service import process_workflow_job
from scripts import deck_processing_worker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest


class _ClosableSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_instant_deck_worker_accepts_only_vertical_slice_jobs() -> None:
    expected = {
        "source_ingestion",
        "source_extraction",
        "brand_extraction",
        "instant_deck_generation",
        "schema_validation",
        "db_publisher",
        "export",
    }

    assert set(INSTANT_DECK_PIPELINE_JOB_TYPES) == expected
    assert set(expected_job_types("instant_deck_pipeline")) == expected
    assert "smart_deck_context" not in INSTANT_DECK_PIPELINE_JOB_TYPES
    assert "apply_version" not in INSTANT_DECK_PIPELINE_JOB_TYPES


def test_instant_upload_does_not_create_legacy_smart_deck_context() -> None:
    instant_stages = source_pipeline_stage_order(instant_upload=True)
    legacy_stages = source_pipeline_stage_order(instant_upload=False)

    assert "smart_deck_context" not in instant_stages
    assert "smart_deck_context" in legacy_stages
    assert instant_stages == (
        "source_extraction",
        "db_publisher",
        "brand_extraction",
    )


def test_package_import_does_not_replace_the_canonical_pipeline_builder() -> None:
    assert (
        app.services.deck_processing.CANONICAL_SOURCE_PIPELINE_JOB_SEQUENCE
        is workflow_jobs.SOURCE_PIPELINE_JOB_SEQUENCE
    )
    assert workflow_jobs.ensure_pipeline_jobs_for_run.__module__ == workflow_jobs.__name__


def test_authoritative_instant_worker_reconciles_deferred_credit_release(monkeypatch) -> None:
    sessions: list[_ClosableSession] = []
    calls: list[_ClosableSession] = []

    def session_factory() -> _ClosableSession:
        session = _ClosableSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        deck_processing_worker,
        "AUDIT_HEALTH_ONLY",
        False,
    )
    monkeypatch.setattr(deck_processing_worker, "SessionLocal", session_factory, raising=False)
    monkeypatch.setattr(deck_processing_worker.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        "app.services.llm.instant_html_operation_service.reconcile_release_pending_operations",
        lambda db: calls.append(db) or 1,
    )
    monkeypatch.setattr(deck_processing_worker, "LAST_RELEASE_RECONCILIATION_AT", 0.0)

    assert deck_processing_worker._reconcile_deferred_instant_releases(
        configured_job_types_csv="instant_deck_generation,db_publisher",
        force=True,
    ) == 1
    assert calls == sessions
    assert sessions[0].closed is True
    assert deck_processing_worker._reconcile_deferred_instant_releases(
        configured_job_types_csv="instant_deck_generation,db_publisher",
    ) is None
    assert len(sessions) == 1


def test_normal_worker_recovers_expired_leases_before_claiming(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(deck_processing_worker, "configured_worker_job_types", lambda: {"instant_deck_generation"})
    monkeypatch.setattr(deck_processing_worker, "worker_recovery_only", lambda: False)
    monkeypatch.setattr(
        deck_processing_worker,
        "_startup_readiness_check",
        lambda **_kwargs: events.append("ready"),
    )
    monkeypatch.setattr(
        deck_processing_worker,
        "_recover_stale_runs",
        lambda: events.append("recover") or {"recovered": 1, "timedOut": 0},
    )
    monkeypatch.setattr(
        deck_processing_worker,
        "_reconcile_deferred_instant_releases",
        lambda **_kwargs: events.append("reconcile"),
    )
    monkeypatch.setattr(
        deck_processing_worker,
        "run_once",
        lambda **_kwargs: events.append("claim") or False,
    )
    monkeypatch.setattr(deck_processing_worker, "_record_heartbeat", lambda **_kwargs: True)

    deck_processing_worker.run_worker(once=True, idle_sleep_seconds=0)

    assert events == ["ready", "recover", "reconcile", "claim"]


def test_unsupported_job_fails_final_with_structured_identity(caplog, monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(id="worker_user", email="worker@example.com", name="Worker Owner", password_hash="unused")
        workspace = Workspace(id="worker_workspace", name="Worker workspace", user_id=user.id)
        deck = Deck(
            id="worker_deck",
            workspace_id=workspace.id,
            user_id=user.id,
            title="Worker deck",
            audience="Investors",
            purpose="Fundraising",
            status="processing",
        )
        job = WorkflowJob(
            id="job_unknown",
            deck_id=deck.id,
            workspace_id=workspace.id,
            user_id=user.id,
            job_type="due_diligence",
            status="running",
            attempt_count=1,
            max_attempts=3,
        )
        db.add_all([user, workspace, deck, job])
        db.commit()

        monkeypatch.setattr("app.workers.dispatch.job_handlers.get_workflow_job_handler", lambda _job_type: None)
        with caplog.at_level("ERROR"), pytest.raises(ValueError, match="Unsupported workflow job type"):
            process_workflow_job(db, job.id, worker_id="worker-test")

        db.refresh(job)
        assert job.status == "failed_final"
        assert job.error_code == "unsupported_workflow_job_type"
        assert job.error_message == "This workflow job type is not supported by the active product worker."
        record = next(item for item in caplog.records if item.message == "unsupported_workflow_job_type")
        assert record.workflow_job_id == job.id
        assert record.deck_id == deck.id
        assert record.job_type == job.job_type
        assert record.worker_id == "worker-test"
    finally:
        db.close()
        engine.dispose()
