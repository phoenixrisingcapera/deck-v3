"""An ID repair must receive the original HTML instead of recreating geometry."""
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.services.llm.instant_html_validation_repair import validation_repair_request, _digest


def test_repair_keeps_the_verified_previous_html_and_reconstructs_exactly():
    original = '<html><main><section><svg><rect x="40" y="80" width="200" height="180"/></svg><p data-source-refs="bad">Source claim</p></section></main></html>'
    body = b'{"presentationIntent":"general"}'
    envelope = {"userPromptHash": sha256(body).hexdigest()}
    envelope["envelopeHash"] = _digest(envelope)
    issues = [{"code": "grounded_fact_unknown", "message": "Unknown data-source-refs: bad", "tagName": "p", "sectionOrdinal": 1, "blocking": True}]
    attempt = SimpleNamespace(id="first", attempt_number=1, request_kind="generation", outcome_known=True,
        validation_summary_json={"status": "failed", "issues": issues})
    kwargs = dict(contract_version="instant-html-validation-repair.v3", previous_output=original)
    result = validation_repair_request(body, envelope, attempt, **kwargs)
    feedback = json.loads(result[0].split(b"\n\n")[1])["validationRepair"]
    assert feedback["previousResponseHtml"] == original
    assert feedback["diagnostics"] == issues
    assert feedback["previousResponseHash"] == sha256(original.encode()).hexdigest()
    assert feedback["previousResponseHash"] == result[2]["previousResponseHash"]
    assert result[1]["envelopeHash"] != envelope["envelopeHash"]
    assert result == validation_repair_request(body, envelope, attempt, **kwargs)
    changed = validation_repair_request(body, envelope, attempt, **{**kwargs, "previous_output": original.replace('height="180"', 'height="-1"')})
    assert changed[1]["envelopeHash"] != result[1]["envelopeHash"]
    assert changed[2]["previousResponseHash"] != result[2]["previousResponseHash"]
    with pytest.raises(ValueError, match="checkpoint"):
        validation_repair_request(body, envelope, attempt, contract_version=kwargs["contract_version"])
    assert b"previousResponseHtml" not in validation_repair_request(body, envelope, attempt)[0]
