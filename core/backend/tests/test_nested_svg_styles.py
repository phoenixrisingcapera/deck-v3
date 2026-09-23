"""The final seven-page output lost light labels from nested SVG styles."""
import os

from playwright.sync_api import sync_playwright

from app.services.rendering.html_deck_compiler import compile_html_deck
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_nested_svg_css_preserves_label_paint_without_bypassing_sanitization():
    html = '''<html><head><title>Pipeline</title><style>
    .deck-section{height:1080px;background:#001830}svg{width:1440px;height:520px}
    </style></head><body><main><section class="deck-section" data-source-slide-ids="source_1">
    <h1>Overview</h1><svg viewBox="0 0 1440 520" aria-label="Pipeline">
    <style>@import url("https://blocked.invalid/import.css");
    .node-title{fill:#F8FAFC;font-size:32px;background-image:url("https://blocked.invalid/image");behavior:url(x)}
    </style><rect x="50" y="100" width="600" height="100" fill="#0F172A"/>
    <text class="node-title" x="100" y="160" data-source-refs="fact_1">Upload</text>
    <script>alert(1)</script></svg></section></main></body></html>'''
    args = dict(selected_source_slide_ids=['source_1'], grounded_fact_ids=['fact_1'],
                grounded_fact_sources={'fact_1': ['source_1']})
    current = compile_html_deck(html, **args)
    legacy = compile_html_deck(html, compiler_version='instant-html-compiler.v29', **args)
    assert 'blocked.invalid' not in current.sanitized_html
    assert 'behavior:' not in current.sanitized_html and 'alert(1)' not in current.sanitized_html
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.route('**/*', lambda route: route.abort())
        page.set_content(current.safe_slide_documents[0])
        assert page.locator('svg style').count() == 0
        assert page.locator('svg text').evaluate('(e)=>getComputedStyle(e).fill') == 'rgb(248, 250, 252)'
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'passed'
        page.set_content(legacy.safe_slide_documents[0])
        assert page.locator('svg text').evaluate('(e)=>getComputedStyle(e).fill') == 'rgb(0, 0, 0)'
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status'] == 'failed'
        assert current.compilation_hash != legacy.compilation_hash
        browser.close()
