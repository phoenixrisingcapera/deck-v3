"""Regression for the observed SVG grounding failure losing its section/tag details."""
import json
from hashlib import sha256
from types import SimpleNamespace
import pytest
from app.services.llm.instant_html_validation_repair import validation_repair_request, _digest


def test_exact_structured_grounding_failure_is_bound_and_reconstructed_without_investor_leak():
    body=b'{"presentationIntent":"general"}'
    envelope={'userPromptHash':sha256(body).hexdigest()};envelope['envelopeHash']=_digest(envelope)
    issues=[{'severity':'error','category':'grounding','code':'grounding_target_invalid','message':'Grounding must be attached to a manifest-backed content element.','blocking':True,'tagName':'text','sectionOrdinal':3}]
    previous=SimpleNamespace(id='attempt-one',attempt_number=1,request_kind='generation',outcome_known=True,validation_summary_json={'status':'failed','issues':issues})
    result=validation_repair_request(body,envelope,previous)
    feedback=json.loads(result[0].split(b'\n\n')[1])['validationRepair']
    assert feedback['diagnostics']==issues
    assert result[1]['envelopeHash']!=envelope['envelopeHash']
    assert result==validation_repair_request(body,envelope,previous,contract_version=result[2]['contractVersion'])
    assert b'people-proof' not in result[0] and b'capital-plan' not in result[0]
    legacy=validation_repair_request(body,envelope,previous,contract_version='instant-html-validation-repair.v1')
    assert legacy==validation_repair_request(body,envelope,previous,contract_version=legacy[2]['contractVersion'])
    previous.validation_summary_json['issues']=[{'code':'presentation_investor_narrative_incomplete'}]
    with pytest.raises(ValueError,match='Investor diagnostics'):
        validation_repair_request(body,envelope,previous)
