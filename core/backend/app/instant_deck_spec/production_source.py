"""Adapt the immutable production source catalog to recovered Source Package v2.

Aliases are application-owned and retain an exact reverse map to canonical facts,
source slides and approved asset bytes. No retrieval or provider calls occur here.
"""
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import base64
import json
import re

from PIL import Image
from .models import (BrandRoleRecord, SourceReference, SourceFactRecord,
    SourceClaimRecord, SourceNumberRecord, SourceSlideRecord, SourceFileIdentity,
    SourceEmbeddingPolicy)
from .source_package import _number_unit, _fact_kind
from .numerical_fidelity import NUMBER as _NUMBER
from .source_package_v2 import (NormalizedSourcePackageV2, SourceBackedBrandMetadataV2,
    SourceAssetRecordV2, AssetSemanticRole, _material_fact, _protect_material_facts,
    _protected_coverage)
from .planner_v4_2 import build_deterministic_envelope_v4_2


def source_package_from_context(context: dict) -> tuple[NormalizedSourcePackageV2, dict]:
    identity = context["sourceDocumentIdentity"]
    checksum = identity["sha256"]
    source_rows = context["sourceSlides"]
    positions = {row["sourceSlideId"]: i for i, row in enumerate(source_rows, 1)}
    source_aliases = {key: f"src_s{i:02d}" for key, i in positions.items()}
    references = [SourceReference(reference_id=f"ref_s{i:02d}_slide",
        source_slide_id=f"src_s{i:02d}", kind="slide") for i in positions.values()]
    counts = defaultdict(int)
    facts, claims, numbers, assets = [], [], [], []
    canonical, evidence_sources, assets_map = {}, {}, {}
    for fact in context["sourceFacts"]:
        source_ids = fact.get("sourceSlideIds") or []
        if not source_ids:  # Deck metadata is not source evidence.
            continue
        if not set(source_ids) <= set(positions):
            raise ValueError("Planner fact references an unselected source")
        ordinal = min(positions[s] for s in source_ids)
        counts[ordinal] += 1
        index = counts[ordinal]
        refs = []
        for source in source_ids:
            # Reference grammar permits two digits; keep IDs local to each page.
            ref = f"ref_s{positions[source]:02d}_b{sum(r.source_slide_id == source_aliases[source] and r.kind == 'block' for r in references):02d}"
            references.append(SourceReference(reference_id=ref, source_slide_id=source_aliases[source],
                kind="block", block_index=index, quoted_text=fact["text"]))
            refs.append(ref)
        fid, cid = f"fact_s{ordinal:02d}_{index:02d}", f"claim_s{ordinal:02d}_{index:02d}"
        facts.append(SourceFactRecord(fact_id=fid, text=fact["text"],
            kind=_fact_kind(slide_position=ordinal, block_type="body", text=fact["text"]), source_reference_ids=refs))
        claims.append(SourceClaimRecord(claim_id=cid, text=fact["text"], fact_ids=[fid], source_reference_ids=refs))
        for alias in [fid, cid]:
            canonical[alias] = [fact["factId"]]
            evidence_sources[alias] = source_ids
        for match in _NUMBER.finditer(fact["text"]) if fact.get("confidence", "high") == "high" else []:
            value = match.group(0).strip()
            if not value:
                continue
            nid = f"num_s{ordinal:02d}_{sum(n.number_id.startswith(f'num_s{ordinal:02d}_') for n in numbers):02d}"
            numbers.append(SourceNumberRecord(number_id=nid, exact_text=value,
                normalized_value=None, unit=_number_unit(value),
                qualifier="source-exact; classification requires local evidence", source_reference_ids=refs[:4]))
            canonical[nid] = [fact["factId"]]
            evidence_sources[nid] = source_ids
    role_map = {"logo": AssetSemanticRole.LITERAL_LOGO, "brand_logo": AssetSemanticRole.LITERAL_LOGO,
                "wordmark": AssetSemanticRole.WORDMARK, "founder_portrait": AssetSemanticRole.FOUNDER_PORTRAIT}
    for raw in context.get("approvedAssets", []):
        sources = raw.get("sourceSlideIds") or []
        if not sources or not set(sources) <= set(positions):
            continue
        uri = raw.get("resolvedDataUrl", "")
        header, encoded = uri.split(",", 1)
        if header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"}:
            raise ValueError("Unsupported approved asset encoding")
        payload = base64.b64decode(encoded, validate=True)
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
        ordinal = min(positions[s] for s in sources)
        aid = f"asset_s{ordinal:02d}_{len(assets)+1:02d}"
        ref = f"ref_s{ordinal:02d}_a{len(assets)+1:02d}"
        references.append(SourceReference(reference_id=ref, source_slide_id=f"src_s{ordinal:02d}", kind="asset"))
        role = role_map.get(raw.get("role"), AssetSemanticRole.EVIDENCE_IMAGE)
        assets.append(SourceAssetRecordV2(asset_id=aid, semantic_role=role, role_confidence=1.0,
            role_reasons=("Persisted approved source asset; no identity inferred from neighbouring text",),
            acquisition="embedded_raster", mime_type=header[5:-7], byte_sha256=sha256(payload).hexdigest(),
            width=width, height=height, alt_text=raw.get("altText") or "Source image",
            source_document_sha256=checksum, source_page=ordinal, source_region=None,
            source_region_sha256=None, source_reference_ids=(ref,), derived_from_asset_id=None,
            required_for_planner=role in {AssetSemanticRole.LITERAL_LOGO, AssetSemanticRole.WORDMARK}))
        assets_map[aid] = raw["assetId"]
    slides = []
    for i, row in enumerate(source_rows, 1):
        source = row["sourceSlideId"]
        slides.append(SourceSlideRecord(source_slide_id=f"src_s{i:02d}", position=i, source_page_number=i,
            title=row.get("title") or "", normalized_text=row.get("text") or "",
            fact_ids=[f.fact_id for f in facts if source in evidence_sources[f.fact_id]],
            claim_ids=[f.claim_id for f in claims if source in evidence_sources[f.claim_id]],
            number_ids=[n.number_id for n in numbers if source in evidence_sources[n.number_id]],
            asset_ids=[a.asset_id for a in assets if a.source_page == i]))
    roles = []
    # Neutral product tokens are labelled as defaults, never as observed branding.
    for name, color in [("paper", "#F8FAFC"), ("ink", "#0F172A"), ("signature", "#2563EB")]:
        roles.append(BrandRoleRecord(role_id="brand_" + name, colour=color,
            provenance="product_default", source_reference_ids=[]))
    brand = context.get("brand") or {}
    # Only provenance-backed observed tokens override product fallbacks.
    tokens = brand.get("tokens") or {}
    provenance = brand.get("tokenProvenance") or {}
    for i, key in enumerate(["brand.surface", "brand.body", "brand.accent"]):
        value = tokens.get(key)
        evidence_key = ["colors.background", "colors.text", "colors.accent"][i]
        token_evidence = provenance.get(evidence_key, {})
        refs = list(positions) if token_evidence.get("classification") in {"confirmed", "source-extracted"} and token_evidence.get("source") not in {None, "unrecorded"} else []
        if re.fullmatch(r"#[0-9a-fA-F]{6}", str(value or "")) and refs and set(refs) <= set(positions):
            roles[i] = BrandRoleRecord(role_id=roles[i].role_id, colour=value,
                provenance="source_observed", source_reference_ids=[f"ref_s{positions[s]:02d}_slide" for s in refs])
    company = brand.get("companyName") if (provenance.get("companyName") or {}).get("classification") in {"confirmed", "source-extracted"} else None
    first_ref = tuple(r.reference_id for r in references if r.kind == "slide")[:8] if company else ()
    brand_record = SourceBackedBrandMetadataV2(organization_name=company,
        organization_source_reference_ids=first_ref, product_candidate=None,
        product_source_reference_ids=(), audience_candidate=None,
        audience_source_reference_ids=(), deck_type_candidate=None,
        deck_type_source_reference_ids=(), roles=tuple(roles),
        wordmark_asset_id=next((a.asset_id for a in assets if a.semantic_role == AssetSemanticRole.WORDMARK), None),
        literal_logo_asset_id=next((a.asset_id for a in assets if a.semantic_role == AssetSemanticRole.LITERAL_LOGO), None),
        brand_symbol_asset_ids=())
    material, selected = _protect_material_facts(tuple(_material_fact(f,
        number_reference_ids={r for n in numbers for r in n.source_reference_ids}) for f in facts))
    coverage = _protected_coverage(material, tuple(numbers), tuple(references), selected)
    package = NormalizedSourcePackageV2(package_id="srcpkgv2_" + checksum[:16], source_checksum=checksum,
        source_package_v1_sha256=None,
        production_context_sha256=sha256(json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest(),
        source_file=SourceFileIdentity(filename=identity["filename"], mime_type=identity["mimeType"],
            byte_size=identity["byteSize"], page_count=len(source_rows), extraction_id=identity["fileId"],
            extractor_version="canonical-production-source.v1"), source_slides=tuple(slides), source_references=tuple(references),
        facts=material, claims=tuple(claims), numbers=tuple(numbers), assets=tuple(assets), brand=brand_record,
        protected_coverage=coverage, debris_exclusions=(), missing_evidence=(), conflicts=(), embedding_policy=SourceEmbeddingPolicy())
    return package, {"evidence": canonical, "assets": assets_map,
                     "slides": {alias: original for original, alias in source_aliases.items()}}


def planner_context(context: dict) -> dict:
    package, aliases = source_package_from_context(context)
    envelope = build_deterministic_envelope_v4_2(package, require_investment_close=False)
    review_gaps = [{"factId": f["factId"], "sourceSlideIds": f.get("sourceSlideIds", []),
        "reason":"Source numerical evidence requires verification; do not guess"}
        for f in context["sourceFacts"] if f.get("confidence", "high") != "high" and _NUMBER.search(f["text"])]
    return {"numericalReviewGaps": review_gaps, "sourcePackage": package.model_dump(mode="json"),
            "applicationEnvelope": envelope.model_dump(mode="json"), "aliases": aliases,
            "metricContextPolicy": "complete-source-notes.v1",
            "numericalPresentationPolicy": "source-linked-labels.v1"}
