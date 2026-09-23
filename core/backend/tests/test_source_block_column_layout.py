"""Iteration 23's published caption copied interleaved source-column fragments."""
from types import SimpleNamespace

from app.services.deck_extractors.slide_block_builder import build_slide_blocks
from app.services.llm.instant_deck_context_builder import _slide_facts


def test_column_layout_survives_raw_blocks_and_provider_fact_catalog():
    columns = ('Upload                              Prepare\n'
               'Presigned object transfer           Extraction and OCR\n'
               'completes.                          persist.')
    record = build_slide_blocks('Pipeline stages\n\n' + columns, 3)
    block = record['blocks'][1]
    assert block['rawText'] == columns
    assert block['normalizedText'] == ' '.join(columns.split())
    slide = SimpleNamespace(id='source_3', raw_text=record['rawText'], title=record['title'], summary=None,
                            blocks=[SimpleNamespace(id='block_3', block_index=1, raw_text=block['rawText'])])
    facts, _ = _slide_facts(slide, 'source_3')
    fact = next(fact for fact in facts if fact.field == 'block:block_3')
    assert fact.text == columns
    assert fact.source_slide_ids == ['source_3']
