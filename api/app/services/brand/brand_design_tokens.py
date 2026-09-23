"""Resolve persisted deck-brand signals into renderer-safe design tokens."""

import re
from typing import Any


DEFAULT_DESIGN_TOKENS = {
    "brand.surface": "#070A12",
    "brand.surfaceAlt": "#111827",
    "brand.heading": "#F8FAFC",
    "brand.body": "#CBD5E1",
    "brand.accent": "#6EE7B7",
    "brand.muted": "#64748B",
    "brand.headingFont": "Inter, sans-serif",
    "brand.bodyFont": "Inter, sans-serif",
}

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_FONT_FAMILY = re.compile(r"^[a-zA-Z0-9 ._-]{1,80}$")


def _color(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and _HEX_COLOR.fullmatch(value.strip()) else fallback


def _font(value: Any, fallback: str) -> str:
    return f"{value.strip()}, sans-serif" if isinstance(value, str) and _FONT_FAMILY.fullmatch(value.strip()) else fallback


def build_brand_design_tokens(brand_profile: Any | None) -> dict[str, str]:
    """Map a deck's canonical brand profile to the renderer token contract."""
    tokens = dict(DEFAULT_DESIGN_TOKENS)
    if brand_profile is None:
        return tokens

    tokens.update(
        {
            "brand.surface": _color(getattr(brand_profile, "background_color", None), tokens["brand.surface"]),
            "brand.surfaceAlt": _color(getattr(brand_profile, "secondary_color", None), tokens["brand.surfaceAlt"]),
            "brand.heading": _color(getattr(brand_profile, "text_color", None), tokens["brand.heading"]),
            "brand.body": _color(getattr(brand_profile, "text_color", None), tokens["brand.body"]),
            "brand.accent": _color(
                getattr(brand_profile, "accent_color", None) or getattr(brand_profile, "primary_color", None),
                tokens["brand.accent"],
            ),
        }
    )
    fonts = getattr(brand_profile, "font_candidates_json", None) or []
    if fonts:
        tokens["brand.headingFont"] = _font(fonts[0], tokens["brand.headingFont"])
        tokens["brand.bodyFont"] = _font(fonts[1] if len(fonts) > 1 else fonts[0], tokens["brand.bodyFont"])
    return tokens


def build_provider_safe_brand_context(
    brand_profile: Any | None,
    *,
    neutral_when_absent: bool = False,
    design_tokens: dict[str, str] | None = None,
    preserve_missing_colors: bool = False,
) -> dict[str, Any]:
    """Return the canonical provider brand contract, with an explicit neutral mode."""
    tokens = dict(design_tokens or build_brand_design_tokens(brand_profile))
    if brand_profile is None:
        if neutral_when_absent:
            # Preserve the complete consumer shape without claiming renderer
            # fallback colors or fonts are recovered brand facts.
            tokens = {key: "" for key in DEFAULT_DESIGN_TOKENS}
        neutral_colors = {
            "primary": None,
            "secondary": None,
            "accent": None,
            "background": None,
            "text": None,
        }
        return {
            "companyName": None,
            "visualDirection": None,
            "palette": [],
            "colors": neutral_colors if neutral_when_absent else {
                "primary": None,
                "secondary": None,
                "accent": tokens["brand.accent"],
                "background": tokens["brand.surface"],
                "text": tokens["brand.heading"],
            },
            "tokens": tokens,
            "instructions": [
                (
                    "No canonical brand values are available; choose an accessible visual system without inferring or claiming a brand identity."
                    if neutral_when_absent
                    else "When no persisted brand profile exists, use the provided brand tokens as the only approved deck color system."
                ),
            ],
        }

    palette_values = getattr(brand_profile, "palette_json", None)
    if palette_values is None:
        palette_values = getattr(brand_profile, "palette", None)
    palette = [value.strip() for value in (palette_values or []) if isinstance(value, str) and _HEX_COLOR.fullmatch(value.strip())]
    color_fields = {
        "primary": ("primary_color", "brand.accent"),
        "secondary": ("secondary_color", "brand.surfaceAlt"),
        "accent": ("accent_color", "brand.accent"),
        "background": ("background_color", "brand.surface"),
        "text": ("text_color", "brand.heading"),
    }
    colors = {
        key: (
            _color(getattr(brand_profile, field, None), "") or None
            if preserve_missing_colors
            else _color(getattr(brand_profile, field, None), tokens[token_key])
        )
        for key, (field, token_key) in color_fields.items()
    }
    return {
        "companyName": getattr(brand_profile, "company_name", None),
        "visualDirection": getattr(brand_profile, "visual_direction", None),
        "palette": palette,
        "colors": colors,
        "tokens": tokens,
        "instructions": [
            "Use the persisted brand profile colors and brand tokens for deck color decisions before inventing new hues.",
            "Prefer brand.colors and brand.palette for slide backgrounds, accents, and text contrast across Smart Deck, Smart Edit, Due Diligence, Insights, and Instant Deck outputs.",
            "If a requested color treatment conflicts with brand readability or contrast, keep the brand palette and report the tradeoff instead of drifting silently.",
        ],
    }


def build_brand_llm_context(brand_profile: Any | None) -> dict[str, Any]:
    """Preserve the standard Smart Deck brand contract."""
    return build_provider_safe_brand_context(brand_profile)
