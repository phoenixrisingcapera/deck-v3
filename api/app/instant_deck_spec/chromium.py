"""Offline Chromium evidence using the production measurement script."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.rendering.playwright_render_child import METRICS_SCRIPT, chromium_launch_options

from .compiler import CompiledDeck


TYPOGRAPHY_SCRIPT = r"""() => [...document.querySelectorAll('[data-da-text-role]')].map(node => {
  const style=getComputedStyle(node), rect=node.getBoundingClientRect();
  return {key:node.dataset.daElementKey || '',role:node.dataset.daTextRole || '',fontSize:parseFloat(style.fontSize || '0'),lineHeight:parseFloat(style.lineHeight || '0'),fontFamily:style.fontFamily,width:rect.width,height:rect.height,textLength:(node.textContent || '').trim().length};
})"""

SVG_INK_SCRIPT = r"""() => [...document.querySelectorAll('svg[data-meaningful-visual="true"]')].map(svg => {
  const viewBox=svg.viewBox.baseVal, viewportArea=Math.max(1, viewBox.width*viewBox.height);
  const marks=[...svg.querySelectorAll('path,rect,circle,ellipse,line,polyline,polygon')];
  let painted=0;
  for (const mark of marks) {
    try {
      const box=mark.getBBox(), stroke=parseFloat(getComputedStyle(mark).strokeWidth || '0');
      painted += Math.max(1, box.width + stroke) * Math.max(1, box.height + stroke);
    } catch (_) {}
  }
  return {elementCount:marks.length,inkRatio:Math.min(1,painted/viewportArea),viewBox:[viewBox.width,viewBox.height]};
})"""

TYPE_FLOORS = {
    "display": 88,
    "headline": 60,
    "subhead": 26,
    "body": 24,
    "label": 20,
    "metric-primary": 120,
    "metric-secondary": 54,
    "metric-label": 30,
}


def _blocking(metrics: dict[str, Any], typography: list[dict[str, Any]], svg_ink: list[dict[str, Any]], console_errors: list[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    checks = (
        ("not_visible", not metrics.get("visible")),
        ("overflow_x", bool(metrics.get("overflowX"))),
        ("overflow_y", bool(metrics.get("overflowY"))),
        ("clipped", bool(metrics.get("clippedElementKeys"))),
        ("severe_overlap", bool(metrics.get("severeOverlapPairs"))),
        ("asset_load", bool((metrics.get("assetLoad") or {}).get("failedImageCount"))),
        ("contrast", (metrics.get("contrast") or {}).get("status") != "passed"),
        ("console_error", bool(console_errors)),
    )
    for code, failed in checks:
        if failed:
            failures.append({"code": code})
    for item in typography:
        floor = TYPE_FLOORS.get(str(item.get("role") or ""))
        if floor is not None and float(item.get("fontSize") or 0) < floor:
            failures.append({"code": "computed_typography_below_floor", "key": item.get("key"), "measured": item.get("fontSize"), "minimum": floor})
    for index, item in enumerate(svg_ink):
        if int(item.get("elementCount") or 0) < 2 or float(item.get("inkRatio") or 0) < 0.035:
            failures.append({"code": "insufficient_meaningful_svg_ink", "index": index, **item, "minimumInkRatio": 0.035})
    return failures


def validate_compiled_deck_in_chromium(compiled: CompiledDeck, *, screenshot_directory: Path | None = None) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    screenshot_directory = screenshot_directory.resolve() if screenshot_directory is not None else None
    if screenshot_directory is not None:
        screenshot_directory.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_options())
        try:
            for slide in compiled.slides:
                page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
                page.context.set_offline(True)
                page.route("**/*", lambda route: route.abort())
                console_errors: list[str] = []
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.set_content(slide.render_document, wait_until="load", timeout=30_000)
                metrics = page.evaluate(METRICS_SCRIPT)
                typography = page.evaluate(TYPOGRAPHY_SCRIPT)
                svg_ink = page.evaluate(SVG_INK_SCRIPT)
                screenshot = page.screenshot(type="png", full_page=False)
                screenshot_path = None
                if screenshot_directory is not None:
                    screenshot_path = screenshot_directory / f"{slide.position:02d}-{slide.slide_id}-{slide.archetype}.png"
                    screenshot_path.write_bytes(screenshot)
                failures = _blocking(metrics, typography, svg_ink, console_errors)
                reports.append({
                    "slideId": slide.slide_id,
                    "position": slide.position,
                    "archetype": slide.archetype,
                    "passed": not failures,
                    "failures": failures,
                    "metrics": metrics,
                    "typography": typography,
                    "meaningfulSvgInk": svg_ink,
                    "consoleErrors": console_errors,
                    "screenshotSha256": hashlib.sha256(screenshot).hexdigest(),
                    "screenshotPath": screenshot_path.name if screenshot_path else None,
                    "browserVersion": browser.version,
                })
                page.close()
        finally:
            browser.close()
    return {
        "schemaVersion": "instant-deck-offline-chromium-report.v1",
        "compilerVersion": compiled.compiler_version,
        "deckContentSha256": compiled.content_sha256,
        "passed": all(report["passed"] for report in reports),
        "slides": reports,
    }
