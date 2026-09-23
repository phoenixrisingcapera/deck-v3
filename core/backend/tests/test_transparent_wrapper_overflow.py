"""Iteration 22: only transparent grid padding extends beyond the canvas."""
import os

from playwright.sync_api import sync_playwright

from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_empty_grid_padding_is_not_clipped_content_but_paint_and_text_still_are():
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('''<style>*{box-sizing:border-box}body{margin:0}section{height:1080px;overflow:hidden}
          .section-inner{height:1134px;padding:72px;display:grid;align-content:start;gap:40px}
          p{font:28px Arial;margin:0;color:#111;background:white}.visual{height:420px}
          .panel{height:380px;background:#eee;padding:40px}</style><section data-da-slide-root="slide">
          <div class="section-inner"><p data-da-element-key="body-01">Pipeline stages</p>
          <svg class="visual" width="1200"><rect width="1000" height="300" fill="navy"/></svg>
          <div class="panel"><p data-da-element-key="body-02">Complete source explanation.</p></div></div></section>''')
        assert page.locator('section').evaluate('(e)=>e.scrollHeight>e.clientHeight')
        assert not page.evaluate(METRICS_SCRIPT)['overflowY']
        page.add_style_tag(content='.section-inner{background:#eee}')
        assert page.evaluate(METRICS_SCRIPT)['overflowY']
        page.add_style_tag(content='.section-inner{background:transparent;border-bottom:4px solid red}')
        assert page.evaluate(METRICS_SCRIPT)['overflowY']
        page.add_style_tag(content='.section-inner{border:none}.panel p{position:absolute;top:1070px}')
        assert page.evaluate(METRICS_SCRIPT)['overflowY']
        browser.close()
