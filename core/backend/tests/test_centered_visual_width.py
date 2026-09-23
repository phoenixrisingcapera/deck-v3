"""Iteration 20: auto margins shrink a max-width-only chart wrapper."""
import os

from playwright.sync_api import sync_playwright

from app.services.llm.full_html_generation_service import _system_prompt


def test_explicit_wrapper_width_prevents_observed_chart_shrinkage():
    css = "width:100%;max-width:1440px;min-width:0;box-sizing:border-box;margin:0 auto"
    assert css in _system_prompt()
    assert css not in _system_prompt("full-html-system-prompt.v29")
    with sync_playwright() as p:
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        browser = p.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_content('''<style>body{margin:0}.deck-section{height:1080px;display:grid;
          grid-template-rows:auto 1fr auto;padding:72px;box-sizing:border-box}
          .content{max-width:1440px;margin:0 auto;display:grid;gap:56px}
          h2{font:64px Arial;margin:0}svg{display:block;width:100%;height:auto}</style>
          <section class="deck-section"><div class="content"><h2>Progress signals</h2>
          <svg viewBox="0 0 1440 420"><rect width="1440" height="420" fill="navy"/>
          <text x="120" y="100" font-size="28" fill="white">Upload</text></svg></div></section>''')
        assert page.locator("svg").bounding_box()["width"] < 600
        page.add_style_tag(content=".deck-section .content{" + css + "}")
        box = page.locator("svg").bounding_box()
        assert box["width"] == 1440
        assert box["height"] == 420
        assert box["y"] + box["height"] <= 1080
        browser.close()
