"""Observed twenty-page repair: a root token resolves to 100vh in Chromium."""
import os

import pytest
from playwright.sync_api import sync_playwright

from app.services.llm import full_html_generation_service as html
from test_instant_deck_art_direction_contract import _deck


def test_root_viewport_token_matches_real_browser_and_preserves_historical_validation():
    raw = _deck(visuals=3).replace('<style>', '<style>:root{--section-min-h:100vh}').replace('min-height:1080px', 'min-height:var(--section-min-h)')
    context = {'presentationIntent': 'general'}
    html.validate_full_html_presentation_quality(raw, context_pack=context, system_prompt_version=html.FULL_HTML_SYSTEM_PROMPT_VERSION)
    with pytest.raises(html.HtmlDeckCompileError) as historical:
        html.validate_full_html_presentation_quality(raw, context_pack=context, system_prompt_version=html.CAPTION_GROUNDING_SYSTEM_PROMPT_VERSION)
    assert historical.value.code == 'presentation_full_viewport_missing'
    for invalid in (raw.replace('--section-min-h:100vh', '--section-min-h:80vh'), raw.replace('--section-min-h:100vh', '--other:100vh')):
        with pytest.raises(html.HtmlDeckCompileError) as failure:
            html.validate_full_html_presentation_quality(invalid, context_pack=context, system_prompt_version=html.FULL_HTML_SYSTEM_PROMPT_VERSION)
        assert failure.value.code == 'presentation_full_viewport_missing'
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content(raw)
        assert page.locator('.deck-section').first.evaluate('(e)=>getComputedStyle(e).minHeight') == '1080px'
        browser.close()
