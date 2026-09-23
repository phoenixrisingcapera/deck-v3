"""Exercise real attempt accounting and transport dispatch without paid calls."""

import copy
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.openai_full_html_policy import FULL_HTML_OPENAI_MODEL
from app.db.base import CoreBase
from app.db.models import Deck, GenerationJob, InstantDeckOperation, InstantDeckProviderAttempt, User, WorkflowJob, Workspace
from app.services.llm import full_html_generation_service as html
from app.services.llm import instant_html_operation_service as operations


def test_new_prompt_states_the_existing_investor_minimum_and_preserves_v17():
    # The deployed first response had six sections. Its v17 request did not
    # state the compiler's seven-section minimum; retain its exact historic hash.
    assert sha256(html._system_prompt("full-html-system-prompt.v17").encode()).hexdigest() == "33805d0b8b149384b2a252bf67c772dfb57cac3c693cbebcac7422f7815ab753"
    assert "at least seven deck sections" in html._system_prompt("full-html-system-prompt.v18")
    assert "seven-page source, use at least eight sections" in html._system_prompt("full-html-system-prompt.v18")
    families = ["editorial-cover", "metric-led", "people-proof", "capital-plan", "comparison", "timeline"]
    raw = '<html><head><style>.deck-section{min-height:100vh}</style></head><body><main>' + ''.join(
        f'<section class="deck-section" data-layout-intent="layout-{i}" data-composition-family="{family}"><h1>Overview</h1></section>'
        for i, family in enumerate(families)
    ) + '</main></body></html>'
    with pytest.raises(html.HtmlDeckCompileError) as exc:
        html.validate_full_html_presentation_quality(raw, context_pack={"audience": "Investment Committee", "sourceDocumentPageCount": 7}, system_prompt_version="full-html-system-prompt.v18")
    assert exc.value.code == "presentation_investor_narrative_incomplete"


@pytest.fixture
def failed_repair(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        owner = User(id="owner", email="repair@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="workspace", user_id=owner.id, name="Test")
        deck = Deck(id="deck", user_id=owner.id, workspace_id=workspace.id, title="Test", audience="Investors", purpose="Pitch", status="processing")
        workflow = WorkflowJob(id="job", deck_id=deck.id, user_id=owner.id, job_type="instant_deck_generation")
        generation = GenerationJob(id="job", deck_id=deck.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, prompt="Redesign", selected_source_slide_ids_json=["source"])
        operation = InstantDeckOperation(id="operation", deck_id=deck.id, user_id=owner.id, workflow_job_id="job", idempotency_key="test", request_hash="test", charge_status="charged", max_provider_request_starts=2, max_cost_cents=None)
        db.add_all([owner, workspace, deck, workflow, generation, operation])
        db.commit()
        context = {"presentationIntent": "investor_pitch", "deckId": deck.id, "sourceSlides": [{"sourceSlideId": "source"}], "requiredSourceCoverage": []}
        monkeypatch.setattr(html, "_validated_provider_runtime_context", lambda context, supplied: context)
        monkeypatch.setattr(html, "_required_source_coverage_catalog", lambda context: [])
        monkeypatch.setattr(html, "_validated_encrypted_exact_request_body", lambda **kw: None)
        monkeypatch.setattr(html, "store_raw_checkpoint", lambda *args, **kw: None)
        monkeypatch.setattr(html, "_repair_checkpoint_raw", lambda *args, **kw: "<html>fixture</html>")
        monkeypatch.setattr(html, "validate_token_feasibility", lambda **kw: SimpleNamespace(input_tokens=100, output_tokens=8000))

        def start(session, operation_id, **kw):
            # Source-lock construction is outside this transport regression;
            # retain real durable attempt creation, eligibility and accounting.
            kw["locked_prestart_binding"] = lambda *args: {"bindingHash": "bound"}
            return operations.start_provider_attempt(session, operation_id, **kw)

        monkeypatch.setattr(html, "start_provider_attempt", start)
        calls = []

        def provider(provider, model, system, user):
            calls.append((system, user))
            return html.ProviderCallResult("<html>fixture</html>", {"input_tokens": 100, "output_tokens": 200}, "response", {"http_status": 200})

        def reject(*args, **kw):
            raise html.HtmlDeckCompileError("presentation_investor_narrative_incomplete", "Investor narrative is incomplete.")

        monkeypatch.setattr(html, "_compile_candidate", reject)
        with pytest.raises(html.HtmlDeckCompileError):
            html.generate_instant_deck(db, operation_id=operation.id, generation_job_id=generation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, context_pack=context, provider_call=provider)
        attempts = db.query(InstantDeckProviderAttempt).order_by(InstantDeckProviderAttempt.attempt_number).all()
        yield db, generation, operation, context, calls, attempts
    engine.dispose()


def test_second_transport_receives_recorded_feedback_and_third_is_rejected(failed_repair):
    db, generation, operation, context, calls, attempts = failed_repair
    assert len(calls) == len(attempts) == operation.provider_request_starts == 2
    assert calls[0][0] == calls[1][0]  # The audited system/source contract is unchanged.
    assert json.loads(calls[0][1]) == context
    assert calls[1][1].startswith(calls[0][1] + "\n\n")
    feedback = json.loads(calls[1][1].split("\n\n", 1)[1])["validationRepair"]
    assert feedback["previousAttemptId"] == attempts[0].id
    assert feedback["diagnostics"][0]["code"] == "presentation_investor_narrative_incomplete"
    assert feedback["diagnostics"] == attempts[0].validation_summary_json["issues"]
    assert feedback["previousResponseHtml"] == "<html>fixture</html>"
    assert feedback["contractVersion"] == "instant-html-validation-repair.v3"
    for attempt, (_, user) in zip(attempts, calls):
        assert attempt.outcome_metadata_json["requestEnvelope"]["userPromptHash"] == sha256(user.encode()).hexdigest()
    assert attempts[0].outcome_metadata_json["requestEnvelope"]["contextHash"] == attempts[1].outcome_metadata_json["requestEnvelope"]["contextHash"]
    assert operation.actual_input_tokens == 200
    assert operation.actual_output_tokens == 400
    assert operation.actual_provider_cost_cents > 0
    assert operation.status == "failed_final"
    with pytest.raises((operations.InstantOperationBudgetExceeded, operations.InstantOperationConflict)):
        operations.start_provider_attempt(db, operation.id, provider="openai", model=FULL_HTML_OPENAI_MODEL, request_kind="deterministic_validation_retry")
    assert db.query(InstantDeckProviderAttempt).count() == 2


@pytest.mark.parametrize("tamper", ["feedback", "envelope", "diagnostic"])
def test_recovery_accepts_derived_repair_but_rejects_changed_semantics(monkeypatch, failed_repair, tamper):
    db, generation, operation, context, calls, attempts = failed_repair
    envelope = attempts[0].outcome_metadata_json["requestEnvelope"]
    binding = {"contractVersion": "full-html-provider-binding.v5", "bindingHash": "bound", "requestEnvelope": envelope, "requestEnvelopeHash": envelope["envelopeHash"], "sourceTextHashVersion": html.FULL_SOURCE_TEXT_HASH_VERSION, "sourceBlocksHashVersion": html.FULL_SOURCE_BLOCKS_HASH_VERSION}
    generation.llm_context_json = {"fullHtmlProviderBinding": binding}
    db.commit()
    monkeypatch.setattr(html, "_current_source_revision", lambda *args, **kw: binding)
    monkeypatch.setattr(html, "_bound_replay_request", lambda **kw: SimpleNamespace(user_prompt_bytes=calls[0][1].encode(), request_envelope=envelope))

    def verify(selected_attempts=None):
        return html.require_provider_bound_context_revision(db, generation_job_id=generation.id, operation_id=operation.id, context_pack=context, attempts=selected_attempts or attempts, provider="openai", model=FULL_HTML_OPENAI_MODEL, max_output_tokens=8000, require_replay_body=False)

    assert verify() == binding
    assert verify([attempts[1]]) == binding
    metadata = copy.deepcopy(attempts[1].outcome_metadata_json)
    if tamper == "feedback":
        metadata["validationRepair"]["previousAttemptId"] = "another-attempt"
    elif tamper == "envelope":
        metadata["requestEnvelope"]["userPromptHash"] = "0" * 64
        metadata["requestEnvelope"]["envelopeHash"] = html._canonical_hash({k: v for k, v in metadata["requestEnvelope"].items() if k != "envelopeHash"})
        metadata["requestEnvelopeHash"] = metadata["requestEnvelope"]["envelopeHash"]
    else:
        attempts[0].validation_summary_json = {"status": "failed", "issues": [{"code": "another_rule"}]}
    attempts[1].outcome_metadata_json = metadata
    db.commit()
    with pytest.raises(html.InstantHtmlCheckpointRecoveryError):
        verify()
