from __future__ import annotations

import json

from app.services.llm.anthropic_provider import call_anthropic_message, extract_anthropic_text
from app.core.config import settings
from app.schemas.generation import GenerateSlidesRequest, GeneratedDeckPayload
from app.services.generation.shared.build_prompt import build_system_prompt, build_user_prompt
from app.services.rendering.schema_validation import validate_generated_deck


def generate_slides_with_claude(
    payload: GenerateSlidesRequest,
    deck_input: str,
    deck_title: str,
    audience: str,
    purpose: str,
    artifact_context: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> GeneratedDeckPayload:
    resolved_api_key = api_key or settings.anthropic_api_key
    resolved_model = model or settings.anthropic_model
    if not resolved_api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing.")

    raw_payload = call_anthropic_message(
        api_key=resolved_api_key,
        model=resolved_model,
        max_tokens=settings.anthropic_max_tokens,
        system=build_system_prompt(),
        user=build_user_prompt(
            payload=payload,
            deck_input=deck_input,
            deck_title=deck_title,
            audience=audience,
            purpose=purpose,
            artifact_context=artifact_context,
        ),
        timeout=60,
    )
    raw_text = extract_anthropic_text(raw_payload)
    parsed = json.loads(raw_text)
    return validate_generated_deck(parsed)
