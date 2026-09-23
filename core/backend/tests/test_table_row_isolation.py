"""Regression for iteration 4's safe table striping rejected as section position."""
import pytest
from app.services.llm import full_html_generation_service as html
from test_instant_deck_art_direction_contract import _deck


def test_table_row_striping_survives_isolation_but_section_position_is_rejected():
    raw = _deck().replace('</style>', 'tbody tr:nth-child(odd) td{background:#0e1a2f}</style>')
    html.validate_full_html_presentation_quality(raw, system_prompt_version=html.FULL_HTML_SYSTEM_PROMPT_VERSION, context_pack={'presentationIntent':'general'})
    raw = raw.replace('</style>', '.deck-section:nth-child(2){background:#123456}</style>')
    with pytest.raises(html.HtmlDeckCompileError) as failure:
        html.validate_full_html_presentation_quality(raw, system_prompt_version=html.FULL_HTML_SYSTEM_PROMPT_VERSION, context_pack={'presentationIntent':'general'})
    assert failure.value.code == 'presentation_position_selector_forbidden'
