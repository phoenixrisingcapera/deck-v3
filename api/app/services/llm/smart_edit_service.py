from __future__ import annotations

import re
from collections.abc import Callable

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.agents.smart_edit_agent import run as smart_edit_run
from app.ai.architecture_runtime_context import build_architecture_runtime_context
from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact, DeckSlide, DeckSlideBlock, SmartEditRun, SmartEditSuggestion, WorkflowJob
from app.ai.slide_archetypes_context import build_slide_archetype_context
from app.services.admin.agent_telemetry import record_agent_event
from app.services.llm.critique_service import build_critique_decision
from app.services.llm.artifact_persistence import persist_canonical_llm_artifact
from app.services.llm.deck_chunking_service import sync_deck_vector_chunks
from app.services.llm.knowledge_service import build_llm_knowledge_metadata
from app.services.llm.generation_service import _fit_text, _resolve_claude_config, get_generation_provider_config
from app.services.brand.brand_design_tokens import build_brand_llm_context
from app.services.llm.prompt_package_loader import build_prompt_package_text, load_prompt_package
from app.services.llm.structured_json_service import call_structured_json
from app.services.llm.vision_context_service import build_visual_context, prompt_safe_visual_context
from app.services.llm.source_facts import classify_source_fact, summarize_fact_types, summarize_safety_flags
from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks
from app.schemas.smart_deck import RenderSchema
from app.services.llm.element_breakdown_service import breakdown_slide_render_schema
from app.services.deck_processing.workflow_jobs import JOB_STATUS_QUEUED, JOB_TYPE_SMART_EDIT, ensure_workflow_job


ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
MAX_SUGGESTION_TEXT_LENGTH = 4000
SMART_EDIT_ARTIFACT_SCHEMA_VERSION = "smart-edit-artifacts.v1"
SMART_EDIT_FACT_MAX_LENGTH = 320


def _safe_text(value: object, *, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)[:MAX_SUGGESTION_TEXT_LENGTH]


def _normalize_suggestion_payload(payload: dict[str, object], *, original_text: str) -> dict[str, str]:
    suggested_text = _safe_text(payload.get("suggested_text"), fallback=original_text)
    reason = _safe_text(payload.get("reason"), fallback="Suggested by Smart Edit.")
    risk_level = _safe_text(payload.get("risk_level"), fallback="medium").lower()
    if risk_level not in ALLOWED_RISK_LEVELS:
        risk_level = "medium"
    return {
        "original_text": _safe_text(payload.get("original_text"), fallback=original_text),
        "suggested_text": suggested_text or original_text,
        "reason": reason or "Suggested by Smart Edit.",
        "risk_level": risk_level,
    }


def _normalise_fact_text(value: object, *, limit: int = SMART_EDIT_FACT_MAX_LENGTH) -> str:
    text = str(value if value is not None else "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit].strip()


def _instruction_requests_background_change(instruction: str) -> bool:
    normalized = re.sub(r"\s+", " ", instruction.lower()).strip()
    if not any(term in normalized for term in ("background", "backdrop", "canvas")):
        return False
    if re.search(r"\b(?:keep|preserve|retain)\b.{0,30}\b(?:background|backdrop|canvas)\b", normalized):
        return False
    if re.search(r"\b(?:do not|don't|dont|no)\b.{0,30}\b(?:change|modify|replace|redesign)\b.{0,30}\b(?:background|backdrop|canvas)\b", normalized):
        return False
    return bool(
        re.search(
            r"\b(?:change|modify|replace|redesign|update|set|make|create|generate)\b.{0,40}\b(?:background|backdrop|canvas)\b"
            r"|\b(?:background|backdrop|canvas)\b.{0,40}\b(?:change|modify|replace|redesign|update|set|make|create|generate)\b",
            normalized,
        )
    )


def _fact_candidates_from_text(text: str | None) -> list[str]:
    normalized = _normalise_fact_text(text, limit=4000)
    if not normalized:
        return []
    parts = [
        part.strip(" -:\t")
        for part in re.split(r"(?<=[.!?])\s+|\n+|[•·]\s*", normalized)
        if part.strip(" -:\t")
    ]
    if len(parts) <= 1:
        parts = [
            part.strip(" -:\t")
            for part in re.split(r"\s{2,}|;\s+", normalized)
            if part.strip(" -:\t")
        ]
    return [_normalise_fact_text(part) for part in parts if len(part) >= 8]


def _append_source_fact(
    facts: list[dict],
    seen: set[str],
    *,
    source_type: str,
    source_id: str,
    field: str,
    text: object,
    confidence: str,
    scope: str,
) -> None:
    fact_text = _normalise_fact_text(text)
    if not fact_text:
        return
    key = f"{source_type}:{source_id}:{field}:{fact_text.lower()}"
    if key in seen:
        return
    seen.add(key)
    classification = classify_source_fact(
        text=fact_text,
        source_type=source_type,
        field=field,
        confidence=confidence,
    )
    facts.append(
        {
            "id": f"fact_{len(facts) + 1}",
            "sourceType": source_type,
            "sourceId": source_id,
            "field": field,
            "text": fact_text,
            "confidence": confidence,
            "scope": scope,
            **classification,
        }
    )


def _build_smart_edit_source_fact_package(
    *,
    deck: Deck,
    selected_slide: DeckSlide | None,
    selected_block: DeckSlideBlock | None,
    instruction: str,
    audience_type: str,
) -> dict:
    facts: list[dict] = []
    seen: set[str] = set()
    _append_source_fact(facts, seen, source_type="deck_metadata", source_id=deck.id, field="title", text=deck.title, confidence="high", scope="deck")
    _append_source_fact(facts, seen, source_type="deck_metadata", source_id=deck.id, field="audience", text=deck.audience, confidence="high", scope="deck")
    _append_source_fact(facts, seen, source_type="deck_metadata", source_id=deck.id, field="purpose", text=deck.purpose, confidence="high", scope="deck")
    _append_source_fact(facts, seen, source_type="smart_edit_instruction", source_id=deck.id, field="instruction", text=instruction, confidence="high", scope="edit")
    _append_source_fact(facts, seen, source_type="smart_edit_instruction", source_id=deck.id, field="audience_type", text=audience_type, confidence="high", scope="edit")

    if selected_slide is not None:
        _append_source_fact(facts, seen, source_type="source_slide", source_id=selected_slide.id, field="title", text=selected_slide.title, confidence="high", scope="slide")
        _append_source_fact(facts, seen, source_type="source_slide", source_id=selected_slide.id, field="role", text=selected_slide.role, confidence="medium", scope="slide")
        for candidate in _fact_candidates_from_text(selected_slide.raw_text)[:8]:
            _append_source_fact(facts, seen, source_type="source_slide", source_id=selected_slide.id, field="raw_text", text=candidate, confidence="high", scope="slide")

    if selected_block is not None:
        _append_source_fact(facts, seen, source_type="source_block", source_id=selected_block.id, field="block_type", text=selected_block.block_type, confidence="medium", scope="block")
        for candidate in _fact_candidates_from_text(selected_block.raw_text or selected_block.normalized_text)[:6]:
            _append_source_fact(facts, seen, source_type="source_block", source_id=selected_block.id, field="raw_text", text=candidate, confidence="high", scope="block")

    return {
        "schemaVersion": "smart-edit-source-facts.v1",
        "rules": [
            "Use only these sourceFacts for factual claims.",
            "Cite fact IDs in source_fact_ids.",
            "Put missing evidence in missing_inputs or quality_warnings instead of inventing facts.",
            "Facts include factType, evidenceStrength, and safetyFlags; do not strengthen facts marked do_not_strengthen.",
        ],
        "factCount": len(facts),
        "facts": facts[:80],
        "factTypeCounts": summarize_fact_types(facts),
        "safetyFlagCounts": summarize_safety_flags(facts),
        "coverage": {
            "hasSelectedSlide": selected_slide is not None,
            "hasSelectedBlock": selected_block is not None,
            "hasInstruction": bool(_normalise_fact_text(instruction)),
            "selectedBlockFactCount": len([fact for fact in facts if fact["sourceType"] == "source_block"]),
        },
    }


def _build_smart_edit_plan(context: dict) -> dict:
    source_fact_package = context.get("sourceFactPackage") if isinstance(context.get("sourceFactPackage"), dict) else {}
    return {
        "schemaVersion": "smart-edit-plan.v1",
        "knowledgeMetadata": context.get("knowledgeMetadata") or {},
        "sourceFactSummary": {
            "schemaVersion": source_fact_package.get("schemaVersion"),
            "factCount": source_fact_package.get("factCount") or 0,
            "coverage": source_fact_package.get("coverage") or {},
        },
        "steps": [
            {"id": "retrieve", "instruction": "Use selected block, selected slide, neighboring slides, archetype knowledge, and source facts."},
            {"id": "draft", "instruction": "Return a reviewable suggestion with source_fact_ids, missing_inputs, and quality_warnings."},
            {"id": "critique", "instruction": "Check fact IDs, unsupported claims, missing evidence, and risk level."},
            {"id": "repair", "instruction": "If critique status is review, make one bounded repair pass."},
            {"id": "persist", "instruction": "Persist suggestion, artifacts, telemetry, and user review state."},
        ],
    }


def _critique_smart_edit_payload(payload: dict[str, object], source_fact_package: dict) -> dict:
    allowed_fact_ids = {
        str(fact.get("id"))
        for fact in source_fact_package.get("facts", [])
        if isinstance(fact, dict) and fact.get("id")
    }
    fact_by_id = {
        str(fact.get("id")): fact
        for fact in source_fact_package.get("facts", [])
        if isinstance(fact, dict) and fact.get("id")
    }
    source_fact_ids = [str(item) for item in payload.get("source_fact_ids", [])] if isinstance(payload.get("source_fact_ids"), list) else []
    missing_inputs = payload.get("missing_inputs") if isinstance(payload.get("missing_inputs"), list) else []
    quality_warnings = payload.get("quality_warnings") if isinstance(payload.get("quality_warnings"), list) else []
    warnings = [str(item) for item in quality_warnings]
    unsupported_fact_ids = [fact_id for fact_id in source_fact_ids if fact_id not in allowed_fact_ids]
    if allowed_fact_ids and not source_fact_ids:
        warnings.append("No source fact IDs were declared in source_fact_ids.")
    if unsupported_fact_ids:
        warnings.append("Some source_fact_ids do not exist in sourceFactPackage facts.")
    cited_safety_flags = sorted(
        {
            str(flag)
            for fact_id in source_fact_ids
            for flag in (fact_by_id.get(str(fact_id), {}).get("safetyFlags") or [])
        }
    )
    cited_fact_types = sorted(
        {
            str(fact_by_id.get(str(fact_id), {}).get("factType"))
            for fact_id in source_fact_ids
            if fact_by_id.get(str(fact_id), {}).get("factType")
        }
    )
    if "requires_source" in cited_safety_flags and not payload.get("source_facts_used"):
        warnings.append("Cited facts require readable source_facts_used labels.")
    unchanged_output = bool(
        _safe_text(payload.get("suggested_text"))
        and _safe_text(payload.get("suggested_text")) == _safe_text(payload.get("original_text"))
    )
    if unchanged_output:
        warnings.append("Suggested text is unchanged from original text.")
    critique_decision = build_critique_decision(
        warnings=warnings,
        missing_inputs=missing_inputs,
        unsupported_fact_ids=unsupported_fact_ids,
        unsupported_facts=[],
        cited_safety_flags=cited_safety_flags,
        unchanged_output=unchanged_output,
    )
    return {
        "schemaVersion": "smart-edit-critique.v1",
        "status": critique_decision.get("status") if critique_decision.get("status") != "blocking" else "review",
        "warningCount": len(warnings),
        "missingInputCount": len(missing_inputs),
        "allowedSourceFactIds": sorted(allowed_fact_ids),
        "sourceFactIds": source_fact_ids,
        "unsupportedSourceFactIds": unsupported_fact_ids,
        "citedFactTypes": cited_fact_types,
        "citedSafetyFlags": cited_safety_flags,
        "warnings": warnings,
        "missingInputs": missing_inputs,
        "decision": critique_decision,
        "dimensions": critique_decision.get("dimensions") or [],
        "repairActions": critique_decision.get("repairActions") or [],
    }


def _record_smart_edit_artifact(
    db: Session,
    *,
    deck_id: str,
    run_id: str,
    artifact_type: str,
    summary: str,
    payload_json: dict,
    metrics_json: dict | None = None,
) -> DeckLlmArtifact:
    canonical_payload = persist_canonical_llm_artifact(
        db,
        deck_id=deck_id,
        artifact_type=artifact_type,
        payload=payload_json,
    )
    stored_metrics = dict(metrics_json or {})
    if canonical_payload:
        stored_metrics.update(
            {
                "canonicalArtifactFilename": canonical_payload["filename"],
                "canonicalArtifactStoragePath": canonical_payload["storagePath"],
            }
        )
        payload_json = {
            **payload_json,
            "canonicalFilename": canonical_payload["filename"],
            "canonicalStoragePath": canonical_payload["storagePath"],
        }
    artifact = DeckLlmArtifact(
        id=generate_id("artifact"),
        deck_id=deck_id,
        extraction_run_id=None,
        artifact_type=artifact_type,
        artifact_key=run_id,
        schema_version=SMART_EDIT_ARTIFACT_SCHEMA_VERSION,
        status="ready",
        summary=summary,
        payload_json=payload_json,
        bucket_payload_key=canonical_payload["storagePath"] if canonical_payload else None,
        metrics_json=stored_metrics,
    )
    db.add(artifact)
    return artifact


def _map_run(run: SmartEditRun) -> dict:
    return {
        "id": run.id,
        "deck_id": run.deck_id,
        "slide_id": run.slide_id,
        "block_id": run.block_id,
        "instruction": run.instruction,
        "audience_type": run.audience_type,
        "created_at": run.created_at.isoformat() if run.created_at else "",
    }


def _map_suggestion(suggestion: SmartEditSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "run_id": suggestion.run_id,
        "deck_id": suggestion.deck_id,
        "slide_id": suggestion.slide_id,
        "block_id": suggestion.block_id,
        "original_text": suggestion.original_text,
        "suggested_text": suggestion.suggested_text,
        "reason": suggestion.reason,
        "risk_level": suggestion.risk_level,
        "status": suggestion.status,
    }


def _load_block(db: Session, deck_id: str, slide_id: str, block_id: str) -> DeckSlideBlock | None:
    return (
        db.query(DeckSlideBlock)
        .join(DeckSlide, DeckSlide.id == DeckSlideBlock.slide_id)
        .join(Deck, Deck.id == DeckSlide.deck_id)
        .filter(
            Deck.id == deck_id,
            DeckSlide.id == slide_id,
            DeckSlideBlock.id == block_id,
        )
        .one_or_none()
    )


def _load_deck_context(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(selectinload(Deck.slides).selectinload(DeckSlide.blocks))
        .filter(Deck.id == deck_id)
        .one_or_none()
    )


def _load_element_breakdown(session: Session, selected_slide: DeckSlide | None) -> dict | None:
    if selected_slide is None:
        return None
    from app.db.models import GeneratedSlide
    generated: GeneratedSlide | None = (
        session.query(GeneratedSlide)
        .filter(
            GeneratedSlide.source_slide_id == selected_slide.id,
            GeneratedSlide.status == "ready",
        )
        .order_by(GeneratedSlide.created_at.desc())
        .first()
    ) if session is not None else None
    if generated is None or not generated.render_schema_json:
        return None
    try:
        schema = RenderSchema.model_validate(generated.render_schema_json)
        return breakdown_slide_render_schema(slide_id=selected_slide.id, render_schema=schema)
    except Exception:
        return None


def _build_smart_edit_media_context(deck: Deck) -> dict:
    """Build bounded media context for Smart Edit LLM consumption."""
    from app.services.media.media_context import build_deck_media_context

    session = deck._sa_instance_state.session
    if session is None:
        return {"schemaVersion": "deck-media-context.v1", "deckId": deck.id, "assetCount": 0, "totalBytes": 0, "assets": []}

    try:
        return build_deck_media_context(session, deck_id=deck.id)
    except Exception as error:
        # Media context is non-blocking; log and return empty
        import logging
        logging.getLogger(__name__).warning("Failed to build media context for deck %s: %s", deck.id, error)
        return {"schemaVersion": "deck-media-context.v1", "deckId": deck.id, "assetCount": 0, "totalBytes": 0, "assets": []}


def _smart_edit_context(deck: Deck, slide_id: str, block_id: str, *, instruction: str = "", audience_type: str = "") -> dict:
    session = deck._sa_instance_state.session
    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    selected_slide = next((slide for slide in slides if slide.id == slide_id), None)
    selected_block = None
    if selected_slide is not None:
        selected_block = next((block for block in selected_slide.blocks if block.id == block_id), None)
    element_breakdown = _load_element_breakdown(session, selected_slide) if session is not None else None
    source_fact_package = _build_smart_edit_source_fact_package(
        deck=deck,
        selected_slide=selected_slide,
        selected_block=selected_block,
        instruction=instruction,
        audience_type=audience_type,
    )
    brand_context = build_brand_llm_context(deck.brand_profile)
    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
        },
        "selectedSlide": {
            "id": selected_slide.id,
            "title": selected_slide.title,
            "role": selected_slide.role,
            "raw_text": selected_slide.raw_text,
        }
        if selected_slide is not None
        else None,
        "selectedBlock": {
            "id": selected_block.id,
            "block_type": selected_block.block_type,
            "raw_text": selected_block.raw_text,
            "normalized_text": selected_block.normalized_text,
        }
        if selected_block is not None
        else None,
        "neighborSlides": [
            {
                "id": slide.id,
                "title": slide.title,
                "role": slide.role,
                "summary": slide.summary,
            }
            for slide in slides[:12]
        ],
        "slideArchetypeContext": build_slide_archetype_context(
            audience=deck.audience,
            purpose=deck.purpose,
            slide_texts=[selected_slide.raw_text or ""] if selected_slide else [],
            slide_titles=[selected_slide.title or ""] if selected_slide else [],
            slide_roles=[selected_slide.role or ""] if selected_slide else [],
        ),
        # Diligence and conversion plans are review artifacts.  Smart Edit is
        # intentionally constrained to the selected visual block and source facts.
        "brand": brand_context,
        "knowledgeMetadata": build_llm_knowledge_metadata(),
        "runtimeContext": build_architecture_runtime_context(),
        "sourceFactPackage": source_fact_package,
        "elementBreakdown": element_breakdown,
        "mediaContext": _build_smart_edit_media_context(deck),
        "currentBackground": (
            element_breakdown.get("background") if isinstance(element_breakdown, dict) else None
        ),
    }


def create_smart_edit(
    db: Session,
    *,
    deck_id: str,
    slide_id: str,
    block_id: str,
    instruction: str,
    audience_type: str,
) -> dict | None:
    block = _load_block(db, deck_id, slide_id, block_id)
    if block is None:
        return None
    deck = _load_deck_context(db, deck_id)
    if deck is None:
        return None
    provider_config = _resolve_claude_config(db, deck, use_case="smart_edit")
    knowledge_metadata = build_llm_knowledge_metadata()

    run = SmartEditRun(
        id=generate_id("run"),
        deck_id=deck_id,
        slide_id=slide_id,
        block_id=block_id,
        instruction=instruction,
        audience_type=audience_type,
    )
    db.add(run)
    db.flush()

    try:
        deck_context = _smart_edit_context(deck, slide_id, block_id, instruction=instruction, audience_type=audience_type)
        source_fact_package = deck_context.get("sourceFactPackage") if isinstance(deck_context.get("sourceFactPackage"), dict) else {}
        smart_edit_plan = _build_smart_edit_plan(deck_context)
        _record_smart_edit_artifact(
            db,
            deck_id=deck_id,
            run_id=run.id,
            artifact_type="smart_edit_source_facts",
            summary=f"Source fact package for Smart Edit run {run.id}.",
            payload_json=source_fact_package,
            metrics_json={
                "factCount": source_fact_package.get("factCount"),
                "factTypeCounts": source_fact_package.get("factTypeCounts"),
                "safetyFlagCounts": source_fact_package.get("safetyFlagCounts"),
                "selectedBlockFactCount": (source_fact_package.get("coverage") or {}).get("selectedBlockFactCount"),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (deck_context.get("runtimeContext") or {}).get("schemaVersion"),
            },
        )
        _record_smart_edit_artifact(
            db,
            deck_id=deck_id,
            run_id=run.id,
            artifact_type="smart_edit_plan",
            summary=f"Knowledge-aware Smart Edit plan for run {run.id}.",
            payload_json=smart_edit_plan,
            metrics_json={
                "factCount": source_fact_package.get("factCount"),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (deck_context.get("runtimeContext") or {}).get("schemaVersion"),
            },
        )
        raw_suggestion_payload = smart_edit_run(
            deck_id=deck_id,
            slide_id=slide_id,
            block_id=block_id,
            instruction=instruction,
            audience_type=audience_type,
            original_text=block.raw_text,
            deck_context=deck_context,
            provider_config=provider_config,
        )
        suggestion_payload = _normalize_suggestion_payload(raw_suggestion_payload, original_text=block.raw_text)
        raw_suggestion_payload = {**suggestion_payload, **raw_suggestion_payload}
        smart_edit_critique = _critique_smart_edit_payload(raw_suggestion_payload, source_fact_package)
        repair_performed = False
        if smart_edit_critique.get("status") == "review":
            repair_context = {
                **deck_context,
                "repairContext": {
                    "schemaVersion": "smart-edit-repair-context.v1",
                    "critique": smart_edit_critique,
                    "repairActions": smart_edit_critique.get("repairActions") or [],
                    "instruction": "Repair only the critique issues. Preserve factual claims and cite source_fact_ids.",
                },
            }
            repaired_raw_payload = smart_edit_run(
                deck_id=deck_id,
                slide_id=slide_id,
                block_id=block_id,
                instruction=f"{instruction}\nRepair critique issues: {smart_edit_critique.get('warnings')}",
                audience_type=audience_type,
                original_text=block.raw_text,
                deck_context=repair_context,
                provider_config=provider_config,
            )
            repaired_payload = _normalize_suggestion_payload(repaired_raw_payload, original_text=block.raw_text)
            repaired_raw_payload = {**repaired_payload, **repaired_raw_payload}
            repaired_critique = _critique_smart_edit_payload(repaired_raw_payload, source_fact_package)
            _record_smart_edit_artifact(
                db,
                deck_id=deck_id,
                run_id=run.id,
                artifact_type="smart_edit_repair",
                summary=f"Bounded Smart Edit repair pass for run {run.id}.",
                payload_json={
                    "schemaVersion": "smart-edit-repair.v1",
                    "originalCritique": smart_edit_critique,
                    "repairedCritique": repaired_critique,
                    "knowledgeMetadata": knowledge_metadata,
                },
                metrics_json={
                    "originalCritiqueStatus": smart_edit_critique.get("status"),
                    "repairedCritiqueStatus": repaired_critique.get("status"),
                    "repairedWarningCount": repaired_critique.get("warningCount"),
                    "repairedMissingInputCount": repaired_critique.get("missingInputCount"),
                    "repairedBlockingCount": (repaired_critique.get("decision") or {}).get("blockingCount"),
                    "repairedRepairActionCount": len(repaired_critique.get("repairActions") or []),
                },
            )
            suggestion_payload = repaired_payload
            smart_edit_critique = repaired_critique
            raw_suggestion_payload = repaired_raw_payload
            repair_performed = True
        _record_smart_edit_artifact(
            db,
            deck_id=deck_id,
            run_id=run.id,
            artifact_type="smart_edit_critique",
            summary=f"Knowledge-aware Smart Edit critique for run {run.id}.",
            payload_json={
                "schemaVersion": "smart-edit-critique-artifact.v1",
                "critique": smart_edit_critique,
                "sourceFactIds": raw_suggestion_payload.get("source_fact_ids") if isinstance(raw_suggestion_payload.get("source_fact_ids"), list) else [],
                "sourceFactsUsed": raw_suggestion_payload.get("source_facts_used") if isinstance(raw_suggestion_payload.get("source_facts_used"), list) else [],
                "knowledgeMetadata": knowledge_metadata,
            },
            metrics_json={
                "critiqueStatus": smart_edit_critique.get("status"),
                "critiqueWarningCount": smart_edit_critique.get("warningCount"),
                "critiqueMissingInputCount": smart_edit_critique.get("missingInputCount"),
                "critiqueBlockingCount": (smart_edit_critique.get("decision") or {}).get("blockingCount"),
                "repairActionCount": len(smart_edit_critique.get("repairActions") or []),
                "repairPerformed": repair_performed,
            },
        )

        suggestion = SmartEditSuggestion(
            id=generate_id("smart"),
            run_id=run.id,
            deck_id=deck_id,
            slide_id=slide_id,
            block_id=block_id,
            original_text=suggestion_payload["original_text"],
            suggested_text=suggestion_payload["suggested_text"],
            reason=suggestion_payload["reason"],
            risk_level=suggestion_payload["risk_level"],
            status="pending",
        )
        db.add(suggestion)
        db.commit()
        db.refresh(run)
        db.refresh(suggestion)
        record_agent_event(
            db,
            event_name="ai.smart_edit.completed",
            run_type="smart_edit",
            workspace_id=deck.workspace_id,
            deck_id=deck_id,
            user_id=getattr(deck, "user_id", None),
            run_id=run.id,
            status="completed",
            metadata={
                "slideId": slide_id,
                "blockId": block_id,
                "audienceType": audience_type,
                "riskLevel": suggestion.risk_level,
                "suggestionStatus": suggestion.status,
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (deck_context.get("runtimeContext") or {}).get("schemaVersion"),
                "sourceFactCount": source_fact_package.get("factCount"),
                "sourceFactTypeCounts": source_fact_package.get("factTypeCounts"),
                "sourceFactSafetyFlagCounts": source_fact_package.get("safetyFlagCounts"),
                "critiqueStatus": smart_edit_critique.get("status"),
                "critiqueWarningCount": smart_edit_critique.get("warningCount"),
                "critiqueMissingInputCount": smart_edit_critique.get("missingInputCount"),
                "critiqueBlockingCount": (smart_edit_critique.get("decision") or {}).get("blockingCount"),
                "repairActionCount": len(smart_edit_critique.get("repairActions") or []),
                "repairPerformed": repair_performed,
            },
            commit=True,
        )
        return {"run": _map_run(run), "suggestion": _map_suggestion(suggestion)}
    except (KeyError, TypeError, ValueError, SQLAlchemyError) as exc:
        db.rollback()
        record_agent_event(
            db,
            event_name="ai.smart_edit.failed",
            run_type="smart_edit",
            workspace_id=deck.workspace_id,
            deck_id=deck_id,
            user_id=getattr(deck, "user_id", None),
            run_id=run.id,
            event_level="error",
            status="failed",
            error_category=exc.__class__.__name__,
            error_message=str(exc),
            metadata={
                "slideId": slide_id,
                "blockId": block_id,
                "audienceType": audience_type,
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (deck_context.get("runtimeContext") or {}).get("schemaVersion"),
            },
            commit=True,
        )
        raise


def get_smart_edit_run(db: Session, deck_id: str, run_id: str) -> dict | None:
    suggestion = (
        db.query(SmartEditSuggestion)
        .filter(SmartEditSuggestion.deck_id == deck_id, SmartEditSuggestion.run_id == run_id)
        .one_or_none()
    )
    return {"suggestion": _map_suggestion(suggestion)} if suggestion is not None else None


def classify_smart_edit_intent(
    db: Session,
    *,
    deck_id: str,
    slide_id: str,
    block_id: str | None,
    instruction: str,
    audience_type: str,
    deadline=None,
    usage_sink: dict | None = None,
) -> dict | None:
    deck = _load_deck_context(db, deck_id)
    if deck is None:
        return None
    context = _smart_edit_context(deck, slide_id, block_id or "", instruction=instruction, audience_type=audience_type)
    chunk_sync = sync_deck_vector_chunks(db, deck_id, user_instruction=instruction)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text=instruction,
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "accepted_edit", "deck_map_analysis", "audience_profile", "diligence_lens"],
        limit=8,
    )
    visual_context = build_visual_context(deck, slide_id=slide_id, limit=2)
    llm_context = {
        **context,
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {"name": "smart_edit", "version": load_prompt_package("smart_edit")["version"], "section": "intent_classifier"},
    }
    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="smart_edit")
    raw = call_structured_json(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("apiKey"),
        system_prompt="You output only valid JSON for backend-validated smart edit intent classification.",
        user_prompt=build_prompt_package_text("smart_edit", "intent_classifier", context_label="Smart edit classification context", context=llm_context),
        timeout=90,
        max_tokens=1500,
        image_urls=visual_context.get("imageUrls"),
        credential_source=config.get("source", "environment"),
        deadline=deadline,
        usage_sink=usage_sink,
    )
    label = _fit_text(str(((raw.get("intent") or {}).get("label") or raw.get("label") or "rewrite")), 120)
    confidence = str(((raw.get("intent") or {}).get("confidence") or raw.get("confidence") or "medium"))
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return {
        "label": label,
        "confidence": confidence,
        "rationale": _fit_text(str(((raw.get("intent") or {}).get("rationale") or raw.get("rationale") or "")), 500) or None,
        "missingInputs": [str(item)[:300] for item in ((raw.get("intent") or {}).get("missingInputs") or raw.get("missingInputs") or []) if str(item).strip()][:12],
        "system": {
            "provider": config["provider"],
            "model": config["model"],
            "promptPackage": llm_context["promptPackage"],
            "vectorRetrieval": retrieval,
            "vectorSync": chunk_sync,
        },
    }


def _classify_smart_edit_intent_for_patch(instruction: str) -> dict:
    """Classify the durable patch scope without spending a second LLM call.

    The patch generator still receives the complete instruction and context and
    remains the only model call required to create the reviewable change. This
    bounded classifier prevents a non-essential empty structured response from
    failing the job before patch generation begins.
    """
    normalized = instruction.casefold()
    if any(term in normalized for term in ("background", "colour", "color", "font", "layout", "position", "size", "bigger", "smaller")):
        label = "visual_style"
    elif any(term in normalized for term in ("shorten", "rewrite", "wording", "headline", "title", "copy", "text")):
        label = "rewrite"
    else:
        label = "targeted_edit"
    return {
        "label": label,
        "confidence": "medium",
        "rationale": "Deterministic scope classification; the provider generates and validates the reviewable patch.",
        "missingInputs": [],
        "system": {"provider": "deterministic", "model": None},
    }


def create_reviewable_smart_edit_patch(
    db: Session,
    *,
    deck_id: str,
    slide_id: str,
    block_id: str | None,
    instruction: str,
    audience_type: str,
) -> dict | None:
    deck = _load_deck_context(db, deck_id)
    if deck is None:
        return None
    selected_block = _load_block(db, deck_id, slide_id, block_id) if block_id else None
    selected_slide = next((slide for slide in deck.slides if slide.id == slide_id), None)
    if selected_slide is None:
        return None
    if selected_block is None:
        return None
    run_id = generate_id("sew")
    review_run = SmartEditRun(
        id=run_id,
        deck_id=deck_id,
        slide_id=slide_id,
        block_id=selected_block.id,
        instruction=instruction,
        audience_type=audience_type,
        status="queued",
    )
    db.add(review_run)
    job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_SMART_EDIT,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"smart-edit:{run_id}",
        input_payload={"runId": run_id},
    )
    # PostgreSQL cannot infer insert ordering from scalar foreign-key values.
    # Persist the durable workflow root first, while keeping both inserts in
    # this transaction so a later failure still rolls the complete command back.
    # Flush all pending workflow records so its creation event is persisted in
    # dependency order too; the SmartEditRun is still unlinked at this point.
    db.flush()
    review_run.workflow_job_id = job.id
    db.commit()
    return get_reviewable_smart_edit_run(db, deck_id=deck_id, slide_id=slide_id, run_id=run_id)


def execute_reviewable_smart_edit_patch(db: Session, *, run_id: str, deadline=None, usage_sink: dict | None = None) -> dict:
    review_run = db.query(SmartEditRun).filter(SmartEditRun.id == run_id).one_or_none()
    if review_run is None:
        raise ValueError("Smart Edit run not found")
    existing = get_reviewable_smart_edit_run(db, deck_id=review_run.deck_id, slide_id=review_run.slide_id, run_id=run_id)
    if existing is not None and existing.get("status") in {"completed", "no_change", "accepted", "rejected", "applied"}:
        return existing
    review_run.status = "running"
    review_run.error_code = None
    review_run.error_message = None
    db.commit()
    deck_id = review_run.deck_id
    slide_id = review_run.slide_id
    block_id = review_run.block_id
    instruction = review_run.instruction
    audience_type = review_run.audience_type
    deck = _load_deck_context(db, deck_id)
    selected_block = _load_block(db, deck_id, slide_id, block_id)
    selected_slide = next((slide for slide in deck.slides if slide.id == slide_id), None) if deck is not None else None
    if deck is None or selected_block is None or selected_slide is None:
        raise ValueError("Deck, slide, or block not found")
    intent = _classify_smart_edit_intent_for_patch(instruction)
    context = _smart_edit_context(deck, slide_id, block_id or "", instruction=instruction, audience_type=audience_type)
    chunk_sync = sync_deck_vector_chunks(db, deck_id, user_instruction=instruction)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text=f"{instruction}\nIntent: {intent['label']}",
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "accepted_edit", "deck_map_analysis", "diligence_lens", "audience_profile", "generated_version"],
        limit=10,
    )
    visual_context = build_visual_context(deck, slide_id=slide_id, limit=2)
    llm_context = {
        **context,
        "intent": intent,
        "targetContract": {
            "blockId": selected_block.id if selected_block is not None else None,
            "beforeText": selected_block.raw_text if selected_block is not None else None,
            "rules": [
                "beforeText must exactly match targetContract.beforeText.",
                "afterText must contain only the replacement text for this block, never the full slide.",
                "afterText must differ from beforeText when proposing a text edit.",
            ],
        },
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {"name": "smart_edit", "version": load_prompt_package("smart_edit")["version"], "section": "patch_generator"},
    }
    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="smart_edit")
    raw = call_structured_json(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("apiKey"),
        system_prompt="You output only valid JSON for backend-validated smart edit patches.",
        user_prompt=build_prompt_package_text("smart_edit", "patch_generator", context_label="Smart edit patch context", context=llm_context),
        timeout=90,
        max_tokens=2500,
        image_urls=visual_context.get("imageUrls"),
        credential_source=config.get("source", "environment"),
        deadline=deadline,
        usage_sink=usage_sink,
    )
    def repair_patch(validation_error: str) -> dict:
        repair_context = {
            **llm_context,
            "rejectedPatch": raw.get("patch") if isinstance(raw.get("patch"), dict) else raw,
            "targetValidationError": validation_error,
            "repairInstruction": (
                "Return one corrected patch. Match targetContract.beforeText exactly, "
                "change only that block, and provide a distinct afterText without adding facts."
            ),
        }
        return call_structured_json(
            provider=config["provider"],
            model=config["model"],
            api_key=config.get("apiKey"),
            system_prompt="You output only valid JSON for backend-validated smart edit patch repair.",
            user_prompt=build_prompt_package_text("smart_edit", "patch_generator", context_label="Smart edit patch repair context", context=repair_context),
            timeout=90,
            max_tokens=2500,
            image_urls=visual_context.get("imageUrls"),
            credential_source=config.get("source", "environment"),
            deadline=deadline,
            usage_sink=usage_sink,
        )

    patch = _validate_or_repair_reviewable_patch(
        raw,
        original_text=selected_block.raw_text if selected_block else (selected_slide.raw_text or selected_slide.title or ""),
        instruction=instruction,
        repair=repair_patch,
    )
    has_text_change = re.sub(r"\s+", " ", patch["beforeText"]).strip() != re.sub(r"\s+", " ", patch["afterText"]).strip()
    suggestion = SmartEditSuggestion(
        id=generate_id("smart"),
        run_id=run_id,
        deck_id=deck_id,
        slide_id=slide_id,
        block_id=selected_block.id,
        original_text=patch["beforeText"],
        suggested_text=patch["afterText"],
        reason=str(intent.get("rationale") or "AI prepared a reviewable Smart Edit patch."),
        risk_level="medium" if patch.get("requiresReview") else "low",
        status="pending" if has_text_change else "no_change",
    )
    db.add(suggestion)
    artifact = _record_smart_edit_workflow_artifact(
        db,
        deck_id=deck_id,
        run_id=run_id,
        slide_id=slide_id,
        block_id=block_id,
        instruction=instruction,
        audience_type=audience_type,
        intent=intent,
        patch=patch,
        system={
            "provider": config["provider"],
            "model": config["model"],
            "promptPackage": llm_context["promptPackage"],
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
        },
    )
    review_run.status = "completed" if has_text_change else "no_change"
    db.commit()
    return {
        "runId": run_id,
        "deckId": deck_id,
        "slideId": slide_id,
        "blockId": block_id,
        "status": "completed" if has_text_change else "no_change",
        "intent": {k: v for k, v in intent.items() if k != "system"},
        "patch": patch,
        "artifactId": artifact.id,
        "suggestionId": suggestion.id,
        "cached": False,
        "system": intent.get("system") or {},
    }


def get_reviewable_smart_edit_run(db: Session, *, deck_id: str, slide_id: str, run_id: str) -> dict | None:
    run = (
        db.query(SmartEditRun)
        .filter(SmartEditRun.id == run_id, SmartEditRun.deck_id == deck_id, SmartEditRun.slide_id == slide_id)
        .one_or_none()
    )
    if run is None:
        return None
    workflow_job = db.query(WorkflowJob).filter(WorkflowJob.id == run.workflow_job_id).one_or_none()
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == "smart_edit_workflow_run",
            DeckLlmArtifact.artifact_key == run_id,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if artifact is None or not artifact.payload_json:
        failure_stage = "worker" if run.status in {"failed_retryable", "failed_final", "failed", "timed_out"} else None
        return {
            "runId": run_id,
            "deckId": deck_id,
            "slideId": slide_id,
            "blockId": run.block_id,
            "status": run.status,
            "intent": None,
            "patch": None,
            "artifactId": None,
            "suggestionId": None,
            "cached": True,
            "system": {"workflowJobId": run.workflow_job_id},
            "error": {"code": run.error_code, "message": run.error_message, "recoverable": run.status == "failed_retryable"} if run.error_message else None,
            "developer": _smart_edit_developer_envelope(
                run=run,
                workflow_job=workflow_job,
                artifact_id=None,
                suggestion_id=None,
                failure_stage=failure_stage,
            ),
        }
    payload = artifact.payload_json
    if str(payload.get("slideId") or "") != slide_id:
        return None
    suggestion = (
        db.query(SmartEditSuggestion)
        .filter(SmartEditSuggestion.deck_id == deck_id, SmartEditSuggestion.run_id == run_id)
        .one_or_none()
    )
    failure_stage = "suggestion" if suggestion is None else None
    return {
        "runId": run_id,
        "deckId": deck_id,
        "slideId": slide_id,
        "blockId": payload.get("blockId"),
        "status": suggestion.status if suggestion is not None and suggestion.status != "pending" else "completed",
        "intent": payload.get("intent") or {},
        "patch": payload.get("patch") or {},
        "artifactId": artifact.id,
        "suggestionId": suggestion.id if suggestion is not None else None,
        "cached": True,
        "system": payload.get("system") or {},
        "developer": _smart_edit_developer_envelope(
            run=run,
            workflow_job=workflow_job,
            artifact_id=artifact.id,
            suggestion_id=suggestion.id if suggestion is not None else None,
            failure_stage=failure_stage,
        ),
    }


def _smart_edit_developer_envelope(
    *,
    run: SmartEditRun,
    workflow_job: WorkflowJob | None,
    artifact_id: str | None,
    suggestion_id: str | None,
    failure_stage: str | None,
) -> dict:
    terminal_failure = run.status in {"failed_retryable", "failed_final", "failed", "timed_out"}
    return {
        "schemaVersion": "product-developer-envelope.v1",
        "dependencies": [
            {"key": "workflow-job", "status": workflow_job.status if workflow_job is not None else "missing", "resourceId": run.workflow_job_id},
            {"key": "smart-edit-artifact", "status": "ready" if artifact_id else "missing", "resourceId": artifact_id},
            {"key": "smart-edit-suggestion", "status": "ready" if suggestion_id else "missing", "resourceId": suggestion_id},
        ],
        "artifactLineage": {
            "runId": run.id,
            "workflowJobId": run.workflow_job_id,
            "artifactId": artifact_id,
            "suggestionId": suggestion_id,
        },
        "degradation": "degraded" if terminal_failure or failure_stage else "ready" if suggestion_id else "pending",
        "failureStage": failure_stage,
        "errorCode": run.error_code if terminal_failure else None,
    }


def _validate_reviewable_patch(raw: dict, *, original_text: str, instruction: str = "") -> dict:
    patch = raw.get("patch") if isinstance(raw.get("patch"), dict) else raw

    def provider_value(camel_key: str, snake_key: str, default=None):
        """Read the canonical provider field while tolerating documented legacy aliases."""
        if camel_key in patch:
            return patch[camel_key]
        return patch.get(snake_key, default)

    confidence = str(patch.get("confidence") or "medium")
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"

    model_before_text = _fit_text(str(patch.get("beforeText") or patch.get("before_text") or original_text), 4000)
    model_after_text = _fit_text(str(patch.get("afterText") or patch.get("after_text") or original_text), 4000)
    normalized_original_text = re.sub(r"\s+", " ", original_text).strip()
    normalized_model_after_text = re.sub(r"\s+", " ", model_after_text).strip()
    # The persisted selected block is authoritative. Provider-supplied
    # beforeText is descriptive context only: long visual/OCR blocks can be
    # normalized or truncated by the model even when afterText is a valid
    # targeted replacement. Persisting original_text below prevents the model
    # from changing the mutation target without requiring an exact echo.
    # DISABLED: A source-grounded provider may correctly conclude that an
    # already concise block needs no rewrite; that is a terminal no-change
    # result, not a provider failure or a reason to synthesize fallback copy.
    # if normalized_model_after_text == normalized_original_text:
    #     raise ValueError("Smart Edit patch did not change the selected block.")

    element_patches_value = provider_value("elementPatches", "element_patches", [])
    raw_element_patches = element_patches_value if isinstance(element_patches_value, list) else []
    validated_element_patches: list[dict] = []
    seen_element_ids: set[str] = set()
    for ep in raw_element_patches[:16]:
        if not isinstance(ep, dict):
            continue
        element_id = str(ep.get("elementId") or ep.get("element_id") or "")
        if not element_id or element_id in seen_element_ids:
            continue
        if element_id == "__background__" and not _instruction_requests_background_change(instruction):
            continue
        seen_element_ids.add(element_id)
        properties = ep.get("properties") if isinstance(ep.get("properties"), dict) else {}
        cleaned_properties = {
            str(k): v for k, v in properties.items()
            if isinstance(k, str) and k.strip() and v is not None
        }
        validated_element_patches.append({
            "elementId": element_id,
            "properties": cleaned_properties,
            "reason": str(ep.get("reason") or "")[:400] if ep.get("reason") else "",
        })

    return {
        # DISABLED: Model-supplied beforeText was persisted as authoritative,
        # allowing a slide-wide response to be applied to one selected block.
        # "beforeText": _fit_text(str(patch.get("beforeText") or patch.get("before_text") or original_text), 4000),
        "beforeText": _fit_text(original_text, 4000),
        "afterText": model_after_text,
        "layoutPatch": provider_value("layoutPatch", "layout_patch", {}) if isinstance(provider_value("layoutPatch", "layout_patch", {}), dict) else {},
        "elementPatches": validated_element_patches,
        "riskControls": [str(item)[:300] for item in provider_value("riskControls", "risk_controls", []) if str(item).strip()][:12],
        "confidence": confidence,
        "requiresReview": bool(provider_value("requiresReview", "requires_review", True)),
        "sourceFactsUsed": [str(item)[:300] for item in provider_value("sourceFactsUsed", "source_facts_used", []) if str(item).strip()][:12],
        "sourceFactIds": [str(item)[:80] for item in provider_value("sourceFactIds", "source_fact_ids", []) if str(item).strip()][:24],
        "missingInputs": [str(item)[:300] for item in provider_value("missingInputs", "missing_inputs", []) if str(item).strip()][:12],
    }


def _validate_or_repair_reviewable_patch(
    raw: dict,
    *,
    original_text: str,
    instruction: str = "",
    repair: Callable[[str], dict] | None = None,
) -> dict:
    try:
        return _validate_reviewable_patch(raw, original_text=original_text, instruction=instruction)
    except ValueError as exc:
        if repair is None:
            raise
        validation_error = str(exc)

    # DISABLED: Deterministic punctuation/truncation changed user content without
    # a real Qwen response and could turn a no-op into a misleading suggestion.
    # repaired = dict(raw)
    # provider_patch = raw.get("patch") if isinstance(raw.get("patch"), dict) else raw
    # repaired_patch = dict(provider_patch)
    # words = original_text.strip().split()
    # if any(token in instruction.lower() for token in ("concise", "shorten", "shorter")) and len(words) > 8:
    #     keep = max(8, int(len(words) * 0.75))
    #     after_text = " ".join(words[:keep]).rstrip(".,;:") + "..."
    # else:
    #     stripped = original_text.strip()
    #     after_text = stripped[:-1].rstrip() if stripped.endswith(".") else stripped + "."
    # repaired_patch["afterText"] = after_text
    # repaired_patch["riskControls"] = [
    #     *[str(item) for item in repaired_patch.get("riskControls", []) if str(item).strip()],
    #     "Provider returned no textual change; applied a bounded non-factual editorial fallback.",
    # ]
    # repaired["patch"] = repaired_patch
    repaired = repair(validation_error)
    return _validate_reviewable_patch(repaired, original_text=original_text, instruction=instruction)


def _record_smart_edit_workflow_artifact(
    db: Session,
    *,
    deck_id: str,
    run_id: str,
    slide_id: str,
    block_id: str | None,
    instruction: str,
    audience_type: str,
    intent: dict,
    patch: dict,
    system: dict,
) -> DeckLlmArtifact:
    artifact = DeckLlmArtifact(
        id=generate_id("artifact"),
        deck_id=deck_id,
        artifact_type="smart_edit_workflow_run",
        artifact_key=run_id,
        schema_version="smart-edit-workflow.v1",
        status="ready",
        summary=_fit_text(str(intent.get("label") or "Smart edit patch"), 200),
        payload_json={
            "deckId": deck_id,
            "slideId": slide_id,
            "blockId": block_id,
            "instruction": instruction,
            "audienceType": audience_type,
            "intent": {k: v for k, v in intent.items() if k != "system"},
            "patch": patch,
            "system": system,
        },
        metrics_json={
            "requiresReview": patch.get("requiresReview"),
            "missingInputCount": len(patch.get("missingInputs") or []),
            "sourceFactIdCount": len(patch.get("sourceFactIds") or []),
        },
    )
    db.add(artifact)
    db.flush()
    return artifact
