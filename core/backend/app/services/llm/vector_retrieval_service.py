from __future__ import annotations

import hashlib

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, RetrievalTrace, VectorChunk
from app.core.config import settings
from app.db.session import AiSessionLocal
from app.services.llm.deck_chunking_service import INSTANT_DECK_KNOWLEDGE_DECK_ID
from app.services.llm.embedding_service import (
    EmbeddingUnavailableError,
    create_embeddings_with_metadata,
    get_embedding_provider_status,
    resolve_workspace_embedding_config,
)


MINIMUM_COSINE_SIMILARITY = 0.20
RETRIEVAL_CANDIDATE_MULTIPLIER = 3
MAXIMUM_KNOWLEDGE_RESULTS = 6


def retrieve_relevant_chunks(
    db: Session,
    *,
    deck_id: str,
    query_text: str,
    chunk_types: list[str] | None = None,
    limit: int = 8,
) -> dict:
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if deck is None:
        return {"status": "unavailable", "message": "Deck not found.", "chunks": []}
    try:
        runtime_config = resolve_workspace_embedding_config(db, deck.workspace_id)
    except EmbeddingUnavailableError as exc:
        return {"status": "unavailable", "message": str(exc), "chunks": []}
    status = get_embedding_provider_status(runtime_config)
    if status.get("status") != "ready":
        return {
            "status": "unavailable",
            "message": status.get("message") or "Vector retrieval is unavailable.",
            "chunks": [],
        }
    try:
        embedding_result = create_embeddings_with_metadata([query_text], runtime_config=runtime_config)
        query_vector = embedding_result.vectors[0]
    except EmbeddingUnavailableError as exc:
        return {"status": "unavailable", "message": str(exc), "chunks": []}

    vector_db = db
    owns_vector_session = False
    if str(settings.ai_database_url or "").strip() and db.get_bind().dialect.name != "sqlite":
        vector_db = AiSessionLocal()
        owns_vector_session = True
    try:
        distance = VectorChunk.embedding.cosine_distance(query_vector).label("cosine_distance")
        q = vector_db.query(VectorChunk, distance).filter(
            VectorChunk.embedding_status == "ready",
            VectorChunk.embedding.is_not(None),
            VectorChunk.embedding_provider == embedding_result.provider,
            VectorChunk.embedding_model == embedding_result.model,
            VectorChunk.embedding_dimensions == embedding_result.dimensions,
        )
        if chunk_types:
            q = q.filter(VectorChunk.chunk_type.in_(chunk_types))
        candidate_limit = max(limit, limit * RETRIEVAL_CANDIDATE_MULTIPLIER)
        knowledge_candidates = (
            q.filter(VectorChunk.deck_id == INSTANT_DECK_KNOWLEDGE_DECK_ID)
            .order_by(distance)
            .limit(candidate_limit)
            .all()
        )
        # Customer decks are canonical request data, never vector knowledge.
        # Retrieval is deliberately limited to the backend-owned corpus.
        candidates = knowledge_candidates
        ranked: list[tuple[VectorChunk, float, float]] = []
        for row, raw_distance in candidates:
            similarity = max(-1.0, min(1.0, 1.0 - float(raw_distance)))
            if similarity < MINIMUM_COSINE_SIMILARITY:
                continue
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            # Atomic design rules are more actionable than broad pack blobs.
            # Similarity still orders rules within that lane; this small lane
            # prior prevents a large manifest/recipe chunk from crowding out
            # the concrete geometry and composition guidance the model needs.
            design_rule_bonus = 0.18 if metadata.get("lane") == "design_quality_rule" else 0.0
            guidance_bonus = (0.03 if row.deck_id == INSTANT_DECK_KNOWLEDGE_DECK_ID else 0.0) + design_rule_bonus
            ranked.append((row, similarity, similarity + guidance_bonus))
        ranked.sort(key=lambda item: (-item[2], item[0].source_key, item[0].id))
        knowledge_ranked = [item for item in ranked if item[0].deck_id == INSTANT_DECK_KNOWLEDGE_DECK_ID]
        selected = knowledge_ranked[: min(MAXIMUM_KNOWLEDGE_RESULTS, limit)]
        selected.sort(key=lambda item: (-item[2], item[0].source_key, item[0].id))
        ranked = selected[:limit]
        trace = RetrievalTrace(
            id=generate_id("retrieval"),
            workspace_id=deck.workspace_id,
            deck_id=deck_id,
            query_hash=hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
            result_count=len(ranked),
            metadata_json={
                "provider": embedding_result.provider,
                "model": embedding_result.model,
                "dimensions": embedding_result.dimensions,
                "minimumCosineSimilarity": MINIMUM_COSINE_SIMILARITY,
                "candidateCount": len(candidates),
                "results": [
                    {
                        "chunkId": row.id,
                        "scope": "global_knowledge" if row.deck_id == INSTANT_DECK_KNOWLEDGE_DECK_ID else "deck",
                        "similarityScore": round(similarity, 6),
                    }
                    for row, similarity, _ in ranked
                ],
            },
        )
        vector_db.add(trace)
        vector_db.flush()
        trace_id = trace.id
        result_chunks = [
            {
                "id": row.id,
                "chunkType": row.chunk_type,
                "sourceKey": row.source_key,
                "slideId": row.slide_id,
                "blockId": row.block_id,
                "artifactId": row.artifact_id,
                "contentText": row.content_text,
                "metadata": row.metadata_json or {},
                "scope": "global_knowledge" if row.deck_id == INSTANT_DECK_KNOWLEDGE_DECK_ID else "deck",
                "similarityScore": round(similarity, 6),
                "rerankScore": round(rerank_score, 6),
            }
            for row, similarity, rerank_score in ranked
        ]
        if owns_vector_session:
            vector_db.commit()
    except (AttributeError, NotImplementedError, SQLAlchemyError) as exc:
        if owns_vector_session:
            vector_db.rollback()
        return {
            "status": "unavailable",
            "message": f"Vector retrieval is unavailable: {exc}",
            "chunks": [],
        }
    finally:
        if owns_vector_session:
            vector_db.close()
    return {
        "status": "ready",
        "provider": embedding_result.provider,
        "model": embedding_result.model,
        "fallbackLevel": embedding_result.fallback_level,
        "chunks": result_chunks,
        "traceId": trace_id,
        "minimumCosineSimilarity": MINIMUM_COSINE_SIMILARITY,
    }
