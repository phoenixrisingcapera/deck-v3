"""Concurrency-safe creation of the single generation workspace for a deck."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckGenerationWorkspace


def ensure_generation_workspace(
    db: Session,
    *,
    deck_id: str,
    generation_status: str,
    id_prefix: str = "dgw",
) -> DeckGenerationWorkspace:
    """Return the deck workspace after taking the canonical deck-first lock."""
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        # DISABLED: Transaction-scoped advisory locking was introduced to
        # serialize workspace creators, but this service is normally called
        # after the workflow transaction has already read/updated deck, job,
        # slide, and artifact rows. A concurrent request can acquire this
        # advisory lock before waiting on one of those rows while this worker
        # holds that row and waits here, producing the production deadlock.
        # A conflict-safe insert alone can still wait for another transaction's
        # uncommitted unique-index entry while this caller holds other mutable
        # locks. Every creator therefore takes the parent deck row lock first;
        # PostgreSQL serializes same-deck creation before the unique insert.
        # db.execute(
        #     text("SELECT pg_advisory_xact_lock(hashtextextended(:deck_id, 0))"),
        #     {"deck_id": deck_id},
        # )
        db.execute(
            select(Deck.id)
            .where(Deck.id == deck_id)
            .with_for_update()
        )
        workspace = (
            db.query(DeckGenerationWorkspace)
            .filter(DeckGenerationWorkspace.deck_id == deck_id)
            .one_or_none()
        )
        if workspace is None:
            # DISABLED: ON CONFLICT could still wait on an uncommitted unique
            # index entry after callers had already changed other rows.
            # statement = (
            #     postgresql_insert(DeckGenerationWorkspace)
            #     .values(id=generate_id(id_prefix), deck_id=deck_id, generation_status=generation_status)
            #     .on_conflict_do_nothing(index_elements=[DeckGenerationWorkspace.deck_id])
            # )
            # db.execute(statement)
            workspace = DeckGenerationWorkspace(
                id=generate_id(id_prefix),
                deck_id=deck_id,
                generation_status=generation_status,
            )
            db.add(workspace)
            db.flush()
        return workspace

    workspace = (
        db.query(DeckGenerationWorkspace)
        .filter(DeckGenerationWorkspace.deck_id == deck_id)
        .one_or_none()
    )
    if workspace is None:
        workspace = DeckGenerationWorkspace(
            id=generate_id(id_prefix),
            deck_id=deck_id,
            generation_status=generation_status,
        )
        db.add(workspace)
        db.flush()
    return workspace
