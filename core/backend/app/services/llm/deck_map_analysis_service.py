from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact, DeckSlideBlock
from app.services.llm.generation_service import (
    _load_deck,
    get_generation_provider_config,
    _fit_text,
)
from app.services.llm.deck_chunking_service import sync_deck_vector_chunks
from app.services.llm.canonical_deck_intelligence_service import persist_canonical_deck_intelligence
from app.services.llm.prompt_package_loader import build_prompt_package_text, load_prompt_package
from app.services.llm.structured_json_service import call_structured_json
from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks
from app.services.llm.vision_context_service import build_visual_context, prompt_safe_visual_context

logger = logging.getLogger("app.deck_map_analysis")

DECK_MAP_ANALYSIS_ARTIFACT_TYPE = "smart_deck_deck_map_analysis"
DECK_MAP_ANALYSIS_SCHEMA_VERSION = "v1"


class DeckMapMalformedJsonError(ValueError):
    """Typed failure for provider output that cannot satisfy the JSON boundary."""

    code = "deck_map_malformed_json"
    safe_message = "Deck Map analysis returned malformed JSON and was not persisted."
    recoverable = True
    next_action = "retry_job"


def _build_deck_map_context(deck: Deck) -> dict:
    slides = sorted(deck.slides, key=lambda s: s.slide_index)
    blocks: list[DeckSlideBlock] = []
    for slide in slides:
        for block in sorted(slide.blocks, key=lambda b: b.block_index):
            blocks.append(block)

    return {
        "schemaVersion": "deck-map-analysis.v1",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": deck.status,
            "slideCount": len(slides),
            "createdAt": _iso(deck.created_at),
            "updatedAt": _iso(deck.updated_at),
        },
        "slides": [
            {
                "id": s.id,
                "index": s.slide_index,
                "title": s.title,
                "role": s.role,
                "rawText": s.raw_text,
                "narrativeNotes": s.narrative_notes,
                "blockCount": len(s.blocks),
            }
            for s in slides
        ],
        "blocks": [
            {
                "id": b.id,
                "slideId": b.slide_id,
                "blockIndex": b.block_index,
                "blockType": b.block_type,
                "rawText": b.raw_text,
            }
            for b in blocks
        ],
    }


def _build_analysis_prompt(context: dict) -> str:
    return build_prompt_package_text("deck_map", "analyzer", context_label="Deck map context", context=context)


def _coerce_int(value: object, *, default: int, minimum: int, maximum: int | None = None) -> int:
    """Normalize loose provider output before it reaches the strict response schema."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    normalized = max(minimum, normalized)
    return min(maximum, normalized) if maximum is not None else normalized


def _validate_analysis(raw: dict, *, deck_id: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Analysis response must be a JSON object.")

    company = raw.get("company") or {}
    narrative = raw.get("narrative") or {}
    slides_raw = raw.get("slides")
    if not isinstance(slides_raw, list):
        slides_raw = []
    evidence = raw.get("evidence") or {}
    gaps_raw = raw.get("gaps")
    if not isinstance(gaps_raw, list):
        gaps_raw = []
    quality = raw.get("qualityScore") or {}

    return {
        # Contract boundary: DeckMapAnalysisResponse requires deckId inside the
        # nested analysis payload, not only on the surrounding run response.
        "deckId": deck_id,
        "company": {
            "name": _fit_text(str(company.get("name") or ""), 200) or None,
            "stage": _fit_text(str(company.get("stage") or ""), 100) or None,
            "industry": _fit_text(str(company.get("industry") or ""), 100) or None,
            "businessModel": _fit_text(str(company.get("businessModel") or ""), 200) or None,
            "foundingTeam": _fit_text(str(company.get("foundingTeam") or ""), 300) or None,
            "headquarters": _fit_text(str(company.get("headquarters") or ""), 100) or None,
        },
        "narrative": {
            "arcType": _fit_text(str(narrative.get("arcType") or "unknown"), 100),
            "flowAssessment": _fit_text(str(narrative.get("flowAssessment") or ""), 1000),
            "strengthAreas": [str(s)[:200] for s in (narrative.get("strengthAreas") or []) if str(s).strip()][:10],
            "weakAreas": [str(s)[:200] for s in (narrative.get("weakAreas") or []) if str(s).strip()][:10],
            "recommendedRestructuring": _fit_text(str(narrative.get("recommendedRestructuring") or ""), 500) or None,
        },
        "slides": [
            {
                "slideId": str(s.get("slideId") or ""),
                "title": _fit_text(str(s.get("title") or ""), 200),
                "role": _fit_text(str(s.get("role") or "unknown"), 100),
                "purposeAssessment": _fit_text(str(s.get("purposeAssessment") or ""), 500),
                "narrativeContribution": _fit_text(str(s.get("narrativeContribution") or ""), 500),
                "strength": str(s.get("strength") or "adequate")
                    if str(s.get("strength") or "") in {"strong", "adequate", "weak"}
                    else "adequate",
                "improvementSuggestion": _fit_text(str(s.get("improvementSuggestion") or ""), 500) or None,
            }
            for s in slides_raw
            if isinstance(s, dict) and s.get("slideId")
        ],
        "evidence": {
            "overallStrength": _fit_text(str(evidence.get("overallStrength") or ""), 200),
            # DISABLED: Direct int(...) conversion allowed provider phrases such
            # as "not ready" to crash the mounted Deck Map route.
            # "quantitativeClaims": max(0, int(evidence.get("quantitativeClaims") or 0)),
            # "qualitativeClaims": max(0, int(evidence.get("qualitativeClaims") or 0)),
            # "dataSourcesCited": max(0, int(evidence.get("dataSourcesCited") or 0)),
            "quantitativeClaims": _coerce_int(evidence.get("quantitativeClaims"), default=0, minimum=0),
            "qualitativeClaims": _coerce_int(evidence.get("qualitativeClaims"), default=0, minimum=0),
            "dataSourcesCited": _coerce_int(evidence.get("dataSourcesCited"), default=0, minimum=0),
            "strongAreas": [str(s)[:200] for s in (evidence.get("strongAreas") or []) if str(s).strip()][:10],
            "weakAreas": [str(s)[:200] for s in (evidence.get("weakAreas") or []) if str(s).strip()][:10],
        },
        "gaps": [
            {
                "area": _fit_text(str(g.get("area") or ""), 200),
                "importance": str(g.get("importance") or "medium")
                    if str(g.get("importance") or "") in {"critical", "high", "medium", "low"}
                    else "medium",
                "suggestion": _fit_text(str(g.get("suggestion") or ""), 500),
            }
            for g in gaps_raw
            if isinstance(g, dict) and g.get("area")
        ],
        "qualityScore": {
            # DISABLED: Direct int(...) conversion made one malformed score fail
            # the entire analysis instead of falling back to a neutral score.
            # "overall": max(1, min(100, int(quality.get("overall") or 50))),
            "overall": _coerce_int(quality.get("overall"), default=50, minimum=1, maximum=100),
            "narrativeFlow": _coerce_int(quality.get("narrativeFlow"), default=50, minimum=1, maximum=100),
            "evidenceQuality": _coerce_int(quality.get("evidenceQuality"), default=50, minimum=1, maximum=100),
            "investorReadiness": _coerce_int(quality.get("investorReadiness"), default=50, minimum=1, maximum=100),
            "visualStructure": _coerce_int(quality.get("visualStructure"), default=50, minimum=1, maximum=100),
        },
        "system": raw.get("system") if isinstance(raw.get("system"), dict) else {},
    }


def _find_analysis_artifact(db: Session, deck_id: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == DECK_MAP_ANALYSIS_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _record_analysis_artifact(
    db: Session,
    *,
    deck_id: str,
    artifact_key: str,
    summary: str,
    payload_json: dict | None = None,
) -> DeckLlmArtifact:
    artifact = DeckLlmArtifact(
        id=artifact_key,
        deck_id=deck_id,
        artifact_type=DECK_MAP_ANALYSIS_ARTIFACT_TYPE,
        artifact_key=artifact_key,
        schema_version=DECK_MAP_ANALYSIS_SCHEMA_VERSION,
        status="ready",
        summary=summary,
        payload_json=payload_json,
        metrics_json={"generatedAt": datetime.now(timezone.utc).isoformat()},
    )
    db.add(artifact)
    db.flush()
    return artifact


_ANALYSIS_CACHE_TTL_SECONDS = 3600  # 1 hour cache


def _is_recent_analysis(artifact: DeckLlmArtifact) -> bool:
    if artifact.created_at is None:
        return False
    created_at = artifact.created_at
    # SQLAlchemy/Postgres may return this legacy DateTime column without tzinfo.
    # Normalize it to UTC before comparing it with the timezone-aware clock.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created_at).total_seconds()
    return age < _ANALYSIS_CACHE_TTL_SECONDS


def analyze_deck_map(db: Session, deck_id: str) -> dict:
    cached = _find_analysis_artifact(db, deck_id)
    if cached and _is_recent_analysis(cached) and cached.payload_json:
        logger.info("Returning cached deck map analysis for deck %s", deck_id)
        # Revalidate cached artifacts so payloads created before deckId and
        # numeric coercion were added remain loadable from the live product.
        cached_analysis = _validate_analysis(cached.payload_json, deck_id=deck_id)
        return {
            "runId": cached.id,
            "deckId": deck_id,
            "status": "completed",
            "analysis": cached_analysis,
            "cached": True,
        }

    deck = _load_deck(db, deck_id)
    if deck is None:
        return {"runId": "", "deckId": deck_id, "status": "failed", "analysis": None, "cached": False}

    run_id = generate_id("dma")
    chunk_sync = sync_deck_vector_chunks(db, deck_id)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text="Investor-readiness narrative evidence gaps and missing slides",
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "accepted_edit", "diligence_lens", "audience_profile", "market_research"],
        limit=10,
    )
    visual_context = build_visual_context(deck, limit=4)
    context = {
        **_build_deck_map_context(deck),
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {
            "name": "deck_map",
            "version": load_prompt_package("deck_map")["version"],
        },
    }

    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")
    provider = config["provider"]
    resolved_model = config["model"]

    try:
        raw = call_structured_json(
            provider=provider,
            model=resolved_model,
            api_key=config.get("apiKey"),
            system_prompt="You output only valid JSON for backend-validated deck map analysis.",
            user_prompt=_build_analysis_prompt(context),
            timeout=90,
            max_tokens=4000,
            image_urls=visual_context.get("imageUrls"),
            credential_source=config.get("source", "environment"),
        )
    except (json.JSONDecodeError, TypeError) as exc:
        # The worker persists only this stable classification. Raw model output
        # and parser details must never cross the workflow/API boundary.
        raise DeckMapMalformedJsonError(DeckMapMalformedJsonError.safe_message) from exc
    validated = _validate_analysis(raw, deck_id=deck_id)
    validated["system"] = {
        "provider": provider,
        "model": resolved_model,
        "promptPackage": context["promptPackage"],
        "vectorRetrieval": {
            "status": retrieval.get("status"),
            "message": retrieval.get("message"),
            "chunkCount": len(retrieval.get("chunks") or []),
        },
        "vectorSync": {
            "status": chunk_sync.get("status"),
            "message": chunk_sync.get("message"),
            "chunkCount": chunk_sync.get("chunkCount"),
        },
    }

    summary = _fit_text(
        validated.get("narrative", {}).get("flowAssessment", "Deck map analysis completed."), 500
    )

    _record_analysis_artifact(
        db,
        deck_id=deck_id,
        artifact_key=run_id,
        summary=summary,
        payload_json=validated,
    )
    persist_canonical_deck_intelligence(db, deck_id)
    db.commit()

    return {
        "runId": run_id,
        "deckId": deck_id,
        "status": "completed",
        "analysis": validated,
        "cached": False,
    }


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
