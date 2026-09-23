"""Observed fifteen-page rerun: Published spills out of a squeezed final node."""
import os

from playwright.sync_api import sync_playwright

from app.services.llm.full_html_generation_service import _system_prompt, SHARED_IMAGE_CANVAS_SYSTEM_PROMPT_VERSION
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_final_node_keeps_equal_width_and_contrast_safe_label_inset():
    assert 'six equal 200-unit boxes' in _system_prompt()
    assert 'six equal 200-unit boxes' not in _system_prompt(SHARED_IMAGE_CANVAS_SYSTEM_PROMPT_VERSION)
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('<style>body{margin:0;background:#001830}section{height:1080px}</style>'
                         '<section data-da-slide-root="slide"><svg width="1440" height="420" viewBox="0 0 1440 420">'
                         '<rect x="1240" y="160" width="120" height="100" fill="#ffa860"/>'
                         '<text x="1300" y="215" font-family="Arial" font-size="32" text-anchor="middle" '
                         'fill="#001830" data-da-element-key="body-06">Published</text></svg></section>')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'failed'
        page.locator('rect').evaluate('(e)=>{e.setAttribute("x","1200");e.setAttribute("width","200")}')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'passed'
        label = page.locator('text').evaluate('(e)=>{const b=e.getBBox();return {left:b.x,right:b.x+b.width}}')
        assert label['left'] >= 1224 and label['right'] <= 1376
        browser.close()
