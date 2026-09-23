from __future__ import annotations

import hashlib
import re
from typing import Any

from app.db.models import Deck, DeckSlide, DeckSlideAsset, DeckSlideBlock

SOURCE_V1_SCHEMA_VERSION = "smart-deck-source-v1.1"

_SPACE_RE = re.compile(r"\s+")


def compact_text(value: str | None, *, limit: int = 1200) -> str:
    text = _SPACE_RE.sub(" ", (value or "").strip())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def stable_content_hash(value: str | None) -> str | None:
    text = compact_text(value, limit=20000)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_block_kind(block: DeckSlideBlock, *, block_index: int | None = None) -> str:
    text = compact_text(block.normalized_text or block.text or block.raw_text, limit=400)
    text_lower = text.lower()
    raw_type = (block.block_type or "").lower()
    source_kind = (block.source_kind or "").lower()
    combined = " ".join([raw_type, source_kind, text_lower])

    if block.asset_id or any(token in combined for token in ("chart", "graph", "plot", "axis", "legend")):
        return "chart"
    if any(token in combined for token in ("table", "row", "column")):
        return "table"
    if any(token in combined for token in ("image", "figure", "logo", "photo", "picture")):
        return "image"
    if any(token in combined for token in ("footer", "page number", "copyright", "confidential")):
        return "footer"
    if (block_index == 0 or block.block_index == 0) and len(text) <= 160:
        return "headline"
    if raw_type in {"title", "heading", "header"} or source_kind in {"title", "heading", "header"}:
        return "headline"
    if _looks_like_metric(text):
        return "metric"
    if len(text) <= 90 and not text.endswith("."):
        return "label"
    return "body"


def infer_semantic_role(block: DeckSlideBlock, *, block_kind: str, block_index: int | None = None) -> str:
    text = compact_text(block.normalized_text or block.text or block.raw_text, limit=300).lower()
    if block_kind == "headline" or block_index == 0 or block.block_index == 0:
        return "slide_title"
    if block_kind == "metric" or any(token in text for token in ("arr", "mrr", "tam", "sam", "som", "%", "$", "£")):
        return "metric_or_market_claim"
    if any(token in text for token in ("problem", "pain", "challenge", "why now")):
        return "problem_claim"
    if any(token in text for token in ("solution", "platform", "product", "workflow")):
        return "solution_claim"
    if any(token in text for token in ("customer", "user", "buyer", "icp")):
        return "customer_claim"
    if any(token in text for token in ("competitor", "alternative", "incumbent")):
        return "competition_claim"
    if block_kind in {"chart", "table", "image"}:
        return "visual_evidence"
    return "supporting_text"


def infer_slide_semantic_type(slide: DeckSlide) -> str:
    text = compact_text(" ".join([slide.title or "", slide.raw_text or ""]), limit=1200).lower()
    if any(token in text for token in ("problem", "pain", "challenge")):
        return "problem"
    if any(token in text for token in ("solution", "product", "platform")):
        return "solution"
    if any(token in text for token in ("market", "tam", "sam", "som")):
        return "market"
    if any(token in text for token in ("traction", "growth", "revenue", "arr", "mrr")):
        return "traction"
    if any(token in text for token in ("competitor", "competition", "landscape")):
        return "competition"
    if any(token in text for token in ("team", "founder")):
        return "team"
    if any(token in text for token in ("ask", "raise", "funding")):
        return "funding"
    return slide.semantic_slide_type or slide.role or "source_slide"


def build_source_block_payload(block: DeckSlideBlock, *, block_index: int | None = None) -> dict[str, Any]:
    text = compact_text(block.text or block.normalized_text or block.raw_text, limit=1800)
    block_kind = block.block_kind or infer_block_kind(block, block_index=block_index)
    semantic_role = block.semantic_role or infer_semantic_role(block, block_kind=block_kind, block_index=block_index)
    return {
        "id": block.id,
        "blockId": block.id,
        "blockIndex": block.block_index,
        "blockType": block.block_type,
        "blockKind": block_kind,
        "semanticRole": semantic_role,
        "text": text,
        "rawText": compact_text(block.raw_text, limit=1800),
        "normalizedText": compact_text(block.normalized_text, limit=1800),
        "contentHash": block.content_hash or stable_content_hash(text),
        "sourceKind": block.source_kind,
        "extractionSource": block.extraction_source,
        "confidence": block.confidence,
    }


def build_source_asset_payload(asset: DeckSlideAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "assetId": asset.id,
        "assetType": asset.asset_type,
        "assetKind": asset.asset_kind,
        "label": asset.label,
        "mimeType": asset.mime_type,
        "storageProvider": asset.storage_provider,
        "storagePath": asset.storage_path,
        "width": asset.width,
        "height": asset.height,
        "sha256": asset.sha256,
    }


def build_source_slide_payload(slide: DeckSlide) -> dict[str, Any]:
    blocks = sorted(slide.blocks, key=lambda item: item.block_index)
    assets = sorted(slide.assets, key=lambda item: item.created_at)
    semantic_type = slide.semantic_slide_type or infer_slide_semantic_type(slide)
    return {
        "id": slide.id,
        "slideId": slide.id,
        "slideIndex": slide.slide_index,
        "slideNumber": slide.slide_number or slide.source_page_number or slide.slide_index + 1,
        "title": compact_text(slide.title, limit=240),
        "role": slide.role,
        "semanticSlideType": semantic_type,
        "summary": compact_text(slide.summary or slide.narrative_notes or slide.raw_text, limit=500),
        "rawText": compact_text(slide.raw_text, limit=4000),
        "textHash": slide.text_hash or stable_content_hash(slide.raw_text),
        "thumbnailPath": slide.thumbnail_path,
        "thumbnailMimeType": slide.thumbnail_mime_type,
        "previewImagePath": slide.rendered_image_path or slide.thumbnail_path,
        "widthPoints": slide.width_points,
        "heightPoints": slide.height_points,
        "blocks": [build_source_block_payload(block, block_index=index) for index, block in enumerate(blocks)],
        "assets": [build_source_asset_payload(asset) for asset in assets],
    }


def build_source_v1_context(deck: Deck) -> dict[str, Any]:
    slides = sorted(deck.slides, key=lambda item: (item.slide_index, item.id))
    source_file = deck.file
    return {
        "schemaVersion": SOURCE_V1_SCHEMA_VERSION,
        "sourceVersion": "original_source_v1",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "status": deck.status,
            "sourceType": deck.source_type,
            "slideCount": len(slides),
            "summary": deck.summary,
            "sourceFile": {
                "id": source_file.id if source_file else None,
                "filename": source_file.original_filename or source_file.filename if source_file else None,
                "mimeType": source_file.mime_type if source_file else None,
                "fileExtension": source_file.file_extension if source_file else None,
                "storageProvider": source_file.storage_provider if source_file else None,
                "storagePath": source_file.storage_path if source_file else None,
                "pageCount": source_file.page_count if source_file else None,
            },
        },
        "slides": [build_source_slide_payload(slide) for slide in slides],
        "runtimeContract": {
            "userControlsChanges": True,
            "sourceSlidesAreImmutableBaseline": True,
            "generatedVersionsAreReviewable": True,
            "defaultNextAction": "select_slides_to_change",
        },
    }


def build_source_enrichment_prompt(context: dict[str, Any]) -> dict[str, str]:
    system = (
        "You are DeckAiStack's source-deck analyst. Return only valid JSON. "
        "Do not invent facts. Use the provided slide and block ids exactly. "
        "Classify each block as headline, body, metric, chart, table, image, label, or footer. "
        "Give semantic roles that help an investor decide which slides to improve."
    )
    user = {
        "task": "source_slide_semantic_enrichment",
        "schema": {
            "slides": [
                {
                    "slideId": "string",
                    "semanticSlideType": "problem|solution|market|traction|competition|team|funding|source_slide",
                    "summary": "short source-only summary",
                    "blocks": [
                        {
                            "blockId": "string",
                            "blockKind": "headline|body|metric|chart|table|image|label|footer",
                            "semanticRole": "short role label",
                            "confidence": 0.0,
                        }
                    ],
                }
            ]
        },
        "sourceContext": context,
    }
    return {"system": system, "user": compact_text(__import__("json").dumps(user, ensure_ascii=False), limit=24000)}


def _looks_like_metric(text: str) -> bool:
    if not text:
        return False
    digit_count = sum(1 for char in text if char.isdigit())
    if digit_count >= 3 and any(token in text for token in ("%", "$", "£", "x", "m", "k")):
        return True
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|m|bn|k|x)\b", text.lower()))
