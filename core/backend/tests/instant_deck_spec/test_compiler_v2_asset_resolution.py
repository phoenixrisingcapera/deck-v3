from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from io import BytesIO
import socket

import fitz
from PIL import Image, ImageDraw
from pydantic import ValidationError
import pytest

from app.instant_deck_spec.asset_resolution_v2 import (
    AssetResolutionError,
    ExtractedSourceAssetV2,
    FocalPointV2,
    NormalizedCropBoxV2,
    ResolvedAssetBundleV2,
    SourceAssetByteCatalogV2,
    TypographyPlanV2,
    _contain,
    _cover,
    _validated_image,
    extract_source_asset_catalog_v2,
    resolve_source_assets_v2,
    validate_asset_request_ids_v2,
)
from app.instant_deck_spec.chromium import validate_compiled_deck_in_chromium
from app.instant_deck_spec.compiler import compile_deck_spec
from app.instant_deck_spec.compiler_v2 import compile_deck_spec_v2
from app.instant_deck_spec.models import (
    CompositionVariant,
    DeckSpec,
    NormalizedSourcePackage,
    SlideArchetype,
    VisualType,
)
from app.instant_deck_spec.publication import OfflinePublicationRejected, build_publication_candidate


@dataclass(frozen=True, slots=True)
class SyntheticAssetUse:
    asset_ref: str
    role: str
    treatment: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SyntheticPlannerSlide:
    archetype: str
    asset_use: SyntheticAssetUse | None = None


@dataclass(frozen=True, slots=True)
class SyntheticPlanner:
    slides: tuple[SyntheticPlannerSlide, ...]


@dataclass(frozen=True, slots=True)
class SyntheticContext:
    pdf_bytes: bytes
    package: NormalizedSourcePackage
    spec: DeckSpec
    planner: SyntheticPlanner
    catalog: SourceAssetByteCatalogV2
    typography: TypographyPlanV2


def _image_bytes(*, portrait: bool) -> bytes:
    size = (360, 540) if portrait else (480, 240)
    mode = "RGB" if portrait else "RGBA"
    background = (237, 224, 194) if portrait else (0, 0, 0, 0)
    image = Image.new(mode, size, background)
    draw = ImageDraw.Draw(image)
    if portrait:
        draw.ellipse((108, 54, 252, 198), fill=(26, 46, 65))
        draw.rounded_rectangle((72, 180, 288, 504), radius=54, fill=(58, 104, 125))
    else:
        draw.polygon(((42, 132), (126, 50), (210, 132)), fill=(201, 66, 62, 255))
        draw.rectangle((70, 126, 182, 210), fill=(26, 46, 65, 255))
        draw.rectangle((250, 82, 432, 158), fill=(201, 66, 62, 255))
    output = BytesIO()
    if portrait:
        image.save(output, format="JPEG", quality=91, optimize=False, progressive=False)
    else:
        image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _source_pdf_bytes() -> bytes:
    logo = _image_bytes(portrait=False)
    portrait = _image_bytes(portrait=True)
    document = fitz.open()
    for page_number in range(1, 7):
        page = document.new_page(width=1280, height=720)
        page.insert_text(
            (72, 80),
            f"Synthetic product evidence page {page_number}",
            fontsize=24,
            color=(0.1, 0.18, 0.25),
        )
        if page_number == 1:
            page.insert_image(fitz.Rect(72, 160, 552, 400), stream=logo)
        if page_number == 6:
            page.insert_image(fitz.Rect(760, 110, 1120, 650), stream=portrait)
    payload = document.tobytes(garbage=4, deflate=True, clean=True)
    document.close()
    return payload


def _page_image(pdf_bytes: bytes, page_number: int) -> tuple[bytes, str, int, int]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        images = document[page_number - 1].get_images(full=True)
        assert len(images) == 1
        payload = document.extract_image(images[0][0])
        extension = str(payload["ext"]).casefold()
        mime = "image/png" if extension == "png" else "image/jpeg"
        return bytes(payload["image"]), mime, int(payload["width"]), int(payload["height"])
    finally:
        document.close()


def _visual_payload(
    visual_type: str,
    *,
    items: list[dict] | None = None,
    edges: list[dict] | None = None,
    metrics: list[dict] | None = None,
    steps: list[dict] | None = None,
) -> dict:
    return {
        "type": VisualType(visual_type),
        "narrative_function": "Make the synthetic source evidence presentation-scale.",
        "title": None,
        "asset_ref": None,
        "items": items or [],
        "edges": edges or [],
        "metrics": metrics or [],
        "series": [],
        "steps": steps or [],
        "people": [],
        "quotes": [],
    }


def _composition(
    primitive: str,
    variant: str,
    *,
    density: str,
    alignment: str = "left",
) -> dict:
    return {
        "primitive": SlideArchetype(primitive),
        "variant": CompositionVariant(variant),
        "background_role": "brand_paper",
        "accent_role": "brand_signal",
        "density": density,
        "focal_alignment": alignment,
        "visual_weight": 0.7,
        "maximum_text_area": 0.5,
    }


def _slide(
    position: int,
    archetype: str,
    headline: str,
    evidence: str,
    visual: dict,
    composition: dict,
    *,
    asset_refs: list[str] | None = None,
) -> dict:
    return {
        "slide_id": f"s{position:02d}",
        "position": position,
        "archetype": SlideArchetype(archetype),
        "purpose": "Present one source-backed part of the synthetic narrative.",
        "headline": headline,
        "subhead": "Deterministic evidence, bounded composition, and local source assets.",
        "copy_blocks": [],
        "evidence_refs": [evidence],
        "source_slide_ids": [f"src_s{position:02d}"],
        "omitted_source_slide_ids": [],
        "asset_refs": asset_refs or [],
        "composition": composition,
        "visual": visual,
    }


def _build_context() -> SyntheticContext:
    pdf_bytes = _source_pdf_bytes()
    source_hash = sha256(pdf_bytes).hexdigest()
    logo, logo_mime, logo_width, logo_height = _page_image(pdf_bytes, 1)
    portrait, portrait_mime, portrait_width, portrait_height = _page_image(pdf_bytes, 6)
    source_ids = [f"src_s{index:02d}" for index in range(1, 7)]
    slide_refs = [f"ref_s{index:02d}_slide" for index in range(1, 7)]
    facts = [f"fact_s{index:02d}_01" for index in range(1, 7)]
    claims = [f"claim_s{index:02d}_01" for index in range(1, 7)]
    package = NormalizedSourcePackage.model_validate(
        {
            "schema_version": "instant-deck-source-package.v1",
            "package_id": f"srcpkg_{source_hash[:16]}",
            "source_checksum": source_hash,
            "source_file": {
                "filename": "synthetic-product-owned-fixture.pdf",
                "mime_type": "application/pdf",
                "byte_size": len(pdf_bytes),
                "page_count": 6,
                "extraction_id": "synthetic_asset_contract_v2",
                "extractor_version": "synthetic-fixture.v1",
            },
            "source_slides": [
                {
                    "source_slide_id": source_ids[index],
                    "position": index + 1,
                    "source_page_number": index + 1,
                    "title": f"Synthetic evidence {index + 1}",
                    "normalized_text": f"Synthetic source statement {index + 1}.",
                    "fact_ids": [facts[index]],
                    "claim_ids": [claims[index]],
                    "number_ids": ["num_s05_01"] if index == 4 else [],
                    "asset_ids": (
                        ["asset_s01_01"] if index == 0 else ["asset_s06_01"] if index == 5 else []
                    ),
                    "omission_eligible": False,
                    "omission_reason": None,
                }
                for index in range(6)
            ],
            "source_references": [
                *[
                    {
                        "reference_id": slide_refs[index],
                        "source_slide_id": source_ids[index],
                        "kind": "slide",
                        "block_index": None,
                        "quoted_text": f"Synthetic source statement {index + 1}.",
                    }
                    for index in range(6)
                ],
                {
                    "reference_id": "ref_s01_a01",
                    "source_slide_id": "src_s01",
                    "kind": "asset",
                    "block_index": None,
                    "quoted_text": None,
                },
                {
                    "reference_id": "ref_s06_a01",
                    "source_slide_id": "src_s06",
                    "kind": "asset",
                    "block_index": None,
                    "quoted_text": None,
                },
            ],
            "facts": [
                {
                    "fact_id": facts[index],
                    "kind": "metric" if index == 4 else "general",
                    "text": f"Synthetic verified fact {index + 1}.",
                    "material": True,
                    "source_reference_ids": [slide_refs[index]],
                }
                for index in range(6)
            ],
            "claims": [
                {
                    "claim_id": claims[index],
                    "text": f"Synthetic grounded claim {index + 1}.",
                    "fact_ids": [facts[index]],
                    "source_reference_ids": [slide_refs[index]],
                    "material": True,
                }
                for index in range(6)
            ],
            "numbers": [
                {
                    "number_id": "num_s05_01",
                    "exact_text": "42",
                    "normalized_value": 42.0,
                    "unit": "verified runs",
                    "qualifier": "synthetic product-owned fixture",
                    "source_reference_ids": ["ref_s05_slide"],
                }
            ],
            "assets": [
                {
                    "asset_id": "asset_s01_01",
                    "asset_type": "logo",
                    "mime_type": logo_mime,
                    "sha256": sha256(logo).hexdigest(),
                    "width": logo_width,
                    "height": logo_height,
                    "alt_text": "Synthetic product-owned geometric brand mark",
                    "source_reference_ids": ["ref_s01_a01"],
                },
                {
                    "asset_id": "asset_s06_01",
                    "asset_type": "portrait",
                    "mime_type": portrait_mime,
                    "sha256": sha256(portrait).hexdigest(),
                    "width": portrait_width,
                    "height": portrait_height,
                    "alt_text": "Synthetic product-owned portrait illustration",
                    "source_reference_ids": ["ref_s06_a01"],
                },
            ],
            "brand": {
                "organization_name": "Synthetic Product Lab",
                "organization_source_reference_ids": ["ref_s01_slide"],
                "product_candidate": "A deterministic source-bound compilation system.",
                "product_source_reference_ids": ["ref_s02_slide"],
                "audience_candidate": "Engineering and product reviewers",
                "audience_source_reference_ids": ["ref_s03_slide"],
                "deck_type_candidate": "Technical product narrative",
                "deck_type_source_reference_ids": ["ref_s01_slide"],
                "roles": [
                    {
                        "role_id": "brand_paper",
                        "colour": "#F4E9D4",
                        "provenance": "source_confirmed",
                        "source_reference_ids": ["ref_s01_slide"],
                    },
                    {
                        "role_id": "brand_ink",
                        "colour": "#1A2E41",
                        "provenance": "source_confirmed",
                        "source_reference_ids": ["ref_s01_slide"],
                    },
                    {
                        "role_id": "brand_signal",
                        "colour": "#C9423E",
                        "provenance": "source_confirmed",
                        "source_reference_ids": ["ref_s01_slide"],
                    },
                ],
                "logo_asset_id": "asset_s01_01",
            },
            "debris_exclusions": [],
            "missing_evidence": [],
            "conflicts": [],
            "embedding_policy": {
                "scope": "request_data_only",
                "global_knowledge_eligible": False,
                "embedding_action": "none",
            },
        },
        strict=True,
    )

    item = lambda item_id, label, detail, evidence, group=None: {
        "id": item_id,
        "label": label,
        "detail": detail,
        "value": None,
        "group": group,
        "evidence_refs": [evidence],
        "asset_ref": None,
    }
    slides = [
        _slide(
            1,
            "thesis_cover",
            "Source evidence becomes a deterministic visual system",
            claims[0],
            _visual_payload("typographic"),
            _composition("thesis_cover", "left_focal", density="sparse"),
            asset_refs=["asset_s01_01"],
        ),
        _slide(
            2,
            "problem_landscape",
            "Unbounded inputs create three visible failure modes",
            claims[1],
            _visual_payload(
                "comparison",
                items=[
                    item("signal_1", "Ambiguity", "Identity can drift", claims[1]),
                    item("signal_2", "Mutation", "Bytes can change", claims[1]),
                    item("signal_3", "Network", "Output can disappear", claims[1]),
                ],
            ),
            _composition("problem_landscape", "field", density="balanced"),
        ),
        _slide(
            3,
            "key_insight",
            "Lineage is the design constraint that makes reuse safe",
            claims[2],
            _visual_payload(
                "proof_strip",
                items=[
                    item("proof_1", "Hash bound", "Original bytes stay attributable", claims[2]),
                    item("proof_2", "Page bound", "Source location stays explicit", claims[2]),
                ],
            ),
            _composition("key_insight", "centered_monument", density="sparse", alignment="center"),
        ),
        _slide(
            4,
            "process_pathway",
            "One narrow path turns intent into local render bytes",
            claims[3],
            _visual_payload(
                "process",
                steps=[
                    {"id": "step_1", "label": "Validate", "detail": "Bind source identity", "evidence_refs": [claims[3]]},
                    {"id": "step_2", "label": "Transform", "detail": "Preserve aspect ratio", "evidence_refs": [claims[3]]},
                    {"id": "step_3", "label": "Compile", "detail": "Embed local bytes", "evidence_refs": [claims[3]]},
                ],
            ),
            _composition("process_pathway", "diagonal_flow", density="balanced"),
        ),
        _slide(
            5,
            "metric_proof",
            "Repeated verification is visible, not inferred",
            "num_s05_01",
            _visual_payload(
                "metric",
                metrics=[
                    {
                        "id": "metric_1",
                        "value": "42",
                        "label": "verified runs",
                        "context": "synthetic product-owned fixture",
                        "evidence_refs": ["num_s05_01"],
                    }
                ],
            ),
            _composition("metric_proof", "centered_monument", density="sparse", alignment="center"),
        ),
        _slide(
            6,
            "system_map",
            "The source, resolver, and compiler remain one traceable system",
            claims[5],
            _visual_payload(
                "system_map",
                items=[
                    item("source", "Source", "Request-scoped bytes", claims[5]),
                    item("resolver", "Resolver", "Validated transforms", claims[5]),
                    item("compiler", "Compiler", "Network-free HTML", claims[5]),
                ],
                edges=[
                    {"from": "source", "to": "resolver", "label": "bind", "evidence_refs": [claims[5]]},
                    {"from": "resolver", "to": "compiler", "label": "embed", "evidence_refs": [claims[5]]},
                ],
            ),
            _composition("system_map", "radial", density="balanced", alignment="center"),
            asset_refs=["asset_s06_01"],
        ),
    ]
    spec = DeckSpec.model_validate(
        {
            "schema_version": "deck_spec.v1",
            "compiler_version": "instant-deck-composition-compiler.v1",
            "source_package_id": package.package_id,
            "source_checksum": package.source_checksum,
            "deck_title": "Synthetic Asset Resolution Contract",
            "deck_thesis": "Source-bound asset bytes can be transformed and compiled deterministically.",
            "audience": "Engineering and product reviewers",
            "narrative": {
                "audience_need": "Verify source lineage, visual integrity, and deterministic rendering.",
                "arc": ["identity", "problem", "insight", "solution", "proof", "decision"],
                "opening_move": "State the deterministic source-bound thesis.",
                "closing_move": "Show the traceable system that enforces it.",
                "represented_source_slide_ids": source_ids,
                "omitted_source_slide_ids": [],
            },
            "art_direction": {
                "concept": "Bounded signal",
                "tone": "technical",
                "display_strategy": "grotesk_monument",
                "motif": "Connected source nodes",
                "rhythm": "alternating",
                "paper_role": "brand_paper",
                "ink_role": "brand_ink",
                "signature_role": "brand_signal",
                "support_roles": [],
            },
            "slides": slides,
        },
        strict=True,
    )
    planner = SyntheticPlanner(
        slides=(
            SyntheticPlannerSlide(
                archetype="thesis_cover",
                asset_use=SyntheticAssetUse(
                    asset_ref="asset_s01_01",
                    role="brand_mark",
                    treatment="contained",
                    rationale="Use the source-bound mark as the cover identity.",
                ),
            ),
            SyntheticPlannerSlide(archetype="problem_landscape"),
            SyntheticPlannerSlide(archetype="key_insight"),
            SyntheticPlannerSlide(archetype="process_pathway"),
            SyntheticPlannerSlide(archetype="metric_proof"),
            SyntheticPlannerSlide(
                archetype="system_map",
                asset_use=SyntheticAssetUse(
                    asset_ref="asset_s06_01",
                    role="portrait",
                    treatment="edge_crop",
                    rationale="Use the source-bound portrait beside the system map.",
                ),
            ),
        )
    )
    catalog = extract_source_asset_catalog_v2(
        pdf_bytes,
        package,
        ("asset_s01_01", "asset_s06_01"),
    )
    typography = TypographyPlanV2(
        source_document_sha256=source_hash,
        source_classification="heavy_geometric_display_plus_neutral_sans",
        source_fonts=(),
        exact_source_font_reuse_reason="Synthetic fixture uses documented local fallbacks.",
    )
    return SyntheticContext(pdf_bytes, package, spec, planner, catalog, typography)


@pytest.fixture(scope="module")
def context() -> SyntheticContext:
    return _build_context()


@pytest.fixture(scope="module")
def resolved_bundle(context: SyntheticContext) -> ResolvedAssetBundleV2:
    return resolve_source_assets_v2(context.planner, context.spec, context.package, context.catalog)


def test_pdf_extraction_and_manifest_preserve_source_lineage(
    context: SyntheticContext, resolved_bundle: ResolvedAssetBundleV2
) -> None:
    manifest = resolved_bundle.manifest
    assert manifest.manifest_version == "instant-deck-source-asset-manifest.v2"
    assert manifest.source_document_sha256 == sha256(context.pdf_bytes).hexdigest()
    assert [
        (row.asset_id, row.source_page, row.planner_role, row.transformation.fit)
        for row in manifest.assets
    ] == [
        ("asset_s01_01", 1, "brand_mark", "contain"),
        ("asset_s06_01", 6, "portrait", "cover"),
    ]
    assert manifest.assets[0].slides_consuming == ("s01",)
    assert manifest.assets[1].slides_consuming == ("s06",)
    assert all(row.original_byte_sha256 == row.source_asset_declared_sha256 for row in manifest.assets)
    assert all(row.transformation.aspect_ratio_preserved for row in manifest.assets)


def test_unknown_asset_id_fails_closed(context: SyntheticContext) -> None:
    with pytest.raises(AssetResolutionError, match="unknown_asset_id"):
        validate_asset_request_ids_v2(context.package, ("asset_s99_99",))


def test_duplicate_asset_request_fails_closed(context: SyntheticContext) -> None:
    with pytest.raises(AssetResolutionError, match="duplicate_asset_request"):
        validate_asset_request_ids_v2(context.package, ("asset_s01_01", "asset_s01_01"))


def test_missing_required_asset_fails_closed(context: SyntheticContext) -> None:
    incomplete = replace(context.catalog, assets=(context.catalog.assets[0],))
    with pytest.raises(AssetResolutionError, match="missing_required_asset"):
        resolve_source_assets_v2(context.planner, context.spec, context.package, incomplete)


def test_asset_from_another_source_package_fails_closed(context: SyntheticContext) -> None:
    foreign = replace(context.catalog, source_package_id="srcpkg_0000000000000000")
    with pytest.raises(AssetResolutionError, match="asset_from_another_source_package"):
        resolve_source_assets_v2(context.planner, context.spec, context.package, foreign)


def test_mismatched_byte_hash_fails_closed(context: SyntheticContext) -> None:
    tampered = replace(context.catalog.assets[0], original_bytes=b"not-the-declared-image")
    with pytest.raises(AssetResolutionError, match="asset_byte_hash_mismatch"):
        resolve_source_assets_v2(
            context.planner,
            context.spec,
            context.package,
            replace(context.catalog, assets=(tampered, context.catalog.assets[1])),
        )


def test_unsupported_mime_type_fails_closed(context: SyntheticContext) -> None:
    wrong_mime = replace(context.catalog.assets[0], mime_type="image/webp")
    with pytest.raises(AssetResolutionError, match="unsupported_asset_mime_type"):
        resolve_source_assets_v2(
            context.planner,
            context.spec,
            context.package,
            replace(context.catalog, assets=(wrong_mime, context.catalog.assets[1])),
        )


def test_wrong_source_page_fails_closed(context: SyntheticContext) -> None:
    wrong_page = replace(context.catalog.assets[1], source_page=5)
    with pytest.raises(AssetResolutionError, match="asset_source_page_mismatch"):
        resolve_source_assets_v2(
            context.planner,
            context.spec,
            context.package,
            replace(context.catalog, assets=(context.catalog.assets[0], wrong_page)),
        )


def test_corrupt_bytes_fail_closed_even_when_hash_bound(context: SyntheticContext) -> None:
    corrupt = b"hash-bound-but-not-an-image"
    row = ExtractedSourceAssetV2(
        asset_id="asset_s01_01",
        source_page=1,
        mime_type="image/png",
        width=1,
        height=1,
        original_bytes=corrupt,
    )
    expected = context.package.assets[0].model_copy(
        update={"sha256": sha256(corrupt).hexdigest(), "width": 1, "height": 1}
    )
    with pytest.raises(AssetResolutionError, match="corrupt_asset_bytes"):
        _validated_image(row, expected)


def test_crop_validation_and_aspect_ratio_guards() -> None:
    with pytest.raises(ValidationError):
        FocalPointV2(x=-0.01, y=0.5)
    with pytest.raises(ValidationError):
        NormalizedCropBoxV2(left=0.8, top=0.0, right=0.2, bottom=1.0)

    logo = Image.new("RGBA", (400, 200), (201, 66, 62, 255))
    contained, crop = _contain(logo, width=600, height=600)
    assert contained.size == (600, 600)
    assert contained.getbbox() == (0, 150, 600, 450)
    assert crop == (0.0, 0.0, 1.0, 1.0)

    portrait = Image.new("RGB", (360, 540), "white")
    covered, crop = _cover(portrait, width=480, height=640, focal=(0.5, 0.38))
    assert covered.size == (480, 640)
    crop_ratio = ((crop[2] - crop[0]) * portrait.width) / ((crop[3] - crop[1]) * portrait.height)
    assert crop_ratio == pytest.approx(480 / 640, abs=0.002)


def test_transformation_and_compilation_are_byte_deterministic(context: SyntheticContext) -> None:
    first_bundle = resolve_source_assets_v2(
        context.planner, context.spec, context.package, context.catalog
    )
    second_bundle = resolve_source_assets_v2(
        context.planner, context.spec, context.package, context.catalog
    )
    assert first_bundle.transformed_bytes == second_bundle.transformed_bytes
    assert first_bundle.manifest == second_bundle.manifest
    first = compile_deck_spec_v2(
        context.spec, context.package, assets=first_bundle, typography=context.typography
    )
    second = compile_deck_spec_v2(
        context.spec, context.package, assets=second_bundle, typography=context.typography
    )
    assert first.document_html == second.document_html
    assert first.content_sha256 == second.content_sha256
    assert first.manifest == second.manifest
    assert first.compiler_version == "instant-deck-composition-compiler.v2"


def test_compiler_v1_remains_additive_and_v2_is_network_independent(
    context: SyntheticContext,
    resolved_bundle: ResolvedAssetBundleV2,
    monkeypatch,
) -> None:
    def blocked_socket(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    v1_first = compile_deck_spec(context.spec, context.package)
    v1_second = compile_deck_spec(context.spec, context.package)
    v2 = compile_deck_spec_v2(
        context.spec,
        context.package,
        assets=resolved_bundle,
        typography=context.typography,
    )
    assert v1_first.content_sha256 == v1_second.content_sha256
    assert v1_first.compiler_version == "instant-deck-composition-compiler.v1"
    assert "data-asset-id=" not in v1_first.document_html
    assert v2.document_html.count("data-asset-id=") == 2
    assert v2.document_html.count("data:image/png;base64,") == 2
    assert "http://" not in v2.document_html
    assert "https://" not in v2.document_html
    assert v2.manifest["networkDependentOutput"] is False


def test_tampered_transformed_asset_and_failed_compile_cannot_publish(
    context: SyntheticContext, resolved_bundle: ResolvedAssetBundleV2
) -> None:
    tampered_payloads = tuple(
        (asset_id, payload + b"tamper" if asset_id == "asset_s01_01" else payload)
        for asset_id, payload in resolved_bundle.transformed_bytes
    )
    tampered = ResolvedAssetBundleV2(
        manifest=resolved_bundle.manifest,
        transformed_bytes=tampered_payloads,
    )
    with pytest.raises(AssetResolutionError, match="transformed_asset_hash_mismatch"):
        compile_deck_spec_v2(
            context.spec,
            context.package,
            assets=tampered,
            typography=context.typography,
        )
    with pytest.raises(OfflinePublicationRejected):
        build_publication_candidate(
            design_version_id="designver_failed_asset_compile",
            compiled=None,
            chromium_report=None,
        )


def test_compiler_v2_passes_chromium_quality_gates(
    context: SyntheticContext,
    resolved_bundle: ResolvedAssetBundleV2,
    tmp_path,
) -> None:
    compiled = compile_deck_spec_v2(
        context.spec,
        context.package,
        assets=resolved_bundle,
        typography=context.typography,
    )
    report = validate_compiled_deck_in_chromium(compiled, screenshot_directory=tmp_path)
    assert report["passed"] is True, [
        {
            "slideId": row["slideId"],
            "failures": row["failures"],
            "severeOverlapPairs": row["metrics"]["severeOverlapPairs"],
        }
        for row in report["slides"]
        if not row["passed"]
    ]
    assert len(report["slides"]) == 6
    assert all(
        not row["metrics"]["overflowX"] and not row["metrics"]["overflowY"]
        for row in report["slides"]
    )
    assert all(not row["metrics"]["clippedElementKeys"] for row in report["slides"])
    assert all(row["metrics"]["contrast"]["status"] == "passed" for row in report["slides"])
    assert all(
        (row["metrics"]["assetLoad"] or {}).get("failedImageCount") == 0
        for row in report["slides"]
    )
    assert all(
        "Noto Sans" in item["fontFamily"]
        for row in report["slides"]
        for item in row["typography"]
    )
