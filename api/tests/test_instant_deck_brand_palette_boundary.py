from app.services.brand.brand_extraction import (
    _observed_palette_values,
    _palette_from_color_values,
    _preferred_deck_palette_values,
)


def test_generated_accessibility_roles_do_not_become_observed_brand_colours() -> None:
    palette = {
        "palette": ["#C00018", "#00C0C0", "#90C000", "#EEF3FF", "#0F172A"],
        "observedCandidates": ["#CA0012", "#EEEBE3"],
    }

    assert _observed_palette_values(palette) == ["#CA0012", "#EEEBE3"]


def test_single_brand_colour_gets_tonal_not_unrelated_purple_support() -> None:
    palette = _palette_from_color_values(["#CA0012"], seed=7)

    assert palette is not None
    assert palette["primary"] == "#C00018"
    assert palette["accent"] != "#8B5CF6"
    assert palette["roleOrigins"]["accent"] == "generated_accessibility_role"


def test_vector_design_ink_outranks_full_slide_photo_colours() -> None:
    selected = _preferred_deck_palette_values(
        ["#FFFFFF", "#EEEBE3", "#CA0012", "#000000"],
        ["#78C000", "#00C0C0", "#F09000"],
    )
    palette = _palette_from_color_values(selected, seed=7)

    assert palette is not None
    assert selected == ["#FFFFFF", "#EEEBE3", "#CA0012", "#000000"]
    assert palette["primary"] == "#C00018"
    assert palette["secondary"] == "#F0F0D8"
    assert palette["accent"] not in {"#78C000", "#00C0C0", "#F09000"}
