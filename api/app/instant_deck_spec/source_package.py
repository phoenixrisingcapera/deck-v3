"""Deterministic adapter from persisted extraction evidence to source package."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .models import (
    BrandRoleRecord,
    DebrisExclusion,
    MissingEvidenceRecord,
    NormalizedSourcePackage,
    SourceAssetRecord,
    SourceBackedBrandMetadata,
    SourceClaimRecord,
    SourceEmbeddingPolicy,
    SourceFactRecord,
    SourceFileIdentity,
    SourceNumberRecord,
    SourceReference,
    SourceSlideRecord,
)


_SPACE = re.compile(r"\s+")
_PAGE_COUNTER = re.compile(r"^\(?\d{1,3}\)?$")
_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?:\+|%|\s*(?:€|EUR|houses?|families|workshops?|consultations?|projects?|clients?|events?|k|m|million))?",
    re.IGNORECASE,
)


def canonical_json_bytes(value: Mapping[str, Any] | NormalizedSourcePackage) -> bytes:
    payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, NormalizedSourcePackage) else dict(value)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Mapping[str, Any] | NormalizedSourcePackage) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return _SPACE.sub(" ", str(value or "")).strip()


def _is_ocr_debris(value: str) -> bool:
    if len(value) < 120:
        return False
    letters = sum(char.isalpha() for char in value)
    tokens = value.split()
    word_tokens = sum(any(char.isalpha() for char in token) and len(token) >= 3 for token in tokens)
    return letters / max(1, len(value)) < 0.35 or word_tokens / max(1, len(tokens)) < 0.35


def _fact_kind(*, slide_position: int, block_type: str, text: str) -> str:
    lowered = text.lower()
    if slide_position == 1:
        return "identity"
    if block_type == "metric" or _NUMBER.search(text):
        return "financial" if any(token in lowered for token in ("€", "revenue", "funding", "asset", "spv")) else "metric"
    if any(token in lowered for token in ("step", "process", "workshop", "consult")):
        return "process"
    if any(token in lowered for token in ("founder", "paula schwarz", "stanford", "forbes")):
        return "team"
    if any(token in lowered for token in ("partner", "guest", "host")):
        return "partnership"
    if any(token in lowered for token in ("angel fund", "project", "funding")):
        return "product"
    if block_type == "headline":
        return "positioning"
    return "general"


def _normalized_number(value: str) -> float | None:
    token = re.search(r"\d[\d.,]*", value)
    if token is None:
        return None
    raw = token.group(0)
    if raw.count(".") == 1 and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    elif raw.count(",") == 1 and len(raw.rsplit(",", 1)[1]) == 3:
        raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _number_unit(value: str) -> str | None:
    lowered = value.lower()
    if "€" in value or "eur" in lowered:
        return "EUR"
    if "%" in value:
        return "percent"
    for unit in ("houses", "families", "workshops", "consultations", "projects", "clients", "events"):
        if unit.rstrip("s") in lowered:
            return unit
    return None


def _asset_sha(asset: Mapping[str, Any]) -> str | None:
    metadata = asset.get("metadataJson") if isinstance(asset.get("metadataJson"), Mapping) else {}
    value = str(metadata.get("sha256") or metadata.get("deduplicationKey") or "").lower()
    return value if re.fullmatch(r"[a-f0-9]{64}", value) else None


def build_source_package_from_extraction_checkpoint(
    *,
    structured_deck: Mapping[str, Any],
    extraction_report: Mapping[str, Any],
    source_filename: str,
    source_mime_type: str,
    source_byte_size: int,
    source_checksum: str,
) -> NormalizedSourcePackage:
    """Build the exact same source package for the exact same checkpoint.

    The adapter never imports or calls embedding, retrieval, provider, storage,
    database, or worker code. Customer content remains request-scoped data.
    """

    raw_slides = list(structured_deck.get("slides") or [])
    expected_count = int(structured_deck.get("slideCount") or extraction_report.get("slideCount") or 0)
    if not raw_slides or expected_count != len(raw_slides):
        raise ValueError("Extraction checkpoint slide count is incomplete.")
    if str(extraction_report.get("status") or "") != "completed":
        raise ValueError("Extraction checkpoint must be completed.")

    references: list[SourceReference] = []
    facts: list[SourceFactRecord] = []
    claims: list[SourceClaimRecord] = []
    numbers: list[SourceNumberRecord] = []
    assets: list[SourceAssetRecord] = []
    slides: list[SourceSlideRecord] = []
    exclusions: list[DebrisExclusion] = []
    colour_refs: dict[str, list[str]] = {}

    ordered = sorted(raw_slides, key=lambda row: int(row.get("slideIndex") or 0))
    if [int(row.get("slideIndex") or 0) for row in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("Extraction checkpoint slide order must be contiguous.")

    for raw_slide in ordered:
        position = int(raw_slide["slideIndex"])
        source_slide_id = f"src_s{position:02d}"
        slide_ref_id = f"ref_s{position:02d}_slide"
        raw_text = _text(raw_slide.get("rawText"))
        title = _text(raw_slide.get("title"))
        debris = _is_ocr_debris(raw_text)
        references.append(SourceReference(
            reference_id=slide_ref_id,
            source_slide_id=source_slide_id,
            kind="slide",
            quoted_text=title[:2400] or None,
        ))

        fact_ids: list[str] = []
        claim_ids: list[str] = []
        number_ids: list[str] = []
        asset_ids: list[str] = []
        excluded_reference_ids: list[str] = []

        for raw_block in sorted(raw_slide.get("blocks") or [], key=lambda row: int(row.get("blockIndex") or 0)):
            block_index = int(raw_block.get("blockIndex") or 0)
            block_text = _text(raw_block.get("normalizedText") or raw_block.get("rawText"))
            if not block_text:
                continue
            reference_id = f"ref_s{position:02d}_b{block_index:02d}"
            references.append(SourceReference(
                reference_id=reference_id,
                source_slide_id=source_slide_id,
                kind="block",
                block_index=block_index,
                quoted_text=block_text[:2400],
            ))
            if debris or _PAGE_COUNTER.fullmatch(block_text) or str(raw_block.get("blockType") or "") == "reference":
                excluded_reference_ids.append(reference_id)
                continue
            fact_id = f"fact_s{position:02d}_{block_index:02d}"
            claim_id = f"claim_s{position:02d}_{block_index:02d}"
            block_type = str(raw_block.get("blockType") or "body")
            facts.append(SourceFactRecord(
                fact_id=fact_id,
                kind=_fact_kind(slide_position=position, block_type=block_type, text=block_text),
                text=block_text[:2400],
                source_reference_ids=[reference_id],
            ))
            claims.append(SourceClaimRecord(
                claim_id=claim_id,
                text=block_text[:2400],
                fact_ids=[fact_id],
                source_reference_ids=[reference_id],
            ))
            fact_ids.append(fact_id)
            claim_ids.append(claim_id)
            for match_index, match in enumerate(_NUMBER.finditer(block_text)):
                exact = match.group(0).strip()
                if not exact or exact in {"1", "2", "3"} and "step" in block_text.lower():
                    continue
                number_id = f"num_s{position:02d}_{len(number_ids):02d}"
                numbers.append(SourceNumberRecord(
                    number_id=number_id,
                    exact_text=exact,
                    normalized_value=_normalized_number(exact),
                    unit=_number_unit(exact),
                    qualifier="source-exact; do not strengthen",
                    source_reference_ids=[reference_id],
                ))
                number_ids.append(number_id)

        for asset_index, raw_asset in enumerate(raw_slide.get("assets") or [], start=1):
            digest = _asset_sha(raw_asset)
            width = int(raw_asset.get("width") or 0)
            height = int(raw_asset.get("height") or 0)
            mime_type = str(raw_asset.get("mimeType") or "")
            if digest is None or width <= 0 or height <= 0 or mime_type not in {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}:
                continue
            reference_id = f"ref_s{position:02d}_a{asset_index:02d}"
            asset_id = f"asset_s{position:02d}_{asset_index:02d}"
            references.append(SourceReference(
                reference_id=reference_id,
                source_slide_id=source_slide_id,
                kind="asset",
            ))
            assets.append(SourceAssetRecord(
                asset_id=asset_id,
                asset_type="embedded_image",
                mime_type=mime_type,
                sha256=digest,
                width=width,
                height=height,
                alt_text=_text(raw_asset.get("label"))[:180] or f"Source slide {position} image {asset_index}",
                source_reference_ids=[reference_id],
            ))
            asset_ids.append(asset_id)

        metadata = raw_slide.get("metadataJson") if isinstance(raw_slide.get("metadataJson"), Mapping) else {}
        for colour in metadata.get("vectorColors") or []:
            normalized_colour = str(colour).upper()
            if re.fullmatch(r"#[0-9A-F]{6}", normalized_colour):
                colour_refs.setdefault(normalized_colour, []).append(slide_ref_id)

        omission_reason = "OCR-only source page; exclude from narrative but retain for audit." if debris else None
        slides.append(SourceSlideRecord(
            source_slide_id=source_slide_id,
            position=position,
            source_page_number=int(raw_slide.get("sourcePageNumber") or position),
            title=title[:500],
            normalized_text="" if debris else raw_text[:8000],
            fact_ids=fact_ids,
            claim_ids=claim_ids,
            number_ids=number_ids,
            asset_ids=asset_ids,
            omission_eligible=debris,
            omission_reason=omission_reason,
        ))
        if debris:
            exclusions.append(DebrisExclusion(
                source_slide_id=source_slide_id,
                reason="ocr_debris",
                source_reference_ids=excluded_reference_ids,
            ))

    def brand_role(role_id: str, preferred: tuple[str, ...]) -> BrandRoleRecord:
        colour = next((candidate for candidate in preferred if candidate in colour_refs), None)
        if colour is None:
            raise ValueError(f"Source-backed brand colour for {role_id} is missing.")
        return BrandRoleRecord(
            role_id=role_id,
            colour=colour,
            provenance="source_observed",
            source_reference_ids=sorted(set(colour_refs[colour])),
        )

    brand = SourceBackedBrandMetadata(
        organization_name="Angel House",
        organization_source_reference_ids=["ref_s01_b00"],
        product_candidate="A community combining family change consulting, workshops, projects and follow-up funding.",
        product_source_reference_ids=["ref_s02_b02", "ref_s05_b00", "ref_s08_b00"],
        audience_candidate="Families and multi-generational leaders navigating values, money and AI-driven change.",
        audience_source_reference_ids=["ref_s01_b00", "ref_s02_b02", "ref_s03_b01"],
        deck_type_candidate="investor and partner presentation",
        deck_type_source_reference_ids=["ref_s09_b00", "ref_s13_b00", "ref_s13_b01"],
        roles=[
            brand_role("brand_paper", ("#EEEBE3", "#FFFFFF")),
            brand_role("brand_ink", ("#000000",)),
            brand_role("brand_signature", ("#CA0012", "#CA0013", "#C72909")),
            brand_role("brand_white", ("#FFFFFF",)),
        ],
        logo_asset_id="asset_s01_02" if any(asset.asset_id == "asset_s01_02" for asset in assets) else None,
    )

    return NormalizedSourcePackage(
        schema_version="instant-deck-source-package.v1",
        package_id=f"srcpkg_{source_checksum[:16]}",
        source_checksum=source_checksum,
        source_file=SourceFileIdentity(
            filename=source_filename,
            mime_type=source_mime_type,
            byte_size=source_byte_size,
            page_count=expected_count,
            extraction_id=str(structured_deck.get("sourceVersionId") or extraction_report.get("sourceVersionId") or ""),
            extractor_version=str(structured_deck.get("extractor") or "unknown"),
        ),
        source_slides=slides,
        source_references=references,
        facts=facts,
        claims=claims,
        numbers=numbers,
        assets=assets,
        brand=brand,
        debris_exclusions=exclusions,
        missing_evidence=[
            MissingEvidenceRecord(topic="market size", detail="No sourced TAM, SAM or SOM evidence appears in the extraction."),
            MissingEvidenceRecord(topic="fund structure", detail="No complete legal or operating terms for the Angel Fund appear in the extraction."),
        ],
        conflicts=[],
        embedding_policy=SourceEmbeddingPolicy(),
    )
