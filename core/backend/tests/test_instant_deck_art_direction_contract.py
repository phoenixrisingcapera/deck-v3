import pytest

from app.services.llm.full_html_generation_service import (
    CHROMIUM_READABILITY_FULL_HTML_SYSTEM_PROMPT_VERSION,
    FULL_HTML_SYSTEM_PROMPT_VERSION,
    MAX_DETERMINISTIC_VALIDATION_RETRIES,
    VISUAL_SUBSTANCE_FULL_HTML_SYSTEM_PROMPT_VERSION,
    _system_prompt,
    validate_full_html_presentation_quality,
)
from app.services.rendering.html_deck_compiler import HtmlDeckCompileError
from app.services.llm.instant_html_operation_service import MAX_PROVIDER_REQUEST_STARTS


FAMILIES = (
    "editorial-cover",
    "problem-landscape",
    "product-system",
    "metric-led",
    "people-proof",
    "capital-plan",
)


def _deck(*, final_title: str = "Choose the next move", overflow: str = "hidden", visuals: int = 2) -> str:
    sections = []
    for index, family in enumerate(FAMILIES):
        visual = "<svg viewBox='0 0 100 100'><path d='M0 100L100 0'/></svg>" if index < visuals else ""
        title = final_title if index == len(FAMILIES) - 1 else f"Section {index + 1}"
        sections.append(
            f"<section class='deck-section family-{family}' "
            f"data-layout-intent='intent-{index + 1}' "
            f"data-composition-family='{family}' data-slot-title='{title}'>"
            f"<h2>{title}</h2>{visual}</section>"
        )
    return (
        "<!doctype html><html><head><style>"
        ":root{--font-display:Manrope,sans-serif;--font-body:Inter,sans-serif;"
        "--deck-content-max:1600px}.deck-section{min-height:1080px;overflow:"
        + overflow
        + "}</style></head><body><main>"
        + "".join(sections)
        + "</main></body></html>"
    )


def _assert_failure(raw: str, code: str) -> None:
    with pytest.raises(HtmlDeckCompileError) as raised:
        validate_full_html_presentation_quality(
            raw,
            system_prompt_version=FULL_HTML_SYSTEM_PROMPT_VERSION,
            context_pack={},
        )
    assert raised.value.code == code


def test_v15_accepts_a_visual_decisive_non_scrolling_deck() -> None:
    validate_full_html_presentation_quality(
        _deck(),
        system_prompt_version=FULL_HTML_SYSTEM_PROMPT_VERSION,
        context_pack={},
    )


def test_v15_rejects_scroll_containers() -> None:
    _assert_failure(_deck(overflow="auto"), "presentation_scroll_container_forbidden")


def test_v15_rejects_evidence_directory_as_the_close() -> None:
    _assert_failure(_deck(final_title="Evidence"), "presentation_decisive_close_missing")


def test_v15_rejects_a_text_only_document_template() -> None:
    _assert_failure(_deck(visuals=0), "presentation_visual_storytelling_missing")


def test_v15_rejects_a_transcribed_long_section_title() -> None:
    long_title = "How does it work from charitable support through consultation and follow-up funding"
    _assert_failure(_deck(final_title=long_title), "presentation_section_title_too_long")


def test_current_prompt_preserves_complete_chromium_quality_contract() -> None:
    prompt = _system_prompt(FULL_HTML_SYSTEM_PROMPT_VERSION)

    assert FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v38"
    assert "compute to at least 24px" in prompt
    assert "median of those body elements on every slide must be at least 28px" in prompt
    assert "at least 4.5:1 for normal text and 3:1 for large text" in prompt
    assert "meaningful img or SVG occupies at least 12%" in prompt
    assert "painted visual marks occupy at least 4%" in prompt
    assert "at least 3.5% painted visual ink" in prompt
    assert "CHROMIUM-FOCAL-SCALE CORRECTION" not in _system_prompt(
        CHROMIUM_READABILITY_FULL_HTML_SYSTEM_PROMPT_VERSION
    )
    assert "CHROMIUM-READABILITY CORRECTION" not in _system_prompt(
        VISUAL_SUBSTANCE_FULL_HTML_SYSTEM_PROMPT_VERSION
    )


def test_instant_generation_allows_exactly_one_bounded_validation_retry() -> None:
    assert MAX_DETERMINISTIC_VALIDATION_RETRIES == 1
    assert MAX_PROVIDER_REQUEST_STARTS == 2
