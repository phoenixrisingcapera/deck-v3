"""Exercise the upload worker's persisted budget before provider transport."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.openai_full_html_policy import FULL_HTML_OPENAI_MODEL
from app.db.base import CoreBase
from app.db.models import Deck, DeckSlide, GenerationJob, InstantDeckOperation, User, WorkflowJob, Workspace
from app.services.llm import full_html_generation_service as html
from app.services.llm import instant_html_operation_service as operations
from app.workers.runtime.generation_runtime import handle_instant_deck_generation


class StopBeforeCharge(BaseException):
    """Stop after the locked budget guard, without charging or calling a provider."""


@pytest.mark.parametrize("cost_limit", [None, 500])
def test_upload_worker_preserves_validation_retry_and_rejects_third_request(monkeypatch, cost_limit):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        owner = User(id="owner", email="budget@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="workspace", user_id=owner.id, name="Test")
        deck = Deck(id="deck", user_id=owner.id, workspace_id=workspace.id, title="Test", audience="Investors", purpose="Pitch", status="processing")
        slide = DeckSlide(id="source", deck_id=deck.id, slide_index=0, slide_number=1, title="Test", role="opening", raw_text="Test")
        payload = {"instantOperationId": "operation", "outputContract": "full_html_deck.v1", "generationMode": "instant_deck", "selectedSourceSlideIds": [slide.id], "prompt": "Redesign"}
        job = WorkflowJob(id="job", deck_id=deck.id, user_id=owner.id, workspace_id=workspace.id, job_type="instant_deck_generation", input_json=payload)
        generation = GenerationJob(id=job.id, deck_id=deck.id, status="queued", provider="openai", model=FULL_HTML_OPENAI_MODEL, prompt="Redesign", selected_source_slide_ids_json=[slide.id], llm_context_json={"fullHtmlRequestContextArtifactId": "fixture"})
        operation = InstantDeckOperation(id="operation", deck_id=deck.id, user_id=owner.id, workflow_job_id=job.id, idempotency_key="test", request_hash="test", max_provider_request_starts=2, max_cost_cents=cost_limit)
        db.add_all([owner, workspace, deck, slide, job, generation, operation])
        db.commit()
        monkeypatch.setattr(settings, "openai_api_key", "local-test-only")
        monkeypatch.setattr(settings, "openai_model", FULL_HTML_OPENAI_MODEL)
        monkeypatch.setattr(operations, "validate_output_feasibility", lambda **kw: {})
        monkeypatch.setattr("app.services.llm.openai_provider.instant_openai_model_access_attested", lambda **kw: True)
        monkeypatch.setattr(html, "_require_request_context_ownership", lambda *args, **kw: (operation, deck, owner, job))
        monkeypatch.setattr(html, "resolve_full_html_request_context", lambda **kw: {})
        monkeypatch.setattr(html, "build_full_html_provider_runtime_context", lambda context: context)
        monkeypatch.setattr(html, "validate_full_html_request_feasibility", lambda *args, **kw: {})

        def stop_at_brand_check(_brand):
            raise StopBeforeCharge()

        monkeypatch.setattr("app.services.brand.brand_extraction.confirmed_website_brand_ready", stop_at_brand_check)
        monkeypatch.setattr(operations, "charge_new_operation", lambda session, operation_id, user, locked_eligibility_validator: locked_eligibility_validator(session, operation, user))
        with pytest.raises(StopBeforeCharge):
            handle_instant_deck_generation(db, job, worker_id="local-test")

        db.refresh(operation)
        assert operation.max_provider_request_starts == 2
        assert operation.max_cost_cents == cost_limit
        operation.charge_status = "charged"
        db.commit()
        for kind in ("generation", "deterministic_validation_retry"):
            attempt = operations.start_provider_attempt(db, operation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, request_kind=kind, estimated_input_tokens=100, max_output_tokens=8000)
            if kind == "generation":
                with pytest.raises(operations.InstantOperationConflict, match="recorded compilation-validation"):
                    operations.start_provider_attempt(db, operation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, request_kind="deterministic_validation_retry", estimated_input_tokens=100, max_output_tokens=8000)
                operations.finish_provider_attempt(
                    db, attempt.id, response_state="response_checkpointed", outcome_known=True,
                    usage={"input_tokens": 1000, "output_tokens": 1000},
                )
                db.refresh(operation)
                assert operation.actual_input_tokens == 1000
                assert operation.actual_output_tokens == 1000
                assert operation.actual_provider_cost_cents > 0
                assert operation.max_cost_cents == cost_limit
                attempt.validation_summary_json = {"status": "failed", "issues": [{"code": "grounding_target_invalid"}]}
                db.commit()
                with pytest.raises(operations.InstantOperationConflict, match="recorded compilation-validation"):
                    operations.start_provider_attempt(db, operation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, request_kind="generation", estimated_input_tokens=100, max_output_tokens=8000)
        with pytest.raises(operations.InstantOperationBudgetExceeded, match="request-start budget"):
            operations.start_provider_attempt(db, operation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, request_kind="deterministic_validation_retry", estimated_input_tokens=100, max_output_tokens=8000)
    engine.dispose()
