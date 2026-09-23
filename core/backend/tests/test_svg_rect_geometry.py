"""Observed canary bars disappeared or inverted after invalid SVG attributes."""
import pytest

from app.services.rendering.html_deck_compiler import HtmlDeckCompileError, compile_html_deck


def test_svg_bar_geometry_fails_in_compiler_so_repair_can_receive_it():
    template = '<html><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><svg viewBox="0 0 1440 440" data-source-refs="fact_1"><rect x="100" y="{y}" width="200" height="{height}"/></svg></section></main></body></html>'
    args = dict(selected_source_slide_ids=["source_1"], grounded_fact_ids=["fact_1"], grounded_fact_sources={"fact_1": ["source_1"]})
    for y, height in [("380- (380*0.38)", "380"), ("380", "-144.4")]:
        with pytest.raises(HtmlDeckCompileError) as failure:
            compile_html_deck(template.format(y=y, height=height), **args)
        assert failure.value.code == "svg_rect_geometry_invalid"
        assert failure.value.issues[0]["blocking"] is True
        assert "precomputed" in failure.value.issues[0]["message"]
        # Historical checkpoint bytes and validation remain reconstructible.
        compile_html_deck(template.format(y=y, height=height), compiler_version="instant-html-compiler.v25", **args)
    compile_html_deck(template.format(y="235.6", height="144.4"), **args)


def test_final_evidence_node_cannot_be_cropped_and_geometry_feedback_is_batched():
    html = '<html><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><svg viewBox="0 0 1440 560" data-source-refs="fact_1"><rect x="1240" y="210" width="210" height="120" rx="14"/></svg></section></main></body></html>'
    args = dict(selected_source_slide_ids=["source_1"], grounded_fact_ids=["fact_1"], grounded_fact_sources={"fact_1": ["source_1"]})
    compile_html_deck(html, compiler_version="instant-html-compiler.v26", **args)
    with pytest.raises(HtmlDeckCompileError) as failure:
        compile_html_deck(html, **args)
    assert failure.value.code == 'svg_evidence_rect_clipped'
    assert failure.value.issues[0]['sectionOrdinal'] == 1
    both = html.replace('</svg>', '<rect x="100" y="380" width="100" height="-144.4"/></svg>')
    with pytest.raises(HtmlDeckCompileError) as failure:
        compile_html_deck(both, **args)
    assert {issue['code'] for issue in failure.value.issues} == {'svg_rect_geometry_invalid', 'svg_evidence_rect_clipped'}
    compile_html_deck(html.replace('x="1240"', 'x="1230"'), **args)
