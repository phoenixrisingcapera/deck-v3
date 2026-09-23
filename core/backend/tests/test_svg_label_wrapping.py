"""Iteration 21's single-line sentences spilled beyond four SVG nodes."""
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.services.llm.full_html_generation_service import _validate_svg_label_wrapping
from app.services.llm.instant_html_validation_repair import validation_repair_request, _digest
from app.services.rendering.html_deck_compiler import HtmlDeckCompileError


def test_observed_long_svg_labels_produce_exact_repair_feedback():
    sentences = ["Presigned object transfer completes.", "Extraction, OCR, and thumbnails persist.",
                 "Provider output survives validation.", "Rendered slides become browser-visible."]
    raw = '<section><svg viewBox="0 0 1440 420">' + ''.join(
        f'<text x="210" y="232" font-size="24">{sentence}</text>' for sentence in sentences
    ) + '</svg></section>'
    with pytest.raises(HtmlDeckCompileError) as failure:
        _validate_svg_label_wrapping(raw)
    assert len(failure.value.issues) == 4
    assert all(issue['sectionOrdinal'] == 1 for issue in failure.value.issues)
    body = b'{"presentationIntent":"general"}'
    envelope = {'userPromptHash': sha256(body).hexdigest()}
    envelope['envelopeHash'] = _digest(envelope)
    previous = SimpleNamespace(id='first', attempt_number=1, request_kind='generation', outcome_known=True,
                               validation_summary_json={'status': 'failed', 'issues': failure.value.issues})
    result = validation_repair_request(body, envelope, previous)
    assert json.loads(result[0].split(b'\n\n')[1])['validationRepair']['diagnostics'] == failure.value.issues
    assert result[1]['envelopeHash'] != envelope['envelopeHash']
    assert result == validation_repair_request(body, envelope, previous, contract_version=result[2]['contractVersion'])
    _validate_svg_label_wrapping('<section><svg><text x="210" y="200">Upload</text>'
                                '<text><tspan x="210" y="230">Presigned object</tspan>'
                                '<tspan x="210" y="260">transfer completes.</tspan></text></svg></section>')
