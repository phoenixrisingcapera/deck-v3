"""Observed twenty-page run: direct figcaption grounding has no manifest element."""
import pytest

from app.services.llm.full_html_generation_service import _system_prompt, SIX_NODE_FIT_SYSTEM_PROMPT_VERSION
from app.services.rendering.html_deck_compiler import compile_html_deck, HtmlDeckCompileError


def test_image_caption_uses_manifest_backed_paragraph_and_keeps_source_lineage():
    assert 'Never put data-source-refs or data-bind directly on figcaption' in _system_prompt()
    assert 'IMAGE CAPTION GROUNDING' not in _system_prompt(SIX_NODE_FIT_SYSTEM_PROMPT_VERSION)
    document = '<html><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><figure><figcaption data-source-refs="fact_1">Recovered OCR page 8</figcaption></figure></section></main></body></html>'
    args = dict(selected_source_slide_ids=['source_1'], grounded_fact_ids=['fact_1'],
                grounded_fact_sources={'fact_1': ['source_1']},
                grounded_fact_catalog=[{'factId': 'fact_1', 'text': 'Recovered OCR page 8', 'sourceSlideIds': ['source_1']}])
    with pytest.raises(HtmlDeckCompileError) as failure:
        compile_html_deck(document, **args)
    assert failure.value.code == 'grounding_target_invalid'
    fixed = document.replace('<figcaption data-source-refs="fact_1">', '<figcaption><p data-source-refs="fact_1">').replace('</figcaption>', '</p></figcaption>')
    result = compile_html_deck(fixed, **args)
    assert result.manifest['sourceCoverage']['evidenceBackedSourceSlideIds'] == ['source_1']
    caption = next(e for e in result.manifest['slides'][0]['elements'] if e['tagName'] == 'p')
    assert caption['sourceFactIds'] == ['fact_1']
    with pytest.raises(HtmlDeckCompileError, match='unknown grounded fact'):
        compile_html_deck(fixed.replace('data-source-refs="fact_1"', 'data-source-refs="invented"').replace('Recovered OCR page 8', 'Invented revenue 99%'), **args)
