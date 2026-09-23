"""Deterministic Source Package v2 bridge for the unchanged DeckSpec v1 compiler.

Planner v4.1 is allowed to select derived request-bound assets such as the
Source Package v2 wordmark.  The historical v1 source-package asset ID grammar
cannot represent those IDs, so this module assigns stable v1-compatible aliases
and records the exact mapping.  No asset is substituted and no bytes are
modified by this bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from pydantic import ConfigDict

from .models import (
    NormalizedSourcePackage,
    SourceAssetRecord,
    SourceBackedBrandMetadata,
    StrictModel,
)
from .source_package import canonical_sha256
from .source_package_v2 import (
    AssetSemanticRole,
    NormalizedSourcePackageV2,
    SourceAssetRecordV2,
)


BRIDGE_VERSION_V4_1 = "instant-deck-source-compiler-bridge.v4.1"


class CompilerAssetAliasV4_1(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    planner_asset_id: str
    compiler_asset_id: str
    byte_sha256: str
    semantic_role: AssetSemanticRole
    source_page: int


class CompilerSourceBridgeManifestV4_1(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    contract_version: Literal[
        "instant-deck-source-compiler-bridge.v4.1"
    ] = BRIDGE_VERSION_V4_1
    source_document_sha256: str
    source_package_v2_id: str
    compiler_source_package_v1_id: str
    compiler_source_package_v1_sha256: str
    asset_aliases: tuple[CompilerAssetAliasV4_1, ...]


@dataclass(frozen=True, slots=True)
class CompilerSourceBridgeBundleV4_1:
    compiler_package_v1: NormalizedSourcePackage
    aliased_package_v2: NormalizedSourcePackageV2
    manifest: CompilerSourceBridgeManifestV4_1

    def planner_to_compiler_asset_ids(self) -> dict[str, str]:
        return {
            row.planner_asset_id: row.compiler_asset_id
            for row in self.manifest.asset_aliases
        }


def _compiler_asset_type(role: AssetSemanticRole) -> str:
    if role in {
        AssetSemanticRole.LITERAL_LOGO,
        AssetSemanticRole.WORDMARK,
        AssetSemanticRole.BRAND_SYMBOL,
    }:
        return "logo"
    if role == AssetSemanticRole.FOUNDER_PORTRAIT:
        return "portrait"
    if role == AssetSemanticRole.DIAGRAM:
        return "diagram"
    return "embedded_image"


def _asset_aliases(
    package_v2: NormalizedSourcePackageV2,
    canonical_package_v1: NormalizedSourcePackage,
) -> tuple[CompilerAssetAliasV4_1, ...]:
    used = {row.asset_id for row in canonical_package_v1.assets}
    aliases: list[CompilerAssetAliasV4_1] = []
    for row in sorted(package_v2.assets, key=lambda asset: asset.asset_id):
        compiler_id = row.asset_id
        if compiler_id not in used:
            compiler_id = next(
                (
                    f"asset_s{row.source_page:02d}_{index:02d}"
                    for index in range(99, 0, -1)
                    if f"asset_s{row.source_page:02d}_{index:02d}" not in used
                ),
                "",
            )
            if not compiler_id:
                raise ValueError(f"compiler_asset_alias_exhausted:{row.source_page}")
        used.add(compiler_id)
        aliases.append(
            CompilerAssetAliasV4_1(
                planner_asset_id=row.asset_id,
                compiler_asset_id=compiler_id,
                byte_sha256=row.byte_sha256,
                semantic_role=row.semantic_role,
                source_page=row.source_page,
            )
        )
    return tuple(aliases)


def _replace_asset_ids(value: object, mapping: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {key: _replace_asset_ids(child, mapping) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_asset_ids(child, mapping) for child in value]
    if isinstance(value, tuple):
        return tuple(_replace_asset_ids(child, mapping) for child in value)
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def build_compiler_source_bridge_v4_1(
    package_v2: NormalizedSourcePackageV2,
    canonical_package_v1: NormalizedSourcePackage,
) -> CompilerSourceBridgeBundleV4_1:
    """Materialize a request-bound v1 compiler package without changing v1.

    Existing source assets retain their IDs and bytes.  Derived v2 assets gain
    deterministic aliases.  Semantic roles only refine compiler placement
    types (logo, portrait, diagram, or embedded image).
    """

    if canonical_package_v1.source_checksum != package_v2.source_checksum:
        raise ValueError("canonical_source_checksum_mismatch")
    if canonical_sha256(canonical_package_v1) != package_v2.source_package_v1_sha256:
        raise ValueError("canonical_source_package_v1_hash_mismatch")

    aliases = _asset_aliases(package_v2, canonical_package_v1)
    mapping = {row.planner_asset_id: row.compiler_asset_id for row in aliases}
    compiler_assets = [
        SourceAssetRecord(
            asset_id=mapping[row.asset_id],
            asset_type=_compiler_asset_type(row.semantic_role),
            mime_type=row.mime_type,
            sha256=row.byte_sha256,
            width=row.width,
            height=row.height,
            alt_text=row.alt_text,
            source_reference_ids=list(row.source_reference_ids),
        )
        for row in package_v2.assets
    ]
    logo_asset_id = package_v2.brand.wordmark_asset_id or package_v2.brand.literal_logo_asset_id
    compiler_brand = SourceBackedBrandMetadata(
        organization_name=canonical_package_v1.brand.organization_name,
        organization_source_reference_ids=list(
            canonical_package_v1.brand.organization_source_reference_ids
        ),
        product_candidate=canonical_package_v1.brand.product_candidate,
        product_source_reference_ids=list(
            canonical_package_v1.brand.product_source_reference_ids
        ),
        audience_candidate=canonical_package_v1.brand.audience_candidate,
        audience_source_reference_ids=list(
            canonical_package_v1.brand.audience_source_reference_ids
        ),
        deck_type_candidate=canonical_package_v1.brand.deck_type_candidate,
        deck_type_source_reference_ids=list(
            canonical_package_v1.brand.deck_type_source_reference_ids
        ),
        roles=list(canonical_package_v1.brand.roles),
        logo_asset_id=mapping.get(logo_asset_id) if logo_asset_id else None,
    )
    compiler_package = canonical_package_v1.model_copy(
        update={
            "source_slides": [
                row.model_copy(
                    update={"asset_ids": [mapping.get(asset_id, asset_id) for asset_id in row.asset_ids]}
                )
                for row in package_v2.source_slides
            ],
            "source_references": list(package_v2.source_references),
            "assets": compiler_assets,
            "brand": compiler_brand,
        }
    )
    compiler_hash = canonical_sha256(compiler_package)
    aliased_payload = _replace_asset_ids(package_v2.model_dump(mode="json"), mapping)
    assert isinstance(aliased_payload, dict)
    aliased_payload["source_package_v1_sha256"] = compiler_hash
    aliased_package = NormalizedSourcePackageV2.model_validate_json(
        json.dumps(aliased_payload, sort_keys=True, separators=(",", ":")),
        strict=True,
    )
    manifest = CompilerSourceBridgeManifestV4_1(
        source_document_sha256=package_v2.source_checksum,
        source_package_v2_id=package_v2.package_id,
        compiler_source_package_v1_id=compiler_package.package_id,
        compiler_source_package_v1_sha256=compiler_hash,
        asset_aliases=aliases,
    )
    return CompilerSourceBridgeBundleV4_1(
        compiler_package_v1=compiler_package,
        aliased_package_v2=aliased_package,
        manifest=manifest,
    )


def alias_planner_payload_v4_1(
    payload: dict[str, object], manifest: CompilerSourceBridgeManifestV4_1
) -> dict[str, object]:
    mapping = {
        row.planner_asset_id: row.compiler_asset_id for row in manifest.asset_aliases
    }
    replaced = _replace_asset_ids(payload, mapping)
    assert isinstance(replaced, dict)
    return replaced
