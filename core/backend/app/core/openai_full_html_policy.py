"""Provider-independent OpenAI policy for the ``full_html_deck.v1`` contract.

Source of truth: OpenAI's GPT-5 model page documents snapshot
``gpt-5-2025-08-07``, 400K context, 272K maximum input, 128K maximum
output, and standard prices of $1.25/M input and $10/M output tokens.
Aliases and prefix matching are intentionally prohibited.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
import math
import re
from typing import Iterable


FULL_HTML_OPENAI_MODEL = "gpt-5-2025-08-07"
FULL_HTML_OPENAI_MODELS = frozenset({FULL_HTML_OPENAI_MODEL})
FULL_HTML_CONTEXT_TOKENS = 400_000
FULL_HTML_MAX_INPUT_TOKENS = 272_000
FULL_HTML_MAX_OUTPUT_TOKENS = 128_000
FULL_HTML_MAX_INPUT_BYTES = FULL_HTML_MAX_INPUT_TOKENS * 4
# 190 selected source slides keeps the deterministic whole-deck byte estimate
# (18,000 + count * 4,000) under the renderer-feasible 800,000-byte ceiling.
FULL_HTML_MAX_SOURCE_SLIDES = 190
FULL_HTML_INPUT_USD_PER_MILLION = Decimal("1.25")
FULL_HTML_OUTPUT_USD_PER_MILLION = Decimal("10.00")


class FullHtmlOpenAIPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class TokenFeasibility:
    model: str
    input_tokens: int
    output_tokens: int
    total_context_tokens: int
    worst_case_cost_cents: Decimal


def require_full_html_openai_model(model: str | None) -> str:
    normalized = str(model or "").strip()
    if normalized not in FULL_HTML_OPENAI_MODELS:
        raise FullHtmlOpenAIPolicyError(
            f"full_html_deck.v1 requires exact OpenAI snapshot {FULL_HTML_OPENAI_MODEL}."
        )
    return normalized


def estimate_text_tokens(text: str, *, model: str = FULL_HTML_OPENAI_MODEL) -> int:
    """Use tiktoken when installed; otherwise use a conservative UTF-8 bound.

    The fallback assumes at most three UTF-8 bytes per token and adds framing
    overhead. It intentionally overestimates common English/HTML prompts.
    """

    require_full_html_openai_model(model)
    try:
        import tiktoken  # type: ignore[import-not-found]

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text, disallowed_special=())) + 8
    except ImportError:
        encoded_bytes = len(text.encode("utf-8"))
        # Base64 images tokenize much more densely than ordinary English and
        # HTML. Count those characters one-for-one so environments without
        # tiktoken fail closed before opening a paid provider request.
        base64_chars = sum(
            len(match.group(1))
            for match in re.finditer(
                r"data:image/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/]*={0,2})",
                text,
            )
        )
        ordinary_bytes = max(0, encoded_bytes - base64_chars)
        return math.ceil(ordinary_bytes / 3) + base64_chars + 8


def estimate_request_tokens(parts: Iterable[str], *, model: str = FULL_HTML_OPENAI_MODEL) -> int:
    # Twelve tokens conservatively cover each Responses API message/content envelope.
    values = list(parts)
    return sum(estimate_text_tokens(value, model=model) for value in values) + 12 * len(values)


def estimate_openai_cost_cents(*, input_tokens: int, output_tokens: int) -> Decimal:
    dollars = (
        Decimal(max(0, input_tokens)) * FULL_HTML_INPUT_USD_PER_MILLION
        + Decimal(max(0, output_tokens)) * FULL_HTML_OUTPUT_USD_PER_MILLION
    ) / Decimal(1_000_000)
    return (dollars * Decimal(100)).quantize(Decimal("0.0001"), rounding=ROUND_UP)


def validate_token_feasibility(
    *,
    model: str,
    prompt_parts: Iterable[str],
    max_output_tokens: int,
) -> TokenFeasibility:
    model = require_full_html_openai_model(model)
    if max_output_tokens <= 0 or max_output_tokens > FULL_HTML_MAX_OUTPUT_TOKENS:
        raise FullHtmlOpenAIPolicyError("OpenAI max output must be between 1 and 128000 tokens.")
    input_tokens = estimate_request_tokens(prompt_parts, model=model)
    total = input_tokens + max_output_tokens
    if input_tokens > FULL_HTML_MAX_INPUT_TOKENS:
        raise FullHtmlOpenAIPolicyError("OpenAI full HTML input exceeds the 272000-token model limit.")
    if total > FULL_HTML_CONTEXT_TOKENS:
        raise FullHtmlOpenAIPolicyError("OpenAI full HTML request exceeds the 400000-token context limit.")
    return TokenFeasibility(
        model=model,
        input_tokens=input_tokens,
        output_tokens=max_output_tokens,
        total_context_tokens=total,
        worst_case_cost_cents=estimate_openai_cost_cents(
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
        ),
    )
