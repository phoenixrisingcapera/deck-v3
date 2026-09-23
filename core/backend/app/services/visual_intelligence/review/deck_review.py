from __future__ import annotations

import base64
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from typing import Any, Literal
from uuid import uuid4

from PIL import Image, ImageStat
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.services.visual_intelligence.models import VisionFinding, VisionReview
from app.services.visual_intelligence.review.repair_plan import build_visual_repair_plan


RENDERED_SLIDE_TYPE = "instant_deck_rendered_slide"
CONTACT_SHEET_TYPE = "instant_deck_rendered_contact_sheet"
VISION_REVIEW_TYPE = "instant_deck_vision_review"
VISUAL_REPAIR_PLAN_TYPE = "instant_deck_visual_repair_plan"
VISION_REVIEW_ATTEMPT_TYPE = "instant_deck_vision_review_attempt"


class _LLMInvestorHandoffReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths: list[str] = Field(default_factory=list, max_length=30)
    findings: list[VisionFinding] = Field(default_factory=list, max_length=120)
    recommended_changes: list[str] = Field(default_factory=list, max_length=30)
    handoff_assessment: str = Field(min_length=1, max_length=1200)
    overall_score: int = Field(ge=0, le=100)
    narrative_score: int = Field(ge=0, le=100)
    financial_credibility_score: int = Field(ge=0, le=100)
    investor_clarity_score: int = Field(ge=0, le=100)
    visual_quality_score: int = Field(ge=0, le=100)
    brand_consistency_score: int = Field(ge=0, le=100)
    publication_blocking: Literal[False] = False


def _store_bytes(payload: bytes, *, deck_id: str, artifact_type: str, suffix: str) -> tuple[str, str]:
    digest = sha256(payload).hexdigest()
    key = f"workspaces/{deck_id}/visual-intelligence/{artifact_type}/{digest[:20]}.{suffix}"
    storage = get_upload_storage()
    if not storage.object_exists(key):
        promote_upload(storage.write_bytes(key, payload))
    return key, digest


def _upsert_artifact(
    db: Session, *, deck_id: str, artifact_type: str, artifact_key: str,
    schema_version: str, summary: str, payload_json: dict[str, Any],
    metrics_json: dict[str, Any], bucket_payload_key: str | None = None,
) -> DeckLlmArtifact:
    row = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_type=artifact_type, artifact_key=artifact_key,
    ).one_or_none()
    if row is None:
        row = DeckLlmArtifact(
            id=generate_id("visualartifact"), deck_id=deck_id,
            artifact_type=artifact_type, artifact_key=artifact_key,
        )
        db.add(row)
    row.schema_version = schema_version
    row.status = "ready"
    row.summary = summary
    row.payload_json = payload_json
    row.metrics_json = metrics_json
    row.bucket_payload_key = bucket_payload_key
    db.flush()
    return row


def _pixel_findings(slide_id: str, screenshot: bytes, metrics: dict[str, Any]) -> list[VisionFinding]:
    image = Image.open(BytesIO(screenshot)).convert("RGB")
    sample = image.resize((96, 54))
    stat = ImageStat.Stat(sample)
    luminance_spread = sum(stat.stddev) / 3
    findings: list[VisionFinding] = []
    if image.size != (1920, 1080):
        findings.append(VisionFinding(
            slide_id=slide_id, dimension="scale", severity="important",
            issue=f"Rendered slide is {image.width}x{image.height}; visual review expects 1920x1080.",
        ))
    if luminance_spread < 18:
        findings.append(VisionFinding(
            slide_id=slide_id, dimension="visual_storytelling", severity="advisory",
            issue="Rendered pixels have very little tonal variation; verify that the slide has a clear visual focal point.",
        ))
    text_count = int(metrics.get("visibleTextElementCount") or metrics.get("textElementCount") or 0)
    if text_count > 28:
        findings.append(VisionFinding(
            slide_id=slide_id, dimension="text_density", severity="important",
            issue="The rendered slide contains unusually many visible text elements and may need copy reduction.",
        ))
    return findings


def _contact_sheet(items: list[dict[str, Any]]) -> bytes:
    thumbs: list[Image.Image] = []
    for item in items:
        image = Image.open(BytesIO(item["screenshot"])).convert("RGB")
        image.thumbnail((480, 270))
        thumbs.append(image.copy())
    columns = min(4, len(thumbs))
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 480, rows * 270), (12, 16, 28))
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % columns) * 480, (index // columns) * 270))
    output = BytesIO()
    sheet.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _review_image_urls(rendered_slides: list[dict[str, Any]]) -> list[str]:
    """Bound the investor handoff review to one overview plus representative slides."""
    valid = [item for item in rendered_slides if isinstance(item.get("screenshot"), bytes)]
    if not valid:
        return []
    selected_indexes = sorted({0, len(valid) // 2, len(valid) - 1})
    payloads = [_contact_sheet(valid)]
    for index in selected_indexes:
        image = Image.open(BytesIO(valid[index]["screenshot"])).convert("RGB")
        image.thumbnail((1280, 720))
        output = BytesIO()
        image.save(output, format="JPEG", quality=86, optimize=True)
        payloads.append(output.getvalue())
    return ["data:image/" + ("png" if index == 0 else "jpeg") + ";base64," + base64.b64encode(payload).decode("ascii")
            for index, payload in enumerate(payloads)]


def _strategy_context(db: Session, deck_id: str) -> dict[str, Any]:
    row = (
        db.query(DeckLlmArtifact)
        .filter_by(deck_id=deck_id, artifact_type="instant_deck_vc_strategy", status="ready")
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    payload = row.payload_json if row is not None and isinstance(row.payload_json, dict) else {}
    return {
        "narrativeStrategy": payload.get("narrativeStrategy") or {},
        "deckArchitecture": payload.get("deckArchitecture") or [],
        "financialAnalysis": payload.get("financialAnalysis") or {},
        "investmentCommitteeReview": payload.get("investmentCommitteeReview") or {},
    }


def persist_rendered_deck_review(
    db: Session, *, deck_id: str, operation_id: str, rendered_slides: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Persist real pixels, a contact sheet, and non-blocking deterministic findings."""
    valid = [item for item in rendered_slides if isinstance(item.get("screenshot"), bytes)]
    if not valid:
        return None
    existing_review = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id,
        artifact_type=VISION_REVIEW_TYPE,
        artifact_key=f"vision-review:{operation_id}",
    ).one_or_none()
    preserved_llm_review: dict[str, Any] | None = None
    if existing_review is not None and isinstance(existing_review.payload_json, dict):
        try:
            parsed_existing = VisionReview.model_validate(existing_review.payload_json)
        except ValueError:
            parsed_existing = None
        if parsed_existing is not None and parsed_existing.review_source == "llm_assisted":
            preserved_llm_review = parsed_existing.model_dump(mode="json")
    artifact_ids: list[str] = []
    findings: list[VisionFinding] = []
    for index, item in enumerate(valid, 1):
        slide_id = str(item["slideId"])
        key, digest = _store_bytes(
            item["screenshot"], deck_id=deck_id, artifact_type=RENDERED_SLIDE_TYPE, suffix="png",
        )
        row = _upsert_artifact(
            db, deck_id=deck_id, artifact_type=RENDERED_SLIDE_TYPE,
            artifact_key=f"rendered-slide:{operation_id}:{slide_id}", schema_version="rendered-slide.v1",
            summary=f"Rendered slide {index} at 1920x1080 for visual review.",
            payload_json={"slideId": slide_id, "sha256": digest, "width": 1920, "height": 1080},
            bucket_payload_key=key, metrics_json={"publicationBlocking": False},
        )
        artifact_ids.append(row.id)
        findings.extend(_pixel_findings(slide_id, item["screenshot"], item.get("metrics") or {}))
    sheet_bytes = _contact_sheet(valid)
    sheet_key, sheet_digest = _store_bytes(
        sheet_bytes, deck_id=deck_id, artifact_type=CONTACT_SHEET_TYPE, suffix="png",
    )
    sheet = _upsert_artifact(
        db, deck_id=deck_id, artifact_type=CONTACT_SHEET_TYPE,
        artifact_key=f"contact-sheet:{operation_id}", schema_version="contact-sheet.v1",
        summary="Deck contact sheet generated from exact rendered slide pixels.",
        payload_json={"sha256": sheet_digest, "slideCount": len(valid)}, bucket_payload_key=sheet_key,
        metrics_json={"publicationBlocking": False},
    )
    artifact_ids.append(sheet.id)
    # Render-proof retries for the same immutable operation must not downgrade an
    # already-accounted LLM handoff review to the deterministic baseline. The
    # rendered artifacts are still idempotently refreshed above.
    if preserved_llm_review is not None:
        db.flush()
        return preserved_llm_review
    review = VisionReview(
        rendered_artifact_ids=artifact_ids,
        findings=findings,
        strengths=["Every reviewed slide was rendered at the canonical 1920x1080 viewport."],
    )
    payload = review.model_dump(mode="json")
    _upsert_artifact(
        db, deck_id=deck_id, artifact_type=VISION_REVIEW_TYPE,
        artifact_key=f"vision-review:{operation_id}", schema_version=review.schema_version,
        summary="Advisory rendered-pixel visual review; never a publication gate.",
        payload_json=payload,
        metrics_json={"publicationBlocking": False, "providerStarts": 0, "actualCostCents": 0},
    )
    repair_plan = build_visual_repair_plan(review)
    _upsert_artifact(
        db, deck_id=deck_id, artifact_type=VISUAL_REPAIR_PLAN_TYPE,
        artifact_key=f"visual-repair-plan:{operation_id}", schema_version=repair_plan.schema_version,
        summary="One-pass targeted visual repair plan; advisory until an accounted repair node executes it.",
        payload_json=repair_plan.model_dump(mode="json"),
        metrics_json={"publicationBlocking": False, "providerStarts": 0, "maxRepairPasses": 1},
    )
    db.flush()
    return payload


def enhance_rendered_deck_review_with_llm(
    db: Session, *, deck_id: str, operation_id: str, rendered_slides: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Judge the rendered handoff as an investor without becoming a publication gate."""
    allowance = (
        Decimal(str(settings.ai_vc_vision_review_max_cost_cents))
        if settings.ai_vc_vision_review_max_cost_cents is not None
        else None
    )
    review_row = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id,
        artifact_type=VISION_REVIEW_TYPE,
        artifact_key=f"vision-review:{operation_id}",
    ).one_or_none()
    if review_row is None or not isinstance(review_row.payload_json, dict):
        return None
    current = VisionReview.model_validate(review_row.payload_json)
    if current.review_source == "llm_assisted" or not settings.ai_vc_vision_review_enabled:
        return current.model_dump(mode="json")

    images = _review_image_urls(rendered_slides)
    if not images:
        return current.model_dump(mode="json")
    deck = db.query(Deck).filter(Deck.id == deck_id).one()
    attempt_key = f"vision-review-attempt:{operation_id}"
    previous_attempt = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_key=attempt_key,
    ).one_or_none()
    if previous_attempt is not None:
        if previous_attempt.status == "ready":
            return current.model_dump(mode="json")
        raise ValueError("Existing investor handoff review attempt is not safe to replay")

    from app.services.llm.generation_service import get_generation_provider_config
    from app.services.llm.openai_provider import call_openai_response, parse_openai_structured_response
    model = settings.openai_model
    config = get_generation_provider_config(
        db, deck, preferred_model=model, strict=True, use_case="analysis",
    )
    if config["provider"] != "openai" or config["model"] != model:
        raise ValueError("The investor handoff review provider/model is unavailable")
    attempt = DeckLlmArtifact(
        id=generate_id("visionreviewattempt"),
        deck_id=deck_id,
        artifact_type=VISION_REVIEW_ATTEMPT_TYPE,
        artifact_key=attempt_key,
        schema_version="investor-handoff-review-attempt.v1",
        status="running",
        summary="One bounded rendered-deck investor handoff review request.",
        payload_json={
            "operationId": operation_id,
            "providerStarts": 1,
            "clientRequestId": str(uuid4()),
            "model": model,
            "maxCostCents": str(allowance) if allowance is not None else None,
            "publicationBlocking": False,
        },
        metrics_json={"costKnown": False, "publicationBlocking": False},
    )
    db.add(attempt)
    db.commit()
    system = (
        "Act as a demanding venture investor and pitch-deck creative director. Review the supplied final rendered "
        "deck pixels against the supplied investment strategy. Return JSON only with exactly strengths, findings, "
        "recommended_changes, handoff_assessment, overall_score, narrative_score, financial_credibility_score, "
        "investor_clarity_score, visual_quality_score, brand_consistency_score, and publication_blocking (always false). "
        "Judge whether the deck is materially clearer, more compelling, and more capital-ready than a source-deck "
        "restyle. Assess thesis clarity, investor narrative, economic significance, selection and labelling of "
        "financial evidence, credibility, visual hierarchy, slide-to-slide rhythm, brand consistency, and whether "
        "the close creates a confident investor handoff. Findings use slide_id, issue, severity (advisory, important, "
        "or critical_for_visual_quality), and dimension (focal_point, hierarchy, balance, composition, scale, "
        "alignment, contrast, text_density, chart_readability, diagram_readability, image_quality, brand_fit, "
        "visual_storytelling, rhythm, or repetition). Do not invent facts, infer private company performance, or "
        "treat external benchmarks as company results. Critical quality concerns are internal advice, never "
        "publication blockers. Evaluate the actual rendered deck, not the intent alone."
    )
    user = json.dumps({
        "operationId": operation_id,
        "investmentStrategy": _strategy_context(db, deck_id),
        "deterministicPixelFindings": [item.model_dump(mode="json") for item in current.findings],
        "instruction": "Identify the highest-leverage improvements for an excellent investor-ready handoff.",
    }, separators=(",", ":"))
    transport = getattr(call_openai_response, "__wrapped__", call_openai_response)
    try:
        response = transport(
            api_key=config["apiKey"],
            model=model,
            system=system,
            user=user,
            image_urls=images,
            max_output_tokens=5000,
            timeout=settings.ai_vc_max_runtime_seconds,
            timeout_ceiling=settings.ai_vc_max_runtime_seconds,
            client_request_id=attempt.payload_json["clientRequestId"],
        )
        usage = response.get("usage") or {}
        from app.services.llm.instant_html_operation_service import estimate_model_cost_cents
        estimated_cents = estimate_model_cost_cents(
            "openai",
            model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
        if estimated_cents is None:
            raise ValueError("Investor handoff review usage could not be priced")
        if allowance is not None and Decimal(str(estimated_cents)) > allowance:
            raise ValueError("Investor handoff review exceeded its configured cost allowance")
        llm_review = _LLMInvestorHandoffReview.model_validate(
            json.loads(parse_openai_structured_response(response))
        )
        merged = VisionReview(
            rendered_artifact_ids=current.rendered_artifact_ids,
            findings=[*current.findings, *llm_review.findings][:160],
            strengths=llm_review.strengths,
            recommended_changes=llm_review.recommended_changes,
            handoff_assessment=llm_review.handoff_assessment,
            overall_score=llm_review.overall_score,
            narrative_score=llm_review.narrative_score,
            financial_credibility_score=llm_review.financial_credibility_score,
            investor_clarity_score=llm_review.investor_clarity_score,
            visual_quality_score=llm_review.visual_quality_score,
            brand_consistency_score=llm_review.brand_consistency_score,
            review_source="llm_assisted",
        )
        review_row.schema_version = merged.schema_version
        review_row.payload_json = merged.model_dump(mode="json")
        review_row.summary = "Internal LLM investor-quality handoff review; never a publication or export gate."
        review_row.metrics_json = {
            "publicationBlocking": False,
            "providerStarts": 1,
            "estimatedCostCents": estimated_cents,
            "inputTokens": usage.get("input_tokens"),
            "outputTokens": usage.get("output_tokens"),
        }
        repair_plan = build_visual_repair_plan(merged)
        repair_row = db.query(DeckLlmArtifact).filter_by(
            deck_id=deck_id,
            artifact_type=VISUAL_REPAIR_PLAN_TYPE,
            artifact_key=f"visual-repair-plan:{operation_id}",
        ).one()
        repair_row.payload_json = repair_plan.model_dump(mode="json")
        repair_row.summary = "Internal targeted improvement plan from the final investor-quality review."
        attempt.status = "ready"
        attempt.metrics_json = dict(review_row.metrics_json)
        attempt.summary = "Completed bounded rendered-deck investor handoff review."
        db.commit()
        return merged.model_dump(mode="json")
    except Exception as exc:
        attempt.status = "failed"
        attempt.summary = "Investor handoff review unavailable; canonical deck publication remains unaffected."
        attempt.metrics_json = {
            "costKnown": False,
            "publicationBlocking": False,
            "errorType": type(exc).__name__,
            "providerStarts": 1,
        }
        db.commit()
        raise


def vision_review_status(db: Session, deck_id: str) -> dict[str, Any] | None:
    row = (
        db.query(DeckLlmArtifact)
        .filter_by(deck_id=deck_id, artifact_type=VISION_REVIEW_TYPE, status="ready")
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if row is None or not isinstance(row.payload_json, dict):
        return None
    try:
        review = VisionReview.model_validate(row.payload_json)
    except ValueError:
        return None
    return {
        "status": "ready", "internalProductOnly": True, "publicationBlocking": False,
        **review.model_dump(mode="json"),
    }
