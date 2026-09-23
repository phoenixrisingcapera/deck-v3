from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import CoreBase
from app.db.models import Deck, DeckInputSource, User, Workspace
from app.services.deck_processing import upload_service as uploads
from app.services.llm import investor_public_research as research


def test_presigned_website_reaches_research_and_reports_unavailable(monkeypatch, tmp_path):
    engine=create_engine('sqlite+pysqlite:///:memory:'); CoreBase.metadata.create_all(engine)
    original=tmp_path/'source.pdf';original.write_bytes(b'%PDF-1.4\nfixture')
    monkeypatch.setattr(uploads,'get_upload_storage',lambda:SimpleNamespace(provider='local',object_metadata=lambda path:{'contentLength':original.stat().st_size},resolve_path=lambda path:original,delete=lambda path:None))
    monkeypatch.setattr(uploads,'scan_upload_path',lambda path:{'status':'clean'})
    monkeypatch.setattr(uploads,'transition_deck_state',lambda *args,**kw:None)
    monkeypatch.setattr(uploads,'_sync_source_ingestion_job',lambda *args,**kw:None)
    monkeypatch.setattr(uploads,'get_deck',lambda *args:{'deck':{}})
    with Session(engine) as db:
        user=User(id='owner',email='website@example.test',name='Owner',password_hash='unused')
        workspace=Workspace(id='workspace',user_id='owner',name='Test')
        deck=Deck(id='deck',user_id='owner',workspace_id='workspace',title='Source',audience='Investors',purpose='Pitch',status='uploaded')
        db.add_all([user,workspace,deck]);db.commit()
        def queue(session,deck_id,**kw):
            assert session.query(DeckInputSource).filter_by(deck_id=deck_id,source_type='company_website').one().external_url=='https://example.org'
            return {'status':'queued'}
        monkeypatch.setattr('app.services.deck_processing.workflow_orchestration.queue_source_extraction',queue)
        uploads.complete_deck_upload(db,deck_id=deck.id,storage_path='users/owner/decks/deck/source/file.pdf',filename='source.pdf',mime_type='application/pdf',website_url='https://example.org/',preferred_workspace='instant_deck')
        delivered=[]
        def discover(session,deck_id,command):
            delivered.append(command)
            assert 'https://example.org/' in command['public_brief']
            raise TimeoutError('fixture unavailable')
        monkeypatch.setattr(research,'discover_public_research',discover)
        research.ensure_generation_public_research(
            db, deck, 'operation',
            research_tasks=[{
                'purpose':'market_context',
                'question':'Which public market conditions shape adoption in this category?',
                'publicSearchContext':'business workflow category adoption',
            }],
            model_research_plan={'status':'model_authored'},
        )
        assert len(delivered)==1
        assert research.public_research_status(db,deck.id)['status']=='unavailable'
        research.ensure_generation_public_research(db,deck,'operation');assert len(delivered)==1
        from app.api.routes.upload_rescue import _persist_upload_brand_intent
        other=Deck(id='ordinary',user_id='owner',workspace_id='workspace',title='Source',audience='Investors',purpose='Pitch',status='uploaded')
        db.add(other);db.flush()
        monkeypatch.setattr('app.api.routes.upload_rescue.upsert_company_profile',lambda *args,**kw:None)
        _persist_upload_brand_intent(db,workspace=workspace,deck=other,canonical_intent={'websiteUrl':'https://example.org/'})
        db.flush()
        assert db.query(DeckInputSource).filter_by(deck_id=other.id,source_type='company_website').one().external_url=='https://example.org'


def test_research_runs_multiple_purposes_without_company_website(monkeypatch):
    engine=create_engine('sqlite+pysqlite:///:memory:'); CoreBase.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(id='owner',email='descriptor@example.test',name='Owner',password_hash='unused')
        workspace=Workspace(id='workspace',user_id='owner',name='Test')
        deck=Deck(id='deck',user_id='owner',workspace_id='workspace',title='Private Company',audience='Investors',purpose='Pitch',status='ready')
        db.add_all([user,workspace,deck]);db.commit()
        delivered=[]
        def discover(session,deck_id,command):
            delivered.append(command)
            assert 'Private Company' not in command['public_brief']
            index=len(delivered)
            claim={
                'id':f'external_{index}','category':'external_research','topic':'market_context',
                'comparisonKey':f'key-{index}','text':f'Verified public evidence {index}.',
                'url':f'https://example.org/source-{index}','publisher':'example.org',
                'publicationDate':'2026-01-01','retrievalDate':'2026-09-19T00:00:00+00:00',
                'pageSha256':'0'*64,'evidenceSha256':'1'*64,
            }
            return {'research':{'claims':[claim],'gaps':[],'conflicts':[],
                'costs':{'researchProviderDollars':'0.10'}}}
        monkeypatch.setattr(research,'discover_public_research',discover)
        research.ensure_generation_public_research(
            db,deck,'operation-no-site',
            company_descriptor={
                'category':'saas category','customer_type':'specialist service businesses',
                'product_type':'workflow software',
            },
            research_tasks=[{'purpose':purpose} for purpose in (
                'why_now','competitor_landscape','customer_economics','business_model_benchmark',
            )],
            research_guidance={
                'skills': [{
                    'name':'customer-economics',
                    'retrievalPurposes':['customer_economics'],
                    'instructions':'Define the economic buyer and verify category economics from primary sources.',
                }],
            },
        )
        assert len(delivered)==4
        customer_brief = next(
            command['public_brief'] for command in delivered
            if 'customer economics' in command['public_brief']
        )
        assert 'Define the economic buyer' in customer_brief
        status=research.public_research_status(db,deck.id)
        assert status['status']=='verified'
        assert status['verifiedClaimCount']==4
        assert status['costs']['searchCount']==4
        dossier=research.research_for_generation(db,deck.id)
        assert dossier['reflectionTrace']
        assert dossier['reflectionTrace'][-1]['decision'] in {'continue','complete'}


def test_known_settled_research_failure_advances_to_next_industry_question(monkeypatch):
    engine=create_engine('sqlite+pysqlite:///:memory:'); CoreBase.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(id='known-owner',email='known@example.test',name='Owner',password_hash='unused')
        workspace=Workspace(id='known-workspace',user_id=user.id,name='Test')
        deck=Deck(id='known-deck',user_id=user.id,workspace_id=workspace.id,title='Fictional Company',audience='Investors',purpose='Pitch',status='ready')
        db.add_all([user,workspace,deck]);db.commit()
        delivered=[]
        def discover(_session,_deck_id,command):
            delivered.append(command)
            if len(delivered) == 1:
                raise research.PublicResearchAttemptFailed(
                    'completed but unusable', outcome_known=True,
                    cost_dollars='0.02', search_tool_calls=1,
                )
            return {'research':{'claims':[],'gaps':[{'reason':'no verified source'}],
                'conflicts':[],'costs':{'researchProviderDollars':'0.01','searchToolCalls':1}}}
        monkeypatch.setattr(research,'discover_public_research',discover)
        research.ensure_generation_public_research(
            db,deck,'known-operation',
            research_tasks=[{'purpose':'competitor_landscape'},{'purpose':'market_context'}],
        )
        assert len(delivered) == 2
        dossier=research.research_for_generation(db,deck.id)
        assert dossier['costs']['paidResearchRequests'] == 2
        assert dossier['costs']['searchCount'] == 2
        assert dossier['costs']['researchProviderDollars'] == '0.03'
