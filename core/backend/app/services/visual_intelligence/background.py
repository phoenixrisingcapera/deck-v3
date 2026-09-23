"""Application-owned slide background authoring for the visual intelligence stage.

The visual LLM proposes meaning and intent; Deck V2 authors the concrete,
harmonized backgrounds from canonical brand tokens so the deck never depends
on a model-supplied raw CSS string. Slide one receives a distinct editorial
cover field; every later slide shares the harmonized interior system so the
deck reads as one visual story rather than a sequence of independent pages.
"""

from __future__ import annotations

from typing import Any

from app.services.visual_intelligence.decision_engine import brand_palette
from app.services.visual_intelligence.models import DeckBackgroundSystem, SlideBackground

_NEUTRAL_COVER = (15, 23, 42)      # #0F172A
_NEUTRAL_INK = (255, 255, 255)     # #FFFFFF
_NEUTRAL_SURFACE = (248, 250, 252)  # #F8FAFC
_NEUTRAL_ACCENT = (37, 99, 235)     # #2563EB
_NEUTRAL_TEXT = (15, 23, 42)        # #0F172A

# Interior panels stay on the same harmonized canvas. The treatment label is
# a "visual specific helper": it tells the designer how the slide's own
# primitive creates a field within that shared canvas, not a new background.
_TREATMENTS = {
    "hero": "full-canvas editorial cover field",
    "editorial_statement": "quiet assertion field with an evidence rail",
    "big_number": "metric proof field with a single focal figure",
    "data_chart": "chart proof field on the shared canvas",
    "market_size": "stepped scope field on the shared canvas",
    "financial_bridge": "economic bridge field on the shared canvas",
    "competitive_matrix": "comparison field on the shared canvas",
    "workflow": "flow field on the shared canvas",
    "timeline": "paced milestone field on the shared canvas",
    "funnel": "stage field on the shared canvas",
    "platform_architecture": "system map field on the shared canvas",
    "product_ui": "product moment field on the shared canvas",
    "business_model": "economic system field on the shared canvas",
    "wedge_expansion": "expansion path field on the shared canvas",
    "composition": "harmonized proof field on the shared canvas",
}

_BACKGROUND_PALETTE_KEYS = (
    "background", "backgroundColor", "background_color", "canvas", "surface",
    "bg", "bgLight", "lightSurface", "light", "brandBackgroundColor",
)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _rgb(hex_value: str | None) -> tuple[int, int, int] | None:
    if not hex_value or not hex_value.startswith("#"):
        return None
    value = hex_value[1:]
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        scaled = value / 255
        return scaled / 12.92 if scaled <= 0.03928 else ((scaled + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def _readable_ink_for(canvas: tuple[int, int, int]) -> str:
    return _hex(_NEUTRAL_TEXT) if _luminance(canvas) >= 0.42 else _hex(_NEUTRAL_INK)


def _mix(base: tuple[int, int, int], target: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(round(base[i] + (target[i] - base[i]) * amount)) for i in range(3))  # type: ignore[return-value]


def _choose_canvas(brand: dict[str, Any], *, light: bool = True) -> tuple[tuple[int, int, int], str]:
    palette = brand_palette(brand)
    for key in _BACKGROUND_PALETTE_KEYS:
        candidate = brand.get(key) if isinstance(brand.get(key), str) else None
        rgb = _rgb(candidate)
        if rgb is None:
            continue
        luminance = _luminance(rgb)
        if light and luminance >= 0.6:
            return _mix(rgb, (255, 255, 255), 0.25), candidate
        if not light and luminance <= 0.35:
            return _mix(rgb, _NEUTRAL_COVER, 0.6), candidate
    for candidate in palette:
        rgb = _rgb(candidate)
        if rgb is None:
            continue
        luminance = _luminance(rgb)
        if light and luminance >= 0.6:
            return _mix(rgb, (255, 255, 255), 0.25), candidate
        if not light and luminance <= 0.35:
            return _mix(rgb, _NEUTRAL_COVER, 0.6), candidate
    return (_NEUTRAL_SURFACE if light else _NEUTRAL_COVER), _hex(_NEUTRAL_SURFACE if light else _NEUTRAL_COVER)


def author_deck_background_system(
    brand: dict[str, Any],
    *,
    slide_count: int,
    design_emphasis: str | None = None,
) -> DeckBackgroundSystem:
    """Author one harmonized background system across the whole deck.

    Slide one is the distinct cover. All interior slides share one canvas,
    one surface, one ink and one accent so backgrounds stay homogenized.
    """
    cover_canvas, cover_source = _choose_canvas(brand, light=False)
    interior_canvas, _ = _choose_canvas(brand, light=True)
    accent_rgbs = [rgb for rgb in (_rgb(value) for value in brand_palette(brand)) if rgb is not None]
    accent_rgb = accent_rgbs[0] if accent_rgbs else _NEUTRAL_ACCENT
    one_third = max(1, round(slide_count * (1 / 3)))
    if slide_count > one_third:
        # Saturated field colors in the middle of a deck would break rhythm.
        # Keep the accent as a restrained ingredient, not a full-canvas fill.
        accent_surface = _mix(interior_canvas, accent_rgb, 0.08)
    else:
        accent_surface = _mix(interior_canvas, accent_rgb, 0.12)
    interior_ink = _readable_ink_for(interior_canvas)
    cover_ink = _readable_ink_for(cover_canvas)
    cover_surface = _mix(cover_canvas, accent_rgb, 0.22)
    cover_alt = _mix(cover_canvas, accent_rgb, 0.12)
    surface_hex = _hex(accent_surface)
    system = DeckBackgroundSystem(
        cover=SlideBackground(
            canvas=_hex(cover_canvas),
            surface=_hex(cover_surface),
            surface_alt=_hex(cover_alt),
            accent=_hex(accent_rgb),
            ink=cover_ink,
            treatment="full-canvas editorial cover field",
            harmonization="distinct_cover",
            distinct=True,
            rationale=f"Distinct opener canvas derived from {cover_source or 'the neutral brand field'}.",
        ),
        interior=SlideBackground(
            canvas=_hex(interior_canvas),
            surface=surface_hex,
            surface_alt=_hex(_mix(interior_canvas, accent_rgb, 0.16)),
            accent=_hex(accent_rgb),
            ink=interior_ink,
            treatment="harmonized interior canvas",
            harmonization="shared_interior",
            distinct=False,
            rationale="Every interior slide shares this canvas so the deck reads as one visual story.",
        ),
        harmonization_principle=(
            "Slide one opens on the distinct cover canvas. Every following slide uses the shared "
            "interior canvas with the same surface, accent and ink; per-slide primitives create fields "
            "inside that canvas and never introduce a new slide background."
        ),
        css_tokens={
            "--da-canvas": _hex(interior_canvas),
            "--da-surface": surface_hex,
            "--da-surface-alt": _hex(_mix(interior_canvas, accent_rgb, 0.16)),
            "--da-accent": _hex(accent_rgb),
            "--da-ink": interior_ink,
        },
    )
    return system


def author_slide_background(
    system: DeckBackgroundSystem,
    *,
    slide_index: int,
    visual_primitive: str,
    design_emphasis: str | None = None,
) -> SlideBackground:
    """Resolve one slide's background from the deck-wide harmonized system."""
    if slide_index == 1:
        background = system.cover.model_copy(deep=True)
        background.treatment = _TREATMENTS.get(visual_primitive, _TREATMENTS["hero"])
        background.rationale = (
            "Distinct editorial cover for slide one; interior slides inherit the shared harmonized system."
        )
        return background
    background = system.interior.model_copy(deep=True)
    background.treatment = _TREATMENTS.get(visual_primitive, _TREATMENTS["composition"])
    background.rationale = (
        f"Harmonized interior canvas shared across slides; {visual_primitive or 'composition'} "
        "creates its field inside the same background."
    )
    return background