"""Observed fifteen-page run: an unbounded OCR image clips its heading and captions."""
import base64
import os

import fitz
from playwright.sync_api import sync_playwright

from app.services.llm.full_html_generation_service import _system_prompt, CHART_LABEL_CONTRAST_SYSTEM_PROMPT_VERSION
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_shared_image_frame_leaves_room_for_heading_and_grounded_captions():
    assert 'SHARED IMAGE/TEXT CANVAS' in _system_prompt()
    assert 'SHARED IMAGE/TEXT CANVAS' not in _system_prompt(CHART_LABEL_CONTRAST_SYSTEM_PROMPT_VERSION)
    document = fitz.open()
    sheet = document.new_page(width=1440, height=814)
    sheet.insert_text((100, 100), 'Source image with OCR text', fontsize=40)
    image = base64.b64encode(sheet.get_pixmap().tobytes('png')).decode()
    document.close()
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('<style>body{margin:0}section{height:1080px;display:flex;align-items:center;overflow:hidden}.content{width:1440px;margin:auto;display:grid;gap:28px}h2{font:64px Arial;margin:0}p{font:28px Arial;line-height:1.4;margin:0}img{display:block;width:100%;height:auto}</style>'
                         '<section data-da-slide-root="slide"><div class="content"><h2 data-da-element-key="headline-01">Recovered source image</h2>'
                         f'<img src="data:image/png;base64,{image}" alt="Source" data-da-element-key="image-01">'
                         '<p data-da-element-key="body-01">First caption</p><p data-da-element-key="body-02">Second caption</p>'
                         '<p data-da-element-key="body-03">Final caption</p></div></section>')
        page.locator('img').evaluate('(e)=>e.decode()')
        before = page.evaluate(METRICS_SCRIPT)
        assert before['overflowY'] and before['clippedElementKeys']
        page.add_style_tag(content='img{height:480px;max-width:100%;object-fit:contain}')
        after = page.evaluate(METRICS_SCRIPT)
        assert not after['overflowY'] and not after['clippedElementKeys']
        assert after['assetLoad']['failedImageCount'] == 0
        browser.close()
