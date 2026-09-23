from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import (
    BlockClassification,
    Deck,
    DeckSlide,
    DeckSlideBlock,
    DeckSlideRevision,
    DeckGenerationWorkspace,
    DeckFeedbackEvent,
    DeckGenerationRun,
    DeckSlideVersion,
)
from app.services.deck_processing.save_confirmation import get_latest_save_confirmation_for_deck, map_save_confirmation
from app.services.deck_processing.generation_workspace_service import ensure_generation_workspace
from app.schemas.generation import (
    DeckWorkspaceModelResponse,
    GenerateSlidesRequest,
    GeneratedDeckPayload,
    SlideFeedbackEventResponse,
    SubmitSlideFeedbackRequest,
)
from app.services.generation.claude.claude_generate_slides import generate_slides_with_claude
from app.services.generation.openai.openai_generate_slides import generate_slides_with_openai
from app.services.llm.generation_service import _resolve_claude_config


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _map_block_type(block_type: str) -> str:
    return {
        "heading": "headline",
        "subheading": "body",
        "body": "body",
        "metric": "metric",
        "caption": "body",
        "quote": "quote",
        "image_placeholder": "bullet",
        "shape": "bullet",
        "button_label": "body",
    }.get(block_type, "body")


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.llm_artifacts),
            selectinload(Deck.deck_generation_workspace).selectinload(DeckGenerationWorkspace.generation_runs),
            selectinload(Deck.deck_generation_workspace).selectinload(DeckGenerationWorkspace.slide_versions),
            selectinload(Deck.deck_generation_workspace).selectinload(DeckGenerationWorkspace.feedback_events),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _load_slide_classifications(db: Session, slide_ids: list[str]) -> dict[str, dict | None]:
    if not slide_ids:
        return {}

    blocks = (
        db.query(DeckSlideBlock)
        .filter(DeckSlideBlock.slide_id.in_(slide_ids))
        .order_by(DeckSlideBlock.slide_id.asc(), DeckSlideBlock.block_index.asc())
        .all()
    )
    block_ids = [block.id for block in blocks]
    classifications = []
    if block_ids:
        classifications = (
            db.query(BlockClassification)
            .filter(BlockClassification.block_id.in_(block_ids))
            .order_by(BlockClassification.confidence.desc())
            .all()
        )

    classification_lookup: dict[str, dict | None] = {}
    for block in blocks:
        match = next((item for item in classifications if item.block_id == block.id), None)
        classification_lookup[block.id] = (
            {
                "id": match.id,
                "blockId": match.block_id,
                "semanticTag": match.semantic_tag,
                "diligenceCategory": match.diligence_category,
                "confidence": match.confidence,
            }
            if match is not None
            else None
        )

    return classification_lookup


def _map_workspace_slide(slide: DeckSlide, classification_lookup: dict[str, dict | None]) -> dict:
    blocks = sorted(slide.blocks, key=lambda item: item.block_index)
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "slideNumber": slide.slide_index,
        "title": slide.title,
        "rawText": slide.raw_text,
        "summary": slide.narrative_notes or None,
        "slideRole": slide.role or "unknown",
        "blocks": [
            {
                "id": block.id,
                "deckId": slide.deck_id,
                "slideId": slide.id,
                "blockIndex": block.block_index,
                "blockType": block.block_type,
                "rawText": block.raw_text,
                "currentText": block.raw_text,
                "normalizedText": block.normalized_text,
                "classification": classification_lookup.get(block.id),
            }
            for block in blocks
        ],
    }


def _map_feedback_event(event: DeckFeedbackEvent) -> SlideFeedbackEventResponse:
    payload = json.loads(event.payload_json) if event.payload_json else None
    return SlideFeedbackEventResponse(
        id=event.id,
        slideVersionId=event.slide_version_id,
        generationRunId=event.generation_run_id,
        sourceSlideId=event.source_slide_id,
        eventType=event.event_type,
        notes=event.notes,
        payload=payload,
        createdAt=_iso(event.created_at),
    )


def _map_workspace(db: Session, deck: Deck) -> DeckWorkspaceModelResponse:
    deck_generation_workspace = deck.deck_generation_workspace
    latest_run = None
    if deck_generation_workspace is not None and deck_generation_workspace.generation_runs:
        latest_run = sorted(deck_generation_workspace.generation_runs, key=lambda item: item.created_at, reverse=True)[0]

    slide_ids = [slide.id for slide in deck.slides]
    classification_lookup = _load_slide_classifications(db, slide_ids)

    versions = []
    feedback = []
    if deck_generation_workspace is not None:
        versions = [
            {
                "id": item.id,
                "generationRunId": item.generation_run_id,
                "sourceSlideId": item.source_slide_id,
                "slideIndex": item.slide_index,
                "sourceSlideTitle": item.source_slide_title,
                "versionNumber": item.version_number,
                "title": item.title,
                "status": item.status,
                "generatedSlide": json.loads(item.generated_slide_json),
                "createdAt": _iso(item.created_at),
                "updatedAt": _iso(item.updated_at),
            }
            for item in sorted(deck_generation_workspace.slide_versions, key=lambda version: version.created_at, reverse=True)
        ]
        feedback = [
            _map_feedback_event(item)
            for item in sorted(deck_generation_workspace.feedback_events, key=lambda event: event.created_at, reverse=True)
        ]

    return DeckWorkspaceModelResponse.model_validate(
        {
            "deck": {
                "id": deck.id,
                "workspaceId": deck.workspace_id,
                "title": deck.title,
                "audience": deck.audience,
                "purpose": deck.purpose,
                "status": deck.status,
                "summary": deck.summary or "",
                "createdAt": _iso(deck.created_at),
                "updatedAt": _iso(deck.updated_at),
                "generationStatus": deck_generation_workspace.generation_status if deck_generation_workspace is not None else "idle",
                "generationMode": settings.deck_generation_mode,
                "latestGenerationRunId": latest_run.id if latest_run is not None else None,
            },
            "slides": [
                _map_workspace_slide(slide, classification_lookup)
                for slide in sorted(deck.slides, key=lambda item: item.slide_index)
            ],
            "versions": versions,
            "feedback": [item.model_dump() for item in feedback],
        }
    )


def _fallback_workspace(db: Session, deck: Deck) -> DeckWorkspaceModelResponse:
    deck_generation_workspace = deck.deck_generation_workspace
    latest_run = None
    if deck_generation_workspace is not None and deck_generation_workspace.generation_runs:
        latest_run = sorted(deck_generation_workspace.generation_runs, key=lambda item: item.created_at, reverse=True)[0]

    return DeckWorkspaceModelResponse.model_validate(
        {
            "deck": {
                "id": deck.id,
                "workspaceId": deck.workspace_id,
                "title": deck.title,
                "audience": deck.audience,
                "purpose": deck.purpose,
                "status": deck.status,
                "summary": deck.summary or "",
                "createdAt": _iso(deck.created_at),
                "updatedAt": _iso(deck.updated_at),
                "generationStatus": deck_generation_workspace.generation_status if deck_generation_workspace is not None else "idle",
                "generationMode": settings.deck_generation_mode,
                "latestGenerationRunId": latest_run.id if latest_run is not None else None,
            },
            "slides": [
                {
                    "id": slide.id,
                    "deckId": slide.deck_id,
                    "slideNumber": slide.slide_index + 1,
                    "title": slide.title,
                    "rawText": slide.raw_text,
                    "summary": slide.summary,
                    "slideRole": slide.role,
                    "blocks": [
                        {
                            "id": block.id,
                            "deckId": block.deck_id,
                            "slideId": block.slide_id,
                            "blockIndex": block.block_index,
                            "blockType": block.block_type,
                            "rawText": block.raw_text,
                            "currentText": block.raw_text,
                            "normalizedText": block.normalized_text,
                            "classification": None,
                        }
                        for block in sorted(slide.blocks, key=lambda item: item.block_index)
                    ],
                }
                for slide in sorted(deck.slides, key=lambda item: item.slide_index)
            ],
            "versions": [],
            "feedback": [],
        }
    )


def _ensure_deck_generation_workspace(db: Session, deck: Deck) -> DeckGenerationWorkspace:
    if deck.deck_generation_workspace is not None:
        return deck.deck_generation_workspace

    # REPLACED: Direct insertion could race with source-context and Smart Edit
    # workspace creation for the same deck.
    # deck_generation_workspace = DeckGenerationWorkspace(
    #     id=generate_id("deckgen"),
    #     deck_id=deck.id,
    #     generation_status="idle",
    # )
    # db.add(deck_generation_workspace)
    # db.flush()
    deck_generation_workspace = ensure_generation_workspace(
        db,
        deck_id=deck.id,
        generation_status="idle",
        id_prefix="deckgen",
    )
    deck.deck_generation_workspace = deck_generation_workspace
    return deck_generation_workspace


def _build_deck_input(deck: Deck, selected_slides: list[DeckSlide]) -> str:
    slide_sections: list[str] = []
    for slide in selected_slides:
        block_lines = [
            f"- [{block.block_type}] {block.raw_text}"
            for block in sorted(slide.blocks, key=lambda item: item.block_index)
        ]
        slide_sections.append(
            f"Slide {slide.slide_index}: {slide.title}\n"
            f"Role: {slide.role}\n"
            f"Summary: {slide.raw_text}\n"
            + "\n".join(block_lines)
        )

    return (
        f"Deck title: {deck.title}\n"
        f"Audience: {deck.audience}\n"
        f"Purpose: {deck.purpose}\n"
        f"Summary: {deck.summary}\n\n"
        + "\n\n".join(slide_sections)
    )


def _load_prompt_context(deck: Deck) -> dict | None:
    for artifact in deck.llm_artifacts:
        if artifact.artifact_type == "prompt_context" and artifact.status == "ready":
            return artifact.payload_json
    return None


def _generate_deck_payload(
    payload: GenerateSlidesRequest,
    deck: Deck,
    selected_slides: list[DeckSlide],
    claude_config: dict,
) -> GeneratedDeckPayload:
    audience = payload.audience or deck.audience
    purpose = payload.purpose or deck.purpose
    deck_input = _build_deck_input(deck, selected_slides)

    if claude_config["provider"] == "openai":
        return generate_slides_with_openai(
            payload=payload,
            deck_input=deck_input,
            deck_title=deck.title,
            audience=audience,
            purpose=purpose,
            artifact_context=_load_prompt_context(deck),
            api_key=claude_config.get("apiKey"),
            model=claude_config.get("model"),
        )
    if claude_config["provider"] == "anthropic":
        return generate_slides_with_claude(
            payload=payload,
            deck_input=deck_input,
            deck_title=deck.title,
            audience=audience,
            purpose=purpose,
            artifact_context=_load_prompt_context(deck),
            api_key=claude_config.get("apiKey"),
            model=claude_config.get("model"),
        )
    raise ValueError("Deck generation requires a workspace AI key or OPENAI_API_KEY/ANTHROPIC_API_KEY.")


def get_deck_workspace(db: Session, deck_id: str) -> tuple[DeckWorkspaceModelResponse, dict | None] | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    latest_confirmation = get_latest_save_confirmation_for_deck(db, deck.id)
    try:
        workspace = _map_workspace(db, deck)
    except Exception:
        workspace = _fallback_workspace(db, deck)
    return workspace, map_save_confirmation(latest_confirmation) if latest_confirmation is not None else None


def generate_slides_for_deck(db: Session, deck_id: str, payload: GenerateSlidesRequest) -> tuple[str, DeckWorkspaceModelResponse] | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    deck_generation_workspace = _ensure_deck_generation_workspace(db, deck)
    all_slides = sorted(deck.slides, key=lambda item: item.slide_index)
    if payload.scopeType == "whole_deck":
        selected_slides = all_slides
    else:
        selected_ids = set(payload.selectedSlideIds)
        selected_slides = [slide for slide in all_slides if slide.id in selected_ids]

    if not selected_slides:
        raise ValueError("No slides selected for generation.")

    claude_config = _resolve_claude_config(db, deck)
    run = DeckGenerationRun(
        id=generate_id("genrun"),
        deck_generation_workspace_id=deck_generation_workspace.id,
        deck_id=deck.id,
        status="running",
        provider=claude_config["provider"],
        model=claude_config["model"] if claude_config["provider"] in {"anthropic", "openai"} else None,
        generation_mode=claude_config["provider"],
        scope_type=payload.scopeType,
        request_payload_json=json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True),
    )
    deck_generation_workspace.generation_status = "running"
    db.add(run)
    db.flush()

    try:
        generated_deck = _generate_deck_payload(payload, deck, selected_slides, claude_config)
        run.status = "completed"
        run.generated_deck_json = generated_deck.model_dump_json()
        run.quality_score = generated_deck.quality.overall_score
        deck_generation_workspace.generation_status = "ready"

        source_by_order = selected_slides if payload.scopeType == "selected_slides" else all_slides[: len(generated_deck.slides)]
        for index, generated_slide in enumerate(generated_deck.slides, start=1):
            source_slide = source_by_order[index - 1] if index - 1 < len(source_by_order) else None
            existing_versions = [
                version
                for version in deck_generation_workspace.slide_versions
                if version.source_slide_id == (source_slide.id if source_slide is not None else None)
            ]

            slide_version = DeckSlideVersion(
                id=generate_id("slidever"),
                deck_generation_workspace_id=deck_generation_workspace.id,
                generation_run_id=run.id,
                source_slide_id=source_slide.id if source_slide is not None else None,
                slide_index=source_slide.slide_index if source_slide is not None else index,
                source_slide_title=source_slide.title if source_slide is not None else None,
                version_number=len(existing_versions) + 1,
                title=generated_slide.title,
                status="reviewable",
                generated_slide_json=generated_slide.model_dump_json(),
            )
            db.add(slide_version)

        db.commit()
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        deck_generation_workspace.generation_status = "failed"
        db.commit()
        raise

    workspace_result = get_deck_workspace(db, deck_id)
    if workspace_result is None:
        raise ValueError("Generated workspace could not be reloaded.")
    workspace, _latest_confirmation = workspace_result
    return run.id, workspace


def _record_revision(db: Session, deck_id: str, slide_id: str, block: DeckSlideBlock, next_text: str, reason: str) -> None:
    if block.raw_text == next_text:
        return

    db.add(
        DeckSlideRevision(
            id=generate_id("rev"),
            deck_id=deck_id,
            slide_id=slide_id,
            block_id=block.id,
            previous_text=block.raw_text,
            next_text=next_text,
            reason=reason,
        )
    )
    block.raw_text = next_text
    block.normalized_text = next_text.strip()


def _apply_generated_slide_to_workspace(db: Session, deck: Deck, slide_version: DeckSlideVersion) -> None:
    if slide_version.source_slide_id is None:
        return

    source_slide = next((item for item in deck.slides if item.id == slide_version.source_slide_id), None)
    if source_slide is None:
        return

    generated_slide = json.loads(slide_version.generated_slide_json)
    generated_blocks = generated_slide.get("blocks", [])
    existing_blocks = sorted(source_slide.blocks, key=lambda item: item.block_index)

    for index, generated_block in enumerate(generated_blocks):
        mapped_block_type = _map_block_type(str(generated_block.get("type", "body")))
        text_value = str(generated_block.get("text", "")).strip()
        position_json = json.dumps(
            {
                "x": generated_block.get("x"),
                "y": generated_block.get("y"),
                "w": generated_block.get("w"),
                "h": generated_block.get("h"),
            },
            separators=(",", ":"),
        )
        style_json = json.dumps(
            {
                "role": generated_block.get("role"),
                "generatedType": generated_block.get("type"),
            },
            separators=(",", ":"),
        )

        target_block = existing_blocks[index] if index < len(existing_blocks) else None
        if target_block is None:
            target_block = DeckSlideBlock(
                id=generate_id("block"),
                slide_id=source_slide.id,
                block_index=index,
                raw_text=text_value,
                normalized_text=text_value,
                block_type=mapped_block_type,
                position=position_json,
                style=style_json,
            )
            db.add(target_block)
            existing_blocks.append(target_block)
        else:
            target_block.block_index = index
            target_block.block_type = mapped_block_type
            target_block.position = position_json
            target_block.style = style_json
            _record_revision(db, deck.id, source_slide.id, target_block, text_value, "Accepted generated slide version")

    source_slide.title = str(generated_slide.get("title", source_slide.title))
    source_slide.raw_text = " ".join(
        str(item.get("text", "")).strip()
        for item in generated_blocks
        if str(item.get("text", "")).strip()
    )
    source_slide.narrative_notes = str(generated_slide.get("design_rationale", source_slide.narrative_notes or ""))


def submit_slide_feedback(
    db: Session,
    deck_id: str,
    slide_id: str,
    payload: SubmitSlideFeedbackRequest,
) -> tuple[SlideFeedbackEventResponse, DeckWorkspaceModelResponse] | None:
    deck = _load_deck(db, deck_id)
    if deck is None or deck.deck_generation_workspace is None:
        return None

    slide_version = (
        db.query(DeckSlideVersion)
        .filter(
            DeckSlideVersion.id == payload.slideVersionId,
            DeckSlideVersion.deck_generation_workspace_id == deck.deck_generation_workspace.id,
        )
        .one_or_none()
    )
    if slide_version is None:
        return None

    event = DeckFeedbackEvent(
        id=generate_id("feedback"),
        deck_generation_workspace_id=deck.deck_generation_workspace.id,
        generation_run_id=slide_version.generation_run_id,
        slide_version_id=slide_version.id,
        source_slide_id=slide_id,
        event_type=payload.eventType,
        notes=payload.notes,
        payload_json=json.dumps(
            {
                "applyToWorkspace": payload.applyToWorkspace,
            },
            separators=(",", ":"),
        ),
    )
    db.add(event)

    if payload.eventType == "accepted":
        slide_version.status = "applied" if payload.applyToWorkspace else "accepted"
        if payload.applyToWorkspace:
            _apply_generated_slide_to_workspace(db, deck, slide_version)
    elif payload.eventType == "rejected":
        slide_version.status = "rejected"
    elif payload.eventType == "edited":
        slide_version.status = "edited"

    db.commit()
    db.refresh(event)

    workspace_result = get_deck_workspace(db, deck_id)
    if workspace_result is None:
        raise ValueError("Workspace could not be reloaded after feedback.")
    workspace, _latest_confirmation = workspace_result
    return _map_feedback_event(event), workspace
