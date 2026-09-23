"""The observed overflow need not duplicate SVG facts in a vertical HTML list."""
import pytest
from app.services.rendering.html_deck_compiler import compile_html_deck,HtmlDeckCompileError


def test_svg_root_carries_numeric_grounding_without_a_duplicate_html_inventory():
    html='''<html><head><title>Progress</title></head><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><svg viewBox="0 0 1440 440" data-source-refs="fact_upload fact_publish"><text x="100" y="100">Upload 38%</text><text x="700" y="100">Publish 100%</text></svg></section></main></body></html>'''
    facts=[{'factId':'fact_upload','text':'Upload 38%','sourceSlideIds':['source_1']},{'factId':'fact_publish','text':'Publish 100%','sourceSlideIds':['source_1']}]
    args=dict(selected_source_slide_ids=['source_1'],grounded_fact_ids=[f['factId'] for f in facts],grounded_fact_catalog=facts,grounded_fact_sources={f['factId']:['source_1'] for f in facts},grounded_fact_traceability={f['factId']:{'sourceType':'source_slide','sourceSlideIds':['source_1']} for f in facts})
    result=compile_html_deck(html,**args)
    assert result.manifest['sourceCoverage']['evidenceBackedSourceSlideIds']==['source_1']
    assert '<li' not in result.sanitized_html
    invalid=html.replace(' data-source-refs="fact_upload fact_publish"','').replace('<text x="100"','<text data-source-refs="fact_upload" x="100"')
    with pytest.raises(HtmlDeckCompileError,match='manifest-backed'):
        compile_html_deck(invalid,compiler_version="instant-html-compiler.v24",**args)


def test_svg_fact_labels_are_read_only_and_keep_grounding_checks():
    html = '<html><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><svg viewBox="0 0 1440 440"><text x="100" y="100" data-source-refs="fact_upload">Upload 38%</text><text x="700" y="100"><tspan data-source-refs="fact_publish">Publish 100%</tspan></text></svg></section></main></body></html>'
    args = dict(
        selected_source_slide_ids=["source_1"],
        grounded_fact_ids=["fact_upload", "fact_publish"],
        grounded_fact_sources={"fact_upload": ["source_1"], "fact_publish": ["source_1"]},
    )
    result = compile_html_deck(html, **args)
    labels = [entry for entry in result.manifest["slides"][0]["elements"] if entry["tagName"] in {"text", "tspan"}]
    assert len(labels) == 2
    assert [entry["sourceFactIds"] for entry in labels] == [["fact_upload"], ["fact_publish"]]
    assert all(entry["elementType"] == "text" and entry["locked"] and entry["capabilities"] == ["select"] for entry in labels)
    assert result.manifest["sourceCoverage"]["evidenceBackedSourceSlideIds"] == ["source_1"]
    with pytest.raises(HtmlDeckCompileError, match="unknown grounded fact"):
        compile_html_deck(html.replace('data-source-refs="fact_upload"', 'data-source-refs="invented"'), **args)
    with pytest.raises(HtmlDeckCompileError, match="lineage"):
        compile_html_deck(html, **{**args, "grounded_fact_sources": {"fact_upload": ["unselected"], "fact_publish": ["source_1"]}})
