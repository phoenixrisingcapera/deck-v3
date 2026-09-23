"""Real Chromium regression for iteration 2's legible table and rounded padding."""
import os
from playwright.sync_api import sync_playwright
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_table_contrast_checks_cells_and_fractional_padding_does_not_report_clipping():
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('''<html><head><title>Geometry</title><style>
        *{box-sizing:border-box}body{margin:0;background:#111;color:#111}
        section{height:1080px;padding:72px 56px;display:flex;align-items:center;overflow:hidden}
        .inner{height:938.55px;flex:none;width:100%}
        td{color:#111;background:#fff;font-size:28px}
        </style></head><body><section data-da-slide-root="slide"><div class="inner">
        <table data-da-element-key="table-01"><tr><td data-da-element-key="body-01">Legible evidence</td></tr></table>
        </div></section></body></html>''')
        assert page.locator('section').evaluate('(e)=>e.scrollHeight-e.clientHeight') == 1
        metrics = page.evaluate(METRICS_SCRIPT)
        assert metrics['contrast']['status'] == 'passed'
        assert [c['key'] for c in metrics['contrast']['checks']] == ['body-01']
        assert not metrics['overflowY'] and not metrics['clippedElementKeys']
        # Iteration 6: 20px of empty trailing padding, all content still visible.
        page.locator('section').evaluate('(e)=>e.style.padding="56px"')
        page.locator('.inner').evaluate('(e)=>e.style.height="1007.55px"')
        assert page.locator('section').evaluate('(e)=>e.scrollHeight-e.clientHeight') == 20
        assert not page.evaluate(METRICS_SCRIPT)['overflowY']
        page.locator('td').evaluate('(e)=>e.style.color="#fff"')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'failed'
        page.locator('.inner').evaluate('(e)=>e.style.height="1200px"')
        assert page.evaluate(METRICS_SCRIPT)['overflowY']
        browser.close()
