"""The observed general canary failed solely for three readable white slides."""
from app.services.rendering.html_deck_compiler import compile_html_deck
from app.services.rendering.render_proof_service import deck_presentation_quality_failure_codes
from test_instant_html_presentation_quality_metrics import _metrics


def test_general_palette_retains_visual_quality_and_binds_intent():
    observed = [(0, 0, 0), (1, 0, 0), (.2, .25, .0591), (1, 0, 0), (.2, .4167, .557), (.2, .2778, .0687), (1, 0, 0)]
    metrics = [_metrics(nearWhiteSampleRatio=white, largestVisualAreaRatio=area, visualInkAreaRatio=ink) for white, area, ink in observed]
    assert deck_presentation_quality_failure_codes(metrics, presentation_intent='general') == []
    assert deck_presentation_quality_failure_codes(metrics, presentation_intent='investor_pitch') == ['presentation_near_white_deck_exceeded']
    assert deck_presentation_quality_failure_codes(metrics) == ['presentation_near_white_deck_exceeded']
    insufficient_visuals = [_metrics(nearWhiteSampleRatio=1, largestVisualAreaRatio=0, visualInkAreaRatio=0)] * 7
    assert deck_presentation_quality_failure_codes(insufficient_visuals, presentation_intent='general') == ['presentation_visual_storytelling_missing']
    html = '<html><body><main><section class="deck-section" data-source-slide-ids="source_1"><h1>Overview</h1><p data-source-refs="fact_1">The source provides evidence.</p></section></main></body></html>'
    args = dict(selected_source_slide_ids=['source_1'], grounded_fact_ids=['fact_1'], grounded_fact_sources={'fact_1': ['source_1']})
    general = compile_html_deck(html, **args)
    investor = compile_html_deck(html, presentation_intent='investor_pitch', **args)
    assert general.manifest['presentationIntent'] == 'general'
    assert investor.manifest['presentationIntent'] == 'investor_pitch'
    assert general.compilation_hash != investor.compilation_hash
    assert 'presentationIntent' not in compile_html_deck(html, compiler_version='instant-html-compiler.v27', **args).manifest
