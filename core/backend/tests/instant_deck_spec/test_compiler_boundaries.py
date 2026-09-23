from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.instant_deck_spec.compiler import DeckSpecCompilationError, compile_deck_spec
from app.instant_deck_spec.models import DeckSpec
from app.instant_deck_spec.publication import (
    OfflinePublicationRejected,
    OfflinePublicationState,
    apply_publication_candidate,
    build_publication_candidate,
)
from app.instant_deck_spec.source_package import canonical_json_bytes, canonical_sha256


def test_identical_input_produces_identical_bytes_and_hash(deck_spec, source_package):
    first = compile_deck_spec(deck_spec, source_package)
    second = compile_deck_spec(deck_spec, source_package)
    assert first.document_html.encode("utf-8") == second.document_html.encode("utf-8")
    assert first.content_sha256 == second.content_sha256
    assert first.manifest == second.manifest
    assert canonical_json_bytes(source_package) == canonical_json_bytes(source_package)
    assert canonical_sha256(source_package) == canonical_sha256(source_package)


def test_archetype_outside_seven_family_boundary_fails_closed(deck_spec, source_package):
    payload = deck_spec.model_dump(mode="json", by_alias=True)
    payload["slides"][1]["archetype"] = "traction_strip"
    payload["slides"][1]["composition"]["primitive"] = "traction_strip"
    payload["slides"][1]["composition"]["variant"] = "field"
    payload["slides"][1]["visual"]["type"] = "comparison"
    unsupported = DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    with pytest.raises(DeckSpecCompilationError) as captured:
        compile_deck_spec(unsupported, source_package)
    assert captured.value.code == "primitive_not_implemented"


def test_all_eight_schema_archetypes_resolve_to_seven_structural_families(deck_spec, source_package):
    from app.instant_deck_spec.grammar import STRUCTURAL_GRAMMARS

    compiled = compile_deck_spec(deck_spec, source_package)
    assert len({slide.archetype for slide in compiled.slides}) == 8
    families = {STRUCTURAL_GRAMMARS[slide.archetype].family for slide in deck_spec.slides}
    assert len(families) == 7
    assert STRUCTURAL_GRAMMARS[deck_spec.slides[3].archetype].family == "pathway"
    assert STRUCTURAL_GRAMMARS[deck_spec.slides[4].archetype].family == "pathway"


@pytest.mark.parametrize(
    ("slide_index", "alternate_variant", "expected_marker"),
    [
        (1, "diagonal_flow", "c-problem"),
        (2, "edge_to_edge", "c-insight-edge_to_edge"),
        (6, "radial", "c-system"),
        (7, "diagonal_flow", "c-shift-diagonal_flow"),
    ],
)
def test_new_archetypes_have_materially_distinct_controlled_variants(deck_spec, source_package, slide_index, alternate_variant, expected_marker):
    baseline = compile_deck_spec(deck_spec, source_package)
    payload = deck_spec.model_dump(mode="json", by_alias=True)
    payload["slides"][slide_index]["composition"]["variant"] = alternate_variant
    alternate = DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    changed = compile_deck_spec(alternate, source_package)
    assert changed.slides[slide_index].content_sha256 != baseline.slides[slide_index].content_sha256
    assert expected_marker in changed.slides[slide_index].section_html


def test_customer_source_package_is_never_global_embedding_input(source_package):
    assert source_package.embedding_policy.scope == "request_data_only"
    assert source_package.embedding_policy.global_knowledge_eligible is False
    assert source_package.embedding_policy.embedding_action == "none"
    package_root = Path(__file__).resolve().parents[2] / "app" / "instant_deck_spec"
    implementation = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))
    assert "embedding_service" not in implementation
    assert "vector_retrieval_service" not in implementation
    assert "build_embedding_indexing_intent" not in implementation
    assert "openai_provider" not in implementation
    assert "from openai" not in implementation
    assert "import openai" not in implementation
    assert "import httpx" not in implementation
    assert "import requests" not in implementation


def test_failed_compilation_cannot_change_current_design_version(deck_spec, source_package):
    state = OfflinePublicationState(current_design_version_id="designver_previous", published_design_version_ids=("designver_previous",))
    payload = deck_spec.model_dump(mode="json", by_alias=True)
    payload["slides"][0]["evidence_refs"].append("fact_missing")
    invalid = DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    with pytest.raises(DeckSpecCompilationError):
        compile_deck_spec(invalid, source_package)
    with pytest.raises(OfflinePublicationRejected):
        build_publication_candidate(design_version_id="designver_failed", compiled=None, chromium_report=None)
    assert state.current_design_version_id == "designver_previous"
    assert state.published_design_version_ids == ("designver_previous",)


def test_complete_browser_identity_is_required_for_publication(deck_spec, source_package):
    compiled = compile_deck_spec(deck_spec, source_package)
    report = {
        "passed": True,
        "deckContentSha256": compiled.content_sha256,
        "slides": [{"slideId": slide.slide_id, "passed": True} for slide in compiled.slides],
    }
    candidate = build_publication_candidate(
        design_version_id="designver_offline_candidate",
        compiled=compiled,
        chromium_report=report,
    )
    state = apply_publication_candidate(OfflinePublicationState(current_design_version_id="designver_previous"), candidate)
    assert state.current_design_version_id == "designver_offline_candidate"
    tampered = dict(report, deckContentSha256="0" * 64)
    with pytest.raises(OfflinePublicationRejected):
        build_publication_candidate(design_version_id="designver_tampered", compiled=compiled, chromium_report=tampered)


def test_new_feature_boundary_is_not_imported_by_runtime():
    app_root = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for path in app_root.rglob("*.py"):
        if "instant_deck_spec" in path.parts:
            continue
        if "app.instant_deck_spec" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(app_root)))
    assert offenders == []
