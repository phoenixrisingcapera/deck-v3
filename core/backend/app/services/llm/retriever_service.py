from __future__ import annotations

import enum

from app.db.models import Deck, DeckSlide, DesignVersion, GeneratedSlide, GeneratedSlideElement, GeneratedSlideElementVersion
from app.ai.slide_archetypes_context import build_slide_archetype_context
from app.services.brand.brand_design_tokens import build_brand_llm_context
from app.services.llm.deck_chunking_service import sync_deck_vector_chunks
from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks


class ContextMode(enum.Enum):
    """Controls whether vector retrieval is mandatory or optional.

    ``slide_generation``: Smart Deck slide generation with mandatory top-k
    vector retrieval.  Vector context must be available before prompting.
    ``full_deck``: Instant Deck full-deck generation. The request-creation
    context defers retrieval to the dedicated generation worker, which owns
    the durable deck/global knowledge index and exact provider envelope.
    """

    slide_generation = "slide_generation"
    full_deck = "full_deck"


def _vector_context(deck: Deck, *, query_text: str, chunk_types: list[str], limit: int) -> tuple[dict, dict]:
    session = deck._sa_instance_state.session
    if session is None:
        return (
            {"status": "unavailable", "message": "SQLAlchemy session unavailable for vector sync.", "chunkCount": 0},
            {"status": "unavailable", "message": "SQLAlchemy session unavailable for vector retrieval.", "chunks": []},
        )
    sync = sync_deck_vector_chunks(session, deck.id, user_instruction=query_text)
    retrieval = retrieve_relevant_chunks(session, deck_id=deck.id, query_text=query_text, chunk_types=chunk_types, limit=limit)
    return sync, retrieval


def _empty_vector_context() -> tuple[dict, dict]:
    """Declare the worker-owned retrieval boundary for full-deck mode."""
    return (
        {
            "status": "deferred_to_generation_worker",
            "message": "The generation worker prepares the durable deck and stable-knowledge index.",
            "chunkCount": 0,
        },
        {
            "status": "deferred_to_generation_worker",
            "message": "The generation worker binds scored retrievedGuidance into the exact provider request.",
            "chunks": [],
        },
    )


def _slide_summary(slide: DeckSlide | None) -> dict | None:
    if slide is None:
        return None
    return {
        "id": slide.id,
        "slideNumber": slide.slide_number or slide.source_page_number or slide.slide_index + 1,
        "title": slide.title,
        "rawText": slide.raw_text,
        "summary": slide.summary,
        "thumbnailPath": slide.thumbnail_path,
        "renderedImagePath": slide.rendered_image_path,
        "blocks": [
            {
                "id": block.id,
                "blockIndex": block.block_index,
                "type": block.block_type,
                "text": block.raw_text,
                "normalizedText": block.normalized_text,
            }
            for block in sorted(slide.blocks, key=lambda item: (item.block_index, item.id))
        ],
    }


def _generated_slide_summary(slide: GeneratedSlide | None) -> dict | None:
    if slide is None:
        return None
    return {
        "id": slide.id,
        "sourceSlideId": slide.source_slide_id,
        "slideNumber": slide.slide_number,
        "title": slide.title,
        "validationStatus": slide.validation_status,
        "renderSchemaVersion": (slide.render_schema_json or {}).get("schemaVersion"),
    }


def _element_version_summary(version: GeneratedSlideElementVersion) -> dict:
    return {
        "id": version.id,
        "versionNumber": version.version_number,
        "source": version.source,
        "status": version.status,
        "content": version.content_json,
        "style": version.style_json,
        "changeSummary": version.change_summary,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
    }


def _element_summary(element: GeneratedSlideElement | None, *, include_versions: bool = True) -> dict | None:
    if element is None:
        return None
    versions = sorted(element.versions, key=lambda item: item.version_number, reverse=True)
    return {
        "id": element.id,
        "generatedSlideId": element.generated_slide_id,
        "elementKey": element.element_key,
        "elementType": element.element_type,
        "sourceSlideId": element.source_slide_id,
        "zIndex": element.z_index,
        "position": {
            "x": element.x,
            "y": element.y,
            "width": element.width,
            "height": element.height,
            "rotation": element.rotation,
        },
        "locked": element.locked,
        "visible": element.visible,
        "content": element.content_json,
        "style": element.style_json,
        "versions": [_element_version_summary(version) for version in versions] if include_versions else [],
    }


def build_slide_generation_retrieval_context(
    *,
    deck: Deck,
    selected_slides: list[DeckSlide],
    active_design_version: DesignVersion | None,
    prompt: str,
    additional_context: str | None,
    design_tokens: dict,
    artifact_context: dict | None,
    audience_context: dict | None = None,
    archetype_context: dict | None = None,
) -> dict:
    vector_sync, vector_retrieval = _vector_context(
        deck,
        query_text=prompt,
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "accepted_edit", "deck_map_analysis", "market_research", "generated_version"],
        limit=10,
    )
    return {
        "kind": "slide_generation",
        "contextMode": ContextMode.slide_generation.value,
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": deck.status,
        },
        "brand": {
            "companyName": deck.brand_profile.company_name if deck.brand_profile else None,
            "visualDirection": deck.brand_profile.visual_direction if deck.brand_profile else None,
            "tokens": design_tokens,
        },
        "audienceContext": audience_context,
        "slideArchetypeContext": archetype_context
        or build_slide_archetype_context(
            audience=deck.audience,
            purpose=deck.purpose,
            slide_texts=[slide.raw_text or "" for slide in selected_slides],
            slide_titles=[slide.title or "" for slide in selected_slides],
            slide_roles=[slide.role or "" for slide in selected_slides],
        ),
        "selectedSourceSlides": [_slide_summary(slide) for slide in selected_slides],
        "activeDesignVersion": {
            "id": active_design_version.id,
            "name": active_design_version.name,
            "status": active_design_version.status,
            "generatedSlides": [_generated_slide_summary(slide) for slide in active_design_version.generated_slides],
        }
        if active_design_version
        else None,
        "artifactContext": artifact_context,
        "vectorSync": vector_sync,
        "vectorRetrieval": vector_retrieval,
        "userPrompt": prompt,
        "additionalContext": additional_context,
        "retrievalRules": [
            "Use selectedSourceSlides as the only source slides eligible for generation.",
            "Use brand tokens for colors and styling.",
            "Use audienceContext to adapt wording and information density for the target VC persona.",
            "Use slideArchetypeContext to keep the slide order and slide purpose aligned with the repository archetype corpus.",
            "Return structured JSON only; the backend validator is the persistence gate.",
        ],
    }


def build_element_variation_retrieval_context(
    *,
    deck: Deck,
    generated_slide: GeneratedSlide,
    element: GeneratedSlideElement,
    instruction: str,
    design_tokens: dict,
    audience_context: dict | None = None,
    archetype_context: dict | None = None,
) -> dict:
    source_slide = generated_slide.source_slide
    sibling_elements = sorted(generated_slide.elements, key=lambda item: item.z_index)
    active_versions = sorted(element.versions, key=lambda item: item.version_number, reverse=True)
    vector_sync, vector_retrieval = _vector_context(
        deck,
        query_text=instruction,
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "accepted_edit", "deck_map_analysis", "generated_version"],
        limit=8,
    )
    return {
        "kind": "element_variation",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
        },
        "brand": {
            "companyName": deck.brand_profile.company_name if deck.brand_profile else None,
            "visualDirection": deck.brand_profile.visual_direction if deck.brand_profile else None,
            "tokens": design_tokens,
        },
        "audienceContext": audience_context,
        "slideArchetypeContext": archetype_context
        or build_slide_archetype_context(
            audience=deck.audience,
            purpose=deck.purpose,
            slide_texts=[generated_slide.source_slide.raw_text if generated_slide.source_slide else ""],
            slide_titles=[generated_slide.source_slide.title if generated_slide.source_slide else ""],
            slide_roles=[generated_slide.source_slide.role if generated_slide.source_slide else ""],
        ),
        "generatedSlide": _generated_slide_summary(generated_slide),
        "sourceSlide": _slide_summary(source_slide),
        "selectedElement": _element_summary(element),
        "siblingElements": [_element_summary(item, include_versions=False) for item in sibling_elements],
        "activeElementVersion": _element_version_summary(active_versions[0]) if active_versions else None,
        "vectorSync": vector_sync,
        "vectorRetrieval": vector_retrieval,
        "instruction": instruction,
        "retrievalRules": [
            "Create a variation only for selectedElement.",
            "Do not overwrite the original element.",
            "Adapt the variation to audienceContext without inventing unsupported claims.",
            "Keep the variation consistent with the slideArchetypeContext and the slide's role in the narrative sequence.",
            "Return structured content/style/position JSON only.",
        ],
    }


def build_full_deck_generation_context(
    *,
    deck: Deck,
    selected_slides: list[DeckSlide],
    active_design_version: DesignVersion | None,
    prompt: str,
    additional_context: str | None,
    design_tokens: dict,
    artifact_context: dict | None,
    audience_context: dict | None = None,
    archetype_context: dict | None = None,
) -> dict:
    """Build request-creation context for full-deck Instant Deck.

    The canonical source/brand lanes are assembled here. Durable vector
    indexing and retrieval are deliberately deferred to the generation worker
    so the API does not perform provider I/O and the exact retrieved guidance
    can be persisted with the provider-bound request.
    """
    vector_sync, vector_retrieval = _empty_vector_context()
    brand_context = build_brand_llm_context(deck.brand_profile)
    return {
        "kind": "slide_generation",
        "contextMode": ContextMode.full_deck.value,
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": deck.status,
        },
        "brand": {
            **brand_context,
            "tokens": brand_context["tokens"],
        },
        "audienceContext": audience_context,
        "slideArchetypeContext": archetype_context
        or build_slide_archetype_context(
            audience=deck.audience,
            purpose=deck.purpose,
            slide_texts=[slide.raw_text or "" for slide in selected_slides],
            slide_titles=[slide.title or "" for slide in selected_slides],
            slide_roles=[slide.role or "" for slide in selected_slides],
        ),
        "selectedSourceSlides": [_slide_summary(slide) for slide in selected_slides],
        "activeDesignVersion": {
            "id": active_design_version.id,
            "name": active_design_version.name,
            "status": active_design_version.status,
            "generatedSlides": [_generated_slide_summary(slide) for slide in active_design_version.generated_slides],
        }
        if active_design_version
        else None,
        "artifactContext": artifact_context,
        "vectorSync": vector_sync,
        "vectorRetrieval": vector_retrieval,
        "userPrompt": prompt,
        "additionalContext": additional_context,
        "retrievalRules": [
            "Use selectedSourceSlides as the only source slides eligible for generation.",
            "Use brand.colors, brand.palette, and brand.tokens as the approved color system for the complete redesign.",
            "Preserve persisted brand-profile colors; do not replace them with unrelated or invented hues.",
            "Use audienceContext to adapt wording and information density for the target VC persona.",
            "Use slideArchetypeContext to keep the slide order and slide purpose aligned with the repository archetype corpus.",
            "Return structured JSON only; the backend validator is the persistence gate.",
        ],
    }


def build_generation_context(*, mode: ContextMode, **kwargs) -> dict:
    """Dispatch generation context assembly without changing retrieval policy."""
    if mode is ContextMode.full_deck:
        return build_full_deck_generation_context(**kwargs)
    if mode is ContextMode.slide_generation:
        return build_slide_generation_retrieval_context(**kwargs)
    raise ValueError(f"Unsupported generation context mode: {mode!r}")
