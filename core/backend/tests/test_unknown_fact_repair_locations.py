"""Observed repair repeated an unknown-ID failure without actionable locations."""
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.services.rendering.html_deck_compiler import compile_html_deck, HtmlDeckCompileError
from app.services.llm.instant_html_validation_repair import validation_repair_request, _digest


def test_unknown_references_keep_exact_ids_and_locations_in_the_repair():
    raw = '<html><body><main><section class="deck-section" data-source-slide-ids="source"><h1>Overview</h1><p data-source-refs="fact_bad_p">Validated output</p><svg viewBox="0 0 1440 420" data-source-refs="fact_bad_svg"><text x="100" y="100">Upload</text></svg></section></main></body></html>'
    args = dict(selected_source_slide_ids=["source"], grounded_fact_ids=["fact_valid"],
                grounded_fact_sources={"fact_valid": ["source"]})
    with pytest.raises(HtmlDeckCompileError) as caught:
        compile_html_deck(raw, **args)
    issues = caught.value.issues
    assert [i["tagName"] for i in issues] == ["p", "svg"]
    assert all(i["sectionOrdinal"] == 1 and i["blocking"] for i in issues)
    assert "fact_bad_p" in issues[0]["message"] and "fact_bad_svg" in issues[1]["message"]
    body = b'{"presentationIntent":"general"}'
    envelope = {"userPromptHash": sha256(body).hexdigest()}
    envelope["envelopeHash"] = _digest(envelope)
    attempt = SimpleNamespace(id="first", attempt_number=1, request_kind="generation", outcome_known=True,
        validation_summary_json={"status": "failed", "issues": issues})
    repair = validation_repair_request(body, envelope, attempt)
    assert json.loads(repair[0].split(b"\n\n")[1])["validationRepair"]["diagnostics"] == issues
    assert repair[1]["envelopeHash"] != envelope["envelopeHash"]
    assert repair == validation_repair_request(body, envelope, attempt)
    with pytest.raises(HtmlDeckCompileError) as historical:
        compile_html_deck(raw, compiler_version="instant-html-compiler.v28", **args)
    assert all("tagName" not in i for i in historical.value.issues)
