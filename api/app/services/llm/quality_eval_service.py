from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import ValidationError

from app.schemas.smart_deck import RenderSchema

PROMPT_VERSION = "smart-deck-generation-prompt.v2"
EVAL_SCHEMA_VERSION = "smart-deck-quality-eval.v1"
MAX_REPAIR_PASSES = 1

# These are conservative metadata defaults only. Real provider invoice/cost data
# should override them when the provider response includes usage and billing.
MODEL_COST_PER_1K_TOKENS_USD: dict[str, tuple[Decimal, Decimal]] = {
    "openai/gpt-4.1-mini": (Decimal("0.0004"), Decimal("0.0016")),
    "openai/gpt-4o": (Decimal("0.005"), Decimal("0.015")),
    "gpt-4.1": (Decimal("0.002"), Decimal("0.008")),
    "gpt-5": (Decimal("0.002"), Decimal("0.008")),
    "claude-sonnet-4-5": (Decimal("0.003"), Decimal("0.015")),
    "claude-opus-4-1": (Decimal("0.015"), Decimal("0.075")),
}


@dataclass(frozen=True)
class LlmUsageMetadata:
    promptVersion: str
    provider: str
    model: str | None
    promptTokens: int | None
    completionTokens: int | None
    totalTokens: int | None
    estimatedCostUsd: str | None
    costSource: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "promptVersion": self.promptVersion,
            "provider": self.provider,
            "model": self.model,
            "promptTokens": self.promptTokens,
            "completionTokens": self.completionTokens,
            "totalTokens": self.totalTokens,
            "estimatedCostUsd": self.estimatedCostUsd,
            "costSource": self.costSource,
        }


def estimate_tokens_from_text(value: str | None) -> int:
    if not value:
        return 0
    # Approximation for metadata only. Providers should supply authoritative usage.
    return max(1, math.ceil(len(value) / 4))


def build_llm_usage_metadata(
    *,
    provider: str,
    model: str | None,
    prompt_text: str | None = None,
    completion_text: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: str | Decimal | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> LlmUsageMetadata:
    prompt_tokens = prompt_tokens if prompt_tokens is not None else estimate_tokens_from_text(prompt_text)
    completion_tokens = completion_tokens if completion_tokens is not None else estimate_tokens_from_text(completion_text)
    total_tokens = None
    if prompt_tokens is not None or completion_tokens is not None:
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)

    cost_source = "provider_reported" if cost_usd is not None else "estimated"
    estimated_cost = _normalise_cost(cost_usd)
    if estimated_cost is None and model:
        estimated_cost = _estimate_cost(model, int(prompt_tokens or 0), int(completion_tokens or 0))
    if estimated_cost is None:
        cost_source = "unavailable"

    return LlmUsageMetadata(
        promptVersion=prompt_version,
        provider=provider,
        model=model,
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        totalTokens=total_tokens,
        estimatedCostUsd=estimated_cost,
        costSource=cost_source,
    )


def validate_render_schema_quality(
    render_schema: dict[str, Any],
    *,
    allowed_source_fact_ids: set[str],
    require_source_fact_ids: bool = True,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        validated_schema = RenderSchema.model_validate(render_schema).model_dump()
    except ValidationError as exc:
        return {
            "ok": False,
            "renderSchema": None,
            "errors": [
                {
                    "code": "render_schema_invalid",
                    "message": error.get("msg", "render schema validation failed"),
                    "location": list(error.get("loc", [])),
                }
                for error in exc.errors()
            ],
            "warnings": [],
            "sourceFactIds": [],
            "unknownSourceFactIds": [],
        }

    analytics = validated_schema.get("analytics") if isinstance(validated_schema.get("analytics"), dict) else {}
    source_fact_ids = [str(item) for item in analytics.get("sourceFactIds") or [] if str(item).strip()]
    source_facts_used = [str(item) for item in analytics.get("sourceFactsUsed") or [] if str(item).strip()]
    unknown_source_fact_ids = [fact_id for fact_id in source_fact_ids if fact_id not in allowed_source_fact_ids]

    if require_source_fact_ids and allowed_source_fact_ids and not source_fact_ids:
        errors.append(
            {
                "code": "source_fact_ids_required",
                "message": "renderSchema.analytics.sourceFactIds must include at least one source fact id.",
            }
        )
    if unknown_source_fact_ids:
        errors.append(
            {
                "code": "unknown_source_fact_ids",
                "message": "renderSchema.analytics.sourceFactIds includes ids not present in sourceFactPackage.",
                "factIds": unknown_source_fact_ids,
            }
        )
    if source_fact_ids and not source_facts_used:
        warnings.append(
            {
                "code": "source_fact_labels_missing",
                "message": "renderSchema.analytics.sourceFactsUsed should describe the cited fact ids for reviewability.",
            }
        )
    if analytics.get("confidence") is None:
        warnings.append(
            {
                "code": "confidence_missing",
                "message": "renderSchema.analytics.confidence should be populated for quality review.",
            }
        )

    return {
        "ok": not errors,
        "renderSchema": validated_schema,
        "errors": errors,
        "warnings": warnings,
        "sourceFactIds": source_fact_ids,
        "unknownSourceFactIds": unknown_source_fact_ids,
    }


def evaluate_generated_payload_quality(
    render_payload: dict[str, Any],
    *,
    expected_source_slide_ids: list[str],
    source_fact_package: dict[str, Any],
    require_source_fact_ids: bool = True,
) -> dict[str, Any]:
    allowed_fact_ids = {
        str(fact.get("id"))
        for fact in source_fact_package.get("facts", [])
        if isinstance(fact, dict) and fact.get("id")
    }
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    slide_reports: list[dict[str, Any]] = []
    slides = render_payload.get("slides")
    if not isinstance(slides, list):
        errors.append({"code": "slides_required", "message": "LLM output must include a slides array."})
        slides = []
    if len(slides) != len(expected_source_slide_ids):
        errors.append(
            {
                "code": "slide_count_mismatch",
                "message": "LLM output slide count must match selected source slides.",
                "expected": len(expected_source_slide_ids),
                "actual": len(slides),
            }
        )

    seen_source_slide_ids: set[str] = set()
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            errors.append({"code": "slide_object_required", "message": f"slides[{index}] must be an object."})
            continue
        source_slide_id = str(slide.get("sourceSlideId") or "")
        if source_slide_id not in expected_source_slide_ids:
            errors.append(
                {
                    "code": "unexpected_source_slide_id",
                    "message": "LLM output referenced a source slide that was not selected.",
                    "sourceSlideId": source_slide_id,
                }
            )
        if source_slide_id in seen_source_slide_ids:
            errors.append(
                {
                    "code": "duplicate_source_slide_id",
                    "message": "LLM output duplicated a source slide.",
                    "sourceSlideId": source_slide_id,
                }
            )
        seen_source_slide_ids.add(source_slide_id)
        schema_report = validate_render_schema_quality(
            slide.get("renderSchema") if isinstance(slide.get("renderSchema"), dict) else {},
            allowed_source_fact_ids=allowed_fact_ids,
            require_source_fact_ids=require_source_fact_ids,
        )
        slide_reports.append(
            {
                "sourceSlideId": source_slide_id,
                "title": slide.get("title"),
                "ok": schema_report["ok"],
                "errors": schema_report["errors"],
                "warnings": schema_report["warnings"],
                "sourceFactIds": schema_report["sourceFactIds"],
            }
        )
        errors.extend({**error, "sourceSlideId": source_slide_id} for error in schema_report["errors"])
        warnings.extend({**warning, "sourceSlideId": source_slide_id} for warning in schema_report["warnings"])

    missing_slide_ids = [slide_id for slide_id in expected_source_slide_ids if slide_id not in seen_source_slide_ids]
    if missing_slide_ids:
        errors.append(
            {
                "code": "missing_source_slide_ids",
                "message": "LLM output omitted selected source slides.",
                "sourceSlideIds": missing_slide_ids,
            }
        )

    return {
        "schemaVersion": EVAL_SCHEMA_VERSION,
        "ok": not errors,
        "status": "pass" if not errors else "fail",
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "slides": slide_reports,
        "allowedSourceFactIds": sorted(allowed_fact_ids),
    }


def should_run_repair_pass(eval_report: dict[str, Any], *, completed_repair_passes: int) -> bool:
    if completed_repair_passes >= MAX_REPAIR_PASSES:
        return False
    return not bool(eval_report.get("ok"))


def build_repair_policy(eval_report: dict[str, Any], *, completed_repair_passes: int) -> dict[str, Any]:
    return {
        "schemaVersion": "smart-deck-repair-policy.v1",
        "maxRepairPasses": MAX_REPAIR_PASSES,
        "completedRepairPasses": completed_repair_passes,
        "repairAllowed": should_run_repair_pass(eval_report, completed_repair_passes=completed_repair_passes),
        "blockedAfterRepair": completed_repair_passes >= MAX_REPAIR_PASSES and not bool(eval_report.get("ok")),
        "errorCodes": [str(error.get("code")) for error in eval_report.get("errors", []) if isinstance(error, dict)],
    }


def build_eval_artifact_payload(
    *,
    eval_report: dict[str, Any],
    usage: LlmUsageMetadata,
    source_fact_package: dict[str, Any],
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    return {
        "schemaVersion": EVAL_SCHEMA_VERSION,
        "promptVersion": prompt_version,
        "usage": usage.model_dump(),
        "eval": eval_report,
        "sourceFactSummary": {
            "schemaVersion": source_fact_package.get("schemaVersion"),
            "factCount": source_fact_package.get("factCount"),
            "coverage": source_fact_package.get("coverage") or {},
        },
    }


def _normalise_cost(value: str | Decimal | None) -> str | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return None
    return str(decimal_value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> str | None:
    pricing = MODEL_COST_PER_1K_TOKENS_USD.get(model)
    if pricing is None:
        return None
    prompt_rate, completion_rate = pricing
    estimated = (Decimal(prompt_tokens) / Decimal(1000) * prompt_rate) + (Decimal(completion_tokens) / Decimal(1000) * completion_rate)
    return _normalise_cost(estimated)


def compact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
