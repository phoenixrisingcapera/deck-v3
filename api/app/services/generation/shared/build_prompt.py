from __future__ import annotations

import json
from pathlib import Path

from app.schemas.generation import GenerateSlidesRequest
from app.services.rendering.schema_validation import load_generated_deck_schema


PACKAGE_ROOT = Path(__file__).resolve().parents[5] / "deck_aistack_codes_api_prompt_package"
SYSTEM_PROMPT_PATH = PACKAGE_ROOT / "prompts" / "system_prompt.md"


def build_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

    return (
        "You are the Deck AI Stack slide generation assistant. Output only valid JSON, preserve user facts, "
        "avoid unsafe claims, and return structured slide blocks suitable for backend storage and frontend rendering."
    )


def build_user_prompt(
    payload: GenerateSlidesRequest,
    deck_input: str,
    deck_title: str,
    audience: str,
    purpose: str,
    artifact_context: dict | None = None,
) -> str:
    # The schema is included in the prompt so Claude mode remains useful even without a separate SDK helper.
    schema_json = json.dumps(load_generated_deck_schema(), ensure_ascii=True)

    artifact_section = ""
    if artifact_context:
        artifact_section = f"Deck artifact context:\n{json.dumps(artifact_context, ensure_ascii=True)}\n\n"

    return (
        "Generate a Deck AI Stack slide deck from the following workspace context.\n\n"
        f"Deck title:\n{deck_title}\n\n"
        f"Deck input:\n{deck_input}\n\n"
        f"{artifact_section}"
        f"Target audience:\n{audience}\n\n"
        f"Purpose:\n{purpose}\n\n"
        f"Theme preference:\n{payload.theme}\n\n"
        f"Generation scope:\n{payload.scopeType}\n\n"
        f"Instruction:\n{payload.prompt.strip()}\n\n"
        "Return JSON only. Use structured blocks, not HTML. Use image_placeholder only when necessary. "
        "If a slide is uncertain, mark it needs_review.\n\n"
        f"JSON schema:\n{schema_json}"
    )
