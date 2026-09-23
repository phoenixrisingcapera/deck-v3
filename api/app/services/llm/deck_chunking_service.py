from __future__ import annotations

from datetime import datetime
import hashlib

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.core.config import settings
from app.db.models import (
    Deck,
    DeckLlmArtifact,
    DeckSlide,
    EmbeddingIngestionRun,
    EmbeddingModelRegistry,
    SmartEditSuggestion,
    VectorChunk,
)
from app.db.session import AiSessionLocal
from app.services.llm.embedding_service import (
    EmbeddingUnavailableError,
    create_embeddings_with_metadata,
    get_embedding_provider_status,
    resolve_workspace_embedding_config,
)


CHUNK_TYPES = {
    "deck_summary",
    "slide_raw_text",
    "slide_block",
    "brand_profile",
    "market_research",
    "deck_map_analysis",
    "audience_profile",
    "diligence_lens",
    "accepted_edit",
    "generated_version",
    "instant_deck_knowledge",
    "vc_methodology_knowledge",
}

INSTANT_DECK_KNOWLEDGE_DECK_ID = "__instant_deck_knowledge__"


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _desired_chunk_key(chunk: dict) -> tuple[str, str]:
    return str(chunk["source_key"]), _content_hash(str(chunk["content_text"]))


def _chunk_is_ready_for_runtime(row: VectorChunk, *, provider: str | None, model: str | None, dimensions: int) -> bool:
    return bool(
        row.embedding_status == "ready"
        and row.embedding is not None
        and row.embedding_provider == provider
        and row.embedding_model == model
        and row.embedding_dimensions == dimensions
    )


def _record_embedding_contract(
    vector_db: Session,
    *,
    deck_id: str,
    workspace_id: str | None,
    corpus_hash: str,
    provider: str,
    model: str,
    dimensions: int,
) -> None:
    registry = vector_db.query(EmbeddingModelRegistry).filter(
        EmbeddingModelRegistry.provider == provider,
        EmbeddingModelRegistry.model == model,
    ).one_or_none()
    if registry is None:
        registry = EmbeddingModelRegistry(
            id=generate_id("embmodel"),
            provider=provider,
            model=model,
            dimensions=dimensions,
            status="active",
        )
        vector_db.add(registry)
    else:
        registry.dimensions = dimensions
        registry.status = "active"

    ingestion = vector_db.query(EmbeddingIngestionRun).filter(
        EmbeddingIngestionRun.deck_id == deck_id,
        EmbeddingIngestionRun.content_hash == corpus_hash,
        EmbeddingIngestionRun.provider == provider,
        EmbeddingIngestionRun.model == model,
        EmbeddingIngestionRun.dimensions == dimensions,
        EmbeddingIngestionRun.status == "completed",
    ).one_or_none()
    if ingestion is None:
        vector_db.add(
            EmbeddingIngestionRun(
                id=generate_id("embingest"),
                workspace_id=workspace_id,
                deck_id=deck_id,
                content_hash=corpus_hash,
                provider=provider,
                model=model,
                dimensions=dimensions,
                status="completed",
                completed_at=datetime.utcnow(),
            )
        )


def _sync_vector_chunk_set(
    *,
    deck_id: str,
    workspace_id: str | None,
    chunks: list[dict],
    runtime_config: object | None,
    vector_session: Session | None = None,
) -> dict:
    status = get_embedding_provider_status(runtime_config)
    provider = str(status.get("provider") or "").strip() or None
    model = str(status.get("model") or "").strip() or None
    dimensions = int(status.get("storageDimensions") or status.get("dimensions") or 1024)
    desired_by_key = {_desired_chunk_key(chunk): chunk for chunk in chunks}
    desired_keys = set(desired_by_key)

    vector_db = vector_session or AiSessionLocal()
    owns_vector_session = vector_session is None
    try:
        existing_rows = vector_db.query(VectorChunk).filter(VectorChunk.deck_id == deck_id).all()
        existing_snapshot = {
            (row.source_key, row.content_hash): _chunk_is_ready_for_runtime(
                row,
                provider=provider,
                model=model,
                dimensions=dimensions,
            )
            for row in existing_rows
        }
        # Never keep an AI database transaction open across a provider call.
        if owns_vector_session:
            vector_db.rollback()

        pending_keys = [key for key in desired_keys if not existing_snapshot.get(key, False)]
        pending_chunks = [desired_by_key[key] for key in pending_keys]
        embedding_result = None
        embedding_status = "ready"
        error_message: str | None = None
        vectors_by_key: dict[tuple[str, str], list[float]] = {}
        if pending_chunks:
            try:
                embedding_result = create_embeddings_with_metadata(
                    [str(chunk["content_text"]) for chunk in pending_chunks],
                    runtime_config=runtime_config,
                )
                vectors_by_key = {
                    key: embedding_result.vectors[index]
                    for index, key in enumerate(pending_keys)
                }
                provider = embedding_result.provider
                model = embedding_result.model
                dimensions = embedding_result.dimensions
            except EmbeddingUnavailableError as exc:
                embedding_status = "embedding_unavailable"
                error_message = str(exc)

        with vector_db.begin_nested():
            existing_rows = vector_db.query(VectorChunk).filter(VectorChunk.deck_id == deck_id).all()
            existing_by_key = {(row.source_key, row.content_hash): row for row in existing_rows}
            for row in existing_rows:
                if (row.source_key, row.content_hash) not in desired_keys:
                    vector_db.delete(row)
            for key, chunk in desired_by_key.items():
                row = existing_by_key.get(key)
                if row is None:
                    row = VectorChunk(id=generate_id("vchunk"), deck_id=deck_id)
                    vector_db.add(row)
                row.slide_id = chunk.get("slide_id")
                row.block_id = chunk.get("block_id")
                row.artifact_id = chunk.get("artifact_id")
                row.chunk_type = chunk["chunk_type"]
                row.source_key = chunk["source_key"]
                row.content_hash = key[1]
                row.content_text = chunk["content_text"]
                row.metadata_json = chunk.get("metadata_json") or {}
                vector = vectors_by_key.get(key)
                if vector is not None and embedding_result is not None:
                    row.embedding_provider = embedding_result.provider
                    row.embedding_model = embedding_result.model
                    row.embedding_dimensions = embedding_result.dimensions
                    row.embedding_fallback_level = embedding_result.fallback_level
                    row.embedding_error_category = embedding_result.error_category
                    row.embedding_status = "ready"
                    row.embedding = vector
                elif key not in existing_by_key or not existing_snapshot.get(key, False):
                    row.embedding_provider = None
                    row.embedding_model = None
                    row.embedding_dimensions = None
                    row.embedding_fallback_level = 0
                    row.embedding_error_category = error_message
                    row.embedding_status = embedding_status
                    row.embedding = None

            if embedding_result is not None:
                corpus_hash = _content_hash("\n".join(sorted(key[1] for key in desired_keys)))
                _record_embedding_contract(
                    vector_db,
                    deck_id=deck_id,
                    workspace_id=workspace_id,
                    corpus_hash=corpus_hash,
                    provider=embedding_result.provider,
                    model=embedding_result.model,
                    dimensions=embedding_result.dimensions,
                )
            vector_db.flush()
        if owns_vector_session:
            vector_db.commit()
    except (NotImplementedError, SQLAlchemyError, ValueError, TypeError) as exc:
        if owns_vector_session:
            vector_db.rollback()
        return {
            "status": "degraded",
            "chunkCount": len(chunks),
            "embeddedChunkCount": 0,
            "reusedChunkCount": 0,
            "embeddingStatus": "vector_store_unavailable",
            "message": f"Vector chunk sync degraded: {exc}",
            "provider": provider,
            "model": model,
        }
    finally:
        if owns_vector_session:
            vector_db.close()

    return {
        "status": "ready" if error_message is None else "degraded",
        "chunkCount": len(chunks),
        "embeddedChunkCount": len(vectors_by_key),
        "reusedChunkCount": max(0, len(chunks) - len(pending_chunks)),
        "embeddingStatus": embedding_status,
        "message": error_message,
        "provider": provider,
        "model": model,
        "dimensions": dimensions,
    }


def sync_deck_vector_chunks(
    db: Session,
    deck_id: str,
    *,
    user_instruction: str | None = None,
    audience_label: str | None = None,
    release_core_transaction_before_provider: bool = False,
) -> dict:
    """Enforce the product policy that customer decks are never embedded.

    Instant Deck reads the owner's persisted source records directly. The
    vector store is reserved for backend-owned reusable design guidance.
    Calling this legacy entry point also purges older customer vectors.
    """
    vector_db = (
        db
        if not str(settings.ai_database_url or "").strip() or db.get_bind().dialect.name == "sqlite"
        else AiSessionLocal()
    )
    owns_vector_session = vector_db is not db
    try:
        deleted_chunks = vector_db.query(VectorChunk).filter(VectorChunk.deck_id == deck_id).delete(
            synchronize_session=False
        )
        deleted_runs = vector_db.query(EmbeddingIngestionRun).filter(
            EmbeddingIngestionRun.deck_id == deck_id
        ).delete(synchronize_session=False)
        if owns_vector_session:
            vector_db.commit()
        else:
            vector_db.flush()
    except Exception:
        if owns_vector_session:
            vector_db.rollback()
        raise
    finally:
        if owns_vector_session:
            vector_db.close()
    return {
        "status": "excluded_by_policy",
        "chunkCount": 0,
        "embeddedChunkCount": 0,
        "deletedChunkCount": int(deleted_chunks or 0),
        "deletedIngestionRunCount": int(deleted_runs or 0),
        "queryInstructionPersisted": False,
    }


def _instant_deck_knowledge_chunks() -> list[dict]:
    """Build path-free, backend-owned reusable design guidance chunks."""
    import json

    from app.ai.instant_deck_knowledge_context import (
        build_instant_deck_generation_context,
    )

    source = build_instant_deck_generation_context()
    version = str((source.get("knowledgeSource") or {}).get("version") or "unknown")
    lanes = {
        "prompt_recipe": source.get("promptRecipe") or {},
        "venture_modules": source.get("vcAiStackModules") or {},
        "context_vigilance": source.get("contextVigilancePatterns") or {},
        "grounding_instructions": list(source.get("instructions") or []),
    }
    chunks: list[dict] = []
    for lane, payload in lanes.items():
        content_text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if content_text in {"{}", "[]"}:
            continue
        chunks.append(
            {
                "chunk_type": "instant_deck_knowledge",
                "source_key": f"knowledge:instant_deck:{version}:{lane}",
                "content_text": content_text,
                "metadata_json": {
                    "scope": "global_instant_deck",
                    "knowledgeVersion": version,
                    "lane": lane,
                    "factualAuthority": "guidance_only",
                },
            }
        )
    from app.ai.vc_methodology_knowledge_context import load_vc_methodology_corpus

    methodology = load_vc_methodology_corpus()
    for document in methodology.get("documents") or []:
        chunks.append({
            "chunk_type": "vc_methodology_knowledge",
            "source_key": f"knowledge:vc_methodology:{methodology['corpusVersion']}:{document['documentId']}",
            "content_text": document["abstract"],
            "metadata_json": {
                "scope": "global_instant_deck",
                "knowledgeVersion": methodology["corpusVersion"],
                "lane": "vc_methodology",
                "documentId": document["documentId"],
                "title": document["title"],
                "publicationYear": document["publicationYear"],
                "knowledgeAge": document["knowledgeAge"],
                "permittedRetrievalPurposes": document["permittedRetrievalPurposes"],
                "factualAuthority": "internal_reasoning_only",
                "evidenceClass": "PRODUCT_KNOWLEDGE",
                "currentMarketAuthority": False,
                "sourceUrl": document["sourceUrl"],
                "contentHash": document["contentHash"],
            },
        })
    design_rules = source.get("designQualityRules") or {}
    for rule in design_rules.get("rules") or []:
        if not isinstance(rule, dict) or not str(rule.get("guidance") or "").strip():
            continue
        rule_id = str(rule.get("id") or "rule").strip()
        content_text = json.dumps(
            {
                "id": rule_id,
                "topics": list(rule.get("topics") or []),
                "guidance": str(rule["guidance"]).strip(),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        chunks.append(
            {
                "chunk_type": "instant_deck_knowledge",
                "source_key": f"knowledge:instant_deck:{version}:design_rule:{rule_id}",
                "content_text": content_text,
                "metadata_json": {
                    "scope": "global_instant_deck",
                    "knowledgeVersion": version,
                    "lane": "design_quality_rule",
                    "ruleId": rule_id,
                    "factualAuthority": "guidance_only",
                    "ownership": "product_owned_non_customer_knowledge",
                },
            }
        )
    return chunks


def sync_instant_deck_knowledge_chunks(db: Session | None = None) -> dict:
    """Persist the compact stable Instant Deck knowledge corpus idempotently."""
    return _sync_vector_chunk_set(
        deck_id=INSTANT_DECK_KNOWLEDGE_DECK_ID,
        workspace_id=None,
        chunks=_instant_deck_knowledge_chunks(),
        runtime_config=None,
        vector_session=(
            db
            if db is not None
            and (not str(settings.ai_database_url or "").strip() or db.get_bind().dialect.name == "sqlite")
            else None
        ),
    )


def _load_deck_for_chunking(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.brand_profile),
            selectinload(Deck.llm_artifacts),
        )
        .filter(Deck.id == deck_id)
        .one_or_none()
    )


def _build_chunks(deck: Deck, *, user_instruction: str | None, accepted_edits: list[SmartEditSuggestion], audience_label: str | None) -> list[dict]:
    chunks: list[dict] = [
        {
            "chunk_type": "deck_summary",
            "source_key": f"deck:{deck.id}:summary",
            "content_text": "\n".join(part for part in [deck.title, deck.audience, deck.purpose, deck.summary] if part),
            "metadata_json": {"deckId": deck.id},
        }
    ]
    if deck.brand_profile is not None:
        chunks.append(
            {
                "chunk_type": "brand_profile",
                "source_key": f"deck:{deck.id}:brand_profile",
                "content_text": "\n".join(
                    part
                    for part in [
                        deck.brand_profile.company_name,
                        deck.brand_profile.brand_summary,
                        deck.brand_profile.visual_direction,
                        deck.brand_profile.team_summary,
                    ]
                    if part
                ),
                "metadata_json": {"deckId": deck.id, "brandProfileId": deck.brand_profile.id},
            }
        )
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        chunks.append(
            {
                "chunk_type": "slide_raw_text",
                "source_key": f"slide:{slide.id}:text",
                "slide_id": slide.id,
                "content_text": "\n".join(part for part in [slide.title, slide.role, slide.raw_text, slide.narrative_notes] if part),
                "metadata_json": {"deckId": deck.id, "slideId": slide.id, "role": slide.role, "title": slide.title},
            }
        )
        if slide.role:
            chunks.append(
                {
                    "chunk_type": "diligence_lens",
                    "source_key": f"slide:{slide.id}:role",
                    "slide_id": slide.id,
                    "content_text": str(slide.role),
                    "metadata_json": {"deckId": deck.id, "slideId": slide.id, "role": slide.role, "source": "slide_role"},
                }
            )
        for block in sorted(slide.blocks, key=lambda item: item.block_index):
            chunks.append(
                {
                    "chunk_type": "slide_block",
                    "source_key": f"block:{block.id}:text",
                    "slide_id": slide.id,
                    "block_id": block.id,
                    "content_text": "\n".join(part for part in [block.block_type, block.raw_text, block.normalized_text] if part),
                    "metadata_json": {"deckId": deck.id, "slideId": slide.id, "blockId": block.id, "blockType": block.block_type},
                }
            )
    # User instructions are retrieval queries, not corpus documents. Persisting
    # every prompt polluted later retrieval and caused unbounded deck-local
    # growth; keep the argument only for backward-compatible callers.
    if audience_label and audience_label.strip():
        chunks.append(
            {
                "chunk_type": "audience_profile",
                "source_key": f"deck:{deck.id}:audience_profile:{audience_label.strip().lower()}",
                "content_text": audience_label.strip(),
                "metadata_json": {"deckId": deck.id, "audience": audience_label.strip()},
            }
        )
    for suggestion in accepted_edits:
        chunks.append(
            {
                "chunk_type": "accepted_edit",
                "source_key": f"smart_edit:{suggestion.id}:accepted_edit",
                "slide_id": suggestion.slide_id,
                "block_id": suggestion.block_id,
                "content_text": "\n".join(
                    part
                    for part in [suggestion.original_text, suggestion.suggested_text, suggestion.reason]
                    if part
                ),
                "metadata_json": {
                    "deckId": deck.id,
                    "suggestionId": suggestion.id,
                    "runId": suggestion.run_id,
                    "status": suggestion.status,
                    "riskLevel": suggestion.risk_level,
                },
            }
        )
    chunks.extend(_artifact_chunks(deck))
    return [chunk for chunk in chunks if chunk.get("content_text")]


def _artifact_chunks(deck: Deck) -> list[dict]:
    chunks: list[dict] = []
    for artifact in sorted(deck.llm_artifacts, key=lambda item: item.created_at or datetime.min, reverse=True):
        payload = artifact.payload_json or {}
        if artifact.artifact_type == "smart_deck_market_research":
            chunks.append(
                {
                    "chunk_type": "market_research",
                    "source_key": f"artifact:{artifact.id}:market_research",
                    "artifact_id": artifact.id,
                    "content_text": str((payload.get("investmentThesis") or {}).get("summary") or artifact.summary or ""),
                    "metadata_json": {"artifactType": artifact.artifact_type, "deckId": deck.id},
                }
            )
        elif artifact.artifact_type == "smart_deck_deck_map_analysis":
            chunks.append(
                {
                    "chunk_type": "deck_map_analysis",
                    "source_key": f"artifact:{artifact.id}:deck_map_analysis",
                    "artifact_id": artifact.id,
                    "content_text": str((payload.get("narrative") or {}).get("flowAssessment") or artifact.summary or ""),
                    "metadata_json": {"artifactType": artifact.artifact_type, "deckId": deck.id},
                }
            )
        elif artifact.artifact_type.startswith("due_diligence_"):
            claims = payload.get("claims") if isinstance(payload, dict) else None
            if isinstance(claims, list):
                for idx, claim in enumerate(claims):
                    if not isinstance(claim, dict):
                        continue
                    text = str(claim.get("claim") or claim.get("claimText") or claim.get("claim_text") or "").strip()
                    if not text:
                        continue
                    chunks.append(
                        {
                            "chunk_type": "diligence_lens",
                            "source_key": f"artifact:{artifact.id}:claim:{idx}",
                            "artifact_id": artifact.id,
                            "content_text": text,
                            "metadata_json": {"artifactType": artifact.artifact_type, "deckId": deck.id},
                        }
                    )
        elif artifact.artifact_type.startswith("audience_conversion_"):
            plan = payload.get("deckConversionPlan") if isinstance(payload, dict) else None
            if isinstance(plan, dict):
                chunks.append(
                    {
                        "chunk_type": "generated_version",
                        "source_key": f"artifact:{artifact.id}:audience_conversion_plan",
                        "artifact_id": artifact.id,
                        "content_text": str(plan),
                        "metadata_json": {"artifactType": artifact.artifact_type, "deckId": deck.id},
                    }
                )
    return chunks
