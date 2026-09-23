"""Focused checks for the observed metric/count and source-asset boundaries."""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import base64
import json
from pathlib import Path
from PIL import Image
import pytest
from app.instant_deck_spec.numerical_fidelity import PRESENTATION_POLICY, NumericalFidelityError, metric_presentation, validate_plan_numbers
from app.instant_deck_spec.source_package_v2 import NormalizedSourcePackageV2
from app.services.llm import instant_deck_context_builder as context_builder


def test_metric_labels_preserve_context_and_counts_require_matching_source_steps():
    fixture=json.loads((Path(__file__).parent/'fixtures/investor_mvp_production.json').read_text())
    context=fixture['context'];authority=context['mvpPlanner']
    package=NormalizedSourcePackageV2.model_validate_json(json.dumps(authority['sourcePackage']))
    number=next(n for n in package.numbers if n.exact_text=='120')
    presentation=metric_presentation(number,package,context,authority['aliases'])
    assert presentation['value']=='120'
    assert presentation['label']=='active buyers completed repeat orders during the pilot'
    assert presentation['sourceStatement']=='120 active buyers completed repeat orders during the pilot.'
    assert presentation['composition']=='metric'
    changed=deepcopy(context)
    original=next(r for r in authority['sourcePackage']['source_references'] if r['reference_id'] in number.source_reference_ids)['quoted_text']
    for ref in changed['mvpPlanner']['sourcePackage']['source_references']:
        if ref['reference_id'] in number.source_reference_ids:ref['quoted_text']=original+'\n'+original
    for f in changed['sourceFacts']:
        if f['factId'] in authority['aliases']['evidence'][number.number_id]:f['text']=original+'\n'+original
    changed_package=NormalizedSourcePackageV2.model_validate_json(json.dumps(changed['mvpPlanner']['sourcePackage']))
    assert metric_presentation(number,changed_package,changed,authority['aliases'])['composition']=='source-detail'
    visual=SimpleNamespace(steps=[SimpleNamespace(label='Review',detail=None,evidence_ids=['steps']),SimpleNamespace(label='Decide',detail=None,evidence_ids=['steps'])],items=[],people=[],edges=[])
    slide=SimpleNamespace(headline='A practical 2-step path',subhead=None,narrative_job=None,audience_claim=None,consequence=None,selected_evidence_ids=['steps'],body=[],visual=visual)
    plan=SimpleNamespace(deck_title='Review pathway',slides=[slide])
    source={'sourceFacts':[{'factId':'fact','text':'1.Review the evidence\n2.Decide the next action','confidence':'high'}]}
    aliases={'evidence':{'steps':['fact']}}
    validate_plan_numbers(plan,None,source,aliases,presentation_policy=PRESENTATION_POLICY)
    for invalid in ['A practical 3-step path','Revenue of $2M','A practical 2-step path with 50% growth']:
        slide.headline=invalid
        with pytest.raises(NumericalFidelityError):validate_plan_numbers(plan,None,source,aliases,presentation_policy=PRESENTATION_POLICY)
    slide.headline='A practical 2-step path';visual.steps[1].label='Invented stage'
    with pytest.raises(NumericalFidelityError):validate_plan_numbers(plan,None,source,aliases,presentation_policy=PRESENTATION_POLICY)
    visual.steps[1].label='Decide';source['sourceFacts'][0]['confidence']='low'
    with pytest.raises(NumericalFidelityError):validate_plan_numbers(plan,None,source,aliases,presentation_policy=PRESENTATION_POLICY)


def test_large_source_raster_is_prepared_before_catalog_admission(monkeypatch):
    image=Image.new('RGB',(1600,900),'#32765c')
    buf=BytesIO();image.save(buf,format='PNG',compress_level=0);original=buf.getvalue()
    assert len(original)>192*1024
    monkeypatch.setattr(context_builder,'get_upload_storage',lambda:SimpleNamespace(iter_bytes=lambda *args,**kwargs:iter([original])))
    asset=SimpleNamespace(id='photo',mime_type='image/png',storage_path='private/source/photo',created_at=1,label='Source photograph')
    slide=SimpleNamespace(id='source-slide',assets=[asset])
    result=context_builder._build_approved_assets(SimpleNamespace(brand_assets=[]),[slide])
    assert len(result)==1 and result[0].source_slide_ids==['source-slide']
    assert result[0].original_sha256!=result[0].rendered_sha256
    body=base64.b64decode(result[0].resolved_data_url.split(',')[1])
    assert len(body)<=192*1024
    with Image.open(BytesIO(body)) as rendered:
        assert rendered.width/rendered.height==1600/900
        assert rendered.width>=640
    assert original==buf.getvalue()
