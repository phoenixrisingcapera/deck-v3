from app.services.rendering.html_deck_compiler import (
    COMPILER_VERSION,
    PRESENTATION_PROOF_COMPILER_VERSION,
    READABLE_BODY_COMPILER_VERSION,
    RENDER_AUTHORED_BACKGROUND_GUARD_CSS,
    RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS,
    VISUAL_SUBSTANCE_COMPILER_VERSION,
    sanitize_and_scope_css,
)
from app.services.rendering.render_proof_service import (
    deck_presentation_quality_failure_codes,
    presentation_quality_failure_codes,
    render_metrics_have_blocking_failure,
)


def _metrics(**quality_overrides: object) -> dict:
    quality = {
        "policyVersion": "presentation-scale.v2",
        "visibleWordCount": 82,
        "textElementCount": 9,
        "substantialBodyCount": 4,
        "minimumSubstantialBodyFontSize": 24,
        "medianSubstantialBodyFontSize": 28,
        "smallReadableTextKeys": [],
        "maximumHeadingFontSize": 64,
        "maximumTextFontSize": 88,
        "visualElementCount": 1,
        "largestVisualAreaRatio": 0.18,
        "visualInkAreaRatio": 0.12,
        "backgroundSampleCount": 15,
        "nearWhiteSampleRatio": 0.2,
    }
    quality.update(quality_overrides)
    return {
        "visible": True,
        "overflowX": False,
        "overflowY": False,
        "clippedElementKeys": [],
        "severeOverlapPairs": [],
        "assetLoad": {"failedImageCount": 0},
        "accessibility": {"missingImageAlt": 0},
        "contrast": {"status": "passed", "checks": []},
        "presentationQuality": quality,
    }


def test_presentation_quality_accepts_slide_scale_browser_evidence() -> None:
    metrics = _metrics()

    assert presentation_quality_failure_codes(metrics) == []
    assert render_metrics_have_blocking_failure(
        metrics,
        require_presentation_quality=True,
    ) is False


def test_presentation_quality_rejects_tiny_dense_document_layout() -> None:
    metrics = _metrics(
        visibleWordCount=181,
        minimumSubstantialBodyFontSize=14,
        medianSubstantialBodyFontSize=16,
        smallReadableTextKeys=["body-01", "body-02"],
        maximumHeadingFontSize=38,
        maximumTextFontSize=38,
        largestVisualAreaRatio=0.02,
    )

    failures = presentation_quality_failure_codes(metrics)

    assert "presentation_word_count_exceeded" in failures
    assert "presentation_text_below_readable_floor" in failures
    assert "presentation_body_below_readable_floor" in failures
    assert "presentation_body_scale_too_small" in failures
    assert "presentation_heading_scale_too_small" in failures
    assert "presentation_focal_scale_missing" in failures
    assert render_metrics_have_blocking_failure(metrics) is False
    assert render_metrics_have_blocking_failure(
        metrics,
        require_presentation_quality=True,
    ) is True


def test_deck_quality_rejects_near_white_dominance_over_one_third() -> None:
    metrics = [
        _metrics(nearWhiteSampleRatio=ratio)
        for ratio in (0.9, 0.8, 0.7, 0.2, 0.1, 0.0)
    ]

    assert deck_presentation_quality_failure_codes(metrics) == [
        "presentation_near_white_deck_exceeded"
    ]


def test_deck_quality_allows_one_third_near_white_sections() -> None:
    metrics = [
        _metrics(nearWhiteSampleRatio=ratio)
        for ratio in (0.9, 0.8, 0.2, 0.2, 0.1, 0.0)
    ]

    assert deck_presentation_quality_failure_codes(metrics) == []


def test_deck_quality_requires_meaningful_visual_storytelling() -> None:
    metrics = [
        _metrics(visualElementCount=0, largestVisualAreaRatio=0.0)
        for _ in range(7)
    ]

    assert deck_presentation_quality_failure_codes(metrics) == [
        "presentation_visual_storytelling_missing"
    ]


def test_sparse_oversized_svg_does_not_satisfy_focal_or_storytelling_scale() -> None:
    sparse = _metrics(
        maximumTextFontSize=63,
        visualElementCount=1,
        largestVisualAreaRatio=0.24,
        visualInkAreaRatio=0.008,
    )

    assert "presentation_focal_scale_missing" in presentation_quality_failure_codes(sparse)
    assert deck_presentation_quality_failure_codes([sparse] * 7) == [
        "presentation_visual_storytelling_missing"
    ]


def test_substantial_thin_line_diagram_satisfies_deck_storytelling() -> None:
    diagram = _metrics(
        visualElementCount=1,
        largestVisualAreaRatio=0.09,
        visualInkAreaRatio=0.016,
    )

    assert deck_presentation_quality_failure_codes([diagram] * 7) == []


def test_immutable_v1_metrics_remain_valid_under_their_original_policy() -> None:
    legacy = _metrics(policyVersion="presentation-scale.v1")
    legacy["presentationQuality"].pop("visualInkAreaRatio")

    assert presentation_quality_failure_codes(legacy) == []
    assert deck_presentation_quality_failure_codes([legacy] * 7) == []


def test_current_compiler_deterministically_guards_browser_proof_scale_and_contrast() -> None:
    current = sanitize_and_scope_css(".slide{color:#fff}", compiler_version=COMPILER_VERSION)
    visual_substance = sanitize_and_scope_css(
        ".slide{color:#fff}",
        compiler_version=VISUAL_SUBSTANCE_COMPILER_VERSION,
    )
    presentation_proof = sanitize_and_scope_css(
        ".slide{color:#fff}",
        compiler_version=PRESENTATION_PROOF_COMPILER_VERSION,
    )
    readable_body = sanitize_and_scope_css(
        ".slide{color:#fff}",
        compiler_version=READABLE_BODY_COMPILER_VERSION,
    )

    assert COMPILER_VERSION == "instant-html-compiler.v34"
    assert PRESENTATION_PROOF_COMPILER_VERSION == "instant-html-compiler.v20"
    assert READABLE_BODY_COMPILER_VERSION == "instant-html-compiler.v21"
    assert 'data-da-element-key^="headline-"' in current
    assert "font-size:64px!important" in current
    assert 'data-da-element-key^="body-"' in current
    assert "font-size:max(28px,1em)!important" in current
    assert RENDER_AUTHORED_BACKGROUND_GUARD_CSS in current
    assert "--da-ink" in current
    assert RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS not in current
    assert 'data-da-element-key^="headline-"' not in visual_substance
    assert 'data-da-element-key^="headline-"' in presentation_proof
    assert "font-size:max(88px,1em)!important" in presentation_proof
    assert 'data-da-element-key^="headline-"' not in readable_body


def test_sixty_four_pixel_typography_is_valid_focal_scale() -> None:
    metrics = _metrics(
        maximumTextFontSize=64,
        largestVisualAreaRatio=0.0,
        visualInkAreaRatio=0.0,
    )

    assert "presentation_focal_scale_missing" not in presentation_quality_failure_codes(metrics)
