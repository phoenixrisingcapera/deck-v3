"""Deterministic, request-bound image resolution for composition compiler v2.

The module is deliberately unmounted.  It accepts source bytes supplied by the
current request, validates them against ``NormalizedSourcePackage``, transforms
only the two roles demonstrated by PlannerDeckSpec v3, and returns an immutable
manifest plus in-memory data-URI payloads.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Annotated, Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.instant_deck_spec.models import DeckSpec, NormalizedSourcePackage, SourceAssetRecord


ASSET_MANIFEST_VERSION_V2 = "instant-deck-source-asset-manifest.v2"
ASSET_TRANSFORM_VERSION_V2 = "instant-deck-asset-transform.v2"
TYPOGRAPHY_CONTRACT_VERSION_V2 = "instant-deck-typography-plan.v2"
MAX_ORIGINAL_ASSET_BYTES = 16 * 1024 * 1024
MAX_TRANSFORMED_ASSET_BYTES = 2 * 1024 * 1024
SUPPORTED_INPUT_MIME_TYPES = {"image/png", "image/jpeg"}


class AssetResolutionError(ValueError):
    def __init__(self, code: str, detail: str, *, asset_id: str | None = None):
        self.code = code
        self.detail = detail
        self.asset_id = asset_id
        super().__init__(f"{code}:{asset_id or 'bundle'}:{detail}")


class FrozenAssetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class FocalPointV2(FrozenAssetModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class NormalizedCropBoxV2(FrozenAssetModel):
    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_ordered_bounds(self) -> "NormalizedCropBoxV2":
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("crop bounds must have positive width and height")
        return self


class AssetTransformationV2(FrozenAssetModel):
    transform_version: Literal["instant-deck-asset-transform.v2"] = ASSET_TRANSFORM_VERSION_V2
    fit: Literal["contain", "cover"]
    focal_point: FocalPointV2
    crop_box: NormalizedCropBoxV2
    output_width: int = Field(gt=0, le=1600)
    output_height: int = Field(gt=0, le=1600)
    output_mime_type: Literal["image/png"] = "image/png"
    maximum_output_bytes: int = Field(gt=0, le=MAX_TRANSFORMED_ASSET_BYTES)
    aspect_ratio_preserved: Literal[True] = True
    interpolation: Literal["lanczos"] = "lanczos"


class SourceAssetManifestItemV2(FrozenAssetModel):
    asset_id: str
    planner_role: Literal["brand_mark", "portrait"]
    planner_treatment: Literal["contained", "edge_crop"]
    source_document_sha256: Sha256
    source_package_id: str
    source_page: int = Field(ge=1)
    source_asset_type: str
    source_asset_declared_sha256: Sha256
    original_byte_sha256: Sha256
    original_mime_type: Literal["image/png", "image/jpeg"]
    original_width: int = Field(gt=0)
    original_height: int = Field(gt=0)
    transformation: AssetTransformationV2
    transformed_byte_sha256: Sha256
    transformed_byte_size: int = Field(gt=0, le=MAX_TRANSFORMED_ASSET_BYTES)
    transformed_mime_type: Literal["image/png"] = "image/png"
    transformed_width: int = Field(gt=0)
    transformed_height: int = Field(gt=0)
    slides_consuming: tuple[str, ...]


class SourceAssetManifestV2(FrozenAssetModel):
    manifest_version: Literal["instant-deck-source-asset-manifest.v2"] = ASSET_MANIFEST_VERSION_V2
    source_document_sha256: Sha256
    source_package_id: str
    assets: tuple[SourceAssetManifestItemV2, ...]


class EmbeddedFontEvidenceV2(FrozenAssetModel):
    source_name: str
    normalized_family: str
    embedded_subset: bool
    extracted_byte_sha256: Sha256
    extracted_byte_size: int = Field(gt=0)
    redistribution_status: Literal["unverified"] = "unverified"
    reusable_in_compiler: Literal[False] = False


class TypographyPlanV2(FrozenAssetModel):
    contract_version: Literal["instant-deck-typography-plan.v2"] = TYPOGRAPHY_CONTRACT_VERSION_V2
    source_document_sha256: Sha256
    source_classification: Literal["heavy_geometric_display_plus_neutral_sans"]
    source_fonts: tuple[EmbeddedFontEvidenceV2, ...]
    exact_source_font_reuse: Literal[False] = False
    exact_source_font_reuse_reason: str
    display_fallback: Literal["Noto Sans Display"] = "Noto Sans Display"
    body_fallback: Literal["Noto Sans"] = "Noto Sans"
    fallback_policy: Literal["local_classification_mapping"] = "local_classification_mapping"
    network_fonts_allowed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class ExtractedSourceAssetV2:
    asset_id: str
    source_page: int
    mime_type: str
    width: int
    height: int
    original_bytes: bytes

    @property
    def byte_sha256(self) -> str:
        return sha256(self.original_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceAssetByteCatalogV2:
    source_document_sha256: str
    source_package_id: str
    assets: tuple[ExtractedSourceAssetV2, ...]

    def by_id(self) -> dict[str, ExtractedSourceAssetV2]:
        return {row.asset_id: row for row in self.assets}


@dataclass(frozen=True, slots=True)
class ResolvedAssetBundleV2:
    manifest: SourceAssetManifestV2
    transformed_bytes: tuple[tuple[str, bytes], ...]

    def bytes_by_id(self) -> dict[str, bytes]:
        return dict(self.transformed_bytes)

    def data_uri(self, asset_id: str) -> str:
        data = self.bytes_by_id().get(asset_id)
        if data is None:
            raise AssetResolutionError("missing_required_asset", asset_id, asset_id=asset_id)
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


class _PlannerAssetUseV2(Protocol):
    asset_ref: str
    role: str
    treatment: str
    rationale: str


class _PlannerSlideV2(Protocol):
    archetype: str
    asset_use: _PlannerAssetUseV2 | None


class ValidatedPlannerAssetIntentSourceV2(Protocol):
    """Narrow post-validation seam; it does not mount or import a planner version."""

    slides: Sequence[_PlannerSlideV2]


@dataclass(frozen=True, slots=True)
class ValidatedPlannerAssetIntentV2:
    slide_position: int
    archetype: str
    asset_ref: str
    role: str
    treatment: str
    rationale: str


def _validated_planner_asset_intents_v2(
    planner: ValidatedPlannerAssetIntentSourceV2,
) -> tuple[ValidatedPlannerAssetIntentV2, ...]:
    return tuple(
        ValidatedPlannerAssetIntentV2(
            slide_position=index,
            archetype=slide.archetype,
            asset_ref=slide.asset_use.asset_ref,
            role=slide.asset_use.role,
            treatment=slide.asset_use.treatment,
            rationale=slide.asset_use.rationale,
        )
        for index, slide in enumerate(planner.slides, start=1)
        if slide.asset_use is not None
    )


def _source_page(package: NormalizedSourcePackage, asset: SourceAssetRecord) -> int:
    references = {row.reference_id: row.source_slide_id for row in package.source_references}
    slides = {row.source_slide_id: row.source_page_number for row in package.source_slides}
    pages = {
        slides[references[reference]]
        for reference in asset.source_reference_ids
        if reference in references and references[reference] in slides
    }
    if len(pages) != 1:
        raise AssetResolutionError(
            "ambiguous_asset_source_page",
            f"source pages={sorted(pages)}",
            asset_id=asset.asset_id,
        )
    return pages.pop()


def _mime_from_pymupdf_extension(extension: str) -> str | None:
    return {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg"}.get(
        extension.casefold()
    )


def validate_asset_request_ids_v2(
    package: NormalizedSourcePackage,
    requested_asset_ids: tuple[str, ...],
) -> None:
    """Fail closed before any source-document parsing occurs."""

    known_asset_ids = {row.asset_id for row in package.assets}
    if len(requested_asset_ids) != len(set(requested_asset_ids)):
        raise AssetResolutionError("duplicate_asset_request", str(requested_asset_ids))
    unknown = sorted(set(requested_asset_ids) - known_asset_ids)
    if unknown:
        raise AssetResolutionError("unknown_asset_id", ",".join(unknown), asset_id=unknown[0])


def extract_source_asset_catalog_v2(
    source_pdf_bytes: bytes,
    package: NormalizedSourcePackage,
    requested_asset_ids: tuple[str, ...],
) -> SourceAssetByteCatalogV2:
    """Extract exact image streams from the current source PDF only."""

    validate_asset_request_ids_v2(package, requested_asset_ids)

    document_hash = sha256(source_pdf_bytes).hexdigest()
    if document_hash != package.source_checksum:
        raise AssetResolutionError(
            "source_document_hash_mismatch",
            f"{document_hash}!={package.source_checksum}",
        )
    if len(source_pdf_bytes) != package.source_file.byte_size:
        raise AssetResolutionError(
            "source_document_size_mismatch",
            f"{len(source_pdf_bytes)}!={package.source_file.byte_size}",
        )

    assets = {row.asset_id: row for row in package.assets}
    try:
        import fitz

        document = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    except Exception as exc:  # pragma: no cover - exact library error varies
        raise AssetResolutionError("corrupt_source_document", type(exc).__name__) from exc

    extracted: list[ExtractedSourceAssetV2] = []
    try:
        for asset_id in sorted(requested_asset_ids):
            asset = assets[asset_id]
            if asset.mime_type not in SUPPORTED_INPUT_MIME_TYPES:
                raise AssetResolutionError(
                    "unsupported_asset_mime_type", asset.mime_type, asset_id=asset_id
                )
            page_number = _source_page(package, asset)
            page = document[page_number - 1]
            dimension_matches: list[tuple[bytes, str]] = []
            exact_matches: list[tuple[bytes, str]] = []
            for image in page.get_images(full=True):
                payload = document.extract_image(image[0])
                mime = _mime_from_pymupdf_extension(str(payload.get("ext") or ""))
                if (
                    int(payload.get("width") or 0) != asset.width
                    or int(payload.get("height") or 0) != asset.height
                    or mime != asset.mime_type
                ):
                    continue
                raw = bytes(payload["image"])
                dimension_matches.append((raw, mime))
                if sha256(raw).hexdigest() == asset.sha256:
                    exact_matches.append((raw, mime))
            if not exact_matches:
                code = "asset_byte_hash_mismatch" if dimension_matches else "missing_source_asset"
                raise AssetResolutionError(code, asset.sha256, asset_id=asset_id)
            if len(exact_matches) != 1:
                raise AssetResolutionError(
                    "ambiguous_source_asset", f"matches={len(exact_matches)}", asset_id=asset_id
                )
            raw, mime = exact_matches[0]
            if len(raw) > MAX_ORIGINAL_ASSET_BYTES:
                raise AssetResolutionError(
                    "source_asset_too_large", str(len(raw)), asset_id=asset_id
                )
            extracted.append(
                ExtractedSourceAssetV2(
                    asset_id=asset_id,
                    source_page=page_number,
                    mime_type=mime,
                    width=asset.width,
                    height=asset.height,
                    original_bytes=raw,
                )
            )
    finally:
        document.close()
    return SourceAssetByteCatalogV2(
        source_document_sha256=document_hash,
        source_package_id=package.package_id,
        assets=tuple(extracted),
    )


def _validated_image(row: ExtractedSourceAssetV2, expected: SourceAssetRecord):
    if row.mime_type not in SUPPORTED_INPUT_MIME_TYPES:
        raise AssetResolutionError(
            "unsupported_asset_mime_type", row.mime_type, asset_id=row.asset_id
        )
    if row.byte_sha256 != expected.sha256:
        raise AssetResolutionError(
            "asset_byte_hash_mismatch",
            f"{row.byte_sha256}!={expected.sha256}",
            asset_id=row.asset_id,
        )
    if row.mime_type != expected.mime_type:
        raise AssetResolutionError(
            "asset_mime_manifest_mismatch",
            f"{row.mime_type}!={expected.mime_type}",
            asset_id=row.asset_id,
        )
    if (row.width, row.height) != (expected.width, expected.height):
        raise AssetResolutionError(
            "asset_dimension_manifest_mismatch",
            f"{(row.width, row.height)}!={(expected.width, expected.height)}",
            asset_id=row.asset_id,
        )
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(row.original_bytes)) as probe:
            detected_format = probe.format
            probe.verify()
        with Image.open(BytesIO(row.original_bytes)) as decoded:
            image = ImageOps.exif_transpose(decoded).copy()
    except Exception as exc:
        raise AssetResolutionError("corrupt_asset_bytes", type(exc).__name__, asset_id=row.asset_id) from exc
    expected_format = "PNG" if row.mime_type == "image/png" else "JPEG"
    if detected_format != expected_format:
        raise AssetResolutionError(
            "asset_mime_content_mismatch", str(detected_format), asset_id=row.asset_id
        )
    if image.size != (expected.width, expected.height):
        raise AssetResolutionError(
            "asset_dimension_mismatch",
            f"{image.size}!={(expected.width, expected.height)}",
            asset_id=row.asset_id,
        )
    return image


def _contain(image, *, width: int, height: int):
    from PIL import Image

    source = image.convert("RGBA")
    scale = min(width / source.width, height / source.height)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas, (0.0, 0.0, 1.0, 1.0)


def _cover(image, *, width: int, height: int, focal: tuple[float, float]):
    from PIL import Image

    source = image.convert("RGB")
    target_ratio = width / height
    source_ratio = source.width / source.height
    if source_ratio > target_ratio:
        crop_height = source.height
        crop_width = crop_height * target_ratio
    else:
        crop_width = source.width
        crop_height = crop_width / target_ratio
    center_x = focal[0] * source.width
    center_y = focal[1] * source.height
    left = min(max(center_x - crop_width / 2, 0), source.width - crop_width)
    top = min(max(center_y - crop_height / 2, 0), source.height - crop_height)
    box = (
        round(left),
        round(top),
        round(left + crop_width),
        round(top + crop_height),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        raise AssetResolutionError("invalid_computed_crop", str(box))
    transformed = source.crop(box).resize((width, height), Image.Resampling.LANCZOS)
    normalized = (
        box[0] / source.width,
        box[1] / source.height,
        box[2] / source.width,
        box[3] / source.height,
    )
    return transformed, normalized


def _png_bytes(image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _transformation_for_role(role: str) -> tuple[str, tuple[float, float], int, int]:
    if role == "brand_mark":
        return "contain", (0.5, 0.5), 600, 600
    if role == "portrait":
        return "cover", (0.5, 0.38), 480, 640
    raise AssetResolutionError("unsupported_asset_role", role)


def resolve_source_assets_v2(
    planner: ValidatedPlannerAssetIntentSourceV2,
    deck_spec: DeckSpec,
    package: NormalizedSourcePackage,
    catalog: SourceAssetByteCatalogV2,
) -> ResolvedAssetBundleV2:
    """Validate intent/catalog lineage and produce immutable transformed assets."""

    if catalog.source_document_sha256 != package.source_checksum:
        raise AssetResolutionError("asset_from_another_source_document", catalog.source_document_sha256)
    if catalog.source_package_id != package.package_id or deck_spec.source_package_id != package.package_id:
        raise AssetResolutionError("asset_from_another_source_package", catalog.source_package_id)
    if deck_spec.source_checksum != package.source_checksum:
        raise AssetResolutionError("deck_source_checksum_mismatch", deck_spec.source_checksum)

    source_assets = {row.asset_id: row for row in package.assets}
    catalog_assets = catalog.by_id()
    if len(catalog_assets) != len(catalog.assets):
        raise AssetResolutionError("ambiguous_source_asset_catalog", "duplicate asset IDs")
    deck_slides = {row.position: row for row in deck_spec.slides}
    manifest_items: list[SourceAssetManifestItemV2] = []
    transformed_rows: list[tuple[str, bytes]] = []
    for intent in _validated_planner_asset_intents_v2(planner):
        expected = source_assets.get(intent.asset_ref)
        if expected is None:
            raise AssetResolutionError("unknown_asset_id", intent.asset_ref, asset_id=intent.asset_ref)
        source = catalog_assets.get(intent.asset_ref)
        if source is None:
            raise AssetResolutionError(
                "missing_required_asset", intent.asset_ref, asset_id=intent.asset_ref
            )
        expected_page = _source_page(package, expected)
        if source.source_page != expected_page:
            raise AssetResolutionError(
                "asset_source_page_mismatch",
                f"{source.source_page}!={expected_page}",
                asset_id=intent.asset_ref,
            )
        slide = deck_slides.get(intent.slide_position)
        if slide is None or intent.asset_ref not in slide.asset_refs:
            raise AssetResolutionError(
                "planner_compiler_asset_mismatch",
                f"slide_position={intent.slide_position}",
                asset_id=intent.asset_ref,
            )
        fit, focal, output_width, output_height = _transformation_for_role(intent.role)
        required_treatment = "contained" if intent.role == "brand_mark" else "edge_crop"
        if intent.treatment != required_treatment:
            raise AssetResolutionError(
                "unsupported_asset_treatment", intent.treatment, asset_id=intent.asset_ref
            )
        image = _validated_image(source, expected)
        if fit == "contain":
            transformed, crop = _contain(image, width=output_width, height=output_height)
        else:
            transformed, crop = _cover(
                image, width=output_width, height=output_height, focal=focal
            )
        transformed_bytes = _png_bytes(transformed)
        if len(transformed_bytes) > MAX_TRANSFORMED_ASSET_BYTES:
            raise AssetResolutionError(
                "transformed_asset_too_large", str(len(transformed_bytes)), asset_id=intent.asset_ref
            )
        consuming = tuple(
            row.slide_id for row in deck_spec.slides if intent.asset_ref in row.asset_refs
        )
        transformation = AssetTransformationV2(
            fit=fit,
            focal_point=FocalPointV2(x=focal[0], y=focal[1]),
            crop_box=NormalizedCropBoxV2(
                left=round(crop[0], 8),
                top=round(crop[1], 8),
                right=round(crop[2], 8),
                bottom=round(crop[3], 8),
            ),
            output_width=output_width,
            output_height=output_height,
            maximum_output_bytes=MAX_TRANSFORMED_ASSET_BYTES,
        )
        manifest_items.append(
            SourceAssetManifestItemV2(
                asset_id=intent.asset_ref,
                planner_role=intent.role,
                planner_treatment=intent.treatment,
                source_document_sha256=package.source_checksum,
                source_package_id=package.package_id,
                source_page=source.source_page,
                source_asset_type=expected.asset_type,
                source_asset_declared_sha256=expected.sha256,
                original_byte_sha256=source.byte_sha256,
                original_mime_type=source.mime_type,
                original_width=source.width,
                original_height=source.height,
                transformation=transformation,
                transformed_byte_sha256=sha256(transformed_bytes).hexdigest(),
                transformed_byte_size=len(transformed_bytes),
                transformed_width=output_width,
                transformed_height=output_height,
                slides_consuming=consuming,
            )
        )
        transformed_rows.append((intent.asset_ref, transformed_bytes))
    manifest = SourceAssetManifestV2(
        source_document_sha256=package.source_checksum,
        source_package_id=package.package_id,
        assets=tuple(sorted(manifest_items, key=lambda row: row.asset_id)),
    )
    return ResolvedAssetBundleV2(
        manifest=manifest,
        transformed_bytes=tuple(sorted(transformed_rows)),
    )


def diagnose_source_typography_v2(source_pdf_bytes: bytes) -> TypographyPlanV2:
    """Record embedded font evidence without redistributing unverified subsets."""

    document_hash = sha256(source_pdf_bytes).hexdigest()
    try:
        import fitz

        document = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    except Exception as exc:  # pragma: no cover
        raise AssetResolutionError("corrupt_source_document", type(exc).__name__) from exc
    fonts: dict[tuple[str, str], EmbeddedFontEvidenceV2] = {}
    try:
        for page in document:
            for row in page.get_fonts(full=True):
                xref, source_name = int(row[0]), str(row[3])
                extracted = document.extract_font(xref)
                font_bytes = bytes(extracted[3])
                if not font_bytes:
                    continue
                normalized = source_name.split("+", 1)[-1]
                byte_hash = sha256(font_bytes).hexdigest()
                key = (source_name, byte_hash)
                if key in fonts:
                    continue
                fonts[key] = EmbeddedFontEvidenceV2(
                    source_name=source_name,
                    normalized_family=normalized,
                    embedded_subset="+" in source_name,
                    extracted_byte_sha256=byte_hash,
                    extracted_byte_size=len(font_bytes),
                )
    finally:
        document.close()
    return TypographyPlanV2(
        source_document_sha256=document_hash,
        source_classification="heavy_geometric_display_plus_neutral_sans",
        source_fonts=tuple(sorted(fonts.values(), key=lambda row: (row.normalized_family, row.source_name))),
        exact_source_font_reuse_reason=(
            "The PDF exposes embedded subset font programs, but their redistribution licence "
            "and full-glyph completeness are not established; compiler v2 records hashes only."
        ),
    )
