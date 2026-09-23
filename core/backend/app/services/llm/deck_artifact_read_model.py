from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact, DeckSlide, DeckSlideBlock
from app.services.deck_processing.workflow_jobs import list_workflow_jobs_for_deck


ARTIFACT_SCHEMA_VERSION = "deck-llm-artifacts.v1"
PROMPT_CONTEXT_ARTIFACT_TYPE = "prompt_context"
CORE_EXTRACTION_ARTIFACT_TYPES = {
    "deck_profile",
    "slide_catalog",
    PROMPT_CONTEXT_ARTIFACT_TYPE,
}

ROLE_PRIORITY = [
    "cover",
    "problem",
    "solution",
    "market",
    "product",
    "traction",
    "business_model",
    "competition",
    "team",
    "financials",
    "roadmap",
    "ask",
    "generic",
]

METRIC_RE = re.compile(
    r"\b(?:\$?\d[\d,.]*(?:[kKmMbB]|x|%|m|bn|M|B)?|\d+(?:\.\d+)?%)\b"
)


def _excerpt(text: str | None, *, max_words: int = 28) -> str:
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


def _normalize_role(slide: DeckSlide) -> str:
    role = (slide.semantic_slide_type or slide.role or "generic").strip().lower().replace(" ", "_")
    role_aliases = {
        "cover_slide": "cover",
        "title": "cover",
        "intro": "cover",
        "problem_statement": "problem",
        "solution_overview": "solution",
        "go_to_market": "business_model",
        "gtm": "business_model",
        "business_model_overview": "business_model",
        "market_opportunity": "market",
        "team_slide": "team",
        "financial": "financials",
        "ask_slide": "ask",
    }
    return role_aliases.get(role, role if role in ROLE_PRIORITY else "generic")


def _block_excerpt(block: DeckSlideBlock) -> str:
    return _excerpt(block.raw_text or block.normalized_text or "", max_words=16)


def _metric_tokens(text: str) -> list[str]:
    seen: list[str] = []
    for match in METRIC_RE.findall(text):
        if match not in seen:
            seen.append(match)
        if len(seen) >= 8:
            break
    return seen


def _ordered_role_counts(slides: list[DeckSlide]) -> dict[str, int]:
    counts = Counter(_normalize_role(slide) for slide in slides)
    ordered = {role: counts[role] for role in ROLE_PRIORITY if counts.get(role)}
    extras = sorted(role for role in counts if role not in ordered)
    for role in extras:
        ordered[role] = counts[role]
    return ordered


def _coerce_json_object(value: object | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}


def _latest_workflow_job_ref(db: Session, deck_id: str) -> tuple[str | None, str | None]:
    jobs = list_workflow_jobs_for_deck(db, deck_id)
    if not jobs:
        return None, None
    latest = jobs[0]
    return latest.id, latest.job_type


def _workflow_job_refs_by_extraction_run(db: Session, deck_id: str) -> dict[str, dict[str, str | None]]:
    jobs = list_workflow_jobs_for_deck(db, deck_id)
    mapping: dict[str, dict[str, str | None]] = {}
    for job in jobs:
        if job.extraction_run_id and job.extraction_run_id not in mapping:
            mapping[job.extraction_run_id] = {
                "workflowJobId": job.id,
                "workflowJobType": job.job_type,
            }
    return mapping


def _isoformat_or_fallback(value: object | None, fallback: datetime | None = None) -> str:
    candidate = value or fallback or datetime.utcnow()
    if hasattr(candidate, "isoformat"):
        return candidate.isoformat()
    return str(candidate)


def _build_deck_profile(deck: Deck, slides: list[DeckSlide]) -> dict:
    all_text = "\n".join(slide.raw_text for slide in slides if slide.raw_text)
    role_counts = _ordered_role_counts(slides)
    return {
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "deckId": deck.id,
        "title": deck.title,
        "audience": deck.audience,
        "purpose": deck.purpose,
        "status": deck.status,
        "slideCount": len(slides),
        "roleDistribution": role_counts,
        "narrativeSequence": [_normalize_role(slide) for slide in slides],
        "metricSignals": _metric_tokens(all_text),
        "topTitles": [slide.title for slide in slides[:8] if slide.title],
    }


def _build_slide_catalog(slides: list[DeckSlide]) -> dict:
    payload = []
    for slide in slides:
        ordered_blocks = sorted(slide.blocks, key=lambda item: item.block_index)
        block_type_counts = Counter(block.block_type for block in ordered_blocks)
        payload.append(
            {
                "slideId": slide.id,
                "slideIndex": slide.slide_index,
                "slideNumber": slide.slide_number or slide.slide_index + 1,
                "title": slide.title,
                "role": _normalize_role(slide),
                "rawTextExcerpt": _excerpt(slide.raw_text, max_words=36),
                "blockCount": len(ordered_blocks),
                "assetCount": len(slide.assets),
                "blockTypes": dict(sorted(block_type_counts.items())),
                "exampleBlocks": [_block_excerpt(block) for block in ordered_blocks[:3] if _block_excerpt(block)],
                "metricSignals": _metric_tokens(slide.raw_text or ""),
            }
        )
    return {
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "slides": payload,
    }


def _build_role_examples(slides: list[DeckSlide]) -> list[dict]:
    grouped: dict[str, list[DeckSlide]] = defaultdict(list)
    for slide in slides:
        grouped[_normalize_role(slide)].append(slide)

    examples: list[dict] = []
    ordered_roles = [role for role in ROLE_PRIORITY if role in grouped] + sorted(
        role for role in grouped if role not in ROLE_PRIORITY
    )
    for role in ordered_roles:
        role_slides = grouped[role]
        examples.append(
            {
                "role": role,
                "count": len(role_slides),
                "examples": [
                    {
                        "slideId": slide.id,
                        "slideIndex": slide.slide_index,
                        "title": slide.title,
                        "summary": _excerpt(slide.raw_text or slide.summary or slide.narrative_notes, max_words=28),
                        "exampleBlocks": [
                            _block_excerpt(block)
                            for block in sorted(slide.blocks, key=lambda item: item.block_index)[:2]
                            if _block_excerpt(block)
                        ],
                    }
                    for slide in role_slides[:2]
                ],
            }
        )
    return examples


def _build_prompt_context(deck: Deck, slides: list[DeckSlide], deck_profile: dict, slide_catalog: dict) -> dict:
    consistency_rules = [
        "Preserve company-specific facts, metrics, and proper nouns from the source deck.",
        "Treat the source deck's role order as the default narrative unless the user asks to reshape it.",
        "Reuse the source deck's strongest slide examples before inventing new structure.",
        "Keep repeated metrics numerically consistent across generated slides.",
    ]
    return {
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "deckId": deck.id,
        "instruction": "Use this deterministic artifact bundle as the first structural reference for generation and editing.",
        "deckProfile": deck_profile,
        "roleExamples": _build_role_examples(slides),
        "slideCatalog": slide_catalog["slides"],
        "consistencyRules": consistency_rules,
        "generationHints": {
            "preferredRoleOrder": deck_profile["narrativeSequence"],
            "metricSignals": deck_profile["metricSignals"],
            "audience": deck.audience,
            "purpose": deck.purpose,
        },
    }


def _artifact_records(deck: Deck, slides: list[DeckSlide]) -> list[dict]:
    deck_profile = _build_deck_profile(deck, slides)
    slide_catalog = _build_slide_catalog(slides)
    prompt_context = _build_prompt_context(deck, slides, deck_profile, slide_catalog)
    return [
        {
            "artifact_type": "deck_profile",
            "artifact_key": "deck_profile",
            "summary": f"Deck-level profile for {len(slides)} extracted slides.",
            "payload_json": deck_profile,
            "metrics_json": {
                "slideCount": len(slides),
                "roleCount": len(deck_profile["roleDistribution"]),
                "metricSignalCount": len(deck_profile["metricSignals"]),
            },
        },
        {
            "artifact_type": "slide_catalog",
            "artifact_key": "slide_catalog",
            "summary": f"Slide-by-slide catalog for {len(slides)} extracted slides.",
            "payload_json": slide_catalog,
            "metrics_json": {
                "slideCount": len(slide_catalog["slides"]),
            },
        },
        {
            "artifact_type": PROMPT_CONTEXT_ARTIFACT_TYPE,
            "artifact_key": "prompt_context",
            "summary": "Stable JSON context bundle for Smart Deck and Smart Edit LLM prompts.",
            "payload_json": prompt_context,
            "metrics_json": {
                "roleExampleCount": len(prompt_context["roleExamples"]),
                "consistencyRuleCount": len(prompt_context["consistencyRules"]),
            },
        },
    ]


def rebuild_deck_llm_artifacts(db: Session, deck: Deck, extraction_run_id: str | None = None) -> list[DeckLlmArtifact]:
    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck.id,
        DeckLlmArtifact.artifact_type.in_(CORE_EXTRACTION_ARTIFACT_TYPES),
    ).delete(synchronize_session=False)

    created: list[DeckLlmArtifact] = []
    for record in _artifact_records(deck, slides):
        artifact = DeckLlmArtifact(
            id=generate_id("artifact"),
            deck_id=deck.id,
            extraction_run_id=extraction_run_id,
            artifact_type=record["artifact_type"],
            artifact_key=record["artifact_key"],
            schema_version=ARTIFACT_SCHEMA_VERSION,
            status="ready",
            summary=record["summary"],
            payload_json=record["payload_json"],
            metrics_json=record["metrics_json"],
        )
        db.add(artifact)
        created.append(artifact)

    db.flush()
    return created


def get_deck_llm_artifact_bundle(db: Session, deck_id: str) -> dict:
    deck = (
        db.query(Deck)
        .options(selectinload(Deck.llm_artifacts))
        .filter(Deck.id == deck_id)
        .first()
    )
    if deck is None:
        raise ValueError("Deck not found")

    deck_timestamp = deck.updated_at or deck.created_at or datetime.utcnow()
    artifacts = sorted(
        deck.llm_artifacts,
        key=lambda item: (item.artifact_type or "", item.created_at or datetime.min),
    )
    extraction_run_ids = [
        artifact.extraction_run_id
        for artifact in sorted(deck.llm_artifacts, key=lambda item: item.created_at or datetime.min, reverse=True)
        if artifact.extraction_run_id is not None
    ]
    latest_extraction_run_id = extraction_run_ids[0] if extraction_run_ids else None
    latest_workflow_job_id, latest_workflow_job_type = _latest_workflow_job_ref(db, deck.id)
    workflow_refs = _workflow_job_refs_by_extraction_run(db, deck.id)

    return {
        "deckId": deck.id,
        "extractionRunId": latest_extraction_run_id,
        "workflowJobId": latest_workflow_job_id,
        "workflowJobType": latest_workflow_job_type,
        "artifacts": [
            {
                "id": artifact.id,
                "extractionRunId": artifact.extraction_run_id,
                "workflowJobId": (workflow_refs.get(artifact.extraction_run_id or "") or {}).get("workflowJobId"),
                "workflowJobType": (workflow_refs.get(artifact.extraction_run_id or "") or {}).get("workflowJobType"),
                "artifactType": artifact.artifact_type or "unknown",
                "artifactKey": artifact.artifact_key or artifact.artifact_type or artifact.id,
                "schemaVersion": artifact.schema_version or ARTIFACT_SCHEMA_VERSION,
                "status": artifact.status or "unknown",
                "summary": artifact.summary,
                "payloadJson": _coerce_json_object(artifact.payload_json),
                "metricsJson": _coerce_json_object(artifact.metrics_json),
                "createdAt": _isoformat_or_fallback(artifact.created_at, deck_timestamp),
                "updatedAt": _isoformat_or_fallback(artifact.updated_at, deck_timestamp),
            }
            for artifact in artifacts
        ],
    }


def get_prompt_context_artifact(deck: Deck) -> dict | None:
    for artifact in deck.llm_artifacts:
        if artifact.artifact_type == PROMPT_CONTEXT_ARTIFACT_TYPE and artifact.status == "ready":
            return artifact.payload_json
    return None
