"""Deterministic request-bound assets for composition compiler v3.

Compiler v2 is intentionally left untouched.  V3 adds only the product-owned
synthetic roles demonstrated by Planner v4: a contained source logo, a cropped
founder portrait, and source event photography used as network evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .asset_resolution_v2 import (
    AssetResolutionError,
    SourceAssetByteCatalogV2,
    TypographyPlanV2,
    _contain,
    _cover,
    _png_bytes,
    _source_page,
    _validated_image,
)
from .models import DeckSpec, NormalizedSourcePackage, SlideArchetype


ASSET_MANIFEST_VERSION_V3 = "instant-deck-source-asset-manifest.v3"
ASSET_TRANSFORM_VERSION_V3 = "instant-deck-asset-transform.v3"
MAX_TRANSFORMED_ASSET_BYTES_V3 = 2 * 1024 * 1024
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FocalPointV3(_FrozenModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CropBoxV3(_FrozenModel):
    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_ordered_bounds(self) -> "CropBoxV3":
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("crop bounds must have positive width and height")
        return self


class AssetTransformationV3(_FrozenModel):
    transform_version: Literal["instant-deck-asset-transform.v3"] = ASSET_TRANSFORM_VERSION_V3
    fit: Literal["contain", "cover"]
    focal_point: FocalPointV3
    crop_box: CropBoxV3
    output_width: int = Field(gt=0, le=1600)
    output_height: int = Field(gt=0, le=1600)
    aspect_ratio_preserved: Literal[True] = True
    output_mime_type: Literal["image/png"] = "image/png"


class SourceAssetManifestItemV3(_FrozenModel):
    asset_id: str
    compiler_role: Literal["brand_mark", "founder_portrait", "network_evidence"]
    source_document_sha256: Sha256
    source_package_id: str
    source_page: int = Field(ge=1)
    source_asset_type: str
    original_byte_sha256: Sha256
    original_mime_type: Literal["image/png", "image/jpeg"]
    original_width: int = Field(gt=0)
    original_height: int = Field(gt=0)
    transformation: AssetTransformationV3
    transformed_byte_sha256: Sha256
    transformed_byte_size: int = Field(gt=0, le=MAX_TRANSFORMED_ASSET_BYTES_V3)
    transformed_width: int = Field(gt=0)
    transformed_height: int = Field(gt=0)
    slides_consuming: tuple[str, ...]


class SourceAssetManifestV3(_FrozenModel):
    manifest_version: Literal["instant-deck-source-asset-manifest.v3"] = ASSET_MANIFEST_VERSION_V3
    source_document_sha256: Sha256
    source_package_id: str
    assets: tuple[SourceAssetManifestItemV3, ...]


@dataclass(frozen=True, slots=True)
class ResolvedAssetBundleV3:
    manifest: SourceAssetManifestV3
    transformed_bytes: tuple[tuple[str, bytes], ...]

    def bytes_by_id(self) -> dict[str, bytes]:
        return dict(self.transformed_bytes)

    def data_uri(self, asset_id: str) -> str:
        import base64

        payload = self.bytes_by_id().get(asset_id)
        if payload is None:
            raise AssetResolutionError("missing_required_asset", asset_id, asset_id=asset_id)
        return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")


def _role_for(archetype: SlideArchetype, asset_type: str) -> tuple[str, str, tuple[float, float], int, int]:
    if archetype == SlideArchetype.THESIS_COVER and asset_type == "logo":
        return "brand_mark", "contain", (0.5, 0.5), 620, 280
    if archetype == SlideArchetype.PEOPLE_PROOF and asset_type == "portrait":
        return "founder_portrait", "cover", (0.5, 0.38), 520, 700
    if archetype == SlideArchetype.PARTNERSHIP_ECOSYSTEM and asset_type in {
        "embedded_image",
        "page_render",
    }:
        return "network_evidence", "cover", (0.5, 0.5), 760, 560
    raise AssetResolutionError(
        "asset_role_archetype_mismatch", f"{archetype.value}:{asset_type}"
    )


def resolve_source_assets_v3(
    deck_spec: DeckSpec,
    package: NormalizedSourcePackage,
    catalog: SourceAssetByteCatalogV2,
) -> ResolvedAssetBundleV3:
    """Resolve every compiler-v3 asset from the current request catalog only."""

    if catalog.source_document_sha256 != package.source_checksum:
        raise AssetResolutionError("asset_from_another_source_document", catalog.source_document_sha256)
    if catalog.source_package_id != package.package_id or deck_spec.source_package_id != package.package_id:
        raise AssetResolutionError("asset_from_another_source_package", catalog.source_package_id)
    expected = {row.asset_id: row for row in package.assets}
    supplied = catalog.by_id()
    required = tuple(dict.fromkeys(asset_id for slide in deck_spec.slides for asset_id in slide.asset_refs))
    if set(supplied) != set(required):
        raise AssetResolutionError(
            "asset_catalog_coverage_mismatch",
            f"required={sorted(required)};supplied={sorted(supplied)}",
        )

    manifest_items: list[SourceAssetManifestItemV3] = []
    transformed_rows: list[tuple[str, bytes]] = []
    for asset_id in sorted(required):
        source_asset = expected.get(asset_id)
        if source_asset is None:
            raise AssetResolutionError("unknown_asset_id", asset_id, asset_id=asset_id)
        source = supplied[asset_id]
        if source.source_page != _source_page(package, source_asset):
            raise AssetResolutionError("asset_source_page_mismatch", str(source.source_page), asset_id=asset_id)
        consuming = tuple(slide for slide in deck_spec.slides if asset_id in slide.asset_refs)
        if not consuming:
            raise AssetResolutionError("unused_asset", asset_id, asset_id=asset_id)
        roles = {_role_for(slide.archetype, source_asset.asset_type) for slide in consuming}
        if len(roles) != 1:
            raise AssetResolutionError("ambiguous_asset_role", str(sorted(roles)), asset_id=asset_id)
        role, fit, focal, width, height = roles.pop()
        image = _validated_image(source, source_asset)
        if fit == "contain":
            transformed, crop = _contain(image, width=width, height=height)
        else:
            transformed, crop = _cover(image, width=width, height=height, focal=focal)
        payload = _png_bytes(transformed)
        if len(payload) > MAX_TRANSFORMED_ASSET_BYTES_V3:
            raise AssetResolutionError("transformed_asset_too_large", str(len(payload)), asset_id=asset_id)
        transformation = AssetTransformationV3(
            fit=fit,
            focal_point=FocalPointV3(x=focal[0], y=focal[1]),
            crop_box=CropBoxV3(
                left=round(crop[0], 8),
                top=round(crop[1], 8),
                right=round(crop[2], 8),
                bottom=round(crop[3], 8),
            ),
            output_width=width,
            output_height=height,
        )
        manifest_items.append(
            SourceAssetManifestItemV3(
                asset_id=asset_id,
                compiler_role=role,
                source_document_sha256=package.source_checksum,
                source_package_id=package.package_id,
                source_page=source.source_page,
                source_asset_type=source_asset.asset_type,
                original_byte_sha256=source.byte_sha256,
                original_mime_type=source.mime_type,
                original_width=source.width,
                original_height=source.height,
                transformation=transformation,
                transformed_byte_sha256=sha256(payload).hexdigest(),
                transformed_byte_size=len(payload),
                transformed_width=width,
                transformed_height=height,
                slides_consuming=tuple(slide.slide_id for slide in consuming),
            )
        )
        transformed_rows.append((asset_id, payload))
    return ResolvedAssetBundleV3(
        manifest=SourceAssetManifestV3(
            source_document_sha256=package.source_checksum,
            source_package_id=package.package_id,
            assets=tuple(manifest_items),
        ),
        transformed_bytes=tuple(transformed_rows),
    )


def validate_typography_lineage_v3(
    typography: TypographyPlanV2, package: NormalizedSourcePackage
) -> None:
    if typography.source_document_sha256 != package.source_checksum:
        raise AssetResolutionError(
            "typography_from_another_source_document", typography.source_document_sha256
        )
