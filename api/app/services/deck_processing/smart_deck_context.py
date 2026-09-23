"""Smart Deck source workspace preparation.

Owns: building the source_v1 Smart Deck workspace from already-persisted source
slides/blocks, optional label enrichment, and source artifacts for the Smart
Deck UI baseline.
Must not own: source extraction, preview rendering, workflow job claiming, or
final Smart Deck ready publication.
Stage: smart_deck_context.
Status: KEEP
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import (
    Deck,
    DeckGenerationRun,
    DeckGenerationWorkspace,
    DeckSlide,
    DeckSlideBlock,
    DeckSlideVersion,
)
from app.services.llm.artifact_service import write_source_v1_artifacts
from app.services.rendering.schema_validation import validate_source_labels
from app.services.llm.prompt_builder import (
    build_source_enrichment_prompt,
    build_source_v1_context,
    infer_block_kind,
    infer_semantic_role,
    infer_slide_semantic_type,
    stable_content_hash,
)
from app.services.llm.source_enrichment import enrich_source_labels_with_llm
from app.services.deck_processing.generation_workspace_service import ensure_generation_workspace

SOURCE_RUN_MODE = "source_ingestion_v1"
SOURCE_VERSION_STATUS = "source_v1"


def prepare_smart_deck_source_workspace(
    db: Session,
    deck_id: str,
    *,
    commit: bool = False,
) -> dict[str, Any]:
    """Create the original source V1 baseline used by the Smart Deck UI.

    The deterministic extractor owns thumbnails and raw slide/block records. The
    optional LLM enrichment step can name/classify the extracted slide blocks,
    but only after output validation. The DB is updated only through this service.

    Audit note: this is close to the requested SmartDeckContext compiler, but it
    currently emits source_v1 workspace artifacts rather than a single typed
    `smart_deck_context` artifact containing brand_profile, deck_map, and
    source_facts. That gap is tracked in docs/smart_deck_pipeline_file_audit.md.
    """
    deck = _load_deck(db, deck_id)
    if deck is None:
        raise ValueError("Deck not found")
    if not deck.slides:
        raise ValueError("Deck has no extracted source slides")

    slide_ids = {slide.id for slide in deck.slides}
    block_ids = {block.id for slide in deck.slides for block in slide.blocks}

    deterministic_enrichment = _build_deterministic_enrichment(deck)
    deterministic_validated = validate_source_labels(deterministic_enrichment, slide_ids=slide_ids, block_ids=block_ids)

    initial_context = build_source_v1_context(deck)
    prompt_bundle = build_source_enrichment_prompt(initial_context)
    llm_result = enrich_source_labels_with_llm(
        prompt_bundle=prompt_bundle,
        slide_ids=slide_ids,
        block_ids=block_ids,
    )
    validated_enrichment = llm_result.get("validated") if llm_result.get("used") else None
    if not isinstance(validated_enrichment, dict) or not validated_enrichment.get("ok"):
        validated_enrichment = deterministic_validated
        enrichment_source = "deterministic"
    else:
        enrichment_source = "llm"

    _apply_source_labels(deck, validated_enrichment, source=enrichment_source)

    workspace = _ensure_generation_workspace(db, deck)
    context = build_source_v1_context(deck)
    source_run = _upsert_source_generation_run(
        db,
        workspace=workspace,
        deck=deck,
        request_payload={
            "sourceVersion": "original_source_v1",
            "prompt": prompt_bundle,
            "contextArtifact": "smart_deck_source_v1_context/source_v1_context",
            "llmStatus": llm_result.get("status"),
            "llmProvider": llm_result.get("provider"),
            "llmModel": llm_result.get("model"),
        },
        provider=str(llm_result.get("provider") or "deterministic") if enrichment_source == "llm" else "deterministic",
        model=str(llm_result.get("model") or "source_v1") if enrichment_source == "llm" else "source_v1",
        generated_payload={
            "sourceVersion": "original_source_v1",
            "enrichmentSource": enrichment_source,
            "llmStatus": llm_result.get("status"),
            "llmProvider": llm_result.get("provider"),
            "llmModel": llm_result.get("model"),
            "llmError": llm_result.get("error"),
            "validated": validated_enrichment,
        },
    )
    source_versions = _upsert_source_slide_versions(
        db,
        workspace=workspace,
        generation_run=source_run,
        deck=deck,
        context=context,
    )
    enrichment_payload = {
        "status": enrichment_source,
        "llmStatus": llm_result.get("status"),
        "provider": llm_result.get("provider"),
        "model": llm_result.get("model"),
        "error": llm_result.get("error"),
        **validated_enrichment,
    }
    artifacts = write_source_v1_artifacts(
        db,
        deck=deck,
        context=context,
        prompt_bundle=prompt_bundle,
        extraction_run_id=None,
        source_versions=source_versions,
        enrichment=enrichment_payload,
    )

    workspace.generation_status = "source_ready"
    db.flush()
    if commit:
        db.commit()

    return {
        "ok": True,
        "deckId": deck.id,
        "workspaceId": workspace.id,
        "sourceRunId": source_run.id,
        "sourceVersion": "original_source_v1",
        "slideCount": len(deck.slides),
        "sourceSlideVersionCount": len(source_versions),
        "artifactCount": len(artifacts),
        "artifactTypes": [artifact.artifact_type for artifact in artifacts],
        "enrichmentSource": enrichment_source,
        "llmStatus": llm_result.get("status"),
        "llmProvider": llm_result.get("provider"),
        "llmModel": llm_result.get("model"),
        "nextAction": "select_slides_to_change",
    }


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.file),
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
            selectinload(Deck.deck_generation_workspace),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _build_deterministic_enrichment(deck: Deck) -> dict[str, Any]:
    slides_payload: list[dict[str, Any]] = []
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        blocks_payload: list[dict[str, Any]] = []
        for index, block in enumerate(sorted(slide.blocks, key=lambda item: item.block_index)):
            block_kind = infer_block_kind(block, block_index=index)
            blocks_payload.append(
                {
                    "blockId": block.id,
                    "blockKind": block_kind,
                    "semanticRole": infer_semantic_role(block, block_kind=block_kind, block_index=index),
                    "confidence": 0.72,
                }
            )
        slides_payload.append(
            {
                "slideId": slide.id,
                "semanticSlideType": infer_slide_semantic_type(slide),
                "summary": _slide_summary(slide),
                "confidence": 0.72,
                "blocks": blocks_payload,
            }
        )
    return {"slides": slides_payload}


def _apply_source_labels(deck: Deck, enrichment: dict[str, Any], *, source: str) -> None:
    slide_labels = {
        item["slideId"]: item
        for item in enrichment.get("slides", [])
        if isinstance(item, dict) and item.get("slideId")
    }
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        slide_label = slide_labels.get(slide.id, {})
        slide.semantic_slide_type = slide_label.get("semanticSlideType") or infer_slide_semantic_type(slide)
        slide.summary = slide_label.get("summary") or _slide_summary(slide)
        slide.text_hash = stable_content_hash(slide.raw_text)
        slide.metadata_json = {
            **(slide.metadata_json or {}),
            "sourceVersion": "original_source_v1",
            "semanticEnrichment": source,
        }
        block_labels = {
            item["blockId"]: item
            for item in slide_label.get("blocks", [])
            if isinstance(item, dict) and item.get("blockId")
        }
        for index, block in enumerate(sorted(slide.blocks, key=lambda item: item.block_index)):
            label = block_labels.get(block.id, {})
            _apply_block_label(block, label, index=index, source=source)


def _apply_block_label(block: DeckSlideBlock, label: dict[str, Any], *, index: int, source: str) -> None:
    block_kind = label.get("blockKind") or infer_block_kind(block, block_index=index)
    semantic_role = label.get("semanticRole") or infer_semantic_role(block, block_kind=block_kind, block_index=index)
    text = block.text or block.normalized_text or block.raw_text
    block.block_kind = block_kind
    block.semantic_role = semantic_role
    block.text = text
    block.extraction_stage = "source_v1"
    block.extraction_source = block.extraction_source or "deterministic_pdf"
    block.content_hash = stable_content_hash(text)
    block.metadata_json = {
        **(block.metadata_json or {}),
        "sourceVersion": "original_source_v1",
        "semanticEnrichment": source,
        "semanticConfidence": label.get("confidence"),
    }


def _ensure_generation_workspace(db: Session, deck: Deck) -> DeckGenerationWorkspace:
    if deck.deck_generation_workspace is not None:
        return deck.deck_generation_workspace

    # REPLACED: The former query-then-insert implementation raced when a worker,
    # direct context request, or Smart Edit created the same deck workspace.
    # workspace = db.query(DeckGenerationWorkspace).filter(DeckGenerationWorkspace.deck_id == deck.id).first()
    # if workspace is None:
    #     workspace = DeckGenerationWorkspace(
    #         id=generate_id("dgw"),
    #         deck_id=deck.id,
    #         generation_status="source_ready",
    #     )
    #     db.add(workspace)
    #     db.flush()
    # return workspace
    return ensure_generation_workspace(
        db,
        deck_id=deck.id,
        generation_status="source_ready",
    )


def _upsert_source_generation_run(
    db: Session,
    *,
    workspace: DeckGenerationWorkspace,
    deck: Deck,
    request_payload: dict[str, Any],
    provider: str,
    model: str,
    generated_payload: dict[str, Any],
) -> DeckGenerationRun:
    generation_run = (
        db.query(DeckGenerationRun)
        .filter(
            DeckGenerationRun.deck_id == deck.id,
            DeckGenerationRun.deck_generation_workspace_id == workspace.id,
            DeckGenerationRun.generation_mode == SOURCE_RUN_MODE,
            DeckGenerationRun.scope_type == "source_deck",
        )
        .order_by(DeckGenerationRun.created_at.desc())
        .first()
    )
    generated_deck_json = json.dumps(generated_payload, ensure_ascii=False)
    if generation_run is None:
        generation_run = DeckGenerationRun(
            id=generate_id("dgr"),
            deck_generation_workspace_id=workspace.id,
            deck_id=deck.id,
            status="completed",
            provider=provider,
            model=model,
            generation_mode=SOURCE_RUN_MODE,
            scope_type="source_deck",
            request_payload_json=json.dumps(request_payload, ensure_ascii=False),
            generated_deck_json=generated_deck_json,
            quality_score=None,
        )
        db.add(generation_run)
    else:
        generation_run.status = "completed"
        generation_run.provider = provider
        generation_run.model = model
        generation_run.request_payload_json = json.dumps(request_payload, ensure_ascii=False)
        generation_run.generated_deck_json = generated_deck_json
        generation_run.error_message = None
        generation_run.updated_at = datetime.utcnow()
    db.flush()
    return generation_run


def _upsert_source_slide_versions(
    db: Session,
    *,
    workspace: DeckGenerationWorkspace,
    generation_run: DeckGenerationRun,
    deck: Deck,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    slide_context_by_id = {
        slide["slideId"]: slide
        for slide in context.get("slides", [])
        if isinstance(slide, dict) and slide.get("slideId")
    }
    source_versions: list[dict[str, Any]] = []
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        version_payload = {
            "versionRole": "original_source_v1",
            "sourceSlideId": slide.id,
            "sourceSlideIndex": slide.slide_index,
            "title": slide.title,
            "semanticSlideType": slide.semantic_slide_type,
            "source": slide_context_by_id.get(slide.id, {}),
        }
        version = (
            db.query(DeckSlideVersion)
            .filter(
                DeckSlideVersion.deck_generation_workspace_id == workspace.id,
                DeckSlideVersion.generation_run_id == generation_run.id,
                DeckSlideVersion.source_slide_id == slide.id,
                DeckSlideVersion.version_number == 1,
            )
            .first()
        )
        if version is None:
            version = DeckSlideVersion(
                id=generate_id("dsv"),
                deck_generation_workspace_id=workspace.id,
                generation_run_id=generation_run.id,
                source_slide_id=slide.id,
                slide_index=slide.slide_index,
                source_slide_title=slide.title,
                version_number=1,
                title=slide.title or f"Slide {slide.slide_index + 1}",
                status=SOURCE_VERSION_STATUS,
                generated_slide_json=json.dumps(version_payload, ensure_ascii=False),
            )
            db.add(version)
        else:
            version.slide_index = slide.slide_index
            version.source_slide_title = slide.title
            version.title = slide.title or f"Slide {slide.slide_index + 1}"
            version.status = SOURCE_VERSION_STATUS
            version.generated_slide_json = json.dumps(version_payload, ensure_ascii=False)
            version.updated_at = datetime.utcnow()
        db.flush()
        source_versions.append(
            {
                "slideId": slide.id,
                "slideVersionId": version.id,
                "versionNumber": version.version_number,
                "status": version.status,
                "title": version.title,
            }
        )
    return source_versions


def _slide_summary(slide: DeckSlide) -> str:
    text = (slide.raw_text or slide.narrative_notes or slide.title or "").strip()
    if not text:
        return slide.title or f"Slide {slide.slide_index + 1}"
    return text[:500]
