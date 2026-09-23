from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact
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

logger = logging.getLogger("app.market_research")

MARKET_RESEARCH_ARTIFACT_TYPE = "smart_deck_market_research"
MARKET_RESEARCH_SCHEMA_VERSION = "v2"


def _build_market_research_context(deck: Deck) -> dict:
    slides = sorted(deck.slides, key=lambda s: s.slide_index)
    blocks: list = []
    for slide in slides:
        for block in sorted(slide.blocks, key=lambda b: b.block_index):
            blocks.append(block)

    return {
        "schemaVersion": "market-research.v1",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "slideCount": len(slides),
        },
        "slides": [
            {
                "title": s.title,
                "role": s.role,
                "rawText": s.raw_text,
            }
            for s in slides
        ],
        "blocks": [
            {
                "blockType": b.block_type,
                "rawText": b.raw_text,
            }
            for b in blocks
        ],
    }


def _build_market_research_prompt(context: dict) -> str:
    return build_prompt_package_text("market_research", "analyst", context_label="Market research context", context=context)


_VALID_SEVERITIES = {"critical", "high", "medium", "low"}


def _citation_status(payload: dict) -> str:
    sources = payload.get("sources") or []
    if not sources:
        return "no_sources"
    claim_groups = [payload.get("marketSizing"), payload.get("investmentThesis"), payload.get("vcAssessment")]
    claim_groups.extend(payload.get("competitors") or [])
    claim_groups.extend(payload.get("risks") or [])
    linked = sum(1 for claim in claim_groups if isinstance(claim, dict) and claim.get("citationIds"))
    if linked == 0:
        return "uncited"
    return "cited" if linked == len(claim_groups) else "partial"


def _validate_research(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Research response must be a JSON object.")

    company = raw.get("company") or {}
    sizing = raw.get("marketSizing") or {}
    competitors_raw = raw.get("competitors")
    if not isinstance(competitors_raw, list):
        competitors_raw = []
    thesis = raw.get("investmentThesis") or {}
    risks_raw = raw.get("risks")
    if not isinstance(risks_raw, list):
        risks_raw = []
    vc = raw.get("vcAssessment") or {}
    sources = []
    source_ids = set()
    for item in raw.get("sources") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        parsed = urlsplit(url)
        if (
            any(ord(char) < 32 or ord(char) == 127 for char in url)
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            continue
        source_id = _fit_text(str(item.get("id") or ""), 120)
        title = _fit_text(str(item.get("title") or ""), 300)
        if not source_id or not title or source_id in source_ids:
            continue
        source_ids.add(source_id)
        sources.append({"id": source_id, "title": title, "url": url, "provider": _fit_text(str(item.get("provider") or ""), 120) or None, "publishedDate": item.get("publishedDate") or None})

    def citations(value: object) -> list[str]:
        return [str(item)[:120] for item in value if str(item) in source_ids][:20] if isinstance(value, list) else []

    validated = {
        "company": {
            "name": _fit_text(str(company.get("name") or ""), 200) or None,
            "description": _fit_text(str(company.get("description") or ""), 500) or None,
            "foundedYear": max(1900, min(2030, int(company.get("foundedYear") or 0))) if company.get("foundedYear") else None,
            "headquarters": _fit_text(str(company.get("headquarters") or ""), 200) or None,
            "businessModel": _fit_text(str(company.get("businessModel") or ""), 200) or None,
            "fundingStage": _fit_text(str(company.get("fundingStage") or ""), 100) or None,
            "totalRaised": _fit_text(str(company.get("totalRaised") or ""), 100) or None,
            "teamSize": _fit_text(str(company.get("teamSize") or ""), 100) or None,
            "keyFinding": _fit_text(str(company.get("keyFinding") or ""), 500) or None,
        },
        "marketSizing": {
            "tam": _fit_text(str(sizing.get("tam") or ""), 200) or None,
            "sam": _fit_text(str(sizing.get("sam") or ""), 200) or None,
            "som": _fit_text(str(sizing.get("som") or ""), 200) or None,
            "growthRate": _fit_text(str(sizing.get("growthRate") or ""), 100) or None,
            "sourceConfidence": str(sizing.get("sourceConfidence") or "medium")
                if str(sizing.get("sourceConfidence") or "") in {"high", "medium", "low"}
                else "medium",
            "note": _fit_text(str(sizing.get("note") or ""), 500) or None,
            "citationIds": citations(sizing.get("citationIds")),
        },
        "competitors": [
            {
                "name": _fit_text(str(c.get("name") or ""), 200),
                "category": _fit_text(str(c.get("category") or "direct"), 100),
                "threats": _fit_text(str(c.get("threats") or ""), 300) or None,
                "weaknesses": _fit_text(str(c.get("weaknesses") or ""), 300) or None,
                "differentiation": _fit_text(str(c.get("differentiation") or ""), 300) or None,
                "citationIds": citations(c.get("citationIds")),
            }
            for c in competitors_raw
            if isinstance(c, dict) and c.get("name")
        ],
        "industryTrends": _fit_text(str(raw.get("industryTrends") or ""), 1000) or None,
        "investmentThesis": {
            "summary": _fit_text(str(thesis.get("summary") or ""), 800),
            "strengths": [str(s)[:300] for s in (thesis.get("strengths") or []) if str(s).strip()][:8],
            "weaknesses": [str(s)[:300] for s in (thesis.get("weaknesses") or []) if str(s).strip()][:8],
            "differentiators": [str(s)[:300] for s in (thesis.get("differentiators") or []) if str(s).strip()][:8],
            "citationIds": citations(thesis.get("citationIds")),
        },
        "risks": [
            {
                "risk": _fit_text(str(r.get("risk") or ""), 300),
                "severity": str(r.get("severity") or "medium")
                    if str(r.get("severity") or "") in _VALID_SEVERITIES
                    else "medium",
                "mitigation": _fit_text(str(r.get("mitigation") or ""), 500) or None,
                "citationIds": citations(r.get("citationIds")),
            }
            for r in risks_raw
            if isinstance(r, dict) and r.get("risk")
        ],
        "vcAssessment": {
            "score": max(1, min(100, int(vc.get("score") or 50))),
            "stageFit": _fit_text(str(vc.get("stageFit") or ""), 200),
            "strengths": [str(s)[:300] for s in (vc.get("strengths") or []) if str(s).strip()][:8],
            "concerns": [str(s)[:300] for s in (vc.get("concerns") or []) if str(s).strip()][:8],
            "diligenceQuestions": [str(q)[:500] for q in (vc.get("diligenceQuestions") or []) if str(q).strip()][:10],
            "citationIds": citations(vc.get("citationIds")),
        },
        "sources": sources,
        "system": raw.get("system") if isinstance(raw.get("system"), dict) else {},
    }
    validated["citationStatus"] = _citation_status(validated)
    return validated


def adapt_market_research_for_read(payload: dict, *, deck_id: str) -> dict:
    adapted = {**payload, "deckId": deck_id}
    adapted.setdefault("sources", [])
    for key in ("marketSizing", "investmentThesis", "vcAssessment"):
        if isinstance(adapted.get(key), dict):
            adapted[key] = {**adapted[key], "citationIds": list(adapted[key].get("citationIds") or [])}
    for key in ("competitors", "risks"):
        adapted[key] = [{**item, "citationIds": list(item.get("citationIds") or [])} for item in adapted.get(key) or [] if isinstance(item, dict)]
    # Recompute rather than trusting legacy optimistic values.
    adapted["citationStatus"] = _citation_status(adapted)
    return adapted


def _find_research_artifact(db: Session, deck_id: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == MARKET_RESEARCH_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _record_research_artifact(
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
        artifact_type=MARKET_RESEARCH_ARTIFACT_TYPE,
        artifact_key=artifact_key,
        schema_version=MARKET_RESEARCH_SCHEMA_VERSION,
        status="ready",
        summary=summary,
        payload_json=payload_json,
        metrics_json={"generatedAt": datetime.now(timezone.utc).isoformat()},
    )
    db.add(artifact)
    db.flush()
    return artifact


_RESEARCH_CACHE_TTL_SECONDS = 7200  # 2 hour cache


def _is_recent_research(artifact: DeckLlmArtifact) -> bool:
    if artifact.created_at is None:
        return False
    created_at = artifact.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created_at).total_seconds()
    return age < _RESEARCH_CACHE_TTL_SECONDS


def generate_market_research(db: Session, deck_id: str) -> dict:
    cached = _find_research_artifact(db, deck_id)
    if cached and _is_recent_research(cached) and cached.payload_json:
        logger.info("Returning cached market research for deck %s", deck_id)
        cached_research = adapt_market_research_for_read(cached.payload_json, deck_id=deck_id)
        return {
            "runId": cached.id,
            "deckId": deck_id,
            "status": "completed",
            "research": cached_research,
            "cached": True,
        }

    deck = _load_deck(db, deck_id)
    if deck is None:
        return {"runId": "", "deckId": deck_id, "status": "failed", "research": None, "cached": False}

    run_id = generate_id("mr")
    chunk_sync = sync_deck_vector_chunks(db, deck_id)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text="Market sizing competitors trends VC readiness and risk context",
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "deck_map_analysis", "diligence_lens", "audience_profile", "accepted_edit"],
        limit=12,
    )
    visual_context = build_visual_context(deck, limit=4)
    context = {
        **_build_market_research_context(deck),
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {
            "name": "market_research",
            "version": load_prompt_package("market_research")["version"],
        },
    }

    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")
    provider = config["provider"]
    resolved_model = config["model"]

    raw = call_structured_json(
        provider=provider,
        model=resolved_model,
        api_key=config.get("apiKey"),
        system_prompt="You output only valid JSON for backend-validated market research report.",
        user_prompt=_build_market_research_prompt(context),
        timeout=90,
        max_tokens=4000,
        image_urls=visual_context.get("imageUrls"),
        credential_source=config.get("source", "environment"),
    )
    validated = _validate_research(raw)
    # The response contract scopes every research artifact to its source deck.
    validated["deckId"] = deck_id
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
        validated.get("investmentThesis", {}).get("summary", "Market research completed."), 500
    )

    _record_research_artifact(
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
        "research": validated,
        "cached": False,
    }
