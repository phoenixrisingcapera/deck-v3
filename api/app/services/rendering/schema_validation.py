from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.db.models import DeckSlide, DesignVersion, GeneratedSlide, InstantDeckCompilation
from app.schemas.generation import GeneratedDeckPayload

PACKAGE_ROOT = Path(__file__).resolve().parents[4] / "deck_aistack_codes_api_prompt_package"
GENERATED_DECK_SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "generated_deck.schema.json"

BLOCK_KINDS = {"headline", "body", "metric", "chart", "table", "image", "label", "footer"}
SLIDE_TYPES = {"problem", "solution", "market", "traction", "competition", "team", "funding", "source_slide"}


class CompiledArtifactRegenerationRequired(ValueError):
    code = "compiled_artifact_regeneration_required"

    def __init__(self, message: str = "This earlier compiled HTML artifact cannot prove exact source coverage and must be regenerated before export.") -> None:
        self.message = message
        super().__init__(message)


def load_generated_deck_schema() -> dict:
    if GENERATED_DECK_SCHEMA_PATH.exists():
        return json.loads(GENERATED_DECK_SCHEMA_PATH.read_text(encoding="utf-8"))

    # Fallback keeps local generation available even if the package moves.
    return {
        "type": "object",
        "required": ["status", "deck", "slides", "quality"],
    }


def validate_generated_deck(value: object) -> GeneratedDeckPayload:
    # Pydantic validation is the backend gate before generated JSON is returned or persisted.
    return GeneratedDeckPayload.model_validate(value)


def validate_source_labels(value: Any, *, slide_ids: set[str], block_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"ok": False, "slides": [], "messages": [{"code": "payload_required"}]}
    slides_value = value.get("slides")
    if not isinstance(slides_value, list):
        return {"ok": False, "slides": [], "messages": [{"code": "slides_required"}]}
    slides: list[dict[str, Any]] = []
    messages: list[dict[str, str]] = []
    for slide_value in slides_value:
        if not isinstance(slide_value, dict):
            continue
        slide_id = str(slide_value.get("slideId") or slide_value.get("id") or "").strip()
        if slide_id not in slide_ids:
            messages.append({"code": "slide_ignored", "id": slide_id})
            continue
        slide_type = str(slide_value.get("semanticSlideType") or "source_slide").strip().lower()
        if slide_type not in SLIDE_TYPES:
            slide_type = "source_slide"
        blocks: list[dict[str, Any]] = []
        for block_value in slide_value.get("blocks") or []:
            if not isinstance(block_value, dict):
                continue
            block_id = str(block_value.get("blockId") or block_value.get("id") or "").strip()
            if block_id not in block_ids:
                messages.append({"code": "block_ignored", "id": block_id})
                continue
            block_kind = str(block_value.get("blockKind") or "body").strip().lower()
            if block_kind not in BLOCK_KINDS:
                block_kind = "body"
            blocks.append({"blockId": block_id, "blockKind": block_kind, "semanticRole": str(block_value.get("semanticRole") or "supporting_text")[:80]})
        slides.append({"slideId": slide_id, "semanticSlideType": slide_type, "summary": str(slide_value.get("summary") or "")[:800] or None, "blocks": blocks})
    return {"ok": bool(slides), "slides": slides, "messages": messages}


def validate_design_version_slides(db: Session, deck_id: str, design_version_id: str) -> list:
    version = (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generation_job),
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.source_lineage),
        )
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == design_version_id)
        .one_or_none()
    )
    if version is None:
        raise ValueError("Design version not found")
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    if not slides:
        raise ValueError("No generated slides found")
    if version.render_mode == "html_compiled.v1":
        compilation = (
            db.query(InstantDeckCompilation)
            .filter(InstantDeckCompilation.design_version_id == version.id)
            .one_or_none()
        )
        if compilation is None or compilation.status != "compiled" or not compilation.manifest_json:
            raise ValueError("HTML design version is missing its validated compilation manifest.")
        if any(slide.render_mode != "html_compiled.v1" or slide.render_schema_json is not None or not slide.section_id for slide in slides):
            raise ValueError("HTML design version contains inconsistent slide discriminators.")
        manifest = compilation.manifest_json
        if not isinstance(manifest, dict):
            raise ValueError("HTML design version is missing its validated compilation manifest.")
        manifest_slides = manifest.get("slides")
        coverage_keys = {
            "generatedSlideCount",
            "requestedSourceSlideCount",
            "sourceCoverage",
            "groundedFactTraceability",
            "groundedMetricTraceability",
        }
        present_coverage_keys = coverage_keys.intersection(manifest)
        legacy_inference = not present_coverage_keys
        if present_coverage_keys and present_coverage_keys != coverage_keys:
            raise CompiledArtifactRegenerationRequired(
                "This earlier compiled HTML artifact has partial source-coverage metadata and must be regenerated before export."
            )
        persisted_ids = {slide.id for slide in slides}
        generation_job = version.generation_job
        original_requested_values = (
            generation_job.selected_source_slide_ids_json
            if generation_job is not None
            else None
        )
        original_request_is_ambiguous = (
            not isinstance(original_requested_values, list)
            or not original_requested_values
            or any(not isinstance(value, str) or not value.strip() for value in (original_requested_values or []))
        )
        original_requested_source_ids = (
            [value.strip() for value in original_requested_values]
            if not original_request_is_ambiguous
            else []
        )
        if len(original_requested_source_ids) != len(set(original_requested_source_ids)):
            original_request_is_ambiguous = True
        manifest_id_list = [
            str(item.get("generatedSlideId"))
            for item in (manifest_slides or [])
            if isinstance(item, dict) and item.get("generatedSlideId")
        ]
        manifest_ids = set(manifest_id_list)
        advisory = manifest.get("evidencePolicy") == "advisory-draft.v1"
        source_coverage_value = manifest.get("sourceCoverage")
        source_coverage = source_coverage_value if isinstance(source_coverage_value, dict) else {}
        requested_source_ids = list(source_coverage.get("requestedSourceSlideIds") or [])
        covered_source_ids = list(source_coverage.get("coveredSourceSlideIds") or [])
        missing_source_ids = list(source_coverage.get("missingSourceSlideIds") or [])
        evidence_backed_source_ids = list(source_coverage.get("evidenceBackedSourceSlideIds") or [])
        omitted_source_ids = list(source_coverage.get("omittedSourceSlideIds") or [])
        persisted_source_ids: set[str] = set()
        inferred_source_ids: list[str] = []
        inferred_source_seen: set[str] = set()
        lineage_matches_manifest = True
        manifest_by_id = {
            str(item.get("generatedSlideId")): item
            for item in (manifest_slides or [])
            if isinstance(item, dict) and item.get("generatedSlideId")
        }
        for slide in slides:
            manifest_item = manifest_by_id.get(slide.id) or {}
            manifest_lineage = [str(value) for value in (manifest_item.get("sourceSlideIds") or [])]
            persisted_lineage = [
                item.source_slide_id
                for item in sorted(slide.source_lineage, key=lambda value: value.lineage_order)
            ]
            persisted_source_ids.update(persisted_lineage)
            for source_id in manifest_lineage:
                if source_id not in inferred_source_seen:
                    inferred_source_seen.add(source_id)
                    inferred_source_ids.append(source_id)
            if (
                (not advisory and not manifest_lineage)
                or len(manifest_lineage) != len(set(manifest_lineage))
                or len(persisted_lineage) != len(set(persisted_lineage))
                or manifest_lineage != persisted_lineage
            ):
                lineage_matches_manifest = False
        if legacy_inference:
            requested_source_ids = inferred_source_ids
            covered_source_ids = list(inferred_source_ids)
            generated_slide_count = len(manifest_slides or [])
            requested_source_count = len(requested_source_ids)
            coverage_complete = bool(requested_source_ids)
        else:
            generated_slide_count = manifest.get("generatedSlideCount")
            requested_source_count = manifest.get("requestedSourceSlideCount")
            coverage_complete = source_coverage.get("complete") is True
        grounded_traceability = manifest.get("groundedFactTraceability") if not legacy_inference else []
        traceability_valid = isinstance(grounded_traceability, list)
        traceability_by_id: dict[str, dict[str, Any]] = {}
        if traceability_valid:
            for trace in grounded_traceability:
                if not isinstance(trace, dict):
                    traceability_valid = False
                    break
                fact_id = trace.get("factId")
                source_type = trace.get("sourceType")
                source_id = trace.get("sourceId")
                trace_source_ids = trace.get("sourceSlideIds")
                if (
                    not isinstance(fact_id, str)
                    or not fact_id
                    or fact_id in traceability_by_id
                    or not isinstance(source_type, str)
                    or not source_type
                    or not isinstance(source_id, str)
                    or not source_id
                    or not isinstance(trace_source_ids, list)
                    or len(trace_source_ids) != len(set(trace_source_ids))
                    or not set(trace_source_ids) <= set(requested_source_ids)
                    or (source_type == "source_slide" and trace_source_ids != [source_id])
                    or (source_type != "source_slide" and source_id in set(requested_source_ids))
                ):
                    traceability_valid = False
                    break
                traceability_by_id[fact_id] = trace
        if not legacy_inference and traceability_valid:
            for item in manifest_slides or []:
                if not isinstance(item, dict):
                    traceability_valid = False
                    break
                item_lineage = set(item.get("sourceSlideIds") or [])
                referenced_fact_ids = {
                    str(fact_id)
                    for element in (item.get("elements") or [])
                    if isinstance(element, dict)
                    for fact_id in (element.get("sourceFactIds") or [])
                }
                if not referenced_fact_ids <= set(traceability_by_id):
                    traceability_valid = False
                    break
                if any(
                    set(traceability_by_id[fact_id].get("sourceSlideIds") or []) - item_lineage
                    for fact_id in referenced_fact_ids
                ):
                    traceability_valid = False
                    break
        grounded_metric_traceability = manifest.get("groundedMetricTraceability") if not legacy_inference else []
        metric_traceability_valid = isinstance(grounded_metric_traceability, list)
        metric_traceability_by_key: dict[str, dict[str, Any]] = {}
        if metric_traceability_valid:
            for trace in grounded_metric_traceability:
                if not isinstance(trace, dict):
                    metric_traceability_valid = False
                    break
                metric_key = trace.get("metricKey")
                source_type = trace.get("sourceType")
                source_id = trace.get("sourceId")
                trace_source_ids = trace.get("sourceSlideIds")
                if (
                    not isinstance(metric_key, str) or not metric_key or metric_key in metric_traceability_by_key
                    or not isinstance(source_type, str) or not source_type
                    or not isinstance(source_id, str) or not source_id
                    or not isinstance(trace_source_ids, list) or not trace_source_ids
                    or len(trace_source_ids) != len(set(trace_source_ids))
                    or not set(trace_source_ids) <= set(requested_source_ids)
                    or (source_type == "source_slide" and trace_source_ids != [source_id])
                    or (source_type != "source_slide" and source_id in set(requested_source_ids))
                ):
                    metric_traceability_valid = False
                    break
                metric_traceability_by_key[metric_key] = trace
        if not legacy_inference and metric_traceability_valid:
            for item in manifest_slides or []:
                if not isinstance(item, dict):
                    metric_traceability_valid = False
                    break
                item_lineage = set(item.get("sourceSlideIds") or [])
                referenced_metric_keys = {
                    str(metric_key)
                    for element in (item.get("elements") or [])
                    if isinstance(element, dict)
                    for metric_key in (element.get("metricKeys") or [])
                }
                if not referenced_metric_keys <= set(metric_traceability_by_key):
                    metric_traceability_valid = False
                    break
                if any(
                    set(metric_traceability_by_key[metric_key].get("sourceSlideIds") or []) - item_lineage
                    for metric_key in referenced_metric_keys
                ):
                    metric_traceability_valid = False
                    break
        referenced_fact_ids = {
            str(fact_id)
            for item in (manifest_slides or [])
            if isinstance(item, dict)
            for element in (item.get("elements") or [])
            if isinstance(element, dict)
            for fact_id in (element.get("sourceFactIds") or [])
        }
        referenced_metric_keys = {
            str(metric_key)
            for item in (manifest_slides or [])
            if isinstance(item, dict)
            for element in (item.get("elements") or [])
            if isinstance(element, dict)
            for metric_key in (element.get("metricKeys") or [])
        }
        available_evidence_source_ids = {
            str(source_id)
            for trace in [*traceability_by_id.values(), *metric_traceability_by_key.values()]
            for source_id in (trace.get("sourceSlideIds") or [])
        }
        reconstructed_evidence_source_ids = {
            str(source_id)
            for identity, trace in traceability_by_id.items()
            if identity in referenced_fact_ids
            for source_id in (trace.get("sourceSlideIds") or [])
        } | {
            str(source_id)
            for identity, trace in metric_traceability_by_key.items()
            if identity in referenced_metric_keys
            for source_id in (trace.get("sourceSlideIds") or [])
        }
        reconstructed_covered_source_ids = [
            source_id for source_id in requested_source_ids if source_id in reconstructed_evidence_source_ids
        ]
        reconstructed_omitted_source_ids = [
            source_id for source_id in requested_source_ids if source_id not in available_evidence_source_ids
        ]
        generation_context = generation_job.llm_context_json if generation_job is not None and isinstance(generation_job.llm_context_json, dict) else {}
        source_fact_package = generation_context.get("sourceFactPackage") if isinstance(generation_context.get("sourceFactPackage"), dict) else None
        complete_fact_ids = {
            str(item.get("factId") or item.get("id"))
            for item in ((source_fact_package or {}).get("facts") or [])
            if isinstance(item, dict) and (item.get("factId") or item.get("id"))
        }
        complete_metric_keys = {
            str(item.get("metricKey"))
            for item in (generation_context.get("groundedMetrics") or [])
            if isinstance(item, dict) and item.get("metricKey")
        }
        complete_provenance_valid = (
            (source_fact_package is None or set(traceability_by_id) == complete_fact_ids)
            and (not isinstance(generation_context.get("groundedMetrics"), list) or set(metric_traceability_by_key) == complete_metric_keys)
        )
        owned_source_ids = {
            row[0]
            for row in db.query(DeckSlide.id).filter(
                DeckSlide.deck_id == deck_id,
                DeckSlide.id.in_(persisted_source_ids),
            ).all()
        } if persisted_source_ids else set()
        invalid = (
            not isinstance(manifest_slides, list)
            or (not legacy_inference and manifest.get("contractVersion") != "compiled-html-deck-manifest.v2")
            or generated_slide_count != len(slides)
            or len(manifest_id_list) != len(manifest_slides)
            or len(manifest_id_list) != len(manifest_ids)
            or manifest_ids != persisted_ids
            or (not advisory and not coverage_complete)
            or (not legacy_inference and not isinstance(source_coverage_value, dict))
            or (not legacy_inference and manifest.get("coverageComplete") is not True)
            or requested_source_count != len(requested_source_ids)
            or len(requested_source_ids) != len(set(requested_source_ids))
            or len(covered_source_ids) != len(set(covered_source_ids))
            or (not legacy_inference and covered_source_ids != evidence_backed_source_ids)
            or (not legacy_inference and covered_source_ids != reconstructed_covered_source_ids)
            or (not legacy_inference and omitted_source_ids != reconstructed_omitted_source_ids)
            or (not advisory and not legacy_inference and reconstructed_evidence_source_ids != available_evidence_source_ids)
            or (not legacy_inference and len(omitted_source_ids) != len(set(omitted_source_ids)))
            or (not legacy_inference and bool(set(covered_source_ids) & set(omitted_source_ids)))
            or (not advisory and not legacy_inference and set(covered_source_ids) | set(omitted_source_ids) != set(requested_source_ids))
            or (not advisory and bool(missing_source_ids))
            or (not advisory and persisted_source_ids != set(requested_source_ids))
            or not persisted_source_ids <= set(requested_source_ids)
            or owned_source_ids != persisted_source_ids
            or not lineage_matches_manifest
            or not traceability_valid
            or not metric_traceability_valid
            or not complete_provenance_valid
        )
        original_request_mismatch = (
            original_request_is_ambiguous
            or requested_source_ids != original_requested_source_ids
            or (not advisory and persisted_source_ids != set(original_requested_source_ids))
            or not persisted_source_ids <= set(original_requested_source_ids)
        )
        if original_request_mismatch:
            raise CompiledArtifactRegenerationRequired(
                "This compiled HTML artifact cannot prove exact coverage of its original requested source slides and must be regenerated before export."
            )
        if invalid and legacy_inference:
            raise CompiledArtifactRegenerationRequired()
        if invalid:
            raise ValueError("HTML design version persistence does not match its complete compiled manifest.")
        return slides
    missing = [s.id for s in slides if not s.render_schema_json]
    if missing:
        raise ValueError(f"Generated slides missing render_schema_json: {missing}")
    return slides
