from __future__ import annotations

from html import escape
from typing import Any

from app.services.visual_intelligence.models import ChartSpec


_DEFAULT_CHART_BG = "#0B1020"
_DEFAULT_CHART_TEXT = "#F8FAFC"
_DEFAULT_CHART_MUTED = "#CBD5E1"
_DEFAULT_CHART_GRID = "#475569"


def render_chart_svg(
    spec: ChartSpec,
    *,
    width: int = 1200,
    height: int = 640,
    background_tokens: dict[str, str] | None = None,
) -> str:
    """Render a bounded bar/line/area chart without executing model-authored code.

    Uses the authored background system tokens when provided so charts visually
    integrate into the slide's harmonized canvas instead of using hardcoded colors.
    """
    if width < 320 or height < 240:
        raise ValueError("Chart canvas is below the supported minimum")
    left, top, right, bottom = 100, 90, 50, 90
    plot_width, plot_height = width - left - right, height - top - bottom
    values = [value for series in spec.series for value in series.values]
    if spec.chart_type == "waterfall":
        running = 0.0
        waterfall_extents = [0.0]
        for index, value in enumerate(spec.series[0].values):
            category = spec.categories[index].lower()
            if index == 0 or "closing" in category or "ending" in category:
                running = value
                waterfall_extents.extend([0.0, value])
            else:
                waterfall_extents.extend([running, running + value])
                running += value
        values = waterfall_extents
    minimum = min(0.0, min(values))
    maximum = max(0.0, max(values))
    span = maximum - minimum or 1.0
    brand_colors = tuple(spec.brand_palette) or ("#36C5F0", "#A78BFA", "#34D399", "#FBBF24", "#FB7185")

    _tokens = background_tokens or {}
    canvas = str(_tokens.get("--da-canvas") or _tokens.get("background") or "")
    ink = str(_tokens.get("--da-ink") or _tokens.get("color") or "")
    surface = str(_tokens.get("--da-surface") or "")
    accent = str(_tokens.get("--da-accent") or "")

    bg_color = canvas if canvas.startswith("#") and len(canvas) in {7, 4} else _DEFAULT_CHART_BG
    text_color = ink if ink.startswith("#") and len(ink) in {7, 4} else _DEFAULT_CHART_TEXT
    muted_color = surface if surface.startswith("#") and len(surface) in {7, 4} else _DEFAULT_CHART_MUTED
    grid_color = _blend_with(bg_color, _DEFAULT_CHART_GRID, 0.6) if bg_color != _DEFAULT_CHART_BG else _DEFAULT_CHART_GRID

    # Derive chart accent colors from the authored accent when available
    if accent.startswith("#") and len(accent) in {7, 4}:
        brand_colors = _palette_from_accent(accent, count=max(len(brand_colors), 4))

    def x_at(index: int) -> float:
        return left + plot_width * ((index + 0.5) / len(spec.categories))

    def y_at(value: float) -> float:
        return top + plot_height * ((maximum - value) / span)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(spec.title)}">',
        f'<rect width="100%" height="100%" fill="{bg_color}"/>',
        f'<text x="{left}" y="48" fill="{text_color}" font-family="Inter,Arial,sans-serif" font-size="28" font-weight="700">{escape(spec.title)}</text>',
        f'<line x1="{left}" y1="{y_at(0):.2f}" x2="{width-right}" y2="{y_at(0):.2f}" stroke="{grid_color}"/>',
    ]
    if spec.actual_forecast and spec.actual_forecast.transition_after_category in spec.categories:
        boundary_index = spec.categories.index(spec.actual_forecast.transition_after_category)
        boundary_x = left + plot_width * ((boundary_index + 1) / len(spec.categories))
        forecast_text_color = _blend_with(bg_color, text_color, 0.7)
        parts.extend([
            f'<line x1="{boundary_x:.2f}" y1="{top}" x2="{boundary_x:.2f}" y2="{height-bottom}" stroke="{muted_color}" stroke-width="2" stroke-dasharray="8 8"/>',
            f'<text x="{boundary_x + 10:.2f}" y="{top + 20}" fill="{forecast_text_color}" font-family="Inter,Arial,sans-serif" font-size="14">Forecast</text>',
        ])
    if spec.chart_type in {"line", "area"}:
        for series_index, series in enumerate(spec.series):
            points = " ".join(f"{x_at(i):.2f},{y_at(value):.2f}" for i, value in enumerate(series.values))
            color = brand_colors[series_index % len(brand_colors)]
            if spec.chart_type == "area":
                baseline = y_at(0)
                area = f"{x_at(0):.2f},{baseline:.2f} {points} {x_at(len(series.values)-1):.2f},{baseline:.2f}"
                parts.append(f'<polygon points="{area}" fill="{color}" fill-opacity="0.18"/>')
            bindings = series.point_bindings
            if bindings:
                for index in range(len(series.values) - 1):
                    forecast = bindings[index + 1].status in {"forecast", "projected", "scenario", "target"}
                    parts.append(
                        f'<line x1="{x_at(index):.2f}" y1="{y_at(series.values[index]):.2f}" '
                        f'x2="{x_at(index + 1):.2f}" y2="{y_at(series.values[index + 1]):.2f}" '
                        f'stroke="{color}" stroke-width="5" stroke-opacity="{0.68 if forecast else 1}" '
                        f'{"stroke-dasharray=\"12 9\"" if forecast else ""}/>'
                    )
            else:
                parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="5"/>')
            for index, value in enumerate(series.values):
                parts.append(f'<circle cx="{x_at(index):.2f}" cy="{y_at(value):.2f}" r="6" fill="{color}"/>')
                parts.append(f'<text x="{x_at(index):.2f}" y="{y_at(value)-14:.2f}" text-anchor="middle" fill="{text_color}" font-family="Inter,Arial,sans-serif" font-size="14">{escape(f"{value:g}")}</text>')
    elif spec.chart_type == "waterfall":
        group_width = plot_width / len(spec.categories)
        bar_width = min(86.0, group_width * 0.68)
        running = 0.0
        positive_color = _blend_with(bg_color, accent if accent.startswith("#") else "#34D399", 0.35)
        negative_color = _blend_with(bg_color, "#FB7185", 0.35)
        for index, value in enumerate(spec.series[0].values):
            category = spec.categories[index].lower()
            total = index == 0 or "closing" in category or "ending" in category
            start, end = (0.0, value) if total else (running, running + value)
            if not total:
                running = end
            else:
                running = value
            x = x_at(index) - bar_width / 2
            color = brand_colors[0] if total else (positive_color if value >= 0 else negative_color)
            parts.append(f'<rect x="{x:.2f}" y="{min(y_at(start), y_at(end)):.2f}" width="{bar_width:.2f}" height="{abs(y_at(start)-y_at(end)):.2f}" rx="3" fill="{color}"/>')
            parts.append(f'<text x="{x_at(index):.2f}" y="{min(y_at(start), y_at(end))-10:.2f}" text-anchor="middle" fill="{text_color}" font-family="Inter,Arial,sans-serif" font-size="14">{escape(f"{value:g}")}</text>')
            if index < len(spec.categories) - 1:
                parts.append(f'<line x1="{x + bar_width:.2f}" y1="{y_at(end):.2f}" x2="{x_at(index + 1) - bar_width/2:.2f}" y2="{y_at(end):.2f}" stroke="{muted_color}" stroke-dasharray="5 5"/>')
    elif spec.chart_type == "funnel":
        series = spec.series[0]
        maximum_value = max(abs(value) for value in series.values) or 1.0
        band_height = plot_height / len(series.values)
        for index, value in enumerate(series.values):
            band_width = max(120.0, plot_width * abs(value) / maximum_value)
            x = left + (plot_width - band_width) / 2
            y = top + index * band_height
            color = brand_colors[index % len(brand_colors)]
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{band_width:.2f}" height="{max(24.0, band_height-12):.2f}" rx="8" fill="{color}" fill-opacity="{max(0.45, 1-index*0.1):.2f}"/>')
            parts.append(f'<text x="{width/2:.2f}" y="{y + band_height/2:.2f}" text-anchor="middle" fill="{text_color}" font-family="Inter,Arial,sans-serif" font-size="17">{escape(spec.categories[index])}: {escape(f"{value:g}")}</text>')
    else:
        group_width = plot_width / len(spec.categories)
        bar_width = min(64.0, group_width * 0.72 / len(spec.series))
        for series_index, series in enumerate(spec.series):
            color = brand_colors[series_index % len(brand_colors)]
            for index, value in enumerate(series.values):
                zero_y, value_y = y_at(0), y_at(value)
                x = x_at(index) - (len(spec.series) * bar_width / 2) + series_index * bar_width
                parts.append(f'<rect x="{x:.2f}" y="{min(zero_y, value_y):.2f}" width="{bar_width-3:.2f}" height="{abs(zero_y-value_y):.2f}" rx="3" fill="{color}"/>')
                parts.append(f'<text x="{x + (bar_width-3)/2:.2f}" y="{min(zero_y, value_y)-10:.2f}" text-anchor="middle" fill="{text_color}" font-family="Inter,Arial,sans-serif" font-size="14">{escape(f"{value:g}")}</text>')
    for index, category in enumerate(spec.categories):
        parts.append(f'<text x="{x_at(index):.2f}" y="{height-42}" text-anchor="middle" fill="{muted_color}" font-family="Inter,Arial,sans-serif" font-size="16">{escape(category)}</text>')
    if spec.value_unit:
        parts.append(f'<text x="{width-right}" y="48" text-anchor="end" fill="{_blend_with(bg_color, muted_color, 0.7)}" font-family="Inter,Arial,sans-serif" font-size="14">Unit: {escape(spec.value_unit)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _blend_with(hex_color: str, target: str, amount: float) -> str:
    """Blend a target color into a background by a given amount."""
    if not hex_color.startswith("#") or len(hex_color) not in {7, 4}:
        return target
    if not target.startswith("#"):
        return target
    bg = _parse_rgb(hex_color)
    tg = _parse_rgb(target)
    if bg is None or tg is None:
        return target
    amount = max(0.0, min(1.0, amount))
    blended = tuple(int(round(bg[i] + (tg[i] - bg[i]) * amount)) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*blended)


def _parse_rgb(hex_color: str) -> tuple[int, int, int] | None:
    if not hex_color.startswith("#"):
        return None
    value = hex_color[1:]
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _palette_from_accent(accent_hex: str, count: int = 4) -> tuple[str, ...]:
    """Generate a harmonized palette from a single accent color."""
    rgb = _parse_rgb(accent_hex)
    if rgb is None:
        return ("#36C5F0", "#A78BFA", "#34D399", "#FBBF24", "#FB7185")
    h, s, l = _rgb_to_hsl(*rgb)
    palette = []
    for i in range(count):
        hue = (h + i * (360 // count)) % 360
        r, g, b = _hsl_to_rgb(hue, s, l)
        palette.append("#{:02X}{:02X}{:02X}".format(r, g, b))
    return tuple(palette)


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    max_c, min_c = max(r_, g_, b_), min(r_, g_, b_)
    l = (max_c + min_c) / 2
    if max_c == min_c:
        h = s = 0.0
    else:
        d = max_c - min_c
        s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
        if max_c == r_:
            h = ((g_ - b_) / d + (6 if g_ < b_ else 0)) / 6
        elif max_c == g_:
            h = ((b_ - r_) / d + 2) / 6
        else:
            h = ((r_ - g_) / d + 4) / 6
    return h * 360, s, l


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    h_, s_, l_ = h / 360.0, s, l
    if s_ == 0:
        r = g = b = l_
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l_ * (1 + s_) if l_ < 0.5 else l_ + s_ - l_ * s_
        p = 2 * l_ - q
        r = hue_to_rgb(p, q, h_ + 1/3)
        g = hue_to_rgb(p, q, h_)
        b = hue_to_rgb(p, q, h_ - 1/3)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
