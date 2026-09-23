"""Observed 20-page slide: diagram plus wrapped list clips both ends."""
import os

from playwright.sync_api import sync_playwright

from app.services.llm.full_html_generation_service import _system_prompt
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_dense_diagram_details_need_a_separate_readable_section():
    assert "DIAGRAM AND TEXT HEIGHT BUDGET" in _system_prompt()
    assert "DIAGRAM AND TEXT HEIGHT BUDGET" not in _system_prompt("full-html-system-prompt.v36")
    with sync_playwright() as p:
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        browser = p.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_content('''<style>*{box-sizing:border-box}body{margin:0}
          section{height:1080px;overflow:hidden;display:flex;align-items:center;padding:64px}
          .content{width:1440px;margin:auto;display:grid;gap:32px}
          h2,h3{font:64px/1.2 Arial;margin:0}h2{max-width:1200px}
          svg{width:1440px;height:420px;display:block}.details{width:680px}
          li{font:28px/1.4 Arial;margin-bottom:16px}ul{margin:0}</style>
          <section data-da-slide-root="slide"><div class="content">
          <h2 data-da-element-key="headline-01">Pipeline: upload to publish in four validated stages</h2>
          <svg viewBox="0 0 1440 420"><rect width="1440" height="420" fill="navy"/></svg>
          <div class="details"><h3>Lineage coverage</h3><ul>''' + ''.join(
            f'<li data-da-element-key="body-{n}">Pipeline stages {n} — Native text, vector shapes, and reading-order coverage</li>'
            for n in range(5)
        ) + '</ul></div></div></section>')
        before = page.evaluate(METRICS_SCRIPT)
        assert before["overflowY"] and before["clippedElementKeys"]
        # Split the same content; keep all words and original readable type sizes.
        page.evaluate('''() => {
          const next = document.createElement('section');
          next.dataset.daSlideRoot = 'details';
          next.append(document.querySelector('.details')); window.detailsSlide = next;
        }''')
        after = page.evaluate(METRICS_SCRIPT)
        assert not after["overflowY"] and not after["clippedElementKeys"]
        page.evaluate("() => document.querySelector('section').replaceWith(window.detailsSlide)")
        details = page.evaluate(METRICS_SCRIPT)
        assert not details["overflowY"] and not details["clippedElementKeys"]
        assert page.locator("li").count() == 5
        assert page.locator("li").evaluate_all("els => els.every(e => getComputedStyle(e).fontSize === '28px')")
        browser.close()
