import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import Deck, DeckFile, DeckExtractionRun, DeckSlide, User, Workspace, WorkflowJob, WorkflowJobDependency
from app.services.deck_processing.workflow_jobs import ensure_pipeline_jobs_for_run, ensure_workflow_dependency
from app.services.deck_processing.source_page_readiness import require_extracted_page_records
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.workers.runtime.publisher_runtime import _lock_and_validate_source_publisher, handle_db_publisher
from app.workers.runtime.source_pipeline_runtime import handle_miniatures


@pytest.fixture
def source():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        owner = User(id="owner", email="pages@example.test", name="Canary", password_hash="unused")
        ws = Workspace(id="ws", user_id=owner.id, name="Canary")
        deck = Deck(id="deck", user_id=owner.id, workspace_id=ws.id, title="Canary", audience="Test", purpose="Test", status="processing")
        file = DeckFile(id="file", deck_id=deck.id, filename="canary.pdf", mime_type="application/pdf", size=100, checksum_sha256="a" * 64, page_count=2, metadata_json={"preferredWorkspace": "instant_deck"})
        run = DeckExtractionRun(id="run", deck_id=deck.id, source_file_id=file.id, status="completed", slide_count=2)
        db.add_all([owner, ws, deck, file, run])
        for number in (1, 2):
            db.add(DeckSlide(id=f"page{number}", deck_id=deck.id, source_file_id=file.id, extraction_run_id=run.id, source_page_number=number, slide_index=number, title="Page", role="unknown", raw_text=f"CANARY-P{number:02}"))
        db.commit()
        jobs = ensure_pipeline_jobs_for_run(db, deck=deck, run=run, source_checksum=file.checksum_sha256, max_attempts=3)
        for kind in ("source_ingestion", "source_extraction"):
            jobs[kind].status = "completed"
        jobs["source_extraction"].output_json = {"phase": "source_ready", "slideCount": 2}
        db.commit()
        yield db, deck, run, jobs
    engine.dispose()


def test_publishes_pages_without_creating_or_waiting_for_thumbnails(source):
    db, deck, run, jobs = source
    assert "miniatures" not in jobs
    publisher = jobs["db_publisher"]
    deps = db.query(WorkflowJobDependency).filter_by(job_id=publisher.id).all()
    assert [d.depends_on_job_id for d in deps] == [jobs["source_extraction"].id]
    handle_db_publisher(db, publisher, worker_id="test")
    db.commit()
    state = get_deck_workflow_state(db, deck.id)
    assert state["canOpenSmartDeck"] is True
    assert state["source"]["thumbnailCount"] == 0
    assert state["source"]["thumbnailsRequired"] is False
    assert "slide_thumbnails" not in state["missingArtifacts"]
    assert "miniatures" not in [s["key"] for s in state["stages"]]


@pytest.mark.parametrize("damage", ["missing", "wrong_page", "wrong_run"])
def test_publisher_rejects_incomplete_or_foreign_page_records(source, damage):
    db, deck, run, jobs = source
    page = db.get(DeckSlide, "page2")
    if damage == "missing": db.delete(page)
    elif damage == "wrong_page": page.source_page_number = 3
    else: page.extraction_run_id = "other-run"
    db.flush()
    with pytest.raises(ValueError, match="page"):
        _lock_and_validate_source_publisher(db, job=jobs["db_publisher"])


def test_failed_historical_thumbnail_cannot_gate_reused_pipeline_or_polling(source):
    db, deck, run, jobs = source
    old = WorkflowJob(id="old-thumbnail", deck_id=deck.id, user_id=deck.user_id, extraction_run_id=run.id, job_type="miniatures", status="failed_final", error_code="thumbnail_generation_failed")
    db.add(old); db.flush()
    ensure_workflow_dependency(db, job=jobs["db_publisher"], depends_on_job=old)
    db.commit()
    ensure_pipeline_jobs_for_run(db, deck=deck, run=run, source_checksum="a" * 64, max_attempts=3)
    handle_db_publisher(db, jobs["db_publisher"], worker_id="test")
    db.commit()
    state = get_deck_workflow_state(db, deck.id)
    assert state["canOpenSmartDeck"] is True
    assert state["failedJob"] is None
    assert all(j["jobType"] != "miniatures" for j in state["latestJobs"])


def test_historical_thumbnail_dispatch_does_not_render_or_change_source_state(source, monkeypatch):
    db, deck, run, jobs = source
    old = WorkflowJob(id="old-thumbnail", deck_id=deck.id, user_id=deck.user_id, extraction_run_id=run.id, job_type="miniatures", status="running")
    db.add(old); db.commit()
    def forbidden(*args, **kwargs):
        pytest.fail("Instant Deck must not render source thumbnails")
    monkeypatch.setattr("app.workers.runtime.source_pipeline_runtime.extract_source_previews", forbidden)
    handle_miniatures(db, old, worker_id="test")
    assert old.output_json["skipped"] is True
    assert run.status == "completed"
