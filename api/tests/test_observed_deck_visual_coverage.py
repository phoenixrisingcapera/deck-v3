"""Keep iteration 4's real aggregate quality failure rejected."""
from app.services.rendering.render_proof_service import deck_presentation_quality_failure_codes
from test_instant_html_presentation_quality_metrics import _metrics


def test_observed_seven_slide_sequence_requires_more_than_one_substantial_visual():
    observed = [(0,0,0),(1,.1489,.0809),(.1333,.165,.0083),(.2,0,0),(1,.165,.0199),(.1333,.165,.0122),(1,0,0)]
    metrics = [_metrics(nearWhiteSampleRatio=white,largestVisualAreaRatio=area,visualInkAreaRatio=ink) for white,area,ink in observed]
    assert set(deck_presentation_quality_failure_codes(metrics)) == {'presentation_near_white_deck_exceeded','presentation_visual_storytelling_missing'}


def test_large_svg_coordinates_do_not_replace_actual_rendered_visual_coverage():
    observed=[(0,0,0),(1,0,0),(.1333,.0697,.0198),(.2,0,0),(.1333,.1261,.0678),(1,.0996,.0295),(.2,0,0)]
    metrics=[_metrics(nearWhiteSampleRatio=white,largestVisualAreaRatio=area,visualInkAreaRatio=ink) for white,area,ink in observed]
    assert deck_presentation_quality_failure_codes(metrics)==['presentation_visual_storytelling_missing']
