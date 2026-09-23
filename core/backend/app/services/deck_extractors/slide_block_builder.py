from __future__ import annotations

import re

_BULLET_PATTERN = re.compile(r"^([-*•]|\d+[.)])\s+")
_METRIC_PATTERN = re.compile(r"(^|\s)([$£€]?\d[\d,]*(?:\.\d+)?%?|[0-9]+(?:\.[0-9]+)?x)\b", re.IGNORECASE)
_URL_PATTERN = re.compile(r"\bhttps?://|\bwww\.", re.IGNORECASE)
_TABLE_LIKE_PATTERN = re.compile(r"\s{2,}|\|")
_SPEAKER_NOTE_PATTERN = re.compile(r"^(speaker\s+notes?|presenter\s+notes?|notes?)\s*:", re.IGNORECASE)
_CAPTION_PATTERN = re.compile(r"^(figure|fig\.|image|caption|source|photo|table)\s+\d*[:.-]|\bsource:\s+", re.IGNORECASE)
_CHART_PATTERN = re.compile(r"\b(chart|graph|axis|legend|cohort|funnel|trend|forecast|projection|breakdown)\b", re.IGNORECASE)
_CLAIM_PATTERN = re.compile(
    r"\b(we|our|customers?|users?|buyers?|market|product|platform|solution|workflow|teams?)\b"
    r".*\b(is|are|will|can|could|should|need|needs|reduce|reduces|increase|increases|drives|delivers|enables|supports)\b",
    re.IGNORECASE,
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _paragraphs(page_text: str) -> list[str]:
    normalized = page_text.replace("\r\n", "\n")
    sections = re.split(r"\n\s*\n", normalized)
    paragraphs = [section.strip() for section in sections if _normalize_text(section)]
    if paragraphs:
        return paragraphs

    lines = [_normalize_text(line) for line in normalized.splitlines() if _normalize_text(line)]
    return lines


def _build_title(paragraphs: list[str], slide_number: int) -> str:
    if not paragraphs:
        return f"Slide {slide_number}"

    headline = paragraphs[0]
    if len(headline) <= 120:
        return headline
    return headline[:117].rstrip() + "..."


def _classify_block(paragraph: str, *, is_headline: bool) -> str:
    if is_headline:
        return "headline"
    if _URL_PATTERN.search(paragraph):
        return "reference"
    if _BULLET_PATTERN.search(paragraph):
        return "bullet"
    if _SPEAKER_NOTE_PATTERN.search(paragraph):
        return "speaker_note"
    if _CAPTION_PATTERN.search(paragraph):
        return "caption"
    if _CHART_PATTERN.search(paragraph):
        return "chart"
    if _TABLE_LIKE_PATTERN.search(paragraph):
        return "table_like"
    if _METRIC_PATTERN.search(paragraph) and len(paragraph) <= 140:
        return "metric"
    if len(paragraph) <= 48 and paragraph.endswith(":"):
        return "label"
    if _CLAIM_PATTERN.search(paragraph) and len(paragraph) <= 240:
        return "claim"
    return "body"


def build_slide_blocks(page_text: str, slide_number: int, *, source_kind: str = "pdf_text") -> dict:
    paragraphs = _paragraphs(page_text)
    title = _build_title([_normalize_text(paragraph) for paragraph in paragraphs], slide_number)
    blocks: list[dict] = []

    if paragraphs:
        blocks.append(
            {
                "blockIndex": 0,
                "rawText": paragraphs[0],
                "normalizedText": _normalize_text(paragraphs[0]),
                "blockType": _classify_block(paragraphs[0], is_headline=True),
                "sourceKind": source_kind,
                "metadataJson": {"paragraphIndex": 0},
            }
        )

        for block_index, paragraph in enumerate(paragraphs[1:], start=1):
            blocks.append(
                {
                    "blockIndex": block_index,
                    "rawText": paragraph,
                    "normalizedText": _normalize_text(paragraph),
                    "blockType": _classify_block(_normalize_text(paragraph), is_headline=False),
                    "sourceKind": source_kind,
                    "metadataJson": {"paragraphIndex": block_index},
                }
            )
    else:
        blocks.append(
            {
                "blockIndex": 0,
                "rawText": "No extractable text was detected on this slide.",
                "normalizedText": "No extractable text was detected on this slide.",
                "blockType": "body",
                "sourceKind": "pdf_text",
                "metadataJson": {"emptyPage": True},
            }
        )

    return {
        "title": title,
        # Preserve layout columns in both page and block raw records. Only the
        # explicit normalizedText field collapses whitespace.
        "rawText": page_text.strip(),
        "blocks": blocks,
    }
