from __future__ import annotations

from app.db.models import DeckSlide, DeckSlideAsset, DeckSlideBlock


def _json_object(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _slide_enrichment_metadata(slide: DeckSlide) -> dict:
    metadata = _json_object(slide.metadata_json)
    return {
        "sourceVersion": metadata.get("sourceVersion"),
        "enrichmentSource": metadata.get("semanticEnrichment"),
    }


def _block_enrichment_metadata(block: DeckSlideBlock) -> dict:
    metadata = _json_object(block.metadata_json)
    return {
        "sourceVersion": metadata.get("sourceVersion"),
        "enrichmentSource": metadata.get("semanticEnrichment"),
        "semanticConfidence": metadata.get("semanticConfidence"),
    }


def _preview_proxy_url(slide: DeckSlide) -> str | None:
    if not (slide.thumbnail_path or slide.rendered_image_path):
        return None
    return f"/api/decks/{slide.deck_id}/slides/{slide.id}/preview"


def map_source_asset_payload(asset: DeckSlideAsset, slide: DeckSlide) -> dict:
    return {
        "id": asset.id,
        "extractionRunId": asset.extraction_run_id,
        "assetType": asset.asset_type,
        "label": asset.label,
        "mimeType": asset.mime_type,
        "storageProvider": asset.storage_provider,
        "storagePath": asset.storage_path,
        "assetUrl": f"/api/decks/{slide.deck_id}/slides/{slide.id}/assets/{asset.id}" if asset.storage_path else None,
        "pageNumber": asset.page_number,
        "width": asset.width,
        "height": asset.height,
        "metadataJson": asset.metadata_json,
    }


def map_source_block_payload(block: DeckSlideBlock) -> dict:
    return {
        "id": block.id,
        "blockIndex": block.block_index,
        "rawText": block.raw_text,
        "normalizedText": block.normalized_text,
        "text": block.text,
        "blockType": block.block_type,
        "type": block.block_type,
        "blockKind": block.block_kind,
        "semanticRole": block.semantic_role,
        "contentHash": block.content_hash,
        "extractionStage": block.extraction_stage,
        "extractionSource": block.extraction_source,
        "sourceKind": block.source_kind,
        "sourceVersion": _block_enrichment_metadata(block).get("sourceVersion"),
        "enrichmentSource": _block_enrichment_metadata(block).get("enrichmentSource"),
        "semanticConfidence": _block_enrichment_metadata(block).get("semanticConfidence"),
        "metadataJson": block.metadata_json,
    }


def map_source_slide_payload(slide: DeckSlide) -> dict:
    preview_url = _preview_proxy_url(slide)
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "slideIndex": slide.slide_index,
        "slideNumber": slide.slide_number or slide.source_page_number or slide.slide_index,
        "sourcePageNumber": slide.source_page_number,
        "title": slide.title,
        "role": slide.role,
        "semanticSlideType": slide.semantic_slide_type,
        "summary": slide.summary,
        "textHash": slide.text_hash,
        "rawText": slide.raw_text,
        "extractedText": slide.raw_text,
        "thumbnailPath": slide.thumbnail_path,
        "thumbnailMimeType": slide.thumbnail_mime_type,
        "thumbnailUrl": preview_url,
        "previewImageUrl": preview_url,
        "previewUrl": preview_url,
        "widthPoints": slide.width_points,
        "heightPoints": slide.height_points,
        "sourceVersion": _slide_enrichment_metadata(slide).get("sourceVersion"),
        "enrichmentSource": _slide_enrichment_metadata(slide).get("enrichmentSource"),
        "layoutHints": {
            "role": slide.semantic_slide_type or slide.role,
            "hasLargeTitle": bool(slide.title),
            "hasPreview": bool(preview_url),
            "blockCount": len(slide.blocks),
            "assetCount": len(slide.assets),
        },
        "metadataJson": slide.metadata_json,
        "blocks": [
            map_source_block_payload(block)
            for block in sorted(slide.blocks, key=lambda item: item.block_index)
        ],
        "assets": [
            map_source_asset_payload(asset, slide)
            for asset in slide.assets
        ],
    }


__all__ = ["map_source_asset_payload", "map_source_block_payload", "map_source_slide_payload"]
