"""Iteration 13 repeated translucent HTML visual frames and table headings."""
import pytest
from app.services.llm import full_html_generation_service as html
from test_instant_deck_art_direction_contract import _deck


def test_translucent_html_panel_stays_rejected_and_opaque_surface_passes():
    raw=_deck().replace('</style>','.visual-frame{background:rgba(255,255,255,0.10)}</style>')
    args={'system_prompt_version':html.FULL_HTML_SYSTEM_PROMPT_VERSION,'context_pack':{'presentationIntent':'general'}}
    with pytest.raises(html.HtmlDeckCompileError) as failure:
        html.validate_full_html_presentation_quality(raw,**args)
    assert failure.value.code=='presentation_translucent_background_forbidden'
    html.validate_full_html_presentation_quality(raw.replace('rgba(255,255,255,0.10)','#0f172a'),**args)
