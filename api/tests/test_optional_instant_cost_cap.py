from types import SimpleNamespace
import pytest
from app.core.openai_full_html_policy import FULL_HTML_OPENAI_MODEL
from app.services.llm.instant_html_operation_service import normalize_operation_cost_limit, require_next_request_cost_budget, InstantOperationBudgetExceeded


def operation(limit):
    return SimpleNamespace(max_cost_cents=limit, actual_provider_cost_cents=600.0, reserved_provider_cost_cents=0.0)


def test_uncapped_operation_can_continue_above_the_former_five_dollar_limit():
    op = operation(None)
    assert normalize_operation_cost_limit(op) is False
    assert require_next_request_cost_budget(op, provider="openai", model=FULL_HTML_OPENAI_MODEL, estimated_input_tokens=100, max_output_tokens=8000) > 0


def test_explicit_canary_limit_is_still_enforced():
    with pytest.raises(InstantOperationBudgetExceeded):
        normalize_operation_cost_limit(operation(500))


def test_explicit_larger_limit_is_not_silently_clamped():
    op = operation(2000)
    assert normalize_operation_cost_limit(op) is False
    assert op.max_cost_cents == 2000


def test_configuration_and_persistence_share_exact_two_request_default():
    from app.core.config import Settings
    from app.core.instant_deck_request_policy import MAX_PROVIDER_REQUEST_STARTS
    from app.db.models import InstantDeckOperation
    from pydantic import ValidationError
    assert MAX_PROVIDER_REQUEST_STARTS == 2
    assert Settings.model_fields["instant_html_max_provider_starts"].default == 2
    assert InstantDeckOperation.__table__.c.max_provider_request_starts.default.arg == 2
    assert str(InstantDeckOperation.__table__.c.max_provider_request_starts.server_default.arg) == "2"
    assert Settings.model_fields["instant_html_max_operation_cost_cents"].default is None
    for limit in (0, -1):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, instant_html_max_operation_cost_cents=limit)
    for starts in (1, 3):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, instant_html_max_provider_starts=starts)
