from __future__ import annotations

import json

from app.services.llm.openai_provider import call_openai_response, extract_openai_text
from app.core.config import settings
from app.schemas.generation import GenerateSlidesRequest, GeneratedDeckPayload
from app.services.generation.shared.build_prompt import build_system_prompt, build_user_prompt
from app.services.rendering.schema_validation import validate_generated_deck


def generate_slides_with_openai(
    payload: GenerateSlidesRequest,
    deck_input: str,
    deck_title: str,
    audience: str,
    purpose: str,
    artifact_context: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> GeneratedDeckPayload:
    resolved_api_key = api_key or settings.openai_api_key
    resolved_model = model or settings.openai_model
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY is missing.")

    raw_payload = call_openai_response(
        api_key=resolved_api_key,
        model=resolved_model,
        system=build_system_prompt(),
        user=build_user_prompt(
            payload=payload,
            deck_input=deck_input,
            deck_title=deck_title,
            audience=audience,
            purpose=purpose,
            artifact_context=artifact_context,
        ),
        timeout=settings.openai_timeout_seconds,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(extract_openai_text(raw_payload))
    return validate_generated_deck(parsed)
