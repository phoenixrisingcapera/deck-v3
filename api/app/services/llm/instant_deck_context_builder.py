"""Canonical Instant Deck context builder.

Assembles an ``InstantDeckGenerationContext`` from database objects,
replacing the ad-hoc dict assembly currently scattered across
``_build_llm_context`` and ``build_grounded_context_pack``.

This module is the single source of truth for what goes into Instant Deck
generation context. Complete canonical source truth is joined with a compact
backend-owned agent lane and bounded pgvector guidance before transport.
"""

from __future__ import annotations

import base64
from io import BytesIO
from hashlib import sha256
import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Deck, DeckSlide
from app.schemas.instant_deck_context import (
    AssetReference,
    BrandProfileSnapshot,
    BrandTokenProvenance,
    CanonicalSourceBlock,
    CanonicalSourceDeck,
    CanonicalSourceSlide,
    CanonicalTable,
    DesignTokens,
    GenerationConstraints,
    GroundedContextPack,
    InstantDeckGenerationContext,
    InstantDeckOutputContract,
    SourceFact,
    SourceReference,
)
from app.services.brand.brand_design_tokens import (
    build_brand_design_tokens,
    build_brand_llm_context,
    build_provider_safe_brand_context,
)
from app.services.brand.brand_extraction import confirmed_website_brand_ready, website_brand_binding
from app.services.storage.artifact_storage import get_upload_storage

logger = logging.getLogger(__name__)

_CONTEXT_SCHEMA_VERSION = "instant-deck-context.v1"
_APPROVED_ASSET_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
_RASTERIZABLE_ASSET_MIME_TYPES = {"image/svg+xml"}
_MAX_APPROVED_ASSETS = 16
_MAX_SOURCE_ASSET_BYTES = 16 * 1024 * 1024
_MAX_APPROVED_ASSET_BYTES = 192 * 1024
_MAX_APPROVED_ASSET_TOTAL_BYTES = 256 * 1024
_MAX_AGENT_CONTEXT_BYTES = 24 * 1024
_MAX_RETRIEVED_GUIDANCE_BYTES = 16 * 1024
_MAX_RETRIEVED_GUIDANCE_CHUNKS = 6
_MAX_RETRIEVED_CHUNK_TEXT = 1_600
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_MARKDOWN_LIST_ITEM_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
_PLACEHOLDER_SOURCE_TITLE_RE = re.compile(
    r"^(?:slide|page)\s+\d+$|^(?:unknown|unclassified|untitled)$",
    re.IGNORECASE,
)


def resolve_instant_deck_intent(
    *,
    deck: Deck,
    selected_slides: list[DeckSlide],
    audience: str | None,
    deck_type: str | None,
    user_goal: str = "",
) -> tuple[str | None, str | None]:
    """New MVP requests have a product-owned investor audience and purpose.

    Historical operations replay their persisted context instead of this builder.
    Source descriptions and client-provided labels cannot redefine product scope.
    """
    from app.services.llm.instant_deck_mvp_policy import MVP_AUDIENCE
    return MVP_AUDIENCE, "investor_pitch"


def _bounded_json_object(value: dict[str, Any], *, max_bytes: int, lane: str) -> dict[str, Any]:
    import json

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"Instant Deck {lane} exceeds its {max_bytes}-byte bound.")
    return value


def build_compact_instant_deck_agent_context() -> dict[str, Any]:
    """Return the useful knowledge lane without runtime/tool-registry noise."""
    from app.ai.instant_deck_knowledge_context import build_instant_deck_generation_context

    source = build_instant_deck_generation_context()
    compact = {
        "schemaVersion": "instant-deck-agent-context.v1",
        "knowledgeSource": source.get("knowledgeSource") or {},
        "promptRecipe": source.get("promptRecipe") or {},
        "designQualityRules": source.get("designQualityRules") or {},
        "vcAiStackModules": source.get("vcAiStackModules") or {},
        "contextVigilancePatterns": source.get("contextVigilancePatterns") or {},
        "instructions": list(source.get("instructions") or [])[:8],
        "factualAuthority": "canonical_source_only",
    }
    return _bounded_json_object(compact, max_bytes=_MAX_AGENT_CONTEXT_BYTES, lane="agentContext")


def build_bounded_retrieved_guidance(
    db: Session,
    *,
    deck: Deck,
    objective: str,
    audience: str | None,
    deck_type: str | None,
) -> dict[str, Any]:
    """Retrieve only product-owned guidance; customer source stays out of vectors."""
    from app.ai.instant_deck_knowledge_context import load_instant_deck_knowledge
    from app.core.openai_full_html_policy import estimate_text_tokens
    from app.services.llm.deck_chunking_service import (
        sync_deck_vector_chunks,
        sync_instant_deck_knowledge_chunks,
    )
    from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks

    from app.services.llm.instant_deck_mvp_policy import MVP_AUDIENCE, MVP_PURPOSE

    objective, audience, deck_type = MVP_PURPOSE, MVP_AUDIENCE, "investor_pitch"
    query = "\n".join(
        part for part in (
            "Whole-deck investor presentation redesign guidance",
            f"Objective: {objective.strip()}" if objective.strip() else "",
            f"Audience: {audience}" if audience else "",
            f"Deck type: {deck_type}" if deck_type else "",
            "Prioritise problem, product, traction, business model, team, raise, evidence and diligence.",
            "Select creative design patterns that preserve fixed 16:9 geometry, readable density, asset balance, and zero overflow or clipping.",
        ) if part
    )
    knowledge_sync = sync_instant_deck_knowledge_chunks(db)
    deck_policy = sync_deck_vector_chunks(
        db,
        deck.id,
        audience_label=audience,
    )
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck.id,
        query_text=query,
        chunk_types=["instant_deck_knowledge"],
        limit=_MAX_RETRIEVED_GUIDANCE_CHUNKS,
    )
    knowledge = load_instant_deck_knowledge()
    chunks = []
    for item in list(retrieval.get("chunks") or [])[:_MAX_RETRIEVED_GUIDANCE_CHUNKS]:
        if not isinstance(item, dict):
            continue
        text = _provider_safe_retrieved_text(str(item.get("contentText") or ""))
        if not text:
            continue
        if str(item.get("scope") or "") != "global_knowledge":
            logger.warning(
                "instant_deck_retrieval_rejected_non_product_chunk",
                extra={"deck_id": deck.id, "chunk_id": item.get("id")},
            )
            continue
        chunks.append({
            "chunkId": str(item.get("id") or ""),
            "chunkType": str(item.get("chunkType") or ""),
            "sourceKey": str(item.get("sourceKey") or ""),
            "sourceSlideId": item.get("slideId"),
            "content": text[:_MAX_RETRIEVED_CHUNK_TEXT],
            "scope": "global_knowledge",
            "similarityScore": item.get("similarityScore"),
        })
    status = (
        "ready"
        if deck_policy.get("status") == "excluded_by_policy"
        and knowledge_sync.get("status") == "ready"
        and retrieval.get("status") == "ready"
        and chunks
        else "degraded"
    )
    serialized_guidance = json.dumps(chunks, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    skip_reason = None
    if retrieval.get("status") != "ready":
        skip_reason = str(retrieval.get("message") or "retrieval_unavailable")
    elif not chunks:
        skip_reason = "no_design_guidance_above_similarity_threshold"
    result = {
        "schemaVersion": "instant-deck-retrieved-guidance.v1",
        "retrievalStatus": status,
        "retrievalExecuted": retrieval.get("status") == "ready",
        "skipReason": skip_reason,
        "knowledgePackage": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
        },
        "provider": retrieval.get("provider") or knowledge_sync.get("provider"),
        "model": retrieval.get("model") or knowledge_sync.get("model"),
        "traceId": retrieval.get("traceId"),
        "chunkCount": len(chunks),
        "retrievedItemIds": [chunk["chunkId"] for chunk in chunks],
        "tokenCount": estimate_text_tokens(serialized_guidance) if chunks else 0,
        "chunks": chunks,
        "indexStatus": {
            "deck": deck_policy.get("status"),
            "stableKnowledge": knowledge_sync.get("status"),
            "deckEmbeddedChunkCount": 0,
            "knowledgeEmbeddedChunkCount": knowledge_sync.get("embeddedChunkCount", 0),
        },
        "bounds": {
            "maxChunks": _MAX_RETRIEVED_GUIDANCE_CHUNKS,
            "maxChunkCharacters": _MAX_RETRIEVED_CHUNK_TEXT,
            "maxSerializedBytes": _MAX_RETRIEVED_GUIDANCE_BYTES,
        },
        "factualAuthority": "canonical_source_only",
    }
    return _bounded_json_object(result, max_bytes=_MAX_RETRIEVED_GUIDANCE_BYTES, lane="retrievedGuidance")


def _provider_safe_retrieved_text(value: str) -> str:
    """Keep retrieved evidence rich without handing Markdown display syntax to the renderer model."""
    safe_lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cells = _markdown_table_cells(line)
        if cells:
            if _is_markdown_table_separator(cells):
                continue
            line = " · ".join(cell.strip() for cell in cells if cell.strip())
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        if line:
            safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _evidence_class(source: str, status: str) -> str:
    normalized = source.strip().lower()
    if status == "overridden" or normalized == "manual" or normalized.startswith("brand_guidelines"):
        return "confirmed"
    if "generated" in normalized or "fallback" in normalized or "seed" in normalized or normalized in {
        "context_seed", "fallback_safe_fonts", "",
    }:
        return "inferred"
    if normalized.startswith(("deck_", "logo_", "url_")):
        return "source-extracted"
    return "inferred"


def _brand_token_provenance(brand_profile: Any) -> dict[str, BrandTokenProvenance]:
    raw = brand_profile.raw_evidence_json if isinstance(getattr(brand_profile, "raw_evidence_json", None), dict) else {}
    field_evidence = raw.get("fieldEvidence") if isinstance(raw.get("fieldEvidence"), dict) else {}

    def entry(field: str, fallback_source: str = "") -> BrandTokenProvenance:
        evidence = field_evidence.get(field) if isinstance(field_evidence.get(field), dict) else {}
        source = str(evidence.get("source") or fallback_source)
        status = str(evidence.get("status") or "")
        confidence_value = evidence.get("confidence")
        confidence = float(confidence_value) if isinstance(confidence_value, (int, float)) else None
        return BrandTokenProvenance(
            classification=_evidence_class(source, status),
            source=source or "unrecorded",
            confidence=confidence,
        )

    result = {
        "companyName": entry("companyName"),
        "colors.primary": entry("primaryColor"),
        "colors.secondary": entry("secondaryColor"),
        "colors.accent": entry("accentColor"),
        "colors.background": entry("backgroundColor"),
        "colors.text": entry("textColor"),
        "fonts": entry("fontCandidates"),
        "logo": entry("logoUrl", "logo_live_asset" if raw.get("logoAssetId") else ""),
    }
    palette_entry = entry("palette", str(raw.get("paletteSource") or ""))
    result["palette"] = palette_entry
    # The deterministic extractor composes its standard palette as primary,
    # secondary, accent, surface, text.  Preserve role evidence for each value
    # instead of falsely labelling generated accessibility roles as extracted.
    standard_palette_roles = (
        "colors.primary", "colors.secondary", "colors.accent",
        "colors.background", "colors.text",
    )
    for index, _value in enumerate(getattr(brand_profile, "palette_json", None) or []):
        result[f"palette.{index}"] = (
            result[standard_palette_roles[index]].model_copy()
            if index < len(standard_palette_roles)
            else palette_entry.model_copy()
        )
    return result


def _safe_asset_payload(storage_path: str, *, remaining_bytes: int) -> bytes | None:
    if remaining_bytes <= 0:
        return None
    storage = get_upload_storage()
    payload = bytearray()
    try:
        for chunk in storage.iter_bytes(storage_path, chunk_size=64 * 1024):
            payload.extend(chunk)
            if len(payload) > _MAX_SOURCE_ASSET_BYTES:
                return None
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        logger.warning("instant_deck_approved_asset_unavailable", extra={"storage_path": storage_path})
        return None
    return bytes(payload) if payload else None


def _provider_safe_asset_payload(
    mime_type: str,
    payload: bytes,
    *,
    remaining_bytes: int,
) -> tuple[str, bytes] | None:
    """Return a bounded provider-safe raster image.

    SVG is useful brand evidence but is deliberately not sent to the model or
    compiler as active markup. Rasterising the already-persisted asset keeps
    the canonical logo while preserving the raster-only provider boundary.
    """
    if mime_type in _APPROVED_ASSET_MIME_TYPES:
        from PIL import Image, ImageOps, UnidentifiedImageError
        try:
            with Image.open(BytesIO(payload)) as original:
                if original.width * original.height > 25_000_000 or getattr(original, 'n_frames', 1) != 1:
                    return None
                original.load()
                image = ImageOps.exif_transpose(original).convert('RGBA' if 'A' in original.getbands() else 'RGB')
                if len(payload) <= min(remaining_bytes, _MAX_APPROVED_ASSET_BYTES):
                    return mime_type, payload
                # The original stays immutable in storage. The provider/compiler
                # receive a bounded, aspect-preserving raster derivative, never
                # an arbitrary crop or a replacement generated image.
                for edge in (1280, 1024, 800, 640):
                    resized = image.copy()
                    resized.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                    output = BytesIO()
                    resized.save(output, format='WEBP', quality=85, method=6)
                    data = output.getvalue()
                    if len(data) <= min(remaining_bytes, _MAX_APPROVED_ASSET_BYTES):
                        return 'image/webp', data
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            return None
        return None
    if mime_type not in _RASTERIZABLE_ASSET_MIME_TYPES:
        return None
    try:
        import fitz

        document = fitz.open(stream=payload, filetype="svg")
        try:
            if document.page_count != 1:
                return None
            page = document.load_page(0)
            longest_edge = max(float(page.rect.width), float(page.rect.height))
            if longest_edge <= 0:
                return None
            scale = min(4.0, 512.0 / longest_edge)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True)
            raster = pixmap.tobytes("png")
        finally:
            document.close()
    except (RuntimeError, ValueError, TypeError):
        logger.warning("instant_deck_svg_asset_rasterization_failed")
        return None
    if not raster or len(raster) > _MAX_APPROVED_ASSET_BYTES or len(raster) > remaining_bytes:
        return None
    return ("image/png", raster)


def _build_approved_assets(deck: Deck, selected_slides: list[DeckSlide]) -> list[AssetReference]:
    """Inline only bounded canonical images; never expose repository/storage paths."""
    candidates: list[tuple[Any, str, list[str], str]] = []
    for asset in sorted(getattr(deck, "brand_assets", None) or [], key=lambda item: (item.created_at, item.id)):
        if asset.asset_type == "logo":
            provenance = "confirmed" if str(getattr(asset, "source", "") or "") == "upload" else "source-extracted"
            candidates.append((asset, "logo", [], provenance))
    for slide in selected_slides:
        for asset in sorted(getattr(slide, "assets", None) or [], key=lambda item: (item.created_at, item.id)):
            candidates.append((asset, "source_image", [slide.id], "source-extracted"))

    # Give each source page a turn before taking additional images from the
    # same page; a page with many extracted pieces must not consume the catalog.
    groups: dict[str, list] = {}
    for candidate in candidates:
        groups.setdefault(candidate[2][0] if candidate[2] else 'brand', []).append(candidate)
    candidates = [group[index] for index in range(max(map(len, groups.values()), default=0))
                  for group in groups.values() if index < len(group)]
    approved: list[AssetReference] = []
    total_bytes = 0
    seen_ids: set[str] = set()
    for candidate_index, (asset, role, source_slide_ids, provenance) in enumerate(candidates):
        if len(approved) >= _MAX_APPROVED_ASSETS or asset.id in seen_ids:
            continue
        mime_type = str(getattr(asset, "mime_type", None) or "").lower()
        storage_path = str(getattr(asset, "storage_path", None) or "")
        if mime_type not in (_APPROVED_ASSET_MIME_TYPES | _RASTERIZABLE_ASSET_MIME_TYPES) or not storage_path:
            continue
        remaining_bytes = _MAX_APPROVED_ASSET_TOTAL_BYTES - total_bytes
        payload = _safe_asset_payload(storage_path, remaining_bytes=remaining_bytes)
        if payload is None:
            continue
        safe_asset = _provider_safe_asset_payload(
            mime_type,
            payload,
            remaining_bytes=remaining_bytes // max(1, min(_MAX_APPROVED_ASSETS - len(approved), len(candidates) - candidate_index)),
        )
        if safe_asset is None:
            continue
        safe_mime_type, safe_payload = safe_asset
        total_bytes += len(safe_payload)
        seen_ids.add(asset.id)
        approved.append(AssetReference(
            asset_id=asset.id,
            mime_type=safe_mime_type,
            alt_text=str(getattr(asset, "label", None) or role.replace("_", " ")),
            role=role,
            provenance=provenance,
            source_slide_ids=source_slide_ids,
            resolved_data_url=f"data:{safe_mime_type};base64,{base64.b64encode(safe_payload).decode('ascii')}",
            preparation_policy='bounded-source-raster.v1',
            original_sha256=sha256(payload).hexdigest(),
            rendered_sha256=sha256(safe_payload).hexdigest(),
        ))
    return approved


def _ordered_slide_blocks(slide: DeckSlide) -> list[Any]:
    """Return persisted source blocks in their canonical extraction order."""
    return sorted(
        getattr(slide, "blocks", None) or [],
        key=lambda item: (item.block_index, item.id),
    )


def _source_block_fact_id(*, block_id: str, text: str) -> str:
    """Bind fact identity to the persisted block and its exact extracted text."""
    identity = f"{len(block_id)}:{block_id}{len(text)}:{text}".encode("utf-8")
    return f"fact_source_block_{sha256(identity).hexdigest()}"


def _markdown_table_cells(value: str) -> list[str] | None:
    stripped = value.strip()
    if "|" not in stripped:
        return None
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return cells if len(cells) >= 2 else None


def _markdown_table_groups(value: str) -> list[list[str]]:
    """Split both normal pipe rows and PDF-flattened ``| |`` row runs."""
    stripped = value.strip()
    if "|" not in stripped:
        return []
    tokens = [token.strip() for token in stripped.split("|")]
    if tokens and not tokens[0]:
        tokens.pop(0)
    if tokens and not tokens[-1] and stripped.endswith("|"):
        tokens.pop()
    groups: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token:
            current.append(token)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _is_markdown_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(cell) for cell in cells)


def _parse_markdown_tables_with_sources(
    sources: list[tuple[str, str]],
) -> list[tuple[CanonicalTable, list[tuple[list[str], list[str]]]]]:
    """Parse Markdown pipe tables while retaining row-level source pages.

    PDF extraction can split a logical row across line and page boundaries.
    A pending row therefore remains open until its trailing pipe arrives; all
    contributing page IDs are retained on the resulting presentation fact.
    """
    parsed: list[tuple[CanonicalTable, list[tuple[list[str], list[str]]]]] = []
    header: list[str] | None = None
    rows: list[tuple[list[str], list[str]]] = []
    pending: list[str] = []
    pending_sources: list[str] = []

    def finish_row() -> None:
        nonlocal pending, pending_sources
        if pending and header and len(pending) == len(header) and not _is_markdown_table_separator(pending):
            rows.append((list(pending), list(dict.fromkeys(pending_sources))))
        pending = []
        pending_sources = []

    def finish_table() -> None:
        nonlocal header, rows
        finish_row()
        if header and rows:
            parsed.append((CanonicalTable(headers=header, rows=[item[0] for item in rows]), rows))
        header = None
        rows = []

    for source_id, raw_text in sources:
        for line in (raw_text or "").splitlines():
            stripped = line.strip()
            groups = _markdown_table_groups(stripped)
            if header is None:
                if groups and stripped.startswith("|") and not _is_markdown_table_separator(groups[0]):
                    header = groups[0]
                    row_groups = groups[1:]
                    if row_groups and _is_markdown_table_separator(row_groups[0]):
                        row_groups = row_groups[1:]
                    for group_index, group in enumerate(row_groups):
                        if len(group) != len(header):
                            continue
                        is_last_unclosed = group_index == len(row_groups) - 1 and not stripped.endswith("|")
                        if is_last_unclosed:
                            pending = list(group)
                            pending_sources = [source_id]
                        else:
                            rows.append((list(group), [source_id]))
                continue
            if groups and len(groups) == 1 and _is_markdown_table_separator(groups[0]):
                continue
            if groups and stripped.startswith("|"):
                finish_row()
                for group_index, group in enumerate(groups):
                    if len(group) != len(header):
                        continue
                    is_last_unclosed = group_index == len(groups) - 1 and not stripped.endswith("|")
                    if is_last_unclosed:
                        pending = list(group)
                        pending_sources = [source_id]
                    else:
                        rows.append((list(group), [source_id]))
                continue
            if pending and stripped:
                continuation = stripped[:-1].rstrip() if stripped.endswith("|") else stripped
                pending[-1] = f"{pending[-1]} {continuation}".strip()
                pending_sources.append(source_id)
                if stripped.endswith("|"):
                    finish_row()
                continue
            if not stripped:
                finish_table()
                continue
            finish_table()
    finish_table()
    return parsed


def _extract_tables_from_text(raw_text: str) -> list[CanonicalTable]:
    """Best-effort table extraction from slide raw text.

    This is a simple heuristic; real table extraction happens during
    source ingestion. This function exists so the context builder can
    populate the ``tables`` field even when ingestion didn't produce
    structured table objects.
    """
    return [item[0] for item in _parse_markdown_tables_with_sources([("source", raw_text)])]


def _clean_presentation_text(value: str, *, preserve_layout: bool = False) -> str:
    """Remove structural Markdown syntax without changing persisted source."""
    clean_lines: list[str] = []
    for raw_line in (value or "").splitlines() or [value or ""]:
        line = _MARKDOWN_HEADING_RE.sub("", raw_line).strip()
        if not line:
            continue
        cells = _markdown_table_cells(line)
        if cells and _is_markdown_table_separator(cells):
            continue
        line = _MARKDOWN_LIST_ITEM_RE.sub("", line)
        clean_lines.append(line.strip())
    if not clean_lines:
        return ""
    text = ("\n" if preserve_layout else " ").join(clean_lines)
    if _MARKDOWN_LIST_ITEM_RE.match(value or ""):
        text = re.sub(r"\s+(?:[-+*]|\d+[.)])\s+", "; ", text)
    text = text.strip() if preserve_layout else re.sub(r"\s+", " ", text).strip()
    # Canary/source-workflow labels belong to provenance, not the visible
    # redesign. Keep the original raw blocks untouched while giving the model
    # a clean, presentation-safe semantic fact.
    text = re.sub(r"(?i)\s*[-—]\s*canary\s+source\b", "", text).strip(" |—-")
    if text.casefold() == "source and brand notes":
        return "Brand Evidence"
    return text


def _is_probable_ocr_debris(value: str | None) -> bool:
    """Reject symbol-heavy OCR noise without discarding real source prose.

    Image-only PDF pages can produce long strings dominated by punctuation,
    isolated glyphs, and a handful of accidental letter runs. Those strings
    are extraction diagnostics, not founder evidence, and must not become a
    mandatory fact that the model is forced to print on an appendix slide.
    """
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) < 40:
        return False
    alpha_count = sum(character.isalpha() for character in text)
    punctuation_count = sum(
        not character.isalnum() and not character.isspace()
        for character in text
    )
    word_runs = re.findall(r"[A-Za-z]{3,}", text)
    return (
        alpha_count / len(text) < 0.45
        and punctuation_count / len(text) > 0.20
        and len(word_runs) <= max(5, len(text) // 120)
    )


def _meaningful_source_title(value: str | None) -> str:
    title = _clean_presentation_text(value or "").strip(" |—-")
    if (
        not title
        or _PLACEHOLDER_SOURCE_TITLE_RE.fullmatch(title)
        or _is_probable_ocr_debris(title)
    ):
        return ""
    if title.lower() in {"on the company website"}:
        return ""
    return title


def _is_internal_source_instruction(value: str) -> bool:
    """Identify narrow provenance/workflow directives that are not deck facts."""
    normalized = re.sub(r"\s+", " ", value or "").strip()
    return any(
        re.search(pattern, normalized, re.IGNORECASE)
        for pattern in (
            r"\btreat all traction, pricing, roadmap, team, and milestone statements as company[- ]supplied claims requiring diligence\b",
            r"\buse (?:the company website|https?://\S+) as the brand[- ]profile reference\b",
            r"\buse the public repository only as supporting product/open[- ]source context\b",
            r"\bdo not invent customers, revenue, conversion, retention, enterprise contracts, market size, or compliance certifications\b",
            r"\bpersonal contact details supplied in chat are intentionally omitted from this workspace file\b",
        )
    )


def _table_facts(
    selected_slides: list[DeckSlide],
) -> tuple[list[SourceFact], dict[str, list[CanonicalTable]], dict[str, list[str]]]:
    parsed = _parse_markdown_tables_with_sources(
        [(slide.id, slide.raw_text or "") for slide in selected_slides]
    )
    facts: list[SourceFact] = []
    tables_by_source: dict[str, list[CanonicalTable]] = {}
    fact_ids_by_source: dict[str, list[str]] = {}
    for table_index, (table, rows_with_sources) in enumerate(parsed):
        table_sources = list(dict.fromkeys(
            source_id for _, source_ids in rows_with_sources for source_id in source_ids
        ))
        table_source_id = "source_table_" + sha256(
            json.dumps(
                {"headers": table.headers, "sourceSlideIds": table_sources},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if table_sources:
            tables_by_source.setdefault(table_sources[0], []).append(table)
        for row_index, (row, source_ids) in enumerate(rows_with_sources):
            text = "; ".join(
                f"{header}: {cell}" for header, cell in zip(table.headers, row) if cell
            )
            if not text:
                continue
            identity = f"{table_index}:{row_index}:{text}".encode("utf-8")
            fact_id = f"fact_source_table_{sha256(identity).hexdigest()}"
            facts.append(SourceFact(
                fact_id=fact_id,
                # A reconstructed row can span PDF pages.  Keep the derived
                # table as the fact owner and retain every contributing page
                # in source_slide_ids; a source_slide fact is deliberately
                # restricted to one exact slide by the grounding policy.
                source_type="source_table",
                source_id=table_source_id,
                field=f"table:{table_index}:row:{row_index}",
                text=text,
                confidence="high",
                scope="slide",
                source_slide_ids=source_ids,
            ))
            for source_id in source_ids:
                fact_ids_by_source.setdefault(source_id, []).append(fact_id)
    return facts, tables_by_source, fact_ids_by_source


def _slide_facts(
    slide: DeckSlide,
    fact_prefix: str,
) -> tuple[list[SourceFact], list[str]]:
    """Build source facts and fact IDs for a single slide."""
    facts: list[SourceFact] = []
    fact_ids: list[str] = []

    text = slide.raw_text or ""
    title = _meaningful_source_title(slide.title)
    if text.strip() and title:
        fact_id = f"{fact_prefix}_title"
        facts.append(
            SourceFact(
                fact_id=fact_id,
                source_type="source_slide",
                source_id=slide.id,
                field="title",
                text=title,
                confidence="high",
                scope="slide",
                source_slide_ids=[slide.id],
            )
        )
        fact_ids.append(fact_id)

        if slide.summary:
            clean_summary = _clean_presentation_text(slide.summary)
            summary_fact_id = f"{fact_prefix}_summary"
            if clean_summary:
                facts.append(
                SourceFact(
                    fact_id=summary_fact_id,
                    source_type="source_slide",
                    source_id=slide.id,
                    field="summary",
                    text=clean_summary,
                    confidence="high",
                    scope="slide",
                    source_slide_ids=[slide.id],
                )
                )
                fact_ids.append(summary_fact_id)

    for block in _ordered_slide_blocks(slide):
        block_text = block.raw_text or ""
        if not block_text.strip():
            continue
        # Tables are emitted as typed header/row units after cross-page repair.
        if block_text.lstrip().startswith("|"):
            continue
        # Native PDF columns must remain distinguishable in the factual lane,
        # not only in the raw source-page lane. Flattening them creates a
        # sentence interleaving unrelated column fragments.
        presentation_text = _clean_presentation_text(block_text, preserve_layout=True)
        if (
            not presentation_text
            or _is_internal_source_instruction(presentation_text)
            or _is_probable_ocr_debris(presentation_text)
        ):
            continue
        block_fact_id = _source_block_fact_id(block_id=block.id, text=block_text)
        facts.append(
            SourceFact(
                fact_id=block_fact_id,
                source_type="source_slide",
                source_id=slide.id,
                field=f"block:{block.id}",
                text=presentation_text,
                confidence="high",
                scope="slide",
                source_slide_ids=[slide.id],
            )
        )
        fact_ids.append(block_fact_id)

    return facts, fact_ids


def _build_brand_snapshot(deck: Deck) -> BrandProfileSnapshot | None:
    """Build a brand profile snapshot from the deck's brand profile."""
    bp = deck.brand_profile
    if bp is None:
        return None
    if not confirmed_website_brand_ready(bp):
        raise ValueError("The confirmed website brand profile is not ready for Instant Deck generation.")

    llm_ctx = build_brand_llm_context(bp)
    tokens = build_brand_design_tokens(bp)
    website_binding = website_brand_binding(bp)

    return BrandProfileSnapshot(
        company_name=bp.company_name,
        visual_direction=bp.visual_direction,
        primary_color=bp.primary_color,
        secondary_color=bp.secondary_color,
        accent_color=bp.accent_color,
        background_color=bp.background_color,
        text_color=bp.text_color,
        palette=llm_ctx.get("palette", []),
        fonts=list(bp.font_candidates_json or []),
        logo_url=bp.logo_url,
        instructions=llm_ctx.get("instructions", []),
        website_source_url=website_binding.get("sourceUrl"),
        website_evidence_sha256=website_binding.get("evidenceSha256"),
        token_provenance=_brand_token_provenance(bp),
    )


def _build_design_tokens(deck: Deck) -> DesignTokens:
    """Build renderer-safe design tokens from the deck's brand profile."""
    raw = build_brand_design_tokens(deck.brand_profile)
    return DesignTokens(
        surface=raw.get("brand.surface", "#070A12"),
        surface_alt=raw.get("brand.surfaceAlt", "#111827"),
        heading=raw.get("brand.heading", "#F8FAFC"),
        body=raw.get("brand.body", "#CBD5E1"),
        accent=raw.get("brand.accent", "#6EE7B7"),
        muted=raw.get("brand.muted", "#64748B"),
        heading_font=raw.get("brand.headingFont", "Inter, sans-serif"),
        body_font=raw.get("brand.bodyFont", "Inter, sans-serif"),
    )


def build_canonical_source_slide(
    slide: DeckSlide,
    index: int,
    fact_prefix: str,
) -> tuple[CanonicalSourceSlide, list[SourceFact]]:
    """Build a canonical source slide from a DeckSlide ORM object."""
    facts, fact_ids = _slide_facts(slide, fact_prefix)

    # Build asset references from slide assets
    images: list[AssetReference] = []
    for asset in getattr(slide, "assets", []) or []:
        images.append(
            AssetReference(
                asset_id=asset.id,
                mime_type=getattr(asset, "mime_type", "") or "",
                alt_text=getattr(asset, "alt_text", "") or getattr(asset, "label", "") or "",
                source_slide_ids=[slide.id],
            )
        )

    return (
        CanonicalSourceSlide(
            id=slide.id,
            index=index,
            slide_number=slide.slide_number or slide.source_page_number or (index + 1),
            title=slide.title or "",
            role=slide.role or "",
            raw_text=slide.raw_text or "",
            summary=slide.summary,
            notes=slide.narrative_notes or None,
            semantic_slide_type=slide.semantic_slide_type,
            blocks=[
                CanonicalSourceBlock(
                    block_id=block.id,
                    block_index=block.block_index,
                    block_type=block.block_type,
                    text=block.raw_text,
                    normalized_text=block.normalized_text,
                )
                for block in _ordered_slide_blocks(slide)
            ],
            tables=_extract_tables_from_text(slide.raw_text or ""),
            charts=[],
            images=images,
            facts=fact_ids,
            provenance=[
                SourceReference(
                    source_slide_id=slide.id,
                    source_type="source_slide",
                    confidence="high",
                )
            ],
        ),
        facts,
    )


def build_instant_deck_generation_context(
    db: Session,
    *,
    deck: Deck,
    selected_slides: list[DeckSlide],
    user_goal: str,
    audience: str | None = None,
    deck_type: str | None = None,
    base_design_version_id: str | None = None,
    validated_baseline: dict[str, Any] | None = None,
    product_knowledge: dict[str, Any] | None = None,
    agent_context: dict[str, Any] | None = None,
    retrieved_guidance: dict[str, Any] | None = None,
    generation_constraints: GenerationConstraints | None = None,
    output_contract: InstantDeckOutputContract | None = None,
) -> InstantDeckGenerationContext:
    """Build the canonical Instant Deck generation context from DB objects.

    This is the single entry point for assembling the complete bounded
    context that the LLM receives for whole-deck generation. Retrieval is
    prepared explicitly by the worker and remains additive to complete source.
    """
    # Build canonical source slides
    all_facts: list[SourceFact] = []
    canonical_slides: list[CanonicalSourceSlide] = []

    for idx, slide in enumerate(selected_slides):
        canonical_slide, slide_facts = build_canonical_source_slide(
            slide, idx, fact_prefix=f"fact_{idx + 1}"
        )
        canonical_slides.append(canonical_slide)
        all_facts.extend(slide_facts)

    table_facts, tables_by_source, table_fact_ids_by_source = _table_facts(selected_slides)
    all_facts.extend(table_facts)
    for canonical_slide in canonical_slides:
        if canonical_slide.id in tables_by_source:
            canonical_slide.tables = tables_by_source[canonical_slide.id]
        canonical_slide.facts.extend(table_fact_ids_by_source.get(canonical_slide.id, []))

    source_document_page_count = getattr(getattr(deck, "file", None), "page_count", None)
    if type(source_document_page_count) is not int or source_document_page_count <= 0:
        source_document_page_count = None

    source_file = getattr(deck, "file", None)
    source_identity = None
    if source_file is not None and getattr(source_file, "checksum_sha256", None):
        source_identity = {"fileId": source_file.id, "sha256": source_file.checksum_sha256,
            "filename": source_file.original_filename or source_file.filename,
            "mimeType": source_file.mime_type, "byteSize": source_file.size}

    source_deck = CanonicalSourceDeck(
        title=deck.title,
        slide_count=len(canonical_slides),
        document_page_count=source_document_page_count,
        source_file_id=getattr(getattr(deck, "file", None), "id", None),
        source_sha256=getattr(getattr(deck, "file", None), "checksum_sha256", None),
        source_document_identity=source_identity,
        slides=canonical_slides,
    )

    # Add deck-level facts
    if deck.audience:
        all_facts.append(
            SourceFact(
                fact_id="fact_deck_audience",
                source_type="deck_metadata",
                source_id=deck.id,
                field="audience",
                text=str(deck.audience).strip(),
                confidence="high",
                scope="deck",
            )
        )
    if deck.purpose:
        all_facts.append(
            SourceFact(
                fact_id="fact_deck_purpose",
                source_type="deck_metadata",
                source_id=deck.id,
                field="purpose",
                text=str(deck.purpose).strip(),
                confidence="high",
                scope="deck",
            )
        )

    # OCR extraction alone does not verify a numerical reading. Preserve source
    # text, but carry uncertainty into the investor numerical authority.
    unverified_ocr_pages = {
        slide.id for slide in selected_slides
        if any('ocr' in str(getattr(block, 'source_kind', '') or '').lower()
               for block in _ordered_slide_blocks(slide))
        and not (getattr(slide, 'metadata_json', None) or {}).get('sourceTextVerified', False)
    }
    all_facts = [fact.model_copy(update={'confidence':'low'})
        if set(fact.source_slide_ids) & unverified_ocr_pages else fact for fact in all_facts]

    resolved_audience, resolved_deck_type = resolve_instant_deck_intent(
        deck=deck,
        selected_slides=selected_slides,
        audience=audience,
        deck_type=deck_type,
        user_goal=user_goal,
    )

    from app.services.llm.investor_public_research import research_for_generation
    return InstantDeckGenerationContext(
        deck_id=deck.id,
        user_goal=user_goal,
        audience=resolved_audience,
        deck_type=resolved_deck_type,
        source_deck=source_deck,
        source_facts=all_facts,
        external_research=research_for_generation(db, deck.id),
        brand_profile=_build_brand_snapshot(deck),
        design_tokens=_build_design_tokens(deck),
        assets=_build_approved_assets(deck, selected_slides),
        product_knowledge=product_knowledge or {},
        agent_context=agent_context or build_compact_instant_deck_agent_context(),
        retrieved_guidance=retrieved_guidance or {
            "schemaVersion": "instant-deck-retrieved-guidance.v1",
            "retrievalStatus": "not_requested",
            "chunkCount": 0,
            "chunks": [],
            "factualAuthority": "canonical_source_only",
        },
        generation_constraints=generation_constraints or GenerationConstraints(),
        output_contract=output_contract or InstantDeckOutputContract(),
        base_design_version_id=base_design_version_id,
        validated_baseline=validated_baseline,
    )


def context_to_grounded_pack(ctx: InstantDeckGenerationContext) -> dict[str, Any]:
    """Convert a typed ``InstantDeckGenerationContext`` to the grounded
    context pack dict that the LLM provider consumes.

    This is the bridge between the typed canonical context and the
    existing ``build_grounded_context_pack`` dict contract. It ensures
    the LLM receives the same structured data but validated through
    typed schemas first.
    """
    # Build source slides in the grounded format
    source_slides = [
        {
            "sourceSlideId": slide.id,
            "ordinal": slide.index,
            "title": slide.title,
            "text": slide.raw_text,
            "blocks": [
                {
                    "blockId": block.block_id,
                    "blockIndex": block.block_index,
                    "type": block.block_type,
                    "text": block.text,
                    "normalizedText": block.normalized_text,
                }
                for block in slide.blocks
            ],
            "tables": [
                {
                    "headers": table.headers,
                    "rows": table.rows,
                }
                for table in slide.tables
            ],
        }
        for slide in ctx.source_deck.slides
    ]

    # Build source facts in the grounded format
    source_facts = [
        {
            "factId": f.fact_id,
            "sourceType": f.source_type,
            "sourceId": f.source_id,
            "field": f.field,
            "text": f.text,
            "confidence": f.confidence,
            "scope": f.scope,
            "sourceSlideIds": f.source_slide_ids,
        }
        for f in ctx.source_facts
    ]

    authoritative_tokens = {
        "brand.surface": (ctx.brand_profile.background_color or "") if ctx.brand_profile else "",
        "brand.surfaceAlt": (ctx.brand_profile.secondary_color or "") if ctx.brand_profile else "",
        "brand.heading": (ctx.brand_profile.text_color or "") if ctx.brand_profile else "",
        "brand.body": (ctx.brand_profile.text_color or "") if ctx.brand_profile else "",
        "brand.accent": (ctx.brand_profile.accent_color or "") if ctx.brand_profile else "",
        "brand.muted": "",
        "brand.headingFont": (
            ctx.design_tokens.heading_font if ctx.brand_profile and ctx.brand_profile.fonts else ""
        ),
        "brand.bodyFont": (
            ctx.design_tokens.body_font if ctx.brand_profile and ctx.brand_profile.fonts else ""
        ),
    }
    brand = build_provider_safe_brand_context(
        ctx.brand_profile,
        neutral_when_absent=True,
        design_tokens=authoritative_tokens,
        preserve_missing_colors=True,
    )
    brand["sourcePriority"] = [
        "manual_or_brand_guidelines",
        "uploaded_deck_identity",
        "confirmed_company_website_enrichment",
        "neutral_fallback_when_brand_absent",
    ]
    brand["identityPolicy"] = (
        "Preserve the strongest available identity evidence. The uploaded deck is not a narrative template, "
        "but its observed logo, colors and fonts remain brand authority unless explicitly overridden."
    )
    if ctx.brand_profile:
        brand["websiteSourceUrl"] = ctx.brand_profile.website_source_url
        brand["websiteEvidenceSha256"] = ctx.brand_profile.website_evidence_sha256
        brand["tokenProvenance"] = {
            key: value.model_dump(exclude_none=True)
            for key, value in ctx.brand_profile.token_provenance.items()
        }

    from app.services.llm.instant_deck_mvp_policy import MVP_POLICY_VERSION, MVP_PURPOSE

    pack: dict[str, Any] = {
        "contractVersion": "grounded-deck-context.v1",
        "deckId": ctx.deck_id,
        "objective": MVP_PURPOSE,
        "userDirection": ctx.user_goal,
        "mvpPolicyVersion": MVP_POLICY_VERSION,
        "audience": ctx.audience,
        "deckType": ctx.deck_type,
        "presentationIntent": "investor_pitch" if ctx.deck_type == "investor_pitch" else "general",
        "sourceDocumentPageCount": ctx.source_deck.document_page_count,
        "sourceSlides": source_slides,
        "sourceFacts": source_facts,
        "metrics": ctx.metrics,
        "metricSets": ctx.metric_sets,
        "approvedAssets": [
            asset.model_dump(by_alias=True, exclude_none=True)
            for asset in ctx.assets
        ],
        "brand": brand,
        "acceptedDecisions": ctx.accepted_decisions,
        "missingInputs": ctx.missing_inputs,
        "conflicts": ctx.conflicts,
        "baseDesignVersionId": ctx.base_design_version_id,
        "sourcePolicy": {"allowAssumptions": False, "requireProvenanceForMaterialMetrics": True},
        "productKnowledge": ctx.product_knowledge,
        "agentContext": ctx.agent_context,
        "retrievedGuidance": ctx.retrieved_guidance,
        "evidenceLanes": {
            "companySource": source_facts,
            "externalResearch": ctx.external_research,
            "vcInference": ctx.vc_strategy,
        },
        "vcStrategy": ctx.vc_strategy,
        "visualIntelligence": ctx.visual_intelligence,
    }
    from app.core.config import settings
    if settings.instant_html_llm_first_beta:
        from app.services.llm.instant_factual_review import POLICY, require_review_allowance
        pack.update({
            "factualReviewPolicy": POLICY,
            "factualReviewHandoffPolicy": "inert-source-reference-handoff.v1",
            "factualReviewResolutionPolicy": "explicit-source-uncertainty.v1",
            "factualReviewAllowance": {
                "enabled": settings.instant_html_factual_review_enabled,
                "maxRequests": 2,
                "maxCostCents": settings.instant_html_factual_review_max_cost_cents,
            },
            "betaSourceDocument": {"fileId": ctx.source_deck.source_file_id, "sha256": ctx.source_deck.source_sha256},
            "audience": "VC and investor audience",
            "objective": "Redesign the complete uploaded deck for investors, preserving company facts and numerical meaning. Improve narrative, order, copy and visual composition; do not invent missing evidence or a funding request.",
            # Generic composition policy: VC purpose does not impose section
            # families, a funding ask, palette quotas or a fixed slide count.
            "presentationIntent": "general",
        })
        require_review_allowance(pack)
        # The AI-VC beta consumes verified research and the persisted strategy
        # before design. Neither lane changes canonical company source facts.
        pack["externalResearch"] = ctx.external_research
        from app.services.llm.investor_public_research import compiler_research_facts
        pack["sourceFacts"] = [*pack["sourceFacts"], *compiler_research_facts(ctx.external_research)]
    if ctx.validated_baseline is not None:
        pack["validatedBaseline"] = ctx.validated_baseline

    if not settings.instant_html_llm_first_beta and ctx.source_deck.source_document_identity is not None:
        from app.instant_deck_spec.production_source import planner_context
        from app.instant_deck_spec.production_planner import creative_schema
        from app.instant_deck_spec.source_package_v2 import NormalizedSourcePackageV2
        pack["externalResearch"] = ctx.external_research
        pack["sourceDocumentIdentity"] = ctx.source_deck.source_document_identity
        pack["mvpPlanner"] = planner_context(pack)
        package = NormalizedSourcePackageV2.model_validate_json(json.dumps(pack["mvpPlanner"]["sourcePackage"]))
        pack["mvpPlanner"]["creativeSchema"] = creative_schema(package, pack.get("externalResearch"))

    # Derive the source coverage catalog and claim catalog from the pack.
    # These are the same derivations that build_grounded_context_pack does,
    # but computed here so the typed path produces the same contract.
    from app.services.llm.full_html_generation_service import (
        _fact_catalog,
        _fact_traceability,
        _metric_traceability,
        _required_source_coverage_catalog,
    )

    # Validate provenance first (raises on broken traceability)
    _fact_traceability(pack)
    _metric_traceability(pack)
    pack["claimCatalog"] = _fact_catalog(pack)
    pack["requiredSourceCoverage"] = _required_source_coverage_catalog(pack)

    return pack


# ---------------------------------------------------------------------------
# Hash computation for DesignVersion provenance
# ---------------------------------------------------------------------------


def compute_context_hash(ctx: InstantDeckGenerationContext) -> str:
    """Compute a deterministic SHA-256 hash of the canonical generation context.

    This hash is stored on the DesignVersion so the product state is
    traceable back to the exact inputs that produced it.
    """
    import hashlib
    import json

    # Use the grounded pack form for hashing since it's the canonical
    # representation that the LLM consumed.
    pack = context_to_grounded_pack(ctx)
    canonical = json.dumps(pack, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_transformation_plan_hash(plan_dict: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of a transformation plan.

    This hash is stored on the DesignVersion so the product state is
    traceable back to the exact transformation plan that produced it.
    """
    import hashlib
    import json

    canonical = json.dumps(plan_dict, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def persist_design_version_provenance(
    *,
    design_version: Any,
    context_hash: str | None = None,
    transformation_plan_hash: str | None = None,
    validation_report: dict[str, Any] | None = None,
    repair_history: list[dict[str, Any]] | None = None,
) -> None:
    """Attach canonical provenance fields to a DesignVersion.

    This is called after DesignVersion creation to record the exact
    inputs and validation state that produced the version.
    """
    if context_hash:
        design_version.generation_context_hash = context_hash
    if transformation_plan_hash:
        design_version.transformation_plan_hash = transformation_plan_hash
    if validation_report:
        design_version.validation_report_json = validation_report
    if repair_history:
        design_version.repair_history_json = repair_history
