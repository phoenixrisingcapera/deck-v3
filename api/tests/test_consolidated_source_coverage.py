"""Repeated source annotations need not crowd out a grounded visual."""
from app.services.llm.full_html_generation_service import _system_prompt
from app.services.rendering.html_deck_compiler import compile_html_deck


def test_one_substantive_claim_preserves_all_pages_without_footer_inventory():
    assert "REPEATED SOURCE ANNOTATIONS" in _system_prompt()
    assert "REPEATED SOURCE ANNOTATIONS" not in _system_prompt("full-html-system-prompt.v37")
    sources = [f"source_{n}" for n in range(5)]
    facts = []
    for n, source in enumerate(sources):
        facts.extend([
            {"factId": f"claim_{n}", "text": "Provider output survives validation", "sourceSlideIds": [source]},
            {"factId": f"footer_{n}", "text": f"Expected marker: page {n}", "sourceSlideIds": [source]},
        ])
    document = ('<html><body><main><section class="deck-section" data-source-slide-ids="' + ' '.join(sources) + '">'
                '<h1>Overview</h1><p data-source-refs="' + ' '.join(f"claim_{n}" for n in range(5)) + '">'
                'Provider output survives validation</p></section></main></body></html>')
    result = compile_html_deck(document, selected_source_slide_ids=sources,
        grounded_fact_ids=[f["factId"] for f in facts], grounded_fact_catalog=facts,
        grounded_fact_sources={f["factId"]: f["sourceSlideIds"] for f in facts})
    assert result.manifest["sourceCoverage"]["evidenceBackedSourceSlideIds"] == sources
    assert result.sanitized_html.count("Provider output survives validation") == 1
    assert "Expected marker" not in result.sanitized_html
    assert len(result.manifest["slides"]) == 1
