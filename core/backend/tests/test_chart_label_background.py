"""Iteration 24: dark 100% label above an orange bar was invisible on navy."""
import os

from playwright.sync_api import sync_playwright

from app.services.llm.full_html_generation_service import _system_prompt
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_label_above_highlighted_bar_is_checked_against_canvas():
    assert 'including the highlighted final bar' in _system_prompt()
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('<style>body{margin:0;background:#001830}section{height:1080px}</style>'
                         '<section data-da-slide-root="slide"><svg width="1440" height="520">'
                         '<rect x="1080" y="80" width="180" height="360" fill="#ffa860"/>'
                         '<text x="1170" y="67" text-anchor="middle" font-size="28" fill="#001830" '
                         'data-da-element-key="body-06">100%</text></svg></section>')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'failed'
        page.locator('text').evaluate('(e)=>e.setAttribute("fill","#ffffff")')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'passed'
        page.locator('text').evaluate('(e)=>{e.setAttribute("y","130");e.setAttribute("fill","#001830")}')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'passed'
        browser.close()
