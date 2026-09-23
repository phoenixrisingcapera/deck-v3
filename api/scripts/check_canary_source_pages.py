"""Extract and persist the four synthetic canary PDFs without thumbnails or LLM calls."""
import hashlib
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import CoreBase
from app.db.models import Deck, DeckFile, DeckExtractionRun, User, Workspace
from app.services.deck_processing.source_extraction import extract_pdf_deck_structure
from app.services.deck_processing.deterministic_extraction import _persist_slides, _persist_blocks
from app.services.deck_processing.source_page_readiness import require_extracted_page_records
from app.services.deck_processing.workflow_jobs import ensure_pipeline_jobs_for_run
from app.workers.runtime.publisher_runtime import handle_db_publisher
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state


def main():
    output = BACKEND / '.artifacts/canonical-canaries'
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for count in (7, 10, 15, 20):
        path = BACKEND.parent / f'ignore/instant-deck-canary-{count:02}-pages.pdf'
        extracted = extract_pdf_deck_structure(path)
        engine = create_engine('sqlite+pysqlite:///:memory:')
        CoreBase.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            user = User(id='user', email='source-canary@example.test', name='Source Canary', password_hash='unused')
            ws = Workspace(id='ws', user_id=user.id, name='Synthetic canary')
            deck = Deck(id='deck', user_id=user.id, workspace_id=ws.id, title='Synthetic canary', audience='Test', purpose='Test', status='processing')
            file = DeckFile(id='file', deck_id=deck.id, filename=path.name, mime_type='application/pdf', size=path.stat().st_size, checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), page_count=count, metadata_json={'preferredWorkspace':'instant_deck'})
            run = DeckExtractionRun(id='run', deck_id=deck.id, source_file_id=file.id, slide_count=count, status='completed')
            db.add_all([user, ws, deck, file, run]);db.commit()
            slides = _persist_slides(db, deck.id, run.id, file.id, extracted['slides'])
            blocks = _persist_blocks(db, deck.id, run.id, slides, extracted['slides'])
            db.commit()
            pages = require_extracted_page_records(db, deck_id=deck.id, source_file_id=file.id, extraction_run_id=run.id, expected_page_count=count)
            for number, page in enumerate(pages, 1):
                assert f'CANARY-{count:02}-SEP2026-P{number:02}' in page.raw_text, (count, number)
                assert page.thumbnail_path is None
            jobs = ensure_pipeline_jobs_for_run(db, deck=deck, run=run, source_checksum=file.checksum_sha256, max_attempts=3)
            assert 'miniatures' not in jobs
            for kind in ('source_ingestion', 'source_extraction'):jobs[kind].status='completed'
            jobs['source_extraction'].output_json={'phase':'source_ready','slideCount':count}
            db.commit()
            handle_db_publisher(db, jobs['db_publisher'], worker_id='source-canary');db.commit()
            state=get_deck_workflow_state(db, deck.id)
            assert state['canOpenSmartDeck'] and 'slide_thumbnails' not in state['missingArtifacts']
            result={'file':path.name,'expectedPages':count,'persistedPages':len(pages),'matchingMarkers':len(pages),'blocks':len(blocks),'thumbnails':0,'thumbnailJobs':0,'sourcePublication':jobs['db_publisher'].status,'providerRequests':0,'generatedDeckAcceptance':'not_exercised'}
            reports.append(result);print(json.dumps(result),flush=True)
        engine.dispose()
    (output/'source-page-report.json').write_text(json.dumps(reports,indent=2))


if __name__ == '__main__':main()
