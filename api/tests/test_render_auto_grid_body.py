"""Regression for iteration 6's unplaced body text collapsing into one grid cell."""
import os
from playwright.sync_api import sync_playwright
from app.services.rendering.html_deck_compiler import RENDER_AUTO_GRID_BODY_GUARD_CSS, RENDER_AUTO_GRID_ITEM_GUARD_CSS


def test_auto_grid_body_spans_canvas_without_overriding_explicit_source_placement():
    with sync_playwright() as p:
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('''<style>*{box-sizing:border-box}body{margin:0}section{height:1080px;display:flex;align-items:center;padding:60px}.section-inner{width:1440px;display:grid;grid-template-columns:repeat(12,1fr);gap:22px}h2,svg{grid-column:1/-1}h2{font-size:64px;margin:0}p{font-size:28px;margin:0}svg{height:460px;width:100%}</style><section data-da-slide-root="slide"><div class="section-inner"><h2>Pipeline</h2><svg></svg><p>Upload Prepare Generate Publish Presigned object transfer Extraction OCR and source preparation Provider output survives validation Rendered slides become visible Complete the source workflow and review the results</p></div></section>''')
        assert page.locator('p').bounding_box()['width']<200
        page.add_style_tag(content=RENDER_AUTO_GRID_BODY_GUARD_CSS)
        box=page.locator('p').bounding_box()
        assert box['width']==1440 and box['y']>=0 and box['y']+box['height']<=1080
        page.add_style_tag(content='.section-inner > p{grid-column:span 6}')
        assert page.locator('p').bounding_box()['width']<800
        browser.close()


def test_unplaced_marker_in_content_grid_does_not_collapse_into_one_column():
    with sync_playwright() as p:
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.set_content('<style>body{margin:0}.content{width:1440px;display:grid;grid-template-columns:repeat(12,1fr);gap:32px}p{grid-column:span 8}div.marker{font-size:28px;padding:12px}</style><section data-da-slide-root="slide"><div class="content"><p>Evidence</p><div class="marker">Expected marker: SYNTHETIC-CANARY-P03 Synthetic test content with no customer data</div></div></section>')
        assert page.locator('.marker').bounding_box()['width']<200
        page.add_style_tag(content=RENDER_AUTO_GRID_ITEM_GUARD_CSS)
        assert abs(page.locator('.marker').bounding_box()['width']-1440)<1
        assert page.locator('p').bounding_box()['width']<1000
        browser.close()
