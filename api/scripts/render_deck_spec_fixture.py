#!/usr/bin/env python3
"""Build the Angel House seven-family fixture and deterministic visual evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.instant_deck_spec.chromium import validate_compiled_deck_in_chromium
from app.instant_deck_spec.compiler import compile_deck_spec
from app.instant_deck_spec.models import DeckSpec, NormalizedSourcePackage
from app.instant_deck_spec.source_package import (
    build_source_package_from_extraction_checkpoint,
    canonical_json_bytes,
    canonical_sha256,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
FIXTURES = BACKEND_ROOT / "tests" / "instant_deck_spec" / "fixtures"
SCHEMAS = BACKEND_ROOT / "app" / "instant_deck_spec" / "schemas"
EVIDENCE = REPOSITORY_ROOT / "docs" / "evidence" / "instant-deck-seven-primitives"
SOURCE_CHECKSUM = "7c0af58586d3d6e4c4a559a07da3da3835666c77b997b26b06ab0413d6ebf40e"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _schema(model: type[DeckSpec] | type[NormalizedSourcePackage], schema_id: str) -> dict:
    schema = model.model_json_schema(by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    return schema


def _source_package() -> NormalizedSourcePackage:
    checkpoint = json.loads((FIXTURES / "angel_house_extraction_checkpoint.json").read_text(encoding="utf-8"))
    return build_source_package_from_extraction_checkpoint(
        structured_deck=checkpoint["structuredDeck"],
        extraction_report=checkpoint["extractionReport"],
        source_filename="Kopie von Angel House.pdf",
        source_mime_type="application/pdf",
        source_byte_size=39_979_607,
        source_checksum=SOURCE_CHECKSUM,
    )


def _sheet(screenshot_directory: Path, compiled, spec: DeckSpec, *, gallery: bool) -> Path:
    selected = [
        (f"{slide.position:02d}-{slide.slide_id}-{slide.archetype}.png", slide)
        for slide in compiled.slides
    ]
    width, slide_width, slide_height, gutter, columns = 1740, 768, 432, 54, 2
    rows = (len(selected) + columns - 1) // columns
    canvas = Image.new("RGB", (width, rows * (slide_height + 96) + 112), "#111111")
    draw = ImageDraw.Draw(canvas)
    heading = "ANGEL HOUSE · ARCHETYPE GALLERY" if gallery else "ANGEL HOUSE · SEVEN-FAMILY OFFLINE DECK"
    draw.text((84, 38), heading, fill="#F4F0E7")
    for index, (filename, slide_record) in enumerate(selected):
        row, column = divmod(index, columns)
        x = 70 + column * (slide_width + 64)
        y = 92 + row * (slide_height + 96)
        slide = Image.open(screenshot_directory / filename).convert("RGB").resize((slide_width, slide_height), Image.Resampling.LANCZOS)
        if gallery:
            label = f"{slide_record.archetype.upper()} · {spec.slides[index].composition.variant.value.upper()}"
        else:
            label = f"{slide_record.position:02d} · {slide_record.archetype.replace('_', ' ').upper()}"
        draw.text((x, y - 28), label, fill="#D92536")
        canvas.paste(slide, (x, y))
    output = EVIDENCE / ("angel-house-archetype-gallery.png" if gallery else "angel-house-full-deck-contact-sheet.png")
    canvas.save(output, format="PNG", optimize=False)
    return output


def main() -> int:
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    screenshots = EVIDENCE / "slides"
    package = _source_package()
    spec = DeckSpec.model_validate_json((FIXTURES / "angel_house_deck_spec.v1.json").read_text(encoding="utf-8"), strict=True)

    _write_json(
        SCHEMAS / "deck-spec.v1.json",
        _schema(DeckSpec, "https://deck.aistack.codes/schemas/deck-spec.v1.json"),
    )
    _write_json(
        SCHEMAS / "instant-deck-source-package.v1.json",
        _schema(NormalizedSourcePackage, "https://deck.aistack.codes/schemas/instant-deck-source-package.v1.json"),
    )
    _write_json(FIXTURES / "angel_house_source_package.v1.json", package.model_dump(mode="json", by_alias=True))

    first = compile_deck_spec(spec, package)
    second = compile_deck_spec(spec, package)
    if first.document_html != second.document_html or first.content_sha256 != second.content_sha256:
        raise RuntimeError("Deterministic compilation failed.")
    (EVIDENCE / "angel-house-deck-spec-compiled.html").write_text(first.document_html, encoding="utf-8")
    report = validate_compiled_deck_in_chromium(first, screenshot_directory=screenshots)
    _write_json(EVIDENCE / "chromium-report.json", report)
    contact_sheet = _sheet(screenshots, first, spec, gallery=False)
    gallery = _sheet(screenshots, first, spec, gallery=True)

    determinism = {
        "schemaVersion": "instant-deck-determinism-manifest.v1",
        "sourcePackageSchemaVersion": package.schema_version,
        "deckSpecSchemaVersion": spec.schema_version,
        "compilerVersion": first.compiler_version,
        "sourceFileSha256": SOURCE_CHECKSUM,
        "sourcePackageSha256": canonical_sha256(package),
        "deckSpecSha256": hashlib.sha256(canonical_json_bytes(spec.model_dump(mode="json", by_alias=True))).hexdigest(),
        "firstCompileSha256": first.content_sha256,
        "secondCompileSha256": second.content_sha256,
        "identicalBytes": first.document_html.encode("utf-8") == second.document_html.encode("utf-8"),
        "chromiumPassed": report["passed"],
        "contactSheetSha256": hashlib.sha256(contact_sheet.read_bytes()).hexdigest(),
        "gallerySha256": hashlib.sha256(gallery.read_bytes()).hexdigest(),
        "slideScreenshotSha256": {row["slideId"]: row["screenshotSha256"] for row in report["slides"]},
    }
    _write_json(EVIDENCE / "determinism-manifest.json", determinism)
    print(json.dumps(determinism, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
