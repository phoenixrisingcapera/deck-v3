from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.ai_orchestration.errors import AiOrchestrationError
from app.db.models import Deck, DeckSlide


class SmartDeckContextBuilder:
    def build(
        self,
        db: Session,
        *,
        deck_id: str,
        selected_slide_ids: list[str],
        user_instruction: str,
        audience: str | None,
    ) -> dict:
        deck = (
            db.query(Deck)
            .options(
                selectinload(Deck.slides).selectinload(DeckSlide.blocks),
                selectinload(Deck.brand_profile),
            )
            .filter(Deck.id == deck_id)
            .one_or_none()
        )
        if deck is None:
            raise AiOrchestrationError("Deck not found")

        selected_ids = list(dict.fromkeys(selected_slide_ids))
        if selected_ids != selected_slide_ids:
            raise AiOrchestrationError("selectedSlideIds must not contain duplicates")
        if len(selected_ids) > 8:
            raise AiOrchestrationError("Select no more than 8 slides per orchestration run")

        slides_by_id = {slide.id: slide for slide in deck.slides}
        missing = [slide_id for slide_id in selected_ids if slide_id not in slides_by_id]
        if missing:
            raise AiOrchestrationError("selectedSlideIds must belong to this deck")

        selected_slides = [slides_by_id[slide_id] for slide_id in selected_ids]
        brand_profile = deck.brand_profile
        return {
            "deck": {
                "id": deck.id,
                "workspaceId": deck.workspace_id,
                "title": deck.title,
                "audience": audience or deck.audience,
                "purpose": deck.purpose,
                "summary": deck.summary,
            },
            "brand": {
                "companyName": brand_profile.company_name if brand_profile else None,
                "brandSummary": brand_profile.brand_summary if brand_profile else None,
                "visualDirection": brand_profile.visual_direction if brand_profile else None,
                "audienceLabel": brand_profile.audience_label if brand_profile else None,
                "primaryGoal": brand_profile.primary_goal if brand_profile else None,
            },
            "instruction": user_instruction.strip(),
            "selectedSlideIds": selected_ids,
            "selectedSlides": [self._slide_context(slide) for slide in selected_slides],
        }

    def _slide_context(self, slide: DeckSlide) -> dict:
        blocks = sorted(slide.blocks, key=lambda block: block.block_index)
        text = slide.raw_text or slide.summary or "\n".join(block.raw_text for block in blocks if block.raw_text)
        return {
            "slideId": slide.id,
            "slideIndex": slide.slide_index,
            "slideNumber": slide.slide_number,
            "title": slide.title,
            "role": slide.role,
            "text": text[:2400],
            "summary": (slide.summary or "")[:1200],
            "currentSceneGraph": {
                "schemaVersion": "smart-deck-scene-graph.v1",
                "width": 1280,
                "height": 720,
                "elements": [
                    {
                        "id": f"{slide.id}_source_text",
                        "type": "text",
                        "x": 80,
                        "y": 80,
                        "width": 1040,
                        "height": 420,
                        "text": text[:900],
                    }
                ],
            },
        }
