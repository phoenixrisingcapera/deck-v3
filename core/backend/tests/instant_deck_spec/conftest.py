from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.instant_deck_spec.models import DeckSpec
from app.instant_deck_spec.source_package import build_source_package_from_extraction_checkpoint


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE_CHECKSUM = "7c0af58586d3d6e4c4a559a07da3da3835666c77b997b26b06ab0413d6ebf40e"


@pytest.fixture(scope="session")
def source_package():
    checkpoint = json.loads((FIXTURES / "angel_house_extraction_checkpoint.json").read_text(encoding="utf-8"))
    return build_source_package_from_extraction_checkpoint(
        structured_deck=checkpoint["structuredDeck"],
        extraction_report=checkpoint["extractionReport"],
        source_filename="Kopie von Angel House.pdf",
        source_mime_type="application/pdf",
        source_byte_size=39_979_607,
        source_checksum=SOURCE_CHECKSUM,
    )


@pytest.fixture(scope="session")
def deck_spec():
    return DeckSpec.model_validate_json(
        (FIXTURES / "angel_house_deck_spec.v1.json").read_text(encoding="utf-8"),
        strict=True,
    )
