"""Offline beta gate checks with real compilation; no provider network calls."""
import copy
import json
import time
from types import SimpleNamespace
import pytest
from app.services.llm import instant_factual_review as review
from app.services.rendering.html_deck_compiler import compile_html_deck

@pytest.fixture
def case():
    facts = [{'factId':'revenue','text':'FY2024 actual revenue was USD 10 million.','sourceSlideIds':['source']},
             {'factId':'team','text':'There are 12 employees.','sourceSlideIds':['source']}]
    args = dict(selected_source_slide_ids=['source'],grounded_fact_ids=['revenue','team'],grounded_fact_catalog=facts,
        grounded_fact_sources={f['factId']:['source'] for f in facts},
        grounded_fact_traceability={f['factId']:{'sourceType':'source_slide','sourceSlideIds':['source']} for f in facts})
    raw = '''<html><head><title>Overview</title><style>.deck-section{height:1080px;padding:80px;background:#fff;color:#111}p{font-size:40px}</style></head><body><main><section class="deck-section" data-source-slide-ids="source"><h1>Overview</h1><p data-source-refs="revenue">FY2024 actual revenue was USD 12 million.</p><p data-source-refs="team">There are 12 employees.</p></section></main></body></html>'''
    context={'factualReviewPolicy':review.POLICY,'factualReviewAllowance':{'maxRequests':2,'maxCostCents':100},
        'betaSourceDocument':{'fileId':'file','sha256':'a'*64},'sourceDocumentPageCount':1,
        'sourceFacts':facts,'sourceSlides':[{'sourceSlideId':'source'}]}
    return raw,context,lambda value:compile_html_deck(value,**args)

def finding(request,*,ambiguous=False):
    entry=next(e for e in request['generatedElements'] if 'revenue' in e['text'])
    return {'generatedSlide':entry['slide'],'elementKey':entry['elementKey'],'generatedClaim':entry['text'],
        'sourcePage':1,'sourceEvidence':'FY2024 actual revenue was USD 10 million.','sourceFactIds':['revenue'],
        'category':'company_fact','material':True,'discrepancy':'Revenue changed from USD 10 million to USD 12 million.',
        'correction':None if ambiguous else 'FY2024 actual revenue was USD 10 million.','sourceAmbiguous':ambiguous}

def report(request,findings):
    return json.dumps({'findings':findings})

def run(case,callback):
    raw,context,compile=case
    return review.review_candidate(None,SimpleNamespace(id='op',deck_id='deck'),compile(raw),context,compile,
        model='gpt-5-2025-08-07',deadline=time.monotonic()+100,review_call=callback,
        source=([],[{'page':1,'text':'FY2024 actual revenue was USD 10 million. There are 12 employees.'}]))

def test_review_corrects_supported_claim_through_actual_compiler_and_verifies(case, tmp_path):
    from app.services.llm.full_html_generation_service import _full_html_request_envelope, BETA_FULL_HTML_SYSTEM_PROMPT_VERSION
    kwargs=dict(provider='openai',model='gpt-5-2025-08-07',max_output_tokens=32000)
    assert _full_html_request_envelope(context_pack=case[1],**kwargs)['systemPromptVersion']==BETA_FULL_HTML_SYSTEM_PROMPT_VERSION
    assert _full_html_request_envelope(context_pack={},**kwargs)['systemPromptVersion']=='full-html-system-prompt.v38'
    original=copy.deepcopy(case[1]);calls=[]
    def reviewer(phase,request):
        calls.append(phase)
        if phase=='review':return report(request,[finding(request)])
        assert 'FY2024 actual revenue was USD 10 million.' in request['generatedHtml']
        assert 'USD 12 million' not in request['generatedHtml']
        return report(request,[])
    compiled=run(case,reviewer)
    assert calls==['review','verification']
    assert case[1]==original
    assert 'USD 10 million' in compiled.safe_slide_documents[0]
    from app.services.rendering.render_proof_service import BrowserRendererAdapter
    proof=BrowserRendererAdapter()._run_playwright_child(render_document=compiled.safe_slide_documents[0],
        viewport={'width':1920,'height':1080,'deviceScaleFactor':1},timeout_seconds=15)
    assert proof['metrics']['contrast']['status']=='passed'
    assert not proof['metrics']['overflowY'] and not proof['metrics']['clippedElementKeys']
    (tmp_path/'corrected.png').write_bytes(proof['screenshot'])
    # Export the actual compiled document and inspect its text, not a hand-built slide.
    import os, fitz
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'])
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.context.set_offline(True)
        page.set_content(case[2](case[0]).safe_slide_documents[0])
        style_script = '(e)=>({font:getComputedStyle(e).font,color:getComputedStyle(e).color,padding:getComputedStyle(e).padding})'
        original_styles=page.locator('[data-da-element-key]').evaluate_all('(es)=>es.map(' + style_script + ')')
        page.set_content(compiled.safe_slide_documents[0])
        assert page.locator('[data-da-element-key]').evaluate_all('(es)=>es.map(' + style_script + ')')==original_styles
        pdf=page.pdf(width='20in',height='11.25in',print_background=True)
        (tmp_path/'corrected.pdf').write_bytes(pdf)
        with fitz.open(stream=pdf,filetype='pdf') as document:
            text=' '.join(page.get_text() for page in document)
            assert len(document)==1 and 'USD 10 million' in text and 'USD 12 million' not in text
        browser.close()

def test_ambiguous_or_unresolved_review_blocks_without_third_request(case):
    calls=[]
    def ambiguous(phase,request):
        calls.append(phase);return report(request,[finding(request,ambiguous=True)])
    with pytest.raises(review.FactualReviewRequired):run(case,ambiguous)
    assert calls==['review']
    calls.clear()
    def unresolved(phase,request):
        calls.append(phase);return report(request,[finding(request)])
    with pytest.raises(review.FactualReviewRequired):run(case,unresolved)
    assert calls==['review','verification']
    # Minor style suggestions do not cause corrections, verification or failure.
    calls.clear()
    def minor(phase,request):
        calls.append(phase)
        suggestion={**finding(request),'category':'presentation_suggestion','material':False,
            'discrepancy':'Prefer a shorter label without changing the company claim.',
            'sourcePage':None,'sourceEvidence':'','sourceFactIds':[],'correction':None}
        return report(request,[suggestion])
    unchanged=run(case,minor)
    assert calls==['review'] and unchanged.compilation_hash==case[2](case[0]).compilation_hash
    # A company-fact finding cannot be downgraded to a cosmetic suggestion.
    def downgraded(phase,request):
        return report(request,[{**finding(request,ambiguous=True),'material':False}])
    with pytest.raises(review.FactualReviewRequired):run(case,downgraded)
    # Echoed hashes / a claimed reviewed-page list are not accepted coverage evidence.
    def echo(phase,request):
        return json.dumps({'findings':[], 'sourceSha256':'a'*64,'reviewedSourcePages':[1]})
    with pytest.raises(review.FactualReviewRequired):run(case,echo)
    context=copy.deepcopy(case[1]);context['factualReviewAllowance']['maxCostCents']=0
    with pytest.raises(review.FactualReviewRequired):review.require_review_allowance(context)
    uncapped=copy.deepcopy(case[1]);uncapped['factualReviewAllowance'].update(enabled=True,maxCostCents=None)
    review.require_review_allowance(uncapped)


def test_review_ledger_resumes_known_response_and_retains_unknown_cost(monkeypatch):
    from cryptography.fernet import Fernet
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import CoreBase
    from app.db.models import Deck, User, Workspace, InstantDeckOperation, DeckLlmArtifact
    from app.services.llm import openai_provider
    from app.core.config import settings
    engine=create_engine('sqlite+pysqlite:///:memory:')
    CoreBase.metadata.create_all(engine)
    monkeypatch.setattr(settings,'workspace_ai_fernet_key',Fernet.generate_key().decode())
    calls=[]
    def provider(**kwargs):
        calls.append(kwargs)
        return {'id':'resp_synthetic','usage':{'input_tokens':100,'output_tokens':50},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{"synthetic":true}'}]}]}
    monkeypatch.setattr(openai_provider,'call_openai_response',provider)
    with Session(engine) as db:
        db.add(User(id='owner',email='review@example.test',name='Owner',password_hash='unused'))
        db.add(Workspace(id='workspace',user_id='owner',name='Test'))
        db.add(Deck(id='deck',user_id='owner',workspace_id='workspace',title='Synthetic',audience='Investors',purpose='Pitch',status='processing',source_type='pdf',slide_count=1))
        op=InstantDeckOperation(id='op',deck_id='deck',user_id='owner',idempotency_key='test',request_hash='test',max_cost_cents=100)
        db.add(op);db.commit()
        def call(phase='review',request=None):
            return review._paid_review(db,op,phase,request or {'synthetic':True},[],{'maxCostCents':100},'gpt-5-2025-08-07',time.monotonic()+100)
        assert call()==call()
        assert len(calls)==1 and op.actual_provider_cost_cents>0 and op.reserved_provider_cost_cents==0
        assert op.provider_request_starts==0  # Does not consume or renew designer starts.
        known=op.actual_provider_cost_cents
        with pytest.raises(review.FactualReviewRequired):call(request={'changed':True})
        assert len(calls)==1
        def unknown(**kwargs):
            calls.append(kwargs);raise TimeoutError('Synthetic timeout')
        monkeypatch.setattr(openai_provider,'call_openai_response',unknown)
        with pytest.raises(review.FactualReviewRequired):call('verification')
        with pytest.raises(review.FactualReviewRequired):call('verification')
        assert len(calls)==2 and op.reserved_provider_cost_cents>0 and op.actual_provider_cost_cents==known
        rows=db.query(DeckLlmArtifact).all()
        assert {r.status for r in rows}=={'completed','outcome_unknown'}
        with pytest.raises(review.FactualReviewRequired):call('third')
        assert len(calls)==2

        # Promotion binds the review decision to application-owned source and
        # compilation identities, not model output or a reviewed-page claim.
        from hashlib import sha256
        context={'factualReviewPolicy':review.POLICY,'betaSourceDocument':{'sha256':'a'*64}}
        compiled=SimpleNamespace(compilation_hash='compiled')
        with pytest.raises(review.FactualReviewRequired):review.require_review_decision(db,op,compiled,context)
        status=DeckLlmArtifact(id='factstatus_'+sha256(op.id.encode()).hexdigest()[:24],deck_id=op.deck_id,
            artifact_type='instant_factual_review_status',artifact_key='status',status='reviewed_with_suggestions',
            payload_json={'operationId':op.id,'sourceSha256':'a'*64,'compilationHash':'compiled','report':{'findings':[]}})
        db.add(status);db.commit()
        review.require_review_decision(db,op,compiled,context)
        with pytest.raises(review.FactualReviewRequired):review.require_review_decision(db,op,SimpleNamespace(compilation_hash='changed'),context)


def test_inert_handoff_resolves_source_title_and_references_before_full_acceptance(tmp_path):
    from app.services.llm.instant_html_review_candidate import HANDOFF_POLICY, QuarantinedCandidate
    from app.services.llm.full_html_generation_service import _prepare_candidate, _compile_candidate
    from app.services.rendering.html_deck_compiler import HtmlDeckCompileError
    facts = [
        {'factId':'title','field':'title','text':'NORTH STAR Helping teams work together','sourceSlideIds':['s']},
        {'factId':'block','field':'block:cover','text':'NORTH\nSTAR\nHelping teams work together','sourceSlideIds':['s']},
        {'factId':'site','text':'WWW.NORTHSTAR.EXAMPLE','sourceSlideIds':['s']},
        {'factId':'revenue','text':'FY2024 actual revenue was USD 10 million.','sourceSlideIds':['s']},
    ]
    for fact in facts:
        fact.update(sourceType='source_slide',sourceId='s')
    context = {'factualReviewPolicy':review.POLICY,'factualReviewHandoffPolicy':HANDOFF_POLICY,
        'factualReviewAllowance':{'maxRequests':2,'maxCostCents':100},
        'betaSourceDocument':{'fileId':'file','sha256':'a'*64},'sourceDocumentPageCount':1,
        'sourceFacts':facts,'sourceSlides':[{'sourceSlideId':'s'}],'metrics':[],'approvedAssets':[]}
    raw = '''<html><head><title>Overview</title><style>.deck-section{height:1080px;padding:80px;background:#fff;color:#111}p{font-size:40px}small{font-size:30px}</style></head><body><main><section class="deck-section" data-source-slide-ids="s"><h1><span>NORTH STAR</span></h1><small data-source-refs="truncated-id">WWW.NORTHSTAR.EXAMPLE</small><p>FY2024 actual revenue was USD 12 million.</p></section></main></body></html>'''
    original=copy.deepcopy(context)
    prepare=lambda html:_prepare_candidate(html,context_pack=context,selected_ids=['s'])
    compile=lambda html:_compile_candidate(html,context_pack=context,selected_ids=['s'])
    candidate=prepare(raw)
    assert isinstance(candidate,QuarantinedCandidate) and not hasattr(candidate,'safe_slide_documents')
    title=next(c for c in candidate.claims if c['text']=='NORTH STAR')
    assert title['sourceFactIds']==['title'] and title['classification']=='verified_source_missing_reference'
    assert sum(c['text']=='NORTH STAR' for c in candidate.claims)==1
    site=next(c for c in candidate.claims if c['text']=='WWW.NORTHSTAR.EXAMPLE')
    assert site['sourceFactIds']==['site'] and site['originalSourceFactIds']==['truncated-id']
    assert any(c['classification']=='requires_evidence_review' for c in candidate.claims)
    assert context==original
    with pytest.raises(HtmlDeckCompileError):compile(candidate.internal_html)
    with pytest.raises(review.FactualReviewRequired):
        review.require_review_decision(None,SimpleNamespace(id='op'),candidate,context)
    # An empty model response cannot approve an unlinked business claim.
    source=([],[{'page':1,'text':'FY2024 actual revenue was USD 10 million.'}])
    with pytest.raises(review.FactualReviewRequired):
        review.review_candidate(None,SimpleNamespace(id='op'),candidate,context,compile,
            model='gpt-5-2025-08-07',deadline=time.monotonic()+100,
            review_call=lambda *args:'{"findings":[]}',source=source)
    calls=[]
    def reviewer(phase,request):
        calls.append(phase)
        if phase=='review':
            assert request['inputKind']==HANDOFF_POLICY and request['generatedHtml']==''
            return report(request,[finding(request)])
        assert 'USD 12 million' not in request['generatedHtml']
        return report(request,[])
    compiled=review.review_candidate(None,SimpleNamespace(id='op'),candidate,context,compile,
        model='gpt-5-2025-08-07',deadline=time.monotonic()+100,review_call=reviewer,source=source)
    assert calls==['review','verification']
    assert 'USD 10 million' in compiled.safe_slide_documents[0]
    assert 'NORTH STAR' in compiled.safe_slide_documents[0]
    from app.services.rendering.render_proof_service import BrowserRendererAdapter
    proof=BrowserRendererAdapter()._run_playwright_child(render_document=compiled.safe_slide_documents[0],
        viewport={'width':1920,'height':1080,'deviceScaleFactor':1},timeout_seconds=15)
    assert proof['metrics']['contrast']['status']=='passed'
    assert not proof['metrics']['clippedElementKeys']
    (tmp_path/'handoff-corrected.png').write_bytes(proof['screenshot'])
    for unsafe in ['<script>alert(1)</script>','<img onerror="alert(1)">','<svg><foreignObject>bad</foreignObject></svg>']:
        with pytest.raises(HtmlDeckCompileError):prepare(raw.replace('</section>',unsafe+'</section>'))
    # A similar prefix, an ambiguous cover or another company's name cannot bind.
    assert not next(c for c in prepare(raw.replace('NORTH STAR</span>','NORTH STAR LABS</span>')).claims if c['tag']=='h1')['sourceFactIds']
    ambiguous=copy.deepcopy(context);ambiguous['sourceFacts'].append({**facts[0],'factId':'second-title'})
    q=_prepare_candidate(raw,context_pack=ambiguous,selected_ids=['s'])
    assert not next(c for c in q.claims if c['tag']=='h1')['sourceFactIds']
    # Unknown text stays unknown; neither a layout label nor an echoed fact ID is proof.
    invented=prepare(raw.replace('FY2024 actual revenue was USD 12 million.','We have invented customers.'))
    assert any(c['text']=='We have invented customers.' and c['classification']=='requires_evidence_review' for c in invented.claims)


def test_review_reads_verified_pdf_when_optional_page_count_is_missing(monkeypatch):
    import fitz
    from hashlib import sha256
    with fitz.open() as pdf:
        pdf.new_page().insert_text((40, 40), 'Source page one')
        pdf.new_page().insert_text((40, 40), 'Source page two')
        data = pdf.tobytes()
    digest = sha256(data).hexdigest()
    source = SimpleNamespace(mime_type='application/pdf', storage_path='private/source.pdf', checksum_sha256=digest)
    db = SimpleNamespace(query=lambda *args: SimpleNamespace(filter_by=lambda **kw: SimpleNamespace(one=lambda: source)))
    monkeypatch.setattr('app.services.storage.artifact_storage.get_upload_storage',
        lambda: SimpleNamespace(iter_bytes=lambda *args, **kw: iter([data])))
    context = {'betaSourceDocument': {'fileId': 'source', 'sha256': digest}, 'sourceDocumentPageCount': None}
    before = copy.deepcopy(context)
    images, pages = review._source_pdf(db, SimpleNamespace(deck_id='deck'), context)
    assert len(images) == 2 and [p['page'] for p in pages] == [1, 2]
    assert 'Source page two' in pages[1]['text'] and context == before
    context['sourceDocumentPageCount'] = 1
    with pytest.raises(review.FactualReviewRequired): review._source_pdf(db, SimpleNamespace(deck_id='deck'), context)


def test_review_accepts_large_pdf_with_complete_text_and_bounded_visual_sample(monkeypatch):
    import fitz
    from hashlib import sha256
    with fitz.open() as pdf:
        for index in range(32):
            pdf.new_page().insert_text((40, 40), f'Source page {index + 1}')
        data = pdf.tobytes()
    digest = sha256(data).hexdigest()
    source = SimpleNamespace(mime_type='application/pdf', storage_path='private/large.pdf', checksum_sha256=digest)
    db = SimpleNamespace(query=lambda *args: SimpleNamespace(filter_by=lambda **kw: SimpleNamespace(one=lambda: source)))
    monkeypatch.setattr('app.services.storage.artifact_storage.get_upload_storage',
        lambda: SimpleNamespace(iter_bytes=lambda *args, **kw: iter([data])))
    context = {'betaSourceDocument': {'fileId': 'source', 'sha256': digest}, 'sourceDocumentPageCount': 32}
    images, pages = review._source_pdf(db, SimpleNamespace(deck_id='deck'), context)
    chunks = review._source_page_chunks(pages)
    assert len(pages) == 32
    assert len(images) == review.REVIEW_MAX_PAGE_IMAGES
    assert [chunk['firstPage'] for chunk in chunks] == [1, 31]
    assert chunks[-1]['lastPage'] == 32
    assert sum(page['imageIncluded'] for page in pages) == review.REVIEW_MAX_PAGE_IMAGES
    context['sourceDocumentPageCount'] = None
    context['betaSourceDocument']['sha256'] = '0' * 64
    with pytest.raises(review.FactualReviewRequired): review._source_pdf(db, SimpleNamespace(deck_id='deck'), context)


def test_review_coverage_marks_unseen_visual_evidence_as_partial(case):
    pages = [
        {'page': index, 'text': '', 'hasImages': True, 'imageEvidenceLikely': True,
         'imageIncluded': index <= review.REVIEW_MAX_PAGE_IMAGES}
        for index in range(1, review.REVIEW_MAX_PAGE_IMAGES + 3)
    ]
    coverage = review._review_coverage(pages, [{'text': 'claim'}], 1)
    assert coverage['status'] == 'partial'
    assert coverage['uncoveredImageEvidencePages'] == [25, 26]

    raw, context, compiler = case
    calls = []
    def reviewer(phase, request):
        calls.append(request['applicationBinding']['reviewCoverage']['status'])
        return report(request, [])
    with pytest.raises(review.FactualReviewRequired, match='Visual source evidence'):
        review.review_candidate(
            None, SimpleNamespace(id='op', deck_id='deck'), compiler(raw), context, compiler,
            model='gpt-5-2025-08-07', deadline=time.monotonic()+100,
            review_call=reviewer, source=([], pages),
        )
    assert calls == ['partial']


@pytest.mark.parametrize('provider_status', ['incomplete', 'failed', 'refused'])
def test_received_unusable_review_preserves_response_and_settles_usage(monkeypatch, provider_status):
    from cryptography.fernet import Fernet
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import CoreBase
    from app.db.models import Deck, User, Workspace, InstantDeckOperation, DeckLlmArtifact
    from app.services.llm import openai_provider
    from app.core.config import settings
    from app.core.instant_html_raw_checkpoint_crypto import get_instant_html_raw_checkpoint_fernet
    engine = create_engine('sqlite+pysqlite:///:memory:')
    CoreBase.metadata.create_all(engine)
    monkeypatch.setattr(settings, 'workspace_ai_fernet_key', Fernet.generate_key().decode())
    payload = {'id': 'resp_synthetic_invalid', 'status': provider_status,
        'usage': {'input_tokens': 1000, 'output_tokens': 6000},
        'incomplete_details': {'reason': 'max_output_tokens'}}
    if provider_status == 'refused':
        payload.update(status='completed', output=[{'type':'message','content':[{'type':'refusal','refusal':'Synthetic refusal'}]}])
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(payload)
    monkeypatch.setattr(openai_provider, 'call_openai_response', provider)
    with Session(engine) as db:
        db.add(User(id='owner', email='review-invalid@example.test', name='Owner', password_hash='unused'))
        db.add(Workspace(id='workspace', user_id='owner', name='Test'))
        db.add(Deck(id='deck', user_id='owner', workspace_id='workspace', title='Synthetic', audience='Investors', purpose='Pitch', status='processing', source_type='pdf', slide_count=1))
        op = InstantDeckOperation(id='op', deck_id='deck', user_id='owner', idempotency_key='test', request_hash='test', max_cost_cents=100)
        db.add(op); db.commit()
        for _ in range(2):
            with pytest.raises(review.FactualReviewRequired):
                review._paid_review(db, op, 'review', {'synthetic':True}, [], {'maxCostCents':100}, 'gpt-5-2025-08-07', time.monotonic()+100)
        row = db.query(DeckLlmArtifact).one()
        assert len(calls) == 1 and calls[0]['max_output_tokens'] == review.REVIEW_MAX_OUTPUT_TOKENS
        assert row.status == 'invalid_response' and row.metrics_json['costKnown'] is True
        assert op.actual_provider_cost_cents == row.metrics_json['costCents'] > 0
        assert op.reserved_provider_cost_cents == 0
        recovered = get_instant_html_raw_checkpoint_fernet().decrypt(row.payload_json['encryptedProviderResponse'].encode())
        assert json.loads(recovered) == payload


def test_unsupported_added_prose_is_omitted_then_whole_deck_verified(case):
    raw, context, compiler = case
    raw = raw.replace('USD 12 million', 'USD 10 million').replace('</section>', '<p data-source-refs="team">A trusted community built for lasting collaboration.</p></section>')
    calls = []
    def reviewer(phase, request):
        calls.append(phase)
        if phase == 'verification':
            assert 'trusted community' not in request['generatedHtml']
            assert 'USD 10 million' in request['generatedHtml']
            return report(request, [])
        e = next(e for e in request['generatedElements'] if 'trusted community' in e['text'])
        return report(request, [{
            'generatedSlide': e['slide'], 'elementKey': e['elementKey'], 'generatedClaim': e['text'],
            'sourcePage': None, 'sourceEvidence': '', 'sourceFactIds': [], 'category': 'company_fact',
            'material': True, 'discrepancy': 'Unsupported added prose.', 'correction': None, 'sourceAmbiguous': True,
        }])
    result = run((raw, context, compiler), reviewer)
    assert calls == ['review', 'verification']
    assert 'trusted community' not in result.sanitized_html
    assert '12 employees' in result.sanitized_html


def test_unsupported_numeric_claim_is_not_silently_removed(case):
    def reviewer(phase, request):
        f = finding(request, ambiguous=True)
        f.update(sourcePage=None, sourceEvidence='', sourceFactIds=[])
        return report(request, [f])
    with pytest.raises(review.FactualReviewRequired):
        run(case, reviewer)


def test_exact_ambiguous_source_statement_is_visible_and_verified(case):
    raw, context, compiler = case
    context = copy.deepcopy(context)
    context['factualReviewResolutionPolicy'] = review.RESOLUTION_POLICY
    raw = raw.replace('USD 12 million', 'USD 10 million')
    calls = []
    def reviewer(phase, request):
        calls.append(phase)
        assert request['resolutionPolicy'] == review.RESOLUTION_POLICY
        if phase == 'verification':
            assert 'Unconfirmed source statement:' in request['generatedHtml']
            assert 'Clarification required.' in request['generatedHtml']
            assert 'USD 10 million' in request['generatedHtml']
            return report(request, [])
        return report(request, [finding(request, ambiguous=True)])
    result = run((raw, context, compiler), reviewer)
    assert calls == ['review', 'verification']
    assert 'Clarification required.' in result.safe_slide_documents[0]
    # A generated value absent from its cited source cannot acquire this notice
    # as a way to publish an invented figure.
    with pytest.raises(review.FactualReviewRequired):
        run((case[0], context, compiler), reviewer)


def test_historical_checkpoint_draft_exposes_text_without_active_markup(monkeypatch):
    from app.services.llm import full_html_generation_service as generation
    attempt = SimpleNamespace(id='attempt')
    class Query:
        def filter_by(self, **kwargs):
            assert kwargs == {'operation_id': 'operation'}
            return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def first(self): return attempt
    db = SimpleNamespace(query=lambda *args: Query())
    accessed = []
    def checkpoint(db, saved, *, expected_deck_id):
        accessed.append((saved.id, expected_deck_id))
        return '<section class="deck-section"><h1>Draft heading</h1><script>steal()</script><p onclick="steal()">Useful draft content</p><img src="https://example.test/private"><style>secret</style></section>'
    monkeypatch.setattr(generation, '_repair_checkpoint_raw', checkpoint)
    draft = review._checkpoint_draft_text(db, SimpleNamespace(id='operation', deck_id='owned-deck'))
    assert accessed == [('attempt', 'owned-deck')]
    assert draft == [{'slide': 1, 'text': 'Draft heading'}, {'slide': 1, 'text': 'Useful draft content'}]


def test_saved_candidate_is_visible_before_review_without_becoming_accepted(monkeypatch):
    op = SimpleNamespace(id='op', status='provider_running', workflow_job_id='job', completed_at=None, actual_provider_cost_cents=12,
                         reserved_provider_cost_cents=20, actual_input_tokens=100,
                         actual_output_tokens=50, provider_request_starts=2)
    class Query:
        def filter_by(self, **kwargs): return self
        def one_or_none(self): return op
        def all(self): return []
    db = SimpleNamespace(query=lambda *args: Query(), get=lambda *args: None)
    monkeypatch.setattr(review, '_checkpoint_draft_text', lambda *args: [{'slide':1,'text':'Saved draft'}])
    result = review.workflow_review(db, 'deck', 'job')
    assert result['status'] == 'draft'
    assert result['draftText'][0]['text'] == 'Saved draft'
    assert result['reviewRequestCount'] == 0
    assert result['providerUsage']['knownCostCents'] == 12
    op.completed_at = 'terminal'
    assert review.workflow_review(db, 'deck', 'job')['status'] == 'technical_failure'


def test_diagnostic_replay_refuses_a_different_saved_candidate(monkeypatch):
    from app.services.llm import full_html_generation_service as generation
    op = SimpleNamespace(id='op', deck_id='deck', workflow_job_id='job')
    job = SimpleNamespace(deck_id='deck', llm_context_json={})
    class Query:
        def filter_by(self, **kwargs): return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def first(self): return SimpleNamespace(id='attempt')
    db = SimpleNamespace(get=lambda *args: job, query=lambda *args: Query())
    monkeypatch.setattr(generation, '_require_persisted_full_html_request_context', lambda **kwargs: {'sourceSlides':[]})
    monkeypatch.setattr(generation, '_repair_checkpoint_raw', lambda *args, **kwargs: 'unchanged checkpoint')
    monkeypatch.setattr(generation, '_prepare_candidate', lambda *args, **kwargs: SimpleNamespace(compilation_hash='different'))
    monkeypatch.setattr(review, 'apply_corrections', lambda *args: pytest.fail('Mismatched candidate must not be corrected'))
    result = review._saved_review_diagnostic(db, op, {'compilationHash':'original'})
    assert result['code'] == 'candidate_binding_changed'


def test_diagnostic_reconstructs_the_corrected_verification_candidate(monkeypatch):
    from app.services.llm import full_html_generation_service as generation
    op = SimpleNamespace(id='op', deck_id='deck', workflow_job_id='job')
    job = SimpleNamespace(deck_id='deck', llm_context_json={})
    original = SimpleNamespace(compilation_hash='original', internal_html='original html')
    corrected = SimpleNamespace(compilation_hash='corrected', internal_html='corrected html')
    class Query:
        def filter_by(self, **kwargs): return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def first(self): return SimpleNamespace(id='attempt')
    db = SimpleNamespace(get=lambda *args: job, query=lambda *args: Query())
    context = {'sourceSlides': [{'sourceSlideId': 'source'}]}
    monkeypatch.setattr(generation, '_require_persisted_full_html_request_context', lambda **kwargs: context)
    monkeypatch.setattr(generation, '_repair_checkpoint_raw', lambda *args, **kwargs: 'checkpoint')
    prepared = iter((original, corrected, corrected))
    monkeypatch.setattr(generation, '_prepare_candidate', lambda *args, **kwargs: next(prepared))
    monkeypatch.setattr(generation, '_compile_candidate', lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(review, 'apply_corrections', lambda *args, **kwargs: 'corrected html')
    monkeypatch.setattr(review, '_elements', lambda *args: [])
    result = review._saved_review_diagnostic(db, op, {
        'compilationHash': 'corrected',
        'report': {'findings': []},
        'initialReport': {'findings': []},
    })
    assert result['code'] == 'saved_correction_compiles'
    assert result['boundary'] == 'rendering'


def test_verification_resolves_remaining_links_without_another_design(case):
    from app.services.llm.instant_html_review_candidate import prepare_candidate, HANDOFF_POLICY
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION
    raw, context, compile = case
    context = {**context, 'factualReviewHandoffPolicy': HANDOFF_POLICY}
    raw = raw.replace('<h1>Overview</h1>', '<h1>A dozen colleagues build our business</h1>')
    prepare = lambda html: prepare_candidate(html, context=context, compiler_version=COMPILER_VERSION)
    candidate = prepare(raw)
    calls = []
    def reviewer(phase, request):
        calls.append(phase)
        if phase == 'review':
            return report(request, [finding(request)])
        assert request['inputKind'] == HANDOFF_POLICY
        assert any('USD 10 million' in e['text'] for e in request['generatedElements'])
        headline = next(e for e in request['generatedElements'] if 'dozen colleagues' in e['text'])
        return report(request, [{
            'generatedSlide': headline['slide'], 'elementKey': headline['elementKey'],
            'generatedClaim': headline['text'], 'sourcePage': 1,
            'sourceEvidence': 'There are 12 employees.', 'sourceFactIds': ['team'],
            'category': 'company_fact', 'material': True, 'discrepancy': 'Missing evidence link.',
            'correction': headline['text'], 'sourceAmbiguous': False,
        }])
    source = ([], [{'page': 1, 'text': 'FY2024 actual revenue was USD 10 million. There are 12 employees.'}])
    result = review.review_candidate(None, SimpleNamespace(id='op'), candidate, context, compile,
        model='gpt-5-2025-08-07', deadline=time.monotonic()+100, review_call=reviewer,
        source=source, prepare_corrected=prepare)
    assert calls == ['review', 'verification']
    assert 'A dozen colleagues build our business' in result.safe_slide_documents[0]
    assert 'USD 12 million' not in result.safe_slide_documents[0]
    # A second empty review cannot confer a missing reference.
    with pytest.raises(review.FactualReviewRequired):
        review.review_candidate(None, SimpleNamespace(id='op'), candidate, context, compile,
            model='gpt-5-2025-08-07', deadline=time.monotonic()+100,
            review_call=lambda phase, request: report(request, [finding(request)] if phase == 'review' else []),
            source=source, prepare_corrected=prepare)


def test_safe_draft_retains_uncertainty_and_missing_links_as_metadata(case):
    from app.services.llm.instant_html_review_candidate import prepare_candidate, HANDOFF_POLICY
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION, HtmlDeckCompileError
    raw, context, strict_compile = case
    context = {**context, 'factualReviewHandoffPolicy': HANDOFF_POLICY}
    raw = raw.replace('<h1>Overview</h1>', '<h1>Our people build the business</h1>')
    prepare = lambda html: prepare_candidate(html, context=context, compiler_version=COMPILER_VERSION)
    def draft(html, claims):
        return compile_html_deck(html, selected_source_slide_ids=['source'],
            grounded_fact_ids=['revenue', 'team'], grounded_fact_catalog=context['sourceFacts'],
            grounded_fact_sources={'revenue': ['source'], 'team': ['source']},
            draft_claims=claims, advisory_review=True)
    candidate = prepare(raw)
    with pytest.raises(HtmlDeckCompileError): strict_compile(candidate.internal_html)
    result = review.review_candidate(None, SimpleNamespace(id='op'), candidate, context, strict_compile,
        model='gpt-5-2025-08-07', deadline=time.monotonic()+100,
        review_call=lambda phase, request: report(request, [finding(request, ambiguous=True)]),
        source=([], [{'page': 1, 'text': 'FY2024 actual revenue was USD 10 million.'}]),
        prepare_corrected=prepare, compile_draft=draft)
    assert result.manifest['evidencePolicy'] == 'advisory-draft.v1'
    assert result.manifest['draftReferenceWarnings'][0]['slide'] == 1
    assert 'data-da-draft-notice' not in result.safe_slide_documents[0]
    assert 'USD 12 million' in result.safe_slide_documents[0]  # Never guess the source resolution.
    assert 'Our people build the business' in result.safe_slide_documents[0]
    with pytest.raises(HtmlDeckCompileError):
        compile_html_deck(candidate.internal_html, selected_source_slide_ids=['source'],
                          draft_claims=candidate.claims)  # Only application code can select the advisory policy.


def test_draft_layout_warnings_do_not_relax_browser_safety():
    from app.services.rendering.render_proof_service import render_metrics_have_blocking_failure
    metrics = {'visible': True, 'overflowY': True, 'clippedElementKeys': ['body-01']}
    assert render_metrics_have_blocking_failure(metrics)
    assert not render_metrics_have_blocking_failure(metrics, draft=True)
    assert render_metrics_have_blocking_failure(metrics, ['browser error'], draft=True)
    assert render_metrics_have_blocking_failure({'visible': False}, draft=True)


def test_saved_review_resume_keeps_operation_budget_and_forbids_designer():
    from datetime import datetime
    from hashlib import sha256
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import CoreBase
    from app.db.models import User, Workspace, Deck, WorkflowJob, InstantDeckOperation, InstantDeckProviderAttempt, DeckLlmArtifact
    from app.services.llm.instant_html_operation_service import start_provider_attempt, InstantOperationConflict
    engine = create_engine('sqlite+pysqlite:///:memory:')
    CoreBase.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id='owner', email='resume@example.test', name='Owner', password_hash='unused'))
        db.add(Workspace(id='workspace', user_id='owner', name='Test'))
        db.add(Deck(id='deck', user_id='owner', workspace_id='workspace', title='Synthetic', audience='Investors', purpose='Pitch', status='processing', source_type='pdf', slide_count=1))
        job = WorkflowJob(id='job', deck_id='deck', user_id='owner', workspace_id='workspace', job_type='instant_deck_generation', status='failed_final', idempotency_key='job', attempt_count=1, max_attempts=3)
        op = InstantDeckOperation(id='op', deck_id='deck', user_id='owner', workflow_job_id='job', idempotency_key='op', request_hash='test', status='failed_final', terminal_reason='factual_review_required', charge_status='released', completed_at=datetime.utcnow(), provider_request_starts=2, actual_provider_cost_cents=53.1, max_cost_cents=1000)
        db.add_all([job, op])
        for ordinal in (1, 2):
            db.add(InstantDeckProviderAttempt(id=f'attempt{ordinal}', operation_id='op', attempt_number=ordinal, provider='openai', model='gpt-5-2025-08-07', outcome_known=True, raw_artifact_id=f'raw{ordinal}', response_state='response_checkpointed'))
        db.add(DeckLlmArtifact(id='factreview_'+sha256(b'op:review').hexdigest()[:24], deck_id='deck', artifact_type=review.POLICY, artifact_key='review', status='completed', metrics_json={'costKnown': True}, payload_json={'operationId':'op'}))
        db.add(DeckLlmArtifact(id='factstatus_'+sha256(b'op').hexdigest()[:24], deck_id='deck', artifact_type='instant_factual_review_status', artifact_key='status', status='needs_review', payload_json={'sourceSha256':'a'*64, 'report':{'findings':[]}}))
        db.commit()
        assert review.can_resume_saved_review(db, op)
        assert review.queue_saved_review_resume(db, 'deck', current_user_id='owner', workflow_job=job).id == 'job'
        assert op.id == 'op' and op.provider_request_starts == 2 and op.actual_provider_cost_cents == 53.1 and op.max_cost_cents == 1000
        assert job.attempt_count == 1 and job.max_attempts == 3 and job.status == 'queued'
        assert review.require_review_resume_lineage(db, op).payload_json['previousStatus'] == 'failed_final'
        with pytest.raises(InstantOperationConflict):
            start_provider_attempt(db, op.id, provider='openai', model='gpt-5-2025-08-07', request_kind='generation')
        assert review.queue_saved_review_resume(db, 'deck', current_user_id='owner', workflow_job=job).id == 'job'
        assert not review.can_resume_saved_review(db, op)
        assert db.query(InstantDeckProviderAttempt).count() == 2


def test_advisory_missing_lineage_and_unknown_refs_preserve_output_and_coverage(case):
    from app.services.llm.instant_html_review_candidate import prepare_candidate
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION
    raw, context, _ = case
    raw = raw.replace('data-source-slide-ids="source"', '').replace('data-source-refs="revenue"', 'data-source-refs="missing"').replace('data-source-refs="team"', '')
    candidate = prepare_candidate(raw, context=context, compiler_version=COMPILER_VERSION)
    result = compile_html_deck(candidate.internal_html, selected_source_slide_ids=['source', 'unused'],
        grounded_fact_ids=['revenue', 'team', 'unused-fact'],
        grounded_fact_catalog=context['sourceFacts'] + [{'factId':'unused-fact', 'text':'An unused source statement.', 'sourceSlideIds':['unused']}],
        grounded_fact_sources={'revenue':['source'], 'team':['source'], 'unused-fact':['unused']},
        draft_claims=candidate.claims, advisory_review=True)
    assert len(result.safe_slide_documents) == 1
    assert 'USD 12 million' in result.safe_slide_documents[0]
    assert result.manifest['sourceCoverage']['complete'] is False
    assert 'unused' in result.manifest['sourceCoverage']['missingSourceSlideIds']
    assert any(w.get('code') == 'unknown_evidence_reference' for w in result.manifest['draftReferenceWarnings'])
    assert 'data-da-draft-notice' not in result.sanitized_html


def test_unknown_lineage_is_corrected_only_from_canonical_bound_evidence(case):
    from app.services.llm.instant_html_review_candidate import prepare_candidate
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION

    raw, context, _ = case
    raw = raw.replace('data-source-slide-ids="source"', 'data-source-slide-ids="invented-slide-id"')
    candidate = prepare_candidate(raw, context=context, compiler_version=COMPILER_VERSION)
    assert 'data-source-slide-ids="source"' in candidate.internal_html
    correction = next(item for item in candidate.diagnostics if item['code'] == 'source_lineage_corrected')
    assert correction['invalidSourceSlideIds'] == ['invented-slide-id']
    assert correction['correctedSourceSlideIds'] == ['source']
    assert correction['supportingSourceFactIds'] == ['revenue', 'team']


def test_unknown_unbound_lineage_reports_exact_repairable_registry_diagnostics(case):
    from app.services.llm.instant_html_review_candidate import prepare_candidate
    from app.services.rendering.html_deck_compiler import COMPILER_VERSION, HtmlDeckCompileError

    raw, context, _ = case
    raw = raw.replace('data-source-slide-ids="source"', 'data-source-slide-ids="invented-slide-id"')
    raw = raw.replace(' data-source-refs="revenue"', '').replace(' data-source-refs="team"', '')
    with pytest.raises(HtmlDeckCompileError) as raised:
        prepare_candidate(raw, context=context, compiler_version=COMPILER_VERSION)
    issue = raised.value.issues[0]
    assert raised.value.code == 'source_lineage_unknown'
    assert issue['repairable'] is True
    assert issue['generationStage'] == 'pre_factual_review_lineage_validation'
    assert issue['invalidSourceSlideIds'] == ['invented-slide-id']
    assert issue['expectedSourceSlideIds'] == ['source']
