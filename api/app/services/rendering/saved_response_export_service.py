from __future__ import annotations

from collections import OrderedDict

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckLlmArtifact, DeckSlide
from app.services.visualizer.slide_read_model import load_deck_llm_artifact_payload

SAVED_RESPONSE_EXPORT_ARTIFACT_TYPE = "saved_markdown_response"
SMART_DECK_ASSISTANT_ARTIFACT_TYPE = "smart_deck_assistant_run"


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _safe_url(value: object) -> str | None:
    text = _safe_text(value)
    return text or None


def _normalize_source_groups(source_groups: list[dict] | None) -> list[dict]:
    groups: list[dict] = []
    for group in source_groups or []:
        if not isinstance(group, dict):
            continue
        source_type = _safe_text(group.get("sourceType"))
        if not source_type:
            continue
        links: list[dict] = []
        for link in group.get("links") or []:
            if not isinstance(link, dict):
                continue
            label = _safe_text(link.get("label"))
            if not label:
                continue
            links.append({"label": label, "url": _safe_url(link.get("url"))})
        groups.append({"sourceType": source_type, "links": links})
    return groups


def _derive_source_groups(payload: dict, *, slide_id: str) -> list[dict]:
    source_groups: list[dict] = []
    input_context = payload.get("inputContext") if isinstance(payload.get("inputContext"), dict) else {}
    selected_slides = input_context.get("selectedSlides") if isinstance(input_context.get("selectedSlides"), list) else []
    slide_links: list[dict] = []
    for slide in selected_slides:
        if not isinstance(slide, dict):
            continue
        label = _safe_text(slide.get("title")) or f"Slide {slide.get('slideNumber') or slide.get('id') or 'source'}"
        number = slide.get("slideNumber")
        if number:
            label = f"Slide {number} - {label}"
        slide_links.append({"label": label, "url": None})
    if slide_links:
        source_groups.append({"sourceType": "Deck slides", "links": slide_links})

    vector_retrieval = input_context.get("vectorRetrieval") if isinstance(input_context.get("vectorRetrieval"), dict) else {}
    retrieval_chunks = vector_retrieval.get("chunks") if isinstance(vector_retrieval.get("chunks"), list) else []
    retrieval_links: list[dict] = []
    seen_labels: set[str] = set()
    for chunk in retrieval_chunks:
        if not isinstance(chunk, dict):
            continue
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        title = _safe_text(metadata.get("title"))
        chunk_slide_id = _safe_text(chunk.get("slideId"))
        label = title or _safe_text(chunk.get("sourceKey")) or _safe_text(chunk.get("chunkType")) or "Retrieved context"
        if chunk_slide_id:
            label = f"{label} ({chunk_slide_id})"
        if label in seen_labels:
            continue
        seen_labels.add(label)
        retrieval_links.append({"label": label, "url": None})
    if retrieval_links:
        source_groups.append({"sourceType": "Embedded retrieval", "links": retrieval_links})

    if not source_groups:
        source_groups.append({"sourceType": "Deck context", "links": [{"label": f"Slide {slide_id}", "url": None}]})
    return source_groups


def _markdown_value(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {str(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {value[key]}" for key in value)
    return str(value)


def _render_response_markdown(prompt_slug: str, insight: dict, source_groups: list[dict]) -> str:
    lines = [f"# {prompt_slug}", ""]
    summary = _safe_text(insight.get("summary"))
    if summary:
        lines.extend([summary, ""])

    content = insight.get("content") if isinstance(insight.get("content"), dict) else {}
    for key, value in content.items():
        if value in (None, "", []):
            continue
        label = " ".join(part.capitalize() for part in str(key).replace("_", " ").split())
        lines.extend([f"## {label}", "", _markdown_value(value), ""])

    for label, key in (("Assumptions", "assumptions"), ("Missing evidence", "missingEvidence")):
        values = insight.get(key) if isinstance(insight.get(key), list) else []
        if values:
            lines.extend([f"## {label}", "", *[f"- {str(value)}" for value in values], ""])

    suggested_update = _safe_text(insight.get("suggestedSlideUpdate"))
    if suggested_update:
        lines.extend(["## Suggested slide update", "", suggested_update, ""])

    lines.extend(["## Sources", ""])
    for group in source_groups:
        lines.extend([f"### {group['sourceType']}", ""])
        for link in group.get("links") or []:
            label = _safe_text(link.get("label"))
            url = _safe_url(link.get("url"))
            if not label:
                continue
            lines.append(f"- [{label}]({url})" if url else f"- {label}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _preview_payload(artifact: DeckLlmArtifact) -> dict:
    payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
    return {
        "id": artifact.id,
        "deckId": artifact.deck_id,
        "slideId": payload.get("slideId"),
        "promptSlug": payload.get("promptSlug"),
        "markdownContent": payload.get("markdownContent") or "",
        "sourceGroups": _normalize_source_groups(payload.get("sourceGroups") if isinstance(payload.get("sourceGroups"), list) else []),
        "createdAt": artifact.created_at,
    }


def create_saved_response_export(
    db: Session,
    *,
    deck_id: str,
    slide_id: str,
    prompt_slug: str,
    assistant_artifact_id: str,
) -> dict | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    slide = db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id, DeckSlide.id == slide_id).one_or_none()
    if deck is None or slide is None:
        return None

    existing = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == SAVED_RESPONSE_EXPORT_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key == f"{assistant_artifact_id}:{slide_id}:{prompt_slug}",
            DeckLlmArtifact.status == "ready",
        )
        .one_or_none()
    )
    if existing is not None:
        return _preview_payload(existing)

    assistant_artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.id == assistant_artifact_id,
            DeckLlmArtifact.artifact_type == SMART_DECK_ASSISTANT_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .one_or_none()
    )
    if assistant_artifact is None:
        raise ValueError("Assistant response artifact not found.")

    assistant_payload = load_deck_llm_artifact_payload(assistant_artifact)
    insight = assistant_payload.get("insight") if isinstance(assistant_payload, dict) else None
    if not isinstance(insight, dict):
        raise ValueError("Assistant response artifact has no previewable insight.")

    input_context = assistant_payload.get("inputContext") if isinstance(assistant_payload, dict) else None
    selected_slides = input_context.get("selectedSlides") if isinstance(input_context, dict) else None
    selected_slide_ids = {
        str(item.get("id"))
        for item in selected_slides or []
        if isinstance(item, dict) and item.get("id")
    }
    if slide_id not in selected_slide_ids:
        raise ValueError("Assistant response artifact does not include the selected slide.")

    source_groups = _derive_source_groups(assistant_payload, slide_id=slide_id)
    markdown_content = _render_response_markdown(prompt_slug, insight, source_groups)

    artifact = DeckLlmArtifact(
        id=generate_id("artifact"),
        deck_id=deck_id,
        extraction_run_id=None,
        artifact_type=SAVED_RESPONSE_EXPORT_ARTIFACT_TYPE,
        artifact_key=f"{assistant_artifact_id}:{slide_id}:{prompt_slug}",
        schema_version="saved-markdown-response.v1",
        status="ready",
        summary=f"Saved response for slide {slide.slide_index + 1}",
        payload_json={
            "deckId": deck_id,
            "slideId": slide_id,
            "slideNumber": slide.slide_index + 1,
            "slideTitle": slide.title or f"Slide {slide.slide_index + 1}",
            "promptSlug": prompt_slug,
            "assistantArtifactId": assistant_artifact_id,
            "markdownContent": markdown_content,
            "sourceGroups": source_groups,
        },
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return _preview_payload(artifact)


def list_saved_response_exports(db: Session, deck_id: str) -> dict:
    artifacts = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == SAVED_RESPONSE_EXPORT_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .all()
    )
    grouped: OrderedDict[str, dict] = OrderedDict()
    for artifact in artifacts:
        payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
        slide_id = _safe_text(payload.get("slideId"))
        if not slide_id:
            continue
        group = grouped.get(slide_id)
        if group is None:
            group = {
                "slideId": slide_id,
                "slideNumber": int(payload.get("slideNumber") or 0),
                "slideTitle": _safe_text(payload.get("slideTitle")) or f"Slide {payload.get('slideNumber') or '?'}",
                "items": [],
            }
            grouped[slide_id] = group
        group["items"].append(
            {
                "id": artifact.id,
                "deckId": artifact.deck_id,
                "slideId": slide_id,
                "slideNumber": int(payload.get("slideNumber") or 0),
                "slideTitle": _safe_text(payload.get("slideTitle")) or group["slideTitle"],
                "promptSlug": _safe_text(payload.get("promptSlug")),
                "createdAt": artifact.created_at,
            }
        )
    return {"groups": list(grouped.values())}


def get_saved_response_export(db: Session, deck_id: str, export_id: str) -> dict | None:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.id == export_id,
            DeckLlmArtifact.artifact_type == SAVED_RESPONSE_EXPORT_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .one_or_none()
    )
    if artifact is None:
        return None
    return _preview_payload(artifact)
