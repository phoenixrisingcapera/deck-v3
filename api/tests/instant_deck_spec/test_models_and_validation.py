from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.instant_deck_spec.models import DeckSpec, NormalizedSourcePackage
from app.instant_deck_spec.validation import DeckSpecValidationError, validate_deck_spec


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _spec_payload() -> dict:
    return json.loads((FIXTURES / "angel_house_deck_spec.v1.json").read_text(encoding="utf-8"))


def _codes(exc: DeckSpecValidationError) -> set[str]:
    return {issue.code for issue in exc.issues}


def test_schema_valid_angel_house_spec_passes(deck_spec, source_package):
    validate_deck_spec(deck_spec, source_package)


def test_checked_in_schemas_are_strict_versioned_and_complete():
    schema_root = Path(__file__).resolve().parents[2] / "app" / "instant_deck_spec" / "schemas"
    deck_schema = json.loads((schema_root / "deck-spec.v1.json").read_text(encoding="utf-8"))
    source_schema = json.loads((schema_root / "instant-deck-source-package.v1.json").read_text(encoding="utf-8"))
    assert deck_schema["$id"] == "https://deck.aistack.codes/schemas/deck-spec.v1.json"
    assert source_schema["$id"] == "https://deck.aistack.codes/schemas/instant-deck-source-package.v1.json"
    assert deck_schema["additionalProperties"] is False
    assert source_schema["additionalProperties"] is False
    assert "compiler_version" in deck_schema["required"]
    archetypes = set(deck_schema["$defs"]["SlideArchetype"]["enum"])
    assert len(archetypes) == 18
    assert {
        "thesis_cover", "problem_landscape", "key_insight", "process_pathway",
        "timeline_milestones", "metric_proof", "system_map", "comparison_shift",
    } <= archetypes


def test_checked_in_source_package_is_exact_adapter_output(source_package):
    expected = NormalizedSourcePackage.model_validate_json(
        (FIXTURES / "angel_house_source_package.v1.json").read_text(encoding="utf-8"),
        strict=True,
    )
    assert expected == source_package


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda value: value.update({"surprise": True}), "extra_forbidden"),
        (lambda value: value["slides"][0].update({"archetype": "mystery_wall"}), "enum"),
        (lambda value: value["slides"][0].update({"headline": "x" * 81}), "string_too_long"),
        (lambda value: value["slides"][4].update({"subhead": "x" * 181}), "string_too_long"),
        (lambda value: value["slides"][0]["visual"].update({"type": "particle_cloud"}), "enum"),
    ],
)
def test_invalid_schema_fails_closed(mutate, expected):
    payload = _spec_payload()
    mutate(payload)
    with pytest.raises(ValidationError) as captured:
        DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    assert expected in str(captured.value)


def test_missing_evidence_invalid_order_and_duplicate_ids_fail(deck_spec, source_package):
    payload = deck_spec.model_dump(mode="json", by_alias=True)
    payload["slides"][0]["evidence_refs"].append("fact_missing")
    payload["slides"][1]["position"] = 4
    payload["slides"][1]["slide_id"] = "s01"
    invalid = DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    with pytest.raises(DeckSpecValidationError) as captured:
        validate_deck_spec(invalid, source_package)
    assert {"missing_evidence_reference", "invalid_slide_order", "duplicate_slide_id"} <= _codes(captured.value)


def test_malformed_colour_and_asset_fail_model_validation(source_package):
    payload = source_package.model_dump(mode="json")
    colour_payload = deepcopy(payload)
    colour_payload["brand"]["roles"][0]["colour"] = "warm beige"
    with pytest.raises(ValidationError):
        NormalizedSourcePackage.model_validate(colour_payload, strict=True)
    asset_payload = deepcopy(payload)
    asset_payload["assets"][0]["sha256"] = "not-a-sha"
    with pytest.raises(ValidationError):
        NormalizedSourcePackage.model_validate(asset_payload, strict=True)


def test_every_material_claim_and_deck_copy_has_provenance(deck_spec, source_package):
    reference_ids = {row.reference_id for row in source_package.source_references}
    evidence_ids = (
        {row.fact_id for row in source_package.facts}
        | {row.claim_id for row in source_package.claims}
        | {row.number_id for row in source_package.numbers}
    )
    assert all(set(row.source_reference_ids) <= reference_ids for row in source_package.facts if row.material)
    assert all(set(row.source_reference_ids) <= reference_ids and row.fact_ids for row in source_package.claims if row.material)
    for slide in deck_spec.slides:
        assert slide.evidence_refs and set(slide.evidence_refs) <= evidence_ids
        assert all(block.evidence_refs and set(block.evidence_refs) <= set(slide.evidence_refs) for block in slide.copy_blocks)


def test_every_structural_grammar_is_explicit_and_fail_closed():
    from app.instant_deck_spec.grammar import STRUCTURAL_GRAMMARS

    assert len({grammar.family for grammar in STRUCTURAL_GRAMMARS.values()}) == 7
    for grammar in STRUCTURAL_GRAMMARS.values():
        assert grammar.narrative_purpose
        assert grammar.required_content
        assert grammar.dominant_visual_element
        assert grammar.permitted_density
        assert grammar.typography_hierarchy
        assert grammar.variants
        assert grammar.prohibited_when
        assert grammar.visual_types
        assert grammar.text_budget > 0


def test_invalid_new_primitive_contracts_fail_closed(deck_spec, source_package):
    payload = deck_spec.model_dump(mode="json", by_alias=True)
    payload["slides"][6]["visual"]["edges"] = []
    payload["slides"][7]["visual"]["items"][3]["group"] = "THIRD STATE"
    invalid = DeckSpec.model_validate_json(json.dumps(payload), strict=True)
    with pytest.raises(DeckSpecValidationError) as captured:
        validate_deck_spec(invalid, source_package)
    assert {"invalid_system_edge_cardinality", "invalid_comparison_groups"} <= _codes(captured.value)
