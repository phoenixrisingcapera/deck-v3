from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.llm.deck_chunking_service import sync_deck_vector_chunks
from app.services.llm.canonical_deck_intelligence_service import persist_canonical_deck_intelligence
from app.services.llm.generation_service import _fit_text, _load_audience_profile, _load_deck, get_generation_provider_config
from app.services.llm.prompt_package_loader import build_prompt_package_text, load_prompt_package
from app.services.llm.structured_json_service import call_structured_json
from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks
from app.services.llm.vision_context_service import build_visual_context, prompt_safe_visual_context


AUDIENCE_CONVERSION_ANALYSIS_ARTIFACT_TYPE = "audience_conversion_analysis"
AUDIENCE_CONVERSION_PLAN_ARTIFACT_TYPE = "audience_conversion_plan"
AUDIENCE_CONVERSION_GENERATED_ARTIFACT_TYPE = "audience_conversion_generated"


def analyze_audience_conversion(db: Session, deck_id: str, *, target_audience: str | None = None) -> dict:
    return _run_audience_conversion_step(db, deck_id=deck_id, target_audience=target_audience, artifact_type=AUDIENCE_CONVERSION_ANALYSIS_ARTIFACT_TYPE, section="audience_lens")


def plan_audience_conversion(db: Session, deck_id: str, *, target_audience: str | None = None) -> dict:
    return _run_audience_conversion_step(db, deck_id=deck_id, target_audience=target_audience, artifact_type=AUDIENCE_CONVERSION_PLAN_ARTIFACT_TYPE, section="deck_conversion_planner")


def generate_audience_conversion(db: Session, deck_id: str, *, target_audience: str | None = None) -> dict:
    return _run_audience_conversion_step(db, deck_id=deck_id, target_audience=target_audience, artifact_type=AUDIENCE_CONVERSION_GENERATED_ARTIFACT_TYPE, section="slide_action_generator")


def get_latest_audience_conversion(db: Session, deck_id: str) -> dict | None:
    artifact = _find_latest_artifact(db, deck_id, AUDIENCE_CONVERSION_GENERATED_ARTIFACT_TYPE)
    if artifact is None:
        artifact = _find_latest_artifact(db, deck_id, AUDIENCE_CONVERSION_PLAN_ARTIFACT_TYPE)
    if artifact is None:
        artifact = _find_latest_artifact(db, deck_id, AUDIENCE_CONVERSION_ANALYSIS_ARTIFACT_TYPE)
    if artifact is None:
        return None
    return {
        "runId": artifact.artifact_key,
        "deckId": deck_id,
        "status": "completed",
        "conversion": artifact.payload_json,
        "cached": True,
    }


def _run_audience_conversion_step(
    db: Session,
    *,
    deck_id: str,
    target_audience: str | None,
    artifact_type: str,
    section: str,
) -> dict:
    cached = _find_latest_artifact(db, deck_id, artifact_type)
    if cached and cached.payload_json:
        return {
            "runId": cached.artifact_key,
            "deckId": deck_id,
            "status": "completed",
            "conversion": cached.payload_json,
            "cached": True,
        }

    deck = _load_deck(db, deck_id)
    if deck is None:
        return {"runId": "", "deckId": deck_id, "status": "failed", "conversion": None, "cached": False}

    resolved_audience = (target_audience or deck.audience or "investment_committee").strip() or "investment_committee"
    audience_profile = _load_audience_profile(db, resolved_audience)
    chunk_sync = sync_deck_vector_chunks(db, deck_id, audience_label=resolved_audience)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text=f"Audience conversion for {resolved_audience}: priorities objections decision criteria slide actions",
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "audience_profile", "diligence_lens", "deck_map_analysis", "accepted_edit", "generated_version"],
        limit=12,
    )
    visual_context = build_visual_context(deck, limit=4)
    context = {
        "schemaVersion": "audience-conversion.v1",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
        },
        "targetAudience": resolved_audience,
        "audienceProfile": {
            "label": audience_profile.label if audience_profile is not None else resolved_audience,
            "focus": audience_profile.focus if audience_profile is not None else None,
            "tone": audience_profile.tone if audience_profile is not None else None,
        },
        "slides": [
            {
                "id": slide.id,
                "title": slide.title,
                "role": slide.role,
                "rawText": slide.raw_text,
                "summary": slide.summary,
            }
            for slide in sorted(deck.slides, key=lambda item: item.slide_index)
        ],
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {
            "name": "audience_conversion",
            "version": load_prompt_package("audience_conversion")["version"],
            "section": section,
        },
    }
    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")
    raw = call_structured_json(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("apiKey"),
        system_prompt="You output only valid JSON for backend-validated audience conversion workflows.",
        user_prompt=build_prompt_package_text("audience_conversion", section, context_label="Audience conversion context", context=context),
        timeout=90,
        max_tokens=4000,
        image_urls=visual_context.get("imageUrls"),
        credential_source=config.get("source", "environment"),
    )
    validated = _validate_audience_conversion(raw, deck_id=deck_id, target_audience=resolved_audience, context=context, provider=config["provider"], model=config["model"])
    run_id = generate_id("ac")
    _record_audience_conversion_artifact(db, deck_id=deck_id, artifact_type=artifact_type, artifact_key=run_id, payload_json=validated)
    persist_canonical_deck_intelligence(db, deck_id)
    db.commit()
    return {"runId": run_id, "deckId": deck_id, "status": "completed", "conversion": validated, "cached": False}


def _validate_audience_conversion(raw: dict, *, deck_id: str, target_audience: str, context: dict, provider: str, model: str | None) -> dict:
    priorities = [str(item)[:300] for item in raw.get("audiencePriorities", []) if str(item).strip()][:12]
    objections = [str(item)[:300] for item in raw.get("likelyObjections", []) if str(item).strip()][:12]
    criteria = [str(item)[:300] for item in raw.get("decisionCriteria", []) if str(item).strip()][:12]
    missing_evidence = [str(item)[:400] for item in raw.get("missingEvidence", []) if str(item).strip()][:20]
    actions_raw = raw.get("slideLevelActions") if isinstance(raw.get("slideLevelActions"), list) else []
    slide_actions = []
    for item in actions_raw[:30]:
        if not isinstance(item, dict):
            continue
        action = _fit_text(str(item.get("action") or ""), 600)
        if not action:
            continue
        slide_actions.append(
            {
                "slideId": str(item.get("slideId") or "") or None,
                "slideTitle": _fit_text(str(item.get("slideTitle") or ""), 200) or None,
                "currentRole": _fit_text(str(item.get("currentRole") or ""), 100) or None,
                "audienceNeed": _fit_text(str(item.get("audienceNeed") or ""), 300),
                "objection": _fit_text(str(item.get("objection") or ""), 300) or None,
                "action": action,
                "evidenceNeeded": [str(v)[:250] for v in item.get("evidenceNeeded", []) if str(v).strip()][:10],
                "priority": _fit_text(str(item.get("priority") or "medium"), 40),
            }
        )
    recommended_deck_version = raw.get("recommendedDeckVersion") if isinstance(raw.get("recommendedDeckVersion"), dict) else {}
    return {
        "targetAudience": target_audience,
        "audiencePriorities": priorities,
        "likelyObjections": objections,
        "decisionCriteria": criteria,
        "deckConversionPlan": raw.get("deckConversionPlan") if isinstance(raw.get("deckConversionPlan"), dict) else {},
        "slideLevelActions": slide_actions,
        "missingEvidence": missing_evidence,
        "recommendedDeckVersion": {
            "title": _fit_text(str(recommended_deck_version.get("title") or ""), 200) or None,
            "audience": _fit_text(str(recommended_deck_version.get("audience") or target_audience), 120) or target_audience,
            "summary": _fit_text(str(recommended_deck_version.get("summary") or ""), 800) or None,
            "generationPrompt": _fit_text(str(recommended_deck_version.get("generationPrompt") or ""), 1000) or None,
        },
        "requiresReview": bool(raw.get("requiresReview", True)),
        "system": {
            "provider": provider,
            "model": model,
            "promptPackage": context["promptPackage"],
            "vectorRetrieval": {
                "status": (context.get("vectorRetrieval") or {}).get("status"),
                "message": (context.get("vectorRetrieval") or {}).get("message"),
                "chunkCount": len((context.get("vectorRetrieval") or {}).get("chunks") or []),
            },
            "vectorSync": {
                "status": (context.get("vectorSync") or {}).get("status"),
                "message": (context.get("vectorSync") or {}).get("message"),
                "chunkCount": (context.get("vectorSync") or {}).get("chunkCount"),
            },
            "canonicalDeckMapArtifactType": "smart_deck_deck_map_analysis",
        },
    }


def _find_latest_artifact(db: Session, deck_id: str, artifact_type: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == artifact_type,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _record_audience_conversion_artifact(db: Session, *, deck_id: str, artifact_type: str, artifact_key: str, payload_json: dict) -> None:
    db.add(
        DeckLlmArtifact(
            id=generate_id("artifact"),
            deck_id=deck_id,
            artifact_type=artifact_type,
            artifact_key=artifact_key,
            schema_version="audience-conversion.v1",
            status="ready",
            summary=_fit_text(str((payload_json.get("recommendedDeckVersion") or {}).get("summary") or f"Audience conversion for {payload_json.get('targetAudience') or 'target audience'}."), 500),
            payload_json=payload_json,
            metrics_json={"generatedAt": datetime.now(timezone.utc).isoformat()},
        )
    )
