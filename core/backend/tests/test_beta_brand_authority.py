from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import CoreBase
from app.db.models import Deck, DeckBrandProfile, User, Workspace
from app.services.brand import brand_enrichment
from app.services.deck_processing import brand_extraction


@pytest.fixture
def brand_db():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    CoreBase.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id='owner', email='brand@example.test', name='Owner', password_hash='unused'))
        db.add(Workspace(id='workspace', user_id='owner', name='Test'))
        deck = Deck(id='deck', user_id='owner', workspace_id='workspace', title='Synthetic', audience='Investors', purpose='Pitch', status='processing', source_type='pdf', slide_count=1)
        profile = DeckBrandProfile(id='brand', deck_id='deck', primary_color='#CA0012', secondary_color='#EEEBE3', accent_color='#CA0012', background_color='#EEEBE3', text_color='#CA0012', palette_json=['#CA0012','#EEEBE3'], font_candidates_json=['Source Sans'], company_website_url='https://example.test', raw_evidence_json={'confirmedWebsiteUrl':'https://example.test','fieldEvidence':{'fontCandidates':{'source':'deck_extraction','confidence':0.76,'status':'extracted'}},'typographyEvidence':{'source':'source_pdf'}}, processing_status='ready')
        deck.brand_profile=profile
        db.add(deck);db.commit()
        yield db, deck, profile


def test_website_enrichment_keeps_observed_deck_fonts_and_canonical_palette(brand_db, monkeypatch):
    db, deck, profile = brand_db
    monkeypatch.setattr(brand_enrichment, '_extract_typography_evidence', lambda _: (['Website UI','Monospace'], {'source':'website'}))
    brand_enrichment.enrich_brand_profile_after_extract(db, deck.id)
    db.expire_all();db.refresh(profile)
    assert profile.font_candidates_json == ['Source Sans']
    assert profile.raw_evidence_json['typographyEvidence'] == {'source':'source_pdf'}
    assert profile.raw_evidence_json['websiteTypographyEvidence'] == {'source':'website'}
    assert profile.palette_json == ['#CA0012','#EEEBE3']
    assert [v['value'] for v in profile.raw_evidence_json['deterministicSwatches']] == ['#CA0012','#EEEBE3']


def test_beta_brand_workflow_uses_deterministic_extraction_without_brand_llm(brand_db, monkeypatch):
    db, deck, profile = brand_db
    monkeypatch.setattr(settings, 'instant_html_llm_first_beta', True)
    calls=[]
    monkeypatch.setattr(brand_extraction, 'upsert_brand_profile', lambda *a: profile)
    async def extract(*args, **kwargs): calls.append('deterministic')
    monkeypatch.setattr(brand_extraction, 'extract_deck_brand', extract)
    monkeypatch.setattr(brand_extraction, '_enhance_brand_profile_with_slide_analysis', lambda *a: pytest.fail('Beta must not call the secondary brand LLM'))
    monkeypatch.setattr(brand_extraction, 'enrich_brand_profile_after_extract', lambda *a: calls.append('metadata'))
    result=brand_extraction.run_brand_extraction_for_deck(db,deck,company_profile=SimpleNamespace())
    assert calls == ['deterministic','metadata'] and result.id == profile.id
    from app.services.brand.brand_design_tokens import build_provider_safe_brand_context
    context=build_provider_safe_brand_context(result)
    assert context['colors']['primary'] == '#CA0012'
    assert context['tokens']['brand.surface'] == '#EEEBE3'


def test_source_design_palette_preserves_exact_brand_ink_and_background():
    from app.services.brand.brand_extraction import _source_design_palette
    palette = _source_design_palette(['#EEEBE3','#CA0012','#FFFFFF','#EEEBE3','#CA0012'], 7)
    assert palette['primary'] == palette['accent'] == '#CA0012'
    assert palette['background'] == '#EEEBE3'
    assert set(palette['palette']) <= {'#CA0012','#EEEBE3','#FFFFFF','#000000'}


def test_beta_source_identity_outranks_website_sampling(brand_db, monkeypatch):
    import asyncio
    from app.services.brand import brand_extraction as extraction
    db, deck, profile = brand_db
    monkeypatch.setattr(settings, 'instant_html_llm_first_beta', True)
    palette = extraction._source_design_palette(['#CA0012','#EEEBE3'], 1)
    evidence={'paletteSource':'deck_visual','selectedEvidenceKind':'vector_or_block','policy':extraction.SOURCE_BRAND_POLICY}
    monkeypatch.setattr(extraction, '_palette_from_deck_visuals', lambda *a, **kw: (palette, evidence))
    monkeypatch.setattr(extraction, '_palette_from_website_url', lambda *a, **kw: pytest.fail('Do not resample website colors over observed source identity'))
    monkeypatch.setattr(extraction, 'build_website_context', lambda *a: None)
    monkeypatch.setattr(extraction, '_deck_font_candidates', lambda *a: (['Source Sans'],{'source':'source_pdf'}))
    result=asyncio.run(extraction.extract_deck_brand(db,deck.id,None,None,None))
    assert result.primaryColor == '#CA0012' and result.backgroundColor == '#EEEBE3'
    db.refresh(profile)
    assert extraction.confirmed_website_brand_ready(profile)
    assert profile.raw_evidence_json['canonicalExtractionPolicy'] == extraction.SOURCE_BRAND_POLICY


def test_pdf_span_fonts_reach_canonical_brand_without_styled_blocks(brand_db, tmp_path, monkeypatch):
    import fitz
    from app.db.models import DeckSlide
    from app.services.deck_processing import source_extraction
    from app.services.brand.brand_extraction import _deck_font_candidates
    db, deck, profile = brand_db
    path = tmp_path / 'fonts.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 80), 'Source identity heading', fontname='cour', fontsize=24)
        page.insert_text((40, 120), 'Body', fontname='helv', fontsize=12)
        doc.save(path)
    monkeypatch.setattr(source_extraction, 'extract_pdf_embedded_image_assets', lambda *a, **kw: {})
    result = source_extraction.extract_pdf_deck_structure(path)
    metadata = result['slides'][0]['metadataJson']
    db.add(DeckSlide(id='font-slide', deck_id=deck.id, slide_index=1, title='Font test', role='unknown', raw_text='Source identity heading Body', metadata_json=metadata))
    db.flush()
    fonts, evidence = _deck_font_candidates(db, deck)
    assert fonts == ['Courier', 'Helvetica']
    assert evidence['source'] == 'source_pdf_spans'
    profile.font_candidates_json = fonts
    profile.raw_evidence_json = {'fieldEvidence': {'fontCandidates': {'source': 'deck_extraction'}}, 'typographyEvidence': evidence}
    db.commit()
    monkeypatch.setattr(brand_enrichment, '_extract_typography_evidence', lambda _: (['Website UI'], {'source': 'website'}))
    brand_enrichment.enrich_brand_profile_after_extract(db, deck.id)
    assert profile.font_candidates_json == ['Courier', 'Helvetica']
