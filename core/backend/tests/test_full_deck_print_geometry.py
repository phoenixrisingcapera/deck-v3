"""Observed export failures: a smaller print canvas clips content; nested roots spill pages."""
import os

import fitz
from playwright.sync_api import sync_playwright

from app.api.routes.deck_artifacts import _with_full_deck_print_contract


def test_pdf_preserves_proof_canvas_and_paginates_nested_slide_roots():
    # Both wrapper shapes occurred in actual published local canaries. Content
    # near both canvas edges is lost when print changes 1080px to 720px.
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        for wrapper in ('main', 'div class="deck"><main'):
            closing = '</main>' if wrapper == 'main' else '</main></div>'
            document = '<html><head><style>body{margin:0}section{min-height:100vh;display:flex;align-items:center;padding:48px 24px}.content{height:960px;display:flex;flex-direction:column;justify-content:space-between;font:32px Arial}</style></head><body>'
            document += f'<{wrapper}>'
            for number in range(1, 4):
                document += f'<section data-da-slide-root="s{number}"><div class="content"><p>TOP {number}</p><p>BOTTOM {number}</p></div></section>'
            document += closing + '</body></html>'
            page.set_content(_with_full_deck_print_contract(document))
            pdf = fitz.open(stream=page.pdf(print_background=True, prefer_css_page_size=True), filetype='pdf')
            assert len(pdf) == 3
            for number, sheet in enumerate(pdf, 1):
                assert tuple(sheet.rect) == (0, 0, 1440, 810)
                assert f'TOP {number}' in sheet.get_text()
                assert f'BOTTOM {number}' in sheet.get_text()
                for word in sheet.get_text('words'):
                    assert sheet.rect.contains(fitz.Rect(word[:4]))
            pdf.close()
        browser.close()


def test_positioned_slide_children_stay_on_their_own_pdf_page():
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1920, 'height':1080})
        document = '<html><head><style>h1{position:absolute;top:80px;left:80px;font:60px Arial}</style></head><body><main>'
        document += ''.join(f'<section data-da-slide-root="s{i}"><h1>PAGE {i}</h1></section>' for i in range(1,4))
        page.set_content(_with_full_deck_print_contract(document + '</main></body></html>'))
        with fitz.open(stream=page.pdf(print_background=True,prefer_css_page_size=True),filetype='pdf') as pdf:
            assert len(pdf) == 3
            for i, sheet in enumerate(pdf, 1):
                assert sheet.get_text().strip() == f'PAGE {i}'
        browser.close()


def test_saved_advisory_section_styles_apply_to_preview_and_pdf():
    from app.services.rendering.html_deck_compiler import restore_advisory_document_root_css, RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS
    document = '''<html><head><style>
    body{margin:0}*{box-sizing:border-box}
    [data-da-slide-root] section.deck-section{position:relative;width:1920px;height:1080px;padding:96px;display:flex;align-items:center}
    [data-da-slide-root] h1{margin:0;font:60px Arial}
    </style></head><body><main><section class="deck-section" data-da-slide-root="s1"><h1>Investor presentation</h1></section></main></body></html>'''
    document = document.replace('</style>', RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS + '</style>').replace('<h1>', '<h1 data-da-element-key="headline-01">')
    restored = restore_advisory_document_root_css(document)
    assert restore_advisory_document_root_css(restored) == restored
    assert 'section[data-da-slide-root].deck-section' in restored
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1920, 'height':1080})
        for content in (restored, _with_full_deck_print_contract(restored)):
            page.set_content(content)
            heading = page.locator('h1').bounding_box()
            assert page.locator('h1').evaluate('e=>getComputedStyle(e).fontSize') == '60px'
            assert page.locator('h1').evaluate('e=>getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert heading['x'] == 96
            assert 450 < heading['y'] < 540
            assert page.locator('section').evaluate('e=>getComputedStyle(e).position') == 'relative'
        with fitz.open(stream=page.pdf(print_background=True,prefer_css_page_size=True), filetype='pdf') as pdf:
            assert len(pdf) == 1
            assert 'Investor presentation' in pdf[0].get_text()
        browser.close()


def test_svg_relative_line_offsets_survive_compilation_and_pdf():
    from app.services.rendering.html_deck_compiler import (
        COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, _parse_document,
        _sanitize_tree, _serialize, HtmlDeckCompileError,
    )
    import pytest
    document = '''<html><body><section data-da-slide-root="s1"><svg width="800" height="300" viewBox="0 0 800 300"><text x="40" y="50" font-size="24"><tspan x="40" dy="0">Consulting</tspan><tspan x="40" dy="44">Connect values and money</tspan></text></svg></section></body></html>'''
    historical = _parse_document(document)
    _sanitize_tree(historical, {}, {}, compiler_version=SVG_TEXT_LAYOUT_COMPILER_VERSION)
    assert 'dy=' not in _serialize(historical)
    current = _parse_document(document)
    _sanitize_tree(current, {}, {}, compiler_version=COMPILER_VERSION)
    serialized = _serialize(current)
    assert 'dy="44"' in serialized
    with pytest.raises(HtmlDeckCompileError, match='literal lengths'):
        unsafe = _parse_document(document.replace('dy="44"', 'dy="url(https://example.invalid)"'))
        _sanitize_tree(unsafe, {}, {}, compiler_version=COMPILER_VERSION)
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1920, 'height':1080})
        page.set_content(serialized)
        first, second = [page.locator('tspan').nth(i).bounding_box() for i in range(2)]
        assert second['y'] - first['y'] == 44
        assert first['y'] + first['height'] < second['y']
        with fitz.open(stream=page.pdf(),filetype='pdf') as pdf:
            assert 'Consulting' in pdf[0].get_text()
            assert 'Connect values and money' in pdf[0].get_text()
        browser.close()


def test_historical_svg_repair_uses_exact_saved_claims_and_preserves_baseline():
    from app.services.rendering.instant_svg_text_layout import extract_offsets, apply_offsets
    from app.services.rendering.html_deck_compiler import _parse_document, _sanitize_tree, _serialize, SVG_TEXT_LAYOUT_COMPILER_VERSION
    raw = '''<section class="deck-section"><svg viewBox="0 0 800 300"><text x="40" y="50"><tspan x="40" dy="0">Consulting</tspan><tspan x="40" dy="44">Connect values and money</tspan></text></svg></section>'''
    tree = _parse_document(raw)
    _sanitize_tree(tree, {}, {}, compiler_version=SVG_TEXT_LAYOUT_COMPILER_VERSION)
    section = next(n for n in tree.iter() if n.tag.endswith('section'))
    section.set('data-da-slide-root', 'saved-section')
    saved = _serialize(tree)
    rows = extract_offsets(raw, saved)
    assert len(rows) == 2
    restored = apply_offsets(saved, rows)
    assert 'dy="44"' in restored and 'dy=' not in saved
    assert apply_offsets(restored, rows) == restored
    changed = saved.replace('Connect values and money', 'A different claim')
    assert 'dy="44"' not in apply_offsets(changed, rows)
    assert len(extract_offsets(raw, changed)) == 1
    assert 'dy="44"' not in apply_offsets(saved.replace('saved-section', 'other-section'), rows)


def test_svg_line_flow_repairs_missing_offsets_without_source_or_claim_edits():
    from app.services.rendering.instant_svg_text_layout import missing_line_offsets, apply_offsets
    document = '<section class="deck-section" data-da-slide-root="s1"><svg width="800" height="300"><text x="40" y="50" font-size="24"><tspan x="40">Consulting</tspan><tspan x="40">Connect values and money</tspan></text></svg></section>'
    rows = missing_line_offsets(document)
    assert len(rows) == 1 and rows[0]['method'] == 'automatic_line_flow'
    repaired = apply_offsets(document, rows)
    assert missing_line_offsets(repaired) == []
    assert 'Consulting' in repaired and 'Connect values and money' in repaired
    with sync_playwright() as p:
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page()
        page.set_content(repaired)
        a, b = [page.locator('tspan').nth(i).bounding_box() for i in range(2)]
        assert a['y'] + a['height'] < b['y']
        browser.close()
