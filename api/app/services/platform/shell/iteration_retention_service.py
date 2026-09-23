from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import BatchSlideDecision, CompiledDeck, DesignBatch, DesignBatchSlide, GeneratedSlideCandidate, IterationTrainingSnapshot


VISIBLE_ITERATION_LIMIT = 3


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _snapshot_payload(batch: DesignBatch) -> dict:
    selected_slides = sorted(batch.selected_slides, key=lambda item: (item.slide_index_snapshot, item.created_at))
    candidates = sorted(batch.candidate_slides, key=lambda item: (item.slide_index, item.created_at))
    decisions_by_slide_id = {decision.slide_id: decision for decision in batch.slide_decisions}
    compiled_decks = sorted(batch.compiled_decks, key=lambda item: item.created_at, reverse=True)
    return {
        "batchId": batch.id,
        "deckId": batch.deck_id,
        "iterationNumber": batch.batch_number,
        "iterationName": batch.batch_name,
        "scopeType": batch.scope_type,
        "prompt": batch.prompt,
        "audienceLabel": batch.audience_label,
        "selectedSlideCount": batch.selected_slide_count,
        "status": batch.status,
        "selectedSlides": [
            {
                "slideId": item.slide_id,
                "slideIndex": item.slide_index_snapshot,
                "slideTitle": item.slide_title_snapshot,
            }
            for item in selected_slides
        ],
        "candidateSlides": [
            {
                "candidateId": candidate.id,
                "sourceSlideId": candidate.source_slide_id,
                "slideIndex": candidate.slide_index,
                "title": candidate.title,
                "headline": candidate.headline,
                "summary": candidate.summary,
                "status": candidate.status,
                "decision": (
                    {
                        "choice": decisions_by_slide_id[candidate.source_slide_id].choice,
                        "decidedAt": _iso(decisions_by_slide_id[candidate.source_slide_id].decided_at),
                    }
                    if candidate.source_slide_id and candidate.source_slide_id in decisions_by_slide_id
                    else None
                ),
            }
            for candidate in candidates
        ],
        "compiledDecks": [
            {
                "compiledDeckId": item.id,
                "status": item.status,
                "title": item.title,
                "finalizedAt": _iso(item.finalized_at),
            }
            for item in compiled_decks
        ],
        "reviewSummary": {
            "candidateCount": len(candidates),
            "reviewedCandidateCount": sum(1 for candidate in candidates if candidate.source_slide_id in decisions_by_slide_id),
            "keptVersionCount": sum(
                1
                for candidate in candidates
                if candidate.source_slide_id in decisions_by_slide_id and decisions_by_slide_id[candidate.source_slide_id].choice == "generated_version"
            ),
            "keptOriginalCount": sum(
                1
                for candidate in candidates
                if candidate.source_slide_id in decisions_by_slide_id and decisions_by_slide_id[candidate.source_slide_id].choice == "original"
            ),
            "compiledDeckCount": len(compiled_decks),
            "finalDeckPrepared": len(compiled_decks) > 0,
        },
        "labels": {
            "iterationStatus": batch.status,
            "acceptedForUser": batch.status == "reviewed",
            "archivedForUser": batch.status == "archived",
            "hasCompiledDeck": len(compiled_decks) > 0,
        },
        "provenance": {
            "sourceSurface": batch.training_snapshot.source_surface if batch.training_snapshot is not None else None,
            "generatedAt": _iso(batch.created_at),
            "lastUpdatedAt": _iso(batch.updated_at),
        },
        "createdAt": _iso(batch.created_at),
        "updatedAt": _iso(batch.updated_at),
    }


def refresh_iteration_training_snapshot(
    db: Session,
    batch_id: str,
    *,
    source_surface: str = "iteration_history",
    visibility_state: str | None = None,
    export_state: str | None = None,
) -> IterationTrainingSnapshot | None:
    batch = (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.candidate_slides),
            selectinload(DesignBatch.slide_decisions),
            selectinload(DesignBatch.compiled_decks),
        )
        .filter(DesignBatch.id == batch_id)
        .one_or_none()
    )
    if batch is None:
        return None

    snapshot = next(
        (
            item
            for item in db.new
            if isinstance(item, IterationTrainingSnapshot) and item.batch_id == batch.id
        ),
        None,
    )
    if snapshot is None:
        snapshot = db.query(IterationTrainingSnapshot).filter(IterationTrainingSnapshot.batch_id == batch.id).one_or_none()
    if snapshot is None:
        snapshot = IterationTrainingSnapshot(
            id=generate_id("itsnap"),
            deck_id=batch.deck_id,
            batch_id=batch.id,
            source_surface=source_surface,
            visibility_state=visibility_state or ("hidden" if batch.status == "archived" else "visible"),
            export_state=export_state or "pending",
            snapshot_json=_snapshot_payload(batch),
        )
        db.add(snapshot)
        return snapshot

    snapshot.source_surface = source_surface or snapshot.source_surface
    snapshot.visibility_state = visibility_state or snapshot.visibility_state
    snapshot.export_state = export_state or snapshot.export_state
    snapshot.snapshot_json = _snapshot_payload(batch)
    snapshot.updated_at = datetime.utcnow()
    if snapshot.visibility_state == "hidden" and snapshot.archived_at is None:
        snapshot.archived_at = datetime.utcnow()
    db.add(snapshot)
    return snapshot


def apply_iteration_retention(db: Session, deck_id: str, *, visible_limit: int = VISIBLE_ITERATION_LIMIT) -> None:
    batches = (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.candidate_slides),
            selectinload(DesignBatch.slide_decisions),
            selectinload(DesignBatch.compiled_decks),
        )
        .filter(DesignBatch.deck_id == deck_id)
        .order_by(DesignBatch.created_at.desc(), DesignBatch.batch_number.desc())
        .all()
    )
    visible_limit = max(visible_limit, 0)

    for index, batch in enumerate(batches):
        if index < visible_limit:
            if batch.status == "archived":
                batch.status = "reviewed" if any(candidate.status in {"applied", "kept_original"} for candidate in batch.candidate_slides) else "completed"
            refresh_iteration_training_snapshot(db, batch.id, visibility_state="visible")
            continue

        if batch.status != "archived":
            batch.status = "archived"
            batch.updated_at = datetime.utcnow()
        refresh_iteration_training_snapshot(db, batch.id, visibility_state="hidden", export_state="pending")
