from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact

SOURCE_ARTIFACT_SCHEMA_VERSION = "smart-deck-source-artifacts.v1"


def upsert_deck_llm_artifact(
    db: Session,
    *,
    deck_id: str,
    artifact_type: str,
    artifact_key: str,
    summary: str,
    payload_json: dict[str, Any],
    extraction_run_id: str | None = None,
    metrics_json: dict[str, Any] | None = None,
    schema_version: str = SOURCE_ARTIFACT_SCHEMA_VERSION,
) -> DeckLlmArtifact:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == artifact_type,
            DeckLlmArtifact.artifact_key == artifact_key,
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if artifact is None:
        artifact = DeckLlmArtifact(
            id=generate_id("llmart"),
            deck_id=deck_id,
            extraction_run_id=extraction_run_id,
            artifact_type=artifact_type,
            artifact_key=artifact_key,
            schema_version=schema_version,
            status="ready",
            summary=summary,
            payload_json=payload_json,
            metrics_json=metrics_json,
        )
        db.add(artifact)
    else:
        artifact.extraction_run_id = extraction_run_id or artifact.extraction_run_id
        artifact.schema_version = schema_version
        artifact.status = "ready"
        artifact.summary = summary
        artifact.payload_json = payload_json
        artifact.metrics_json = metrics_json
    return artifact


def write_source_v1_artifacts(
    db: Session,
    *,
    deck: Deck,
    context: dict[str, Any],
    prompt_bundle: dict[str, str],
    extraction_run_id: str | None = None,
    source_versions: list[dict[str, Any]] | None = None,
    enrichment: dict[str, Any] | None = None,
) -> list[DeckLlmArtifact]:
    deck_id = deck.id
    slides = context.get("slides") if isinstance(context.get("slides"), list) else []
    slide_facts = [
        {
            "factId": f"source_slide:{slide.get('slideId')}",
            "slideId": slide.get("slideId"),
            "title": slide.get("title"),
            "semanticSlideType": slide.get("semanticSlideType"),
            "textHash": slide.get("textHash"),
            "blockCount": len(slide.get("blocks") or []),
            "assetCount": len(slide.get("assets") or []),
        }
        for slide in slides
        if isinstance(slide, dict)
    ]
    artifacts = [
        upsert_deck_llm_artifact(
            db,
            deck_id=deck_id,
            extraction_run_id=extraction_run_id,
            artifact_type="smart_deck_source_v1_context",
            artifact_key="source_v1_context",
            summary="Source V1 context for Smart Deck slide selection and generation.",
            payload_json=context,
            metrics_json={"slideCount": len(slides)},
        ),
        upsert_deck_llm_artifact(
            db,
            deck_id=deck_id,
            extraction_run_id=extraction_run_id,
            artifact_type="smart_deck_source_facts",
            artifact_key="source_facts_v1",
            summary="Stable source facts derived from the uploaded deck.",
            payload_json={"deckId": deck_id, "sourceVersion": "original_source_v1", "facts": slide_facts},
            metrics_json={"factCount": len(slide_facts)},
        ),
        upsert_deck_llm_artifact(
            db,
            deck_id=deck_id,
            extraction_run_id=extraction_run_id,
            artifact_type="smart_deck_prompt_context",
            artifact_key="source_enrichment_prompt_v1",
            summary="Prompt bundle for source slide semantic enrichment.",
            payload_json=prompt_bundle,
            metrics_json={"systemChars": len(prompt_bundle.get("system") or ""), "userChars": len(prompt_bundle.get("user") or "")},
        ),
        upsert_deck_llm_artifact(
            db,
            deck_id=deck_id,
            extraction_run_id=extraction_run_id,
            artifact_type="smart_deck_source_v1_manifest",
            artifact_key="source_v1_manifest",
            summary="Manifest linking source slides to original source V1 slide versions.",
            payload_json={
                "deckId": deck_id,
                "sourceVersion": "original_source_v1",
                "slideVersions": source_versions or [],
                "enrichmentStatus": (enrichment or {}).get("status", "deterministic"),
            },
            metrics_json={"slideVersionCount": len(source_versions or [])},
        ),
    ]
    if enrichment is not None:
        artifacts.append(
            upsert_deck_llm_artifact(
                db,
                deck_id=deck_id,
                extraction_run_id=extraction_run_id,
                artifact_type="smart_deck_source_enrichment",
                artifact_key="source_enrichment_v1",
                summary="Validated semantic labels for source slides and source blocks.",
                payload_json=enrichment,
                metrics_json={"slideCount": len(enrichment.get("slides") or []) if isinstance(enrichment, dict) else 0},
            )
        )
    return artifacts
