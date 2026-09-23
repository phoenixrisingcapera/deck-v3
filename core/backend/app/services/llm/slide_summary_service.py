from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.db.models import Deck, DeckSlide
from app.services.llm import default_registry
from app.services.llm.generation_service import get_generation_provider_config
from app.services.llm.response_models import LlmGenerationConfig


_SUMMARY_SYSTEM_PROMPT = """You summarize one presentation slide.
Return only a concise plain-text summary of the slide's meaning in one or two sentences.
Use only the supplied slide content. Do not invent facts, advice, or evidence.
Do not use a heading, bullets, markdown, or quotation marks."""


def _summary_source(slide: DeckSlide) -> str:
    block_text = "\n".join(
        str(block.raw_text or "").strip()
        for block in sorted(slide.blocks, key=lambda item: item.block_index)
        if str(block.raw_text or "").strip()
    )
    source = str(slide.raw_text or "").strip() or block_text
    return source[:12000]


def _normalize_summary(value: str) -> str:
    summary = " ".join(str(value or "").strip().split())
    if not summary:
        raise ValueError("AI provider returned an empty slide summary.")
    return summary[:1200].rstrip()


def generate_persisted_slide_summary(
    db: Session,
    *,
    deck_id: str,
    slide_id: str,
    force: bool = False,
) -> dict | None:
    """Generate and persist only ``DeckSlide.summary`` for one source slide.

    This deliberately does not call source enrichment, generation, or version
    services, so requesting a summary cannot create or mutate slide versions.
    """
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    slide = (
        db.query(DeckSlide)
        .options(selectinload(DeckSlide.blocks))
        .filter(DeckSlide.deck_id == deck_id, DeckSlide.id == slide_id)
        .one_or_none()
    )
    if deck is None or slide is None:
        return None

    if slide.summary and not force:
        return {
            "deckId": deck_id,
            "slideId": slide_id,
            "summary": slide.summary,
            "status": "ready",
            "persisted": True,
            "cached": True,
            "provider": None,
            "model": None,
            "updatedAt": slide.updated_at.isoformat() if slide.updated_at else None,
        }

    source = _summary_source(slide)
    if not source:
        raise ValueError("This slide has no extracted text to summarize.")

    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")
    provider = str(config.get("provider") or "")
    model = str(config.get("model") or "")
    api_key = str(config.get("apiKey") or "")
    response = default_registry.get(provider).generate_text(
        system=_SUMMARY_SYSTEM_PROMPT,
        user=(
            f"Slide title: {slide.title or 'Untitled slide'}\n"
            f"Slide role: {slide.role or 'unknown'}\n\n"
            f"Slide content:\n{source}"
        ),
        config=LlmGenerationConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            max_tokens=400,
            timeout_seconds=60,
        ),
    )
    slide.summary = _normalize_summary(response.content)
    db.commit()
    db.refresh(slide)
    return {
        "deckId": deck_id,
        "slideId": slide_id,
        "summary": slide.summary,
        "status": "ready",
        "persisted": True,
        "cached": False,
        "provider": response.provider or provider,
        "model": response.model or model,
        "updatedAt": slide.updated_at.isoformat() if slide.updated_at else None,
    }
