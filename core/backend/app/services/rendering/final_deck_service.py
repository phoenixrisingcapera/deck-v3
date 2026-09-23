from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import (
    BatchSlideDecision,
    CompiledDeck,
    CompiledDeckSlide,
    Deck,
    DeckLlmArtifact,
    DeckSlide,
    DesignBatch,
    GeneratedSlideCandidate,
    Workspace,
)
from app.services.platform.shell.iteration_retention_service import refresh_iteration_training_snapshot
from app.services.training.iteration_training_export_service import auto_export_pending_iteration_training_snapshots

GENERATED_VERSION = "generated_version"
ORIGINAL = "original"
GENERATED_SLIDE_ARTIFACT_TYPE = "smart_deck_generated_slide"


def _load_batch(db: Session, deck_id: str, batch_id: str) -> DesignBatch | None:
    return (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.candidate_slides),
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.slide_decisions),
        )
        .filter(DesignBatch.id == batch_id, DesignBatch.deck_id == deck_id)
        .one_or_none()
    )


def _string_from_payload(payload: dict | None, *keys: str) -> str | None:
    if not payload:
        return None

    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _generated_preview_url(artifact_payload: dict | None, fallback: str | None) -> str | None:
    render_schema = artifact_payload.get("renderSchema") if artifact_payload else None
    schema_json = artifact_payload.get("schemaJson") if artifact_payload else None

    return (
        _string_from_payload(artifact_payload, "previewImageUrl", "previewUrl", "thumbnailUrl")
        or _string_from_payload(
            render_schema if isinstance(render_schema, dict) else None,
            "previewImageUrl",
            "previewUrl",
            "thumbnailUrl",
        )
        or _string_from_payload(
            schema_json if isinstance(schema_json, dict) else None,
            "previewImageUrl",
            "previewUrl",
            "thumbnailUrl",
        )
        or fallback
    )


def _serialize_compiled_deck(compiled_deck: CompiledDeck) -> dict:
    sorted_slides = sorted(compiled_deck.slides, key=lambda item: item.slide_index)
    source_file_name = compiled_deck.source_deck.file.filename if compiled_deck.source_deck.file else None
    return {
        "deckId": compiled_deck.source_deck_id,
        "iterationId": compiled_deck.batch_id,
        "batchId": compiled_deck.batch_id,
        "compiledDeckId": compiled_deck.id,
        "status": compiled_deck.status,
        "title": compiled_deck.title,
        "slideCount": compiled_deck.slide_count,
        "latestSlideVersionId": compiled_deck.latest_slide_version_id,
        "finalizedAt": compiled_deck.finalized_at.isoformat(),
        "manifest": compiled_deck.manifest_json,
        "slides": [
            {
                "sourceSlideId": slide.source_slide_id,
                "generatedSlideCandidateId": slide.generated_slide_candidate_id,
                "slideIndex": slide.slide_index,
                "choice": slide.choice,
                "title": slide.title_snapshot,
                "manifest": slide.manifest_json or {},
            }
            for slide in sorted_slides
        ],
        "redirectTo": "/decks",
        "featuredCard": {
            "deckId": compiled_deck.source_deck_id,
            "compiledDeckId": compiled_deck.id,
            "title": compiled_deck.title,
            "status": "ready",
            "sourceFileName": source_file_name,
            "latestBatchId": compiled_deck.batch_id,
            "latestIterationId": compiled_deck.batch_id,
            "latestSlideVersionId": compiled_deck.latest_slide_version_id,
            "createdAt": compiled_deck.created_at.isoformat(),
            "finalizedAt": compiled_deck.finalized_at.isoformat(),
            "slideCount": compiled_deck.slide_count,
            "openHref": f"/decks/{compiled_deck.source_deck_id}/compiled/{compiled_deck.id}",
            # Compatibility key retained for older frontend consumers; its value now
            # points at the canonical user-facing iteration route.
            "batchHref": f"/decks/{compiled_deck.source_deck_id}/iterations/{compiled_deck.batch_id}",
        },
    }


def get_final_deck_for_iteration(db: Session, deck_id: str, iteration_id: str) -> dict | None:
    compiled = (
        db.query(CompiledDeck)
        .options(
            selectinload(CompiledDeck.source_deck).selectinload(Deck.file),
            selectinload(CompiledDeck.slides),
        )
        .filter(
            CompiledDeck.source_deck_id == deck_id,
            CompiledDeck.batch_id == iteration_id,
            CompiledDeck.status == "ready",
        )
        .order_by(CompiledDeck.finalized_at.desc())
        .first()
    )
    return _serialize_compiled_deck(compiled) if compiled is not None else None


def save_batch_slide_decision(
    db: Session,
    deck_id: str,
    batch_id: str,
    slide_id: str,
    *,
    choice: str,
    generated_slide_candidate_id: str | None = None,
    decided_by_user_id: str | None = None,
    commit: bool = True,
) -> BatchSlideDecision | None:
    if choice not in {GENERATED_VERSION, ORIGINAL}:
        raise ValueError("choice must be generated_version or original")

    batch = _load_batch(db, deck_id, batch_id)
    if batch is None:
        return None

    candidate = None
    if generated_slide_candidate_id:
        candidate = next((item for item in batch.candidate_slides if item.id == generated_slide_candidate_id), None)
        if candidate is None or candidate.source_slide_id != slide_id:
            raise ValueError("generatedSlideVersionId does not belong to this batch slide")
    elif choice == GENERATED_VERSION:
        candidate = next((item for item in batch.candidate_slides if item.source_slide_id == slide_id), None)
        if candidate is None:
            raise ValueError("generated_version requires a generated slide candidate for this slide")
        generated_slide_candidate_id = candidate.id

    if not any(item.slide_id == slide_id for item in batch.selected_slides):
        raise ValueError("slideId is not part of this batch")

    now = datetime.utcnow()
    decision = (
        db.query(BatchSlideDecision)
        .filter(
            BatchSlideDecision.deck_id == deck_id,
            BatchSlideDecision.batch_id == batch_id,
            BatchSlideDecision.slide_id == slide_id,
        )
        .one_or_none()
    )
    if decision is None:
        decision = BatchSlideDecision(
            id=generate_id("decision"),
            deck_id=deck_id,
            batch_id=batch_id,
            slide_id=slide_id,
            created_at=now,
        )

    decision.choice = choice
    decision.generated_slide_candidate_id = generated_slide_candidate_id if choice == GENERATED_VERSION else None
    decision.decided_by_user_id = decided_by_user_id
    decision.decided_at = now
    decision.updated_at = now
    db.add(decision)

    if candidate is not None:
        candidate.status = "applied" if choice == GENERATED_VERSION else "kept_original"
        db.add(candidate)
    elif choice == ORIGINAL:
        original_candidate = next((item for item in batch.candidate_slides if item.source_slide_id == slide_id), None)
        if original_candidate is not None:
            original_candidate.status = "kept_original"
            db.add(original_candidate)

    batch.updated_at = now
    if all(item.status in {"applied", "kept_original"} for item in batch.candidate_slides):
        batch.status = "reviewed"
    db.add(batch)

    if commit:
        refresh_iteration_training_snapshot(db, batch_id, source_surface="iteration_review")
        db.commit()
        auto_export_pending_iteration_training_snapshots(db)
        db.refresh(decision)
    return decision


def prepare_full_deck(
    db: Session,
    deck_id: str,
    batch_id: str,
    *,
    title: str | None = None,
    latest_slide_version_id: str | None = None,
    created_by_user_id: str | None = None,
) -> dict | None:
    existing = get_final_deck_for_iteration(db, deck_id, batch_id)
    if existing is not None:
        return existing

    deck = (
        db.query(Deck)
        .options(
            selectinload(Deck.file),
            selectinload(Deck.slides),
        )
        .filter(Deck.id == deck_id)
        .one_or_none()
    )
    if deck is None:
        return None

    batch = _load_batch(db, deck_id, batch_id)
    if batch is None:
        return None

    candidates_by_slide_id = {item.source_slide_id: item for item in batch.candidate_slides if item.source_slide_id}
    candidates_by_id = {item.id: item for item in batch.candidate_slides}
    decisions_by_slide_id = {item.slide_id: item for item in batch.slide_decisions}
    candidate_artifacts = {
        artifact.artifact_key: artifact
        for artifact in db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == GENERATED_SLIDE_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key.in_([candidate.id for candidate in batch.candidate_slides] or [""]),
        )
        .all()
    }

    try:
        now = datetime.utcnow()
        compiled_title = (title or f"{deck.title} Final Deck").strip()
        sorted_source_slides = sorted(deck.slides, key=lambda item: item.slide_index)
        manifest_slides: list[dict] = []
        compiled = CompiledDeck(
            id=generate_id("compileddeck"),
            source_deck_id=deck.id,
            batch_id=batch.id,
            title=compiled_title,
            status="ready",
            latest_slide_version_id=latest_slide_version_id,
            slide_count=len(sorted_source_slides),
            manifest_json={"slides": manifest_slides},
            created_by_user_id=created_by_user_id,
            finalized_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(compiled)
        db.flush()

        for source_slide in sorted_source_slides:
            decision = decisions_by_slide_id.get(source_slide.id)
            choice = decision.choice if decision is not None else ORIGINAL
            candidate_id = decision.generated_slide_candidate_id if decision is not None else None
            candidate = candidates_by_id.get(candidate_id) if candidate_id else candidates_by_slide_id.get(source_slide.id)
            if choice == GENERATED_VERSION and (candidate_id is None or candidate is None):
                raise ValueError(f"Missing generated version for slide {source_slide.id}")
            if choice == GENERATED_VERSION and candidate.source_slide_id != source_slide.id:
                raise ValueError(f"Generated version {candidate.id} does not belong to slide {source_slide.id}")

            artifact_payload = candidate_artifacts.get(candidate_id).payload_json if candidate_id in candidate_artifacts else None
            title_snapshot = candidate.title if choice == GENERATED_VERSION and candidate is not None else source_slide.title
            content_json = (
                {
                    "title": candidate.title,
                    "headline": candidate.headline,
                    "summary": candidate.summary,
                    "renderSchema": (artifact_payload or {}).get("renderSchema", {}),
                    "schemaJson": (artifact_payload or {}).get("schemaJson", {}),
                }
                if choice == GENERATED_VERSION and candidate is not None
                else {
                    "title": source_slide.title,
                    "rawText": source_slide.raw_text,
                    "summary": source_slide.summary,
                    "metadata": source_slide.metadata_json or {},
                }
            )
            slide_manifest = {
                "sourceDeckId": deck.id,
                "sourceSlideId": source_slide.id,
                "sourceType": choice,
                "generatedSlideCandidateId": candidate_id,
                "slideIndex": source_slide.slide_index,
                "slideNumber": source_slide.slide_number or source_slide.slide_index,
                "choice": choice,
                "title": title_snapshot,
                "contentJson": content_json,
                "previewImageUrl": _generated_preview_url(artifact_payload, source_slide.rendered_image_path)
                if choice == GENERATED_VERSION
                else source_slide.rendered_image_path,
                "speakerNotes": source_slide.narrative_notes,
            }
            manifest_slides.append(slide_manifest)
            db.add(
                CompiledDeckSlide(
                    id=generate_id("compiledslide"),
                    compiled_deck_id=compiled.id,
                    source_slide_id=source_slide.id,
                    generated_slide_candidate_id=candidate_id,
                    slide_index=source_slide.slide_index,
                    choice=choice,
                    title_snapshot=title_snapshot,
                    manifest_json=slide_manifest,
                    created_at=now,
                )
            )

        compiled.manifest_json = {
            "sourceDeckId": deck.id,
            "iterationId": batch.id,
            "batchId": batch.id,
            "compiledDeckId": compiled.id,
            "slides": manifest_slides,
        }
        batch.status = "reviewed"
        deck.summary = f"Final generated deck created from batch {batch.batch_number}."
        deck.updated_at = now
        db.add_all([compiled, batch, deck])
        refresh_iteration_training_snapshot(db, batch.id, source_surface="compiled_deck")
        db.commit()
    except Exception:
        db.rollback()
        raise

    auto_export_pending_iteration_training_snapshots(db)

    compiled = (
        db.query(CompiledDeck)
        .options(
            selectinload(CompiledDeck.source_deck).selectinload(Deck.file),
            selectinload(CompiledDeck.slides),
        )
        .filter(CompiledDeck.id == compiled.id)
        .one()
    )
    return _serialize_compiled_deck(compiled)


def get_compiled_deck(db: Session, deck_id: str, compiled_deck_id: str) -> dict | None:
    compiled = (
        db.query(CompiledDeck)
        .options(
            selectinload(CompiledDeck.source_deck).selectinload(Deck.file),
            selectinload(CompiledDeck.slides),
        )
        .filter(CompiledDeck.id == compiled_deck_id, CompiledDeck.source_deck_id == deck_id)
        .one_or_none()
    )
    return _serialize_compiled_deck(compiled) if compiled is not None else None


def get_latest_compiled_deck(
    db: Session,
    deck_id: str | None = None,
    *,
    user_id: str | None = None,
    include_all: bool = False,
) -> dict | None:
    query = (
        db.query(CompiledDeck)
        .options(
            selectinload(CompiledDeck.source_deck).selectinload(Deck.file),
            selectinload(CompiledDeck.slides),
        )
        .join(CompiledDeck.source_deck)
        .filter(CompiledDeck.status == "ready")
    )
    if deck_id is not None:
        query = query.filter(CompiledDeck.source_deck_id == deck_id)
    if not include_all:
        if user_id is None:
            return None
        query = query.outerjoin(Deck.workspace).filter(or_(Deck.user_id == user_id, Workspace.user_id == user_id))
    compiled = query.order_by(CompiledDeck.finalized_at.desc()).first()
    return _serialize_compiled_deck(compiled) if compiled is not None else None
