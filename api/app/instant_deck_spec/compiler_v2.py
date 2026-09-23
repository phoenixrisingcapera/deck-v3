"""Versioned deterministic compiler v2 with request-bound source assets."""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json

from .asset_resolution_v2 import (
    AssetResolutionError,
    ResolvedAssetBundleV2,
    TypographyPlanV2,
)
from .compiler import BASE_CSS, CompiledDeck, CompiledSlide, DeckSpecCompilationError, _palette
from .composition_renderers import CSS as COMPOSITION_CSS_V1
from .composition_renderers_v2 import CSS_V2, render_slide_v2
from .models import DeckSpec, NormalizedSourcePackage
from .validation import DeckSpecValidationError, validate_deck_spec


COMPILER_VERSION_V2 = "instant-deck-composition-compiler.v2"


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _document(title: str, sections: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title>"
        '<meta name="viewport" content="width=1920,height=1080">'
        f"<style>{BASE_CSS}{COMPOSITION_CSS_V1}{CSS_V2}</style></head>"
        f'<body><main class="deck-document">{sections}</main></body></html>'
    )


def _validate_bundle(
    spec: DeckSpec,
    package: NormalizedSourcePackage,
    assets: ResolvedAssetBundleV2,
    typography: TypographyPlanV2,
) -> None:
    manifest = assets.manifest
    if manifest.source_document_sha256 != package.source_checksum:
        raise AssetResolutionError(
            "asset_from_another_source_document", manifest.source_document_sha256
        )
    if manifest.source_package_id != package.package_id:
        raise AssetResolutionError("asset_from_another_source_package", manifest.source_package_id)
    if typography.source_document_sha256 != package.source_checksum:
        raise AssetResolutionError(
            "typography_from_another_source_document", typography.source_document_sha256
        )
    required = {asset_id for slide in spec.slides for asset_id in slide.asset_refs}
    manifested = {row.asset_id for row in manifest.assets}
    if required != manifested:
        missing = sorted(required - manifested)
        extra = sorted(manifested - required)
        raise AssetResolutionError(
            "asset_manifest_coverage_mismatch", f"missing={missing};extra={extra}"
        )
    transformed = assets.bytes_by_id()
    if set(transformed) != manifested:
        raise AssetResolutionError(
            "asset_payload_coverage_mismatch", f"payload={sorted(transformed)}"
        )
    for row in manifest.assets:
        payload = transformed[row.asset_id]
        if sha256(payload).hexdigest() != row.transformed_byte_sha256:
            raise AssetResolutionError(
                "transformed_asset_hash_mismatch", row.transformed_byte_sha256, asset_id=row.asset_id
            )
        consuming = tuple(slide.slide_id for slide in spec.slides if row.asset_id in slide.asset_refs)
        if consuming != row.slides_consuming:
            raise AssetResolutionError(
                "asset_consumer_mismatch", str(consuming), asset_id=row.asset_id
            )


def compile_deck_spec_v2(
    spec: DeckSpec,
    source_package: NormalizedSourcePackage,
    *,
    assets: ResolvedAssetBundleV2,
    typography: TypographyPlanV2,
) -> CompiledDeck:
    """Compile canonical DeckSpec v1 through the additive compiler-v2 contract."""

    try:
        validate_deck_spec(spec, source_package)
    except DeckSpecValidationError as exc:
        raise DeckSpecCompilationError("semantic_validation_failed", str(exc)) from exc
    _validate_bundle(spec, source_package, assets, typography)

    compiled_slides: list[CompiledSlide] = []
    for slide in spec.slides:
        section = render_slide_v2(slide, _palette(spec, slide, source_package), assets)
        render_document = _document(f"{spec.deck_title} — {slide.position}", section)
        if 'src="http://' in render_document or 'src="https://' in render_document:
            raise DeckSpecCompilationError(
                "network_dependent_asset", slide.slide_id, slide_id=slide.slide_id
            )
        compiled_slides.append(
            CompiledSlide(
                slide_id=slide.slide_id,
                position=slide.position,
                archetype=slide.archetype.value,
                section_html=section,
                render_document=render_document,
                content_sha256=sha256(render_document.encode("utf-8")).hexdigest(),
            )
        )

    document_html = _document(
        spec.deck_title, "".join(slide.section_html for slide in compiled_slides)
    )
    asset_manifest_json = assets.manifest.model_dump(mode="json")
    typography_json = typography.model_dump(mode="json")
    manifest = {
        "schemaVersion": spec.schema_version,
        "inputCompilerVersion": spec.compiler_version,
        "compilerVersion": COMPILER_VERSION_V2,
        "sourcePackageId": source_package.package_id,
        "sourcePackageSha256": sha256(
            _canonical_bytes(source_package.model_dump(mode="json", by_alias=True))
        ).hexdigest(),
        "deckSpecSha256": sha256(
            _canonical_bytes(spec.model_dump(mode="json", by_alias=True))
        ).hexdigest(),
        "assetManifestVersion": assets.manifest.manifest_version,
        "assetManifestSha256": sha256(_canonical_bytes(asset_manifest_json)).hexdigest(),
        "typographyContractVersion": typography.contract_version,
        "typographyPlanSha256": sha256(_canonical_bytes(typography_json)).hexdigest(),
        "networkDependentOutput": False,
        "assets": [
            {
                "assetId": row.asset_id,
                "originalByteSha256": row.original_byte_sha256,
                "transformedByteSha256": row.transformed_byte_sha256,
                "slidesConsuming": list(row.slides_consuming),
            }
            for row in assets.manifest.assets
        ],
        "slides": [
            {
                "slideId": slide.slide_id,
                "position": slide.position,
                "archetype": slide.archetype,
                "contentSha256": slide.content_sha256,
            }
            for slide in compiled_slides
        ],
    }
    content_sha256 = sha256(document_html.encode("utf-8")).hexdigest()
    manifest["contentSha256"] = content_sha256
    return CompiledDeck(
        schema_version=spec.schema_version,
        compiler_version=COMPILER_VERSION_V2,
        source_package_id=source_package.package_id,
        slides=tuple(compiled_slides),
        document_html=document_html,
        content_sha256=content_sha256,
        manifest=manifest,
    )
