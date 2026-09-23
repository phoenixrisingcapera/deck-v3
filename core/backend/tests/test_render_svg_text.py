"""Regression for the actual diagram contrast false positive and missed label overlap."""
import os
from playwright.sync_api import sync_playwright
from app.services.rendering.playwright_render_child import METRICS_SCRIPT


def test_svg_text_uses_its_painted_fill_and_detects_unreadable_or_overlapping_labels():
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('''<html><head><title>Diagram</title><style>body{margin:0;background:#001830;color:#001830}section{height:1080px}svg{width:1440px;height:520px}</style></head>
        <body><section data-da-slide-root="slide"><svg data-da-element-key="decoration-01" viewBox="0 0 1440 520">
        <title>Non-painted accessible description</title><rect width="1440" height="520" fill="transparent"/><rect x="50" y="100" width="600" height="100" fill="#48d8d8"/>
        <text x="80" y="160" font-size="32" fill="#001830">Browser</text>
        <text x="400" y="160" font-size="32" fill="#001830">Queue</text>
        </svg></section></body></html>''')
        metrics=page.evaluate(METRICS_SCRIPT)
        assert metrics['contrast']['status']=='passed'
        assert len(metrics['contrast']['checks'])==2
        assert metrics['presentationQuality']['visualInkAreaRatio']<.1
        assert not metrics['severeOverlapPairs']
        page.locator('text').first.evaluate('(e)=>e.setAttribute("fill","#48d8d8")')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='failed'
        page.locator('text').nth(1).evaluate('(e)=>e.setAttribute("x","80")')
        assert page.evaluate(METRICS_SCRIPT)['severeOverlapPairs']
        browser.close()


def test_svg_translucent_panel_contrast_uses_the_composited_background():
    with sync_playwright() as p:
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('<style>body{margin:0;background:#001830}section{height:1080px}</style><section data-da-slide-root="slide"><svg width="1440" height="520"><rect width="600" height="200" fill="rgba(255,255,255,0.1)"/><text x="80" y="100" font-size="32" fill="#eef3ff">Upload</text></svg></section>')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='passed'
        page.locator('text').evaluate('(e)=>e.setAttribute("fill","#001830")')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='failed'
        browser.close()


def test_svg_sentence_spilling_off_dark_node_fails_contrast():
    with sync_playwright() as p:
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('<style>body{margin:0;background:#48d8d8}section{height:1080px}text{font-family:Arial}</style><section data-da-slide-root="slide"><svg width="1440" height="440"><rect x="980" y="110" width="300" height="180" fill="#001830"/><text x="1130" y="215" text-anchor="middle" fill="#eef3ff" font-size="22">Provider output survives validation</text></svg></section>')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='failed'
        page.locator('text').evaluate('(e)=>e.textContent="Generate"')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='passed'
        browser.close()


def test_rotated_label_edge_must_fit_its_contrast_safe_backplate():
    with sync_playwright() as p:
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('<style>body{margin:0;background:#eef3ff}section{height:1080px}text{font-family:Arial}</style><section data-da-slide-root="slide"><svg width="1440" height="440"><rect x="1340" y="80" width="60" height="120" fill="#001830"/><text x="1370" y="150" text-anchor="middle" fill="#eef3ff" font-size="24" transform="rotate(-90 1370 150)">Published</text></svg></section>')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='failed'
        page.locator('text').evaluate('(e)=>{e.setAttribute("y","140");e.setAttribute("transform","rotate(-90 1370 140)")}')
        assert page.evaluate(METRICS_SCRIPT)['contrast']['status']=='passed'
        browser.close()


def test_grounded_svg_labels_ignore_unpainted_css_backgrounds():
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_content('''<style>body{margin:0;background:#001830}section{height:1080px}
        [data-da-element-key^="body-"]{color:#0f172a!important;background:#f8fafc!important;font-size:28px}
        g{background:white}</style><section data-da-slide-root="slide"><svg width="1440" height="520">
        <g><text x="100" y="100" fill="#eef3ff" data-da-element-key="body-01">Upload 38%</text>
        <text x="500" y="100"><tspan fill="#eef3ff" data-da-element-key="body-02">Publish 100%</tspan></text></g>
        </svg></section>''')
        metrics = page.evaluate(METRICS_SCRIPT)
        assert metrics['contrast']['status'] == 'passed'
        assert all(item['ratio'] > 10 for item in metrics['contrast']['checks'])
        page.locator('tspan').evaluate('(e)=>e.setAttribute("fill", "#001830")')
        metrics = page.evaluate(METRICS_SCRIPT)
        assert metrics['contrast']['status'] == 'failed'
        assert any(item['key'] == 'body-02' and not item['passed'] for item in metrics['contrast']['checks'])
        browser.close()


def test_compiled_indented_tspan_labels_measure_rendered_characters():
    from app.services.rendering.html_deck_compiler import compile_html_deck

    raw = """<html><head><title>Pipeline</title></head><body><main>
    <section class="deck-section" data-source-slide-ids="source_1">
    <h1>Overview</h1><svg width="1440" height="420" viewBox="0 0 1440 420">
    <rect x="40" y="120" width="280" height="180" fill="#001830"/>
    <g fill="#eef3ff" font-size="32" text-anchor="middle"><text x="40" y="210">
                <tspan x="180" y="210">Upload</tspan>
              </text></g></svg></section></main></body></html>"""
    compiled = compile_html_deck(raw, selected_source_slide_ids=["source_1"])
    with sync_playwright() as p:
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        browser = p.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_content(compiled.safe_slide_documents[0])
        metrics = page.evaluate(METRICS_SCRIPT)
        label = next(c for c in metrics["contrast"]["checks"] if "text-1" in c["key"])
        assert label["passed"] and label["ratio"] > label["threshold"] == 3
        page.locator("svg text").evaluate('(n)=>n.setAttribute("fill", "#001830")')
        assert page.evaluate(METRICS_SCRIPT)["contrast"]["status"] == "failed"
        browser.close()
