"""Fail-closed semantic validation for ``deck_spec.v1``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .grammar import STRUCTURAL_GRAMMARS
from .models import DeckSpec, NormalizedSourcePackage, SlideArchetype, SlideSpec, VisualType


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class DeckSpecValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        summary = "; ".join(f"{issue.code}@{issue.path}" for issue in self.issues)
        super().__init__(summary or "deck_spec_validation_failed")


def _duplicates(values: Iterable[str | int]) -> list[str | int]:
    seen: set[str | int] = set()
    duplicates: list[str | int] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _issue(issues: list[ValidationIssue], code: str, path: str, message: str) -> None:
    issues.append(ValidationIssue(code=code, path=path, message=message))


def _validate_source_package(package: NormalizedSourcePackage, issues: list[ValidationIssue]) -> None:
    source_ids = [slide.source_slide_id for slide in package.source_slides]
    positions = [slide.position for slide in package.source_slides]
    if positions != list(range(1, len(positions) + 1)):
        _issue(issues, "invalid_source_order", "source_package.source_slides", "Source slides must be contiguous and ordered.")
    for duplicate in _duplicates(source_ids):
        _issue(issues, "duplicate_source_slide_id", "source_package.source_slides", str(duplicate))

    reference_ids = {row.reference_id for row in package.source_references}
    fact_ids = {row.fact_id for row in package.facts}
    claim_ids = {row.claim_id for row in package.claims}
    number_ids = {row.number_id for row in package.numbers}
    asset_ids = {row.asset_id for row in package.assets}

    identity_groups = {
        "source_reference": [row.reference_id for row in package.source_references],
        "fact": [row.fact_id for row in package.facts],
        "claim": [row.claim_id for row in package.claims],
        "number": [row.number_id for row in package.numbers],
        "asset": [row.asset_id for row in package.assets],
        "brand_role": [row.role_id for row in package.brand.roles],
    }
    for kind, identifiers in identity_groups.items():
        for duplicate in _duplicates(identifiers):
            _issue(issues, f"duplicate_{kind}_id", f"source_package.{kind}", str(duplicate))

    for row in package.source_references:
        if row.source_slide_id not in source_ids:
            _issue(issues, "unknown_reference_source_slide", f"source_references.{row.reference_id}", row.source_slide_id)
    for row in package.facts:
        for reference_id in row.source_reference_ids:
            if reference_id not in reference_ids:
                _issue(issues, "unknown_fact_source_reference", f"facts.{row.fact_id}", reference_id)
    for row in package.claims:
        for fact_id in row.fact_ids:
            if fact_id not in fact_ids:
                _issue(issues, "unknown_claim_fact", f"claims.{row.claim_id}", fact_id)
        for reference_id in row.source_reference_ids:
            if reference_id not in reference_ids:
                _issue(issues, "unknown_claim_source_reference", f"claims.{row.claim_id}", reference_id)
    for row in package.numbers:
        for reference_id in row.source_reference_ids:
            if reference_id not in reference_ids:
                _issue(issues, "unknown_number_source_reference", f"numbers.{row.number_id}", reference_id)
    for row in package.assets:
        for reference_id in row.source_reference_ids:
            if reference_id not in reference_ids:
                _issue(issues, "unknown_asset_source_reference", f"assets.{row.asset_id}", reference_id)

    for slide in package.source_slides:
        for identifier, allowed, kind in (
            (slide.fact_ids, fact_ids, "fact"),
            (slide.claim_ids, claim_ids, "claim"),
            (slide.number_ids, number_ids, "number"),
            (slide.asset_ids, asset_ids, "asset"),
        ):
            for value in identifier:
                if value not in allowed:
                    _issue(issues, f"unknown_slide_{kind}", f"source_slides.{slide.source_slide_id}", value)

    if package.embedding_policy.global_knowledge_eligible is not False or package.embedding_policy.embedding_action != "none":
        _issue(issues, "customer_global_embedding_forbidden", "source_package.embedding_policy", "Customer source must remain request-only.")


def _visual_evidence(slide: SlideSpec) -> Iterable[tuple[str, list[str]]]:
    for index, item in enumerate(slide.visual.items):
        yield f"visual.items[{index}]", item.evidence_refs
    for index, edge in enumerate(slide.visual.edges):
        yield f"visual.edges[{index}]", edge.evidence_refs
    for index, metric in enumerate(slide.visual.metrics):
        yield f"visual.metrics[{index}]", metric.evidence_refs
    for index, series in enumerate(slide.visual.series):
        yield f"visual.series[{index}]", series.evidence_refs
        for point_index, point in enumerate(series.points):
            yield f"visual.series[{index}].points[{point_index}]", point.evidence_refs
    for index, step in enumerate(slide.visual.steps):
        yield f"visual.steps[{index}]", step.evidence_refs
    for index, person in enumerate(slide.visual.people):
        yield f"visual.people[{index}]", person.evidence_refs
    for index, quote in enumerate(slide.visual.quotes):
        yield f"visual.quotes[{index}]", quote.evidence_refs


def _validate_visual_contract(slide: SlideSpec, path: str, issues: list[ValidationIssue]) -> None:
    visual = slide.visual
    populated = {
        "items": bool(visual.items),
        "edges": bool(visual.edges),
        "metrics": bool(visual.metrics),
        "series": bool(visual.series),
        "steps": bool(visual.steps),
        "people": bool(visual.people),
        "quotes": bool(visual.quotes),
    }
    allowed_arrays = {
        VisualType.TYPOGRAPHIC: set(),
        VisualType.IMAGE: {"items"},
        VisualType.METRIC: {"metrics"},
        VisualType.PROCESS: {"steps"},
        VisualType.TIMELINE: {"steps"},
        VisualType.SYSTEM_MAP: {"items", "edges"},
        VisualType.COMPARISON: {"items"},
        VisualType.MARKET_MAP: {"items", "series"},
        VisualType.PROOF_STRIP: {"metrics", "items"},
        VisualType.PEOPLE: {"people"},
        VisualType.CAPITAL_PLAN: {"items", "metrics", "steps"},
        VisualType.QUOTE: {"quotes"},
        VisualType.MATRIX: {"items"},
    }[visual.type]
    for name, has_values in populated.items():
        if has_values and name not in allowed_arrays:
            _issue(issues, "irrelevant_visual_array", f"{path}.visual.{name}", f"{visual.type.value} cannot use {name}.")

    if visual.type in {VisualType.PROCESS, VisualType.TIMELINE} and not 3 <= len(visual.steps) <= 7:
        _issue(issues, "invalid_step_cardinality", f"{path}.visual.steps", "Pathways and timelines require 3-7 steps.")
    if visual.type == VisualType.METRIC and not 1 <= len(visual.metrics) <= 4:
        _issue(issues, "invalid_metric_cardinality", f"{path}.visual.metrics", "Metric proof requires 1-4 metrics.")
    if visual.type == VisualType.SYSTEM_MAP:
        if not 3 <= len(visual.items) <= 8:
            _issue(issues, "invalid_system_item_cardinality", f"{path}.visual.items", "System maps require 3-8 items.")
        if len(visual.edges) < 2:
            _issue(issues, "invalid_system_edge_cardinality", f"{path}.visual.edges", "System maps require at least two relationships.")
        item_ids = {item.id for item in visual.items}
        for edge_index, edge in enumerate(visual.edges):
            if edge.from_id not in item_ids or edge.to not in item_ids:
                _issue(issues, "unknown_system_edge_endpoint", f"{path}.visual.edges[{edge_index}]", f"{edge.from_id}->{edge.to}")
    if slide.archetype == SlideArchetype.PROBLEM_LANDSCAPE and not 3 <= len(visual.items) <= 6:
        _issue(issues, "invalid_problem_item_cardinality", f"{path}.visual.items", "Problem landscapes require 3-6 causal signals.")
    if slide.archetype == SlideArchetype.KEY_INSIGHT and not 2 <= len(visual.items) <= 4:
        _issue(issues, "invalid_insight_proof_cardinality", f"{path}.visual.items", "Key insights require 2-4 supporting proof items.")
    if slide.archetype == SlideArchetype.COMPARISON_SHIFT:
        groups = {item.group for item in visual.items if item.group}
        if len(groups) != 2 or any(sum(item.group == group for item in visual.items) < 2 for group in groups):
            _issue(issues, "invalid_comparison_groups", f"{path}.visual.items", "Comparison shifts require exactly two groups with at least two items each.")
    if visual.type == VisualType.IMAGE and not visual.asset_ref:
        _issue(issues, "image_asset_required", f"{path}.visual.asset_ref", "Image visuals require one approved asset.")


def validate_deck_spec(spec: DeckSpec, source_package: NormalizedSourcePackage) -> None:
    issues: list[ValidationIssue] = []
    _validate_source_package(source_package, issues)

    if spec.source_package_id != source_package.package_id:
        _issue(issues, "source_package_identity_mismatch", "source_package_id", spec.source_package_id)
    if spec.source_checksum != source_package.source_checksum:
        _issue(issues, "source_checksum_mismatch", "source_checksum", spec.source_checksum)

    slide_ids = [slide.slide_id for slide in spec.slides]
    positions = [slide.position for slide in spec.slides]
    for duplicate in _duplicates(slide_ids):
        _issue(issues, "duplicate_slide_id", "slides", str(duplicate))
    for duplicate in _duplicates(positions):
        _issue(issues, "duplicate_slide_position", "slides", str(duplicate))
    if positions != list(range(1, len(spec.slides) + 1)):
        _issue(issues, "invalid_slide_order", "slides", "Slide positions must be sorted and contiguous from one.")
    if spec.slides and spec.slides[0].archetype != SlideArchetype.THESIS_COVER:
        _issue(issues, "opening_role_invalid", "slides[0]", "The opening slide must be thesis_cover.")
    if spec.slides and spec.slides[-1].archetype in {SlideArchetype.THESIS_COVER, SlideArchetype.PARTNERSHIP_ECOSYSTEM}:
        _issue(issues, "closing_role_invalid", f"slides[{len(spec.slides)-1}]", "The close cannot be a cover or partner directory.")

    package_source_ids = {slide.source_slide_id for slide in source_package.source_slides}
    represented = spec.narrative.represented_source_slide_ids
    omitted = spec.narrative.omitted_source_slide_ids
    if _duplicates(represented) or _duplicates(omitted):
        _issue(issues, "duplicate_source_coverage_reference", "narrative", "Coverage references must be unique.")
    if set(represented) & set(omitted):
        _issue(issues, "overlapping_source_coverage", "narrative", "A source slide cannot be represented and omitted.")
    if set(represented) | set(omitted) != package_source_ids:
        _issue(issues, "incomplete_source_coverage", "narrative", "Every source slide must be represented or explicitly omitted.")
    omission_by_id = {slide.source_slide_id: slide for slide in source_package.source_slides}
    for source_id in omitted:
        if source_id not in omission_by_id or not omission_by_id[source_id].omission_eligible:
            _issue(issues, "ineligible_source_omission", "narrative.omitted_source_slide_ids", source_id)

    valid_evidence = (
        {row.fact_id for row in source_package.facts}
        | {row.claim_id for row in source_package.claims}
        | {row.number_id for row in source_package.numbers}
    )
    valid_assets = {row.asset_id for row in source_package.assets}
    valid_roles = {row.role_id for row in source_package.brand.roles}
    art_roles = [
        spec.art_direction.paper_role,
        spec.art_direction.ink_role,
        spec.art_direction.signature_role,
        *spec.art_direction.support_roles,
    ]
    for role in art_roles:
        if role not in valid_roles:
            _issue(issues, "unknown_brand_role", "art_direction", role)

    for index, slide in enumerate(spec.slides):
        path = f"slides[{index}]"
        if _duplicates(slide.evidence_refs):
            _issue(issues, "duplicate_slide_evidence", f"{path}.evidence_refs", slide.slide_id)
        for evidence_id in slide.evidence_refs:
            if evidence_id not in valid_evidence:
                _issue(issues, "missing_evidence_reference", f"{path}.evidence_refs", evidence_id)
        for source_id in slide.source_slide_ids:
            if source_id not in package_source_ids:
                _issue(issues, "missing_source_slide_reference", f"{path}.source_slide_ids", source_id)
        for asset_id in slide.asset_refs:
            if asset_id not in valid_assets:
                _issue(issues, "malformed_or_missing_asset", f"{path}.asset_refs", asset_id)
        if slide.visual.asset_ref and slide.visual.asset_ref not in valid_assets:
            _issue(issues, "malformed_or_missing_asset", f"{path}.visual.asset_ref", slide.visual.asset_ref)
        if slide.composition.background_role not in valid_roles or slide.composition.accent_role not in valid_roles:
            _issue(issues, "unknown_composition_brand_role", f"{path}.composition", slide.slide_id)
        if slide.composition.primitive != slide.archetype:
            _issue(issues, "incompatible_primitive", f"{path}.composition.primitive", slide.slide_id)
        grammar = STRUCTURAL_GRAMMARS.get(slide.archetype)
        allowed_variants = set(grammar.variants) if grammar is not None else None
        if allowed_variants is not None and slide.composition.variant not in allowed_variants:
            _issue(issues, "unsupported_primitive_variant", f"{path}.composition.variant", slide.composition.variant.value)
        allowed_visuals = set(grammar.visual_types) if grammar is not None else None
        if allowed_visuals is not None and slide.visual.type not in allowed_visuals:
            _issue(issues, "unsupported_visual_for_archetype", f"{path}.visual.type", slide.visual.type.value)
        if grammar is not None and slide.composition.density not in grammar.permitted_density:
            _issue(issues, "unsupported_primitive_density", f"{path}.composition.density", slide.composition.density)

        copy_ids = [block.id for block in slide.copy_blocks]
        for duplicate in _duplicates(copy_ids):
            _issue(issues, "duplicate_copy_id", f"{path}.copy_blocks", str(duplicate))
        for block_index, block in enumerate(slide.copy_blocks):
            for evidence_id in block.evidence_refs:
                if evidence_id not in valid_evidence:
                    _issue(issues, "missing_evidence_reference", f"{path}.copy_blocks[{block_index}]", evidence_id)
                if evidence_id not in slide.evidence_refs:
                    _issue(issues, "copy_evidence_not_declared_by_slide", f"{path}.copy_blocks[{block_index}]", evidence_id)
        for evidence_path, evidence_refs in _visual_evidence(slide):
            for evidence_id in evidence_refs:
                if evidence_id not in valid_evidence:
                    _issue(issues, "missing_evidence_reference", f"{path}.{evidence_path}", evidence_id)
                if evidence_id not in slide.evidence_refs:
                    _issue(issues, "visual_evidence_not_declared_by_slide", f"{path}.{evidence_path}", evidence_id)

        _validate_visual_contract(slide, path, issues)
        budget = grammar.text_budget if grammar is not None else None
        total_copy = len(slide.headline) + len(slide.subhead or "") + sum(len(block.text) for block in slide.copy_blocks)
        if budget is not None and total_copy > budget:
            _issue(issues, "primitive_text_budget_exceeded", path, f"{total_copy}>{budget}")

    represented_by_slides = {source_id for slide in spec.slides for source_id in slide.source_slide_ids}
    if represented_by_slides != set(represented):
        _issue(issues, "slide_coverage_mismatch", "slides", "Slide source references must equal narrative represented coverage.")

    if issues:
        raise DeckSpecValidationError(issues)
