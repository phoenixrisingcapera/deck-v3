from __future__ import annotations

from app.instant_deck_spec.chromium import validate_compiled_deck_in_chromium
from app.instant_deck_spec.compiler import compile_deck_spec


def test_compiled_slides_pass_existing_chromium_geometry_contrast_and_type_checks(deck_spec, source_package, tmp_path):
    compiled = compile_deck_spec(deck_spec, source_package)
    report = validate_compiled_deck_in_chromium(compiled, screenshot_directory=tmp_path)
    assert report["passed"] is True, [
        {"slideId": row["slideId"], "failures": row["failures"]}
        for row in report["slides"]
        if not row["passed"]
    ]
    assert len(report["slides"]) == len(deck_spec.slides)
    assert all(row["typography"] for row in report["slides"])
    assert all(not row["metrics"]["overflowX"] and not row["metrics"]["overflowY"] for row in report["slides"])
    assert all(not row["metrics"]["clippedElementKeys"] for row in report["slides"])
    assert all(row["metrics"]["contrast"]["status"] == "passed" for row in report["slides"])
    assert all(
        all(item["elementCount"] >= 2 and item["inkRatio"] >= 0.035 for item in row["meaningfulSvgInk"])
        for row in report["slides"]
    )
