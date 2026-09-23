"""Deterministic compiler for hostile ``full_html_deck.v1`` provider output.

HTML is parsed with html5lib and CSS with tinycss2.  This module deliberately
contains no browser or persistence claims: browser proof is a separate gate.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
import re
import unicodedata
from typing import Any, Iterable
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import html5lib
import tinycss2

from app.core.config import settings
from app.services.rendering.playwright_render_child import MAX_RENDER_DOCUMENT_BYTES


OUTPUT_CONTRACT = "full_html_deck.v1"
RENDER_MODE = "html_compiled.v1"
MANIFEST_CONTRACT_VERSION = "compiled-html-deck-manifest.v2"
LEGACY_COMPILER_VERSION = "instant-html-compiler.v8"
PREVIOUS_COMPILER_VERSION = "instant-html-compiler.v9"
ROOT_SCOPING_COMPILER_VERSION = "instant-html-compiler.v10"
FOREGROUND_GUARD_COMPILER_VERSION = "instant-html-compiler.v11"
REPLAY_COMPILER_VERSION = "instant-html-compiler.v12"
ALT_TEXT_COMPILER_VERSION = "instant-html-compiler.v13"
SEMANTIC_CONTRAST_COMPILER_VERSION = "instant-html-compiler.v14"
BANDED_BODY_COMPILER_VERSION = "instant-html-compiler.v15"
PREVIOUS_CURRENT_COMPILER_VERSION = "instant-html-compiler.v16"
DENSE_METRICS_COMPILER_VERSION = "instant-html-compiler.v17"
EDITORIAL_DENSITY_COMPILER_VERSION = "instant-html-compiler.v18"
VISUAL_SUBSTANCE_COMPILER_VERSION = "instant-html-compiler.v19"
PRESENTATION_PROOF_COMPILER_VERSION = "instant-html-compiler.v20"
READABLE_BODY_COMPILER_VERSION = "instant-html-compiler.v21"
OVERFLOW_SAFE_TEXT_COMPILER_VERSION = "instant-html-compiler.v22"
AUTO_GRID_BODY_COMPILER_VERSION = "instant-html-compiler.v23"
AUTO_GRID_ITEM_COMPILER_VERSION = "instant-html-compiler.v24"
SVG_TEXT_GROUNDING_COMPILER_VERSION = "instant-html-compiler.v25"
RECT_GEOMETRY_COMPILER_VERSION = "instant-html-compiler.v26"
VIEWPORT_GEOMETRY_COMPILER_VERSION = "instant-html-compiler.v27"
INTENT_BOUND_COMPILER_VERSION = "instant-html-compiler.v28"
FACT_DIAGNOSTICS_COMPILER_VERSION = "instant-html-compiler.v29"
SVG_STYLES_COMPILER_VERSION = "instant-html-compiler.v30"
SVG_TEXT_LAYOUT_COMPILER_VERSION = "instant-html-compiler.v31"
SEMANTIC_NUMERIC_COMPILER_VERSION = "instant-html-compiler.v32"
PREVIOUS_CURRENT_COMPILER_VERSION_BACKGROUND = "instant-html-compiler.v33"
COMPILER_VERSION = "instant-html-compiler.v34"
RENDER_AUTHORED_BACKGROUND_GUARD_CSS = (
    '[data-da-slide-root] [data-da-element-key^="headline-"]'
    '{font-size:64px!important;color:var(--da-ink,#0f172a)!important}'
    '[data-da-slide-root] [data-da-element-key^="body-"]'
    '{font-size:max(28px,1em)!important;color:var(--da-ink,#0f172a)!important}'
)
RENDER_TABLE_COHERENCE_GUARD_CSS = (
    '[data-da-slide-root] table'
    '{width:100%;border-collapse:collapse;background:var(--da-canvas,#fff)!important;color:var(--da-ink,#1f2937)}'
    '[data-da-slide-root] table thead'
    '{background:color-mix(in srgb,var(--da-accent,#4f46e5) 18%,var(--da-canvas,#fff))}'
    '[data-da-slide-root] table thead th'
    '{padding:12px 16px;font-weight:600;font-size:clamp(14px,1.2vw,18px);color:var(--da-ink,#1f2937);border-bottom:2px solid color-mix(in srgb,var(--da-accent,#4f46e5) 50%,var(--da-ink,#1f2937))}'
    '[data-da-slide-root] table tbody td'
    '{padding:10px 16px;font-size:clamp(13px,1.05vw,16px);border-bottom:1px solid color-mix(in srgb,var(--da-ink,#1f2937) 12%,transparent)}'
    '[data-da-slide-root] table tbody tr:nth-child(even)'
    '{background:color-mix(in srgb,var(--da-surface,var(--da-canvas,#fff)) 50%,var(--da-canvas,#fff))}'
)
MODERN_COMPILER_VERSIONS = frozenset({
    PREVIOUS_COMPILER_VERSION,
    ROOT_SCOPING_COMPILER_VERSION,
    FOREGROUND_GUARD_COMPILER_VERSION,
    REPLAY_COMPILER_VERSION,
    ALT_TEXT_COMPILER_VERSION,
    SEMANTIC_CONTRAST_COMPILER_VERSION,
    BANDED_BODY_COMPILER_VERSION,
    PREVIOUS_CURRENT_COMPILER_VERSION,
    DENSE_METRICS_COMPILER_VERSION,
    EDITORIAL_DENSITY_COMPILER_VERSION,
    VISUAL_SUBSTANCE_COMPILER_VERSION,
    PRESENTATION_PROOF_COMPILER_VERSION,
    READABLE_BODY_COMPILER_VERSION,
    OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
    AUTO_GRID_BODY_COMPILER_VERSION,
    AUTO_GRID_ITEM_COMPILER_VERSION,
    SVG_TEXT_GROUNDING_COMPILER_VERSION,
    RECT_GEOMETRY_COMPILER_VERSION,
    VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
    SVG_TEXT_LAYOUT_COMPILER_VERSION, SEMANTIC_NUMERIC_COMPILER_VERSION, COMPILER_VERSION,
})
SUPPORTED_COMPILER_VERSIONS = frozenset({LEGACY_COMPILER_VERSION, *MODERN_COMPILER_VERSIONS})
GROUNDING_BINDING_POLICY_VERSION = "grounding-exact-binding.v1"
CLAIM_NORMALIZATION_POLICY_VERSION = "grounding-exact-normalization.v1"
PARSER_VERSION = "html5lib.v1"
SANITIZER_POLICY_VERSION = "instant-html-sanitizer.v1"
RENDERER_VERSION = "html-slide-renderer.v2"
CANVAS = {"width": 1920, "height": 1080, "aspectRatio": "16:9"}
RENDER_SHELL_CSS = (
    "html,body{margin:0;width:1920px;height:1080px;overflow:hidden}"
    "body{background:#fff;color:#000}"
    "body>[data-da-slide-root]{box-sizing:border-box;width:1920px;height:1080px;overflow:hidden}"
)
RENDER_FOREGROUND_GUARD_CSS = (
    "[data-da-slide-root].cover .caption,[data-da-slide-root].cover .note{color:inherit}"
)
RENDER_ACCESSIBLE_SURFACE_GUARD_CSS = (
    "[data-da-slide-root] .bg-accent .badge,[data-da-slide-root].bg-accent .badge,"
    "[data-da-slide-root] .bg-secondary .badge,[data-da-slide-root].bg-secondary .badge"
    "{background:var(--color-panel);color:var(--color-ink)}"
    "[data-da-slide-root] .bg-accent .card,[data-da-slide-root].bg-accent .card,"
    "[data-da-slide-root] .bg-secondary .card,[data-da-slide-root].bg-secondary .card"
    "{background:var(--color-panel);color:var(--color-ink);padding:var(--space-6)}"
    "[data-da-slide-root] .bg-accent .card h1,[data-da-slide-root].bg-accent .card h1,"
    "[data-da-slide-root] .bg-accent .card h2,[data-da-slide-root].bg-accent .card h2,"
    "[data-da-slide-root] .bg-accent .card h3,[data-da-slide-root].bg-accent .card h3,"
    "[data-da-slide-root] .bg-accent .card p,[data-da-slide-root].bg-accent .card p,"
    "[data-da-slide-root] .bg-accent .card li,[data-da-slide-root].bg-accent .card li,"
    "[data-da-slide-root] .bg-secondary .card h1,[data-da-slide-root].bg-secondary .card h1,"
    "[data-da-slide-root] .bg-secondary .card h2,[data-da-slide-root].bg-secondary .card h2,"
    "[data-da-slide-root] .bg-secondary .card h3,[data-da-slide-root].bg-secondary .card h3,"
    "[data-da-slide-root] .bg-secondary .card p,[data-da-slide-root].bg-secondary .card p,"
    "[data-da-slide-root] .bg-secondary .card li,[data-da-slide-root].bg-secondary .card li"
    "{color:var(--color-ink)}"
    "[data-da-slide-root][data-layout-intent=\"grid-quad\"] .grid-3"
    "{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-6)}"
)
RENDER_BANDED_BODY_CONTRAST_GUARD_CSS = (
    '[data-da-slide-root] .band [data-da-element-key^="body-"]'
    '{color:var(--color-body,#0f172a)!important}'
)
RENDER_METRICS_DENSITY_GUARD_CSS = (
    "[data-da-slide-root] .layout-metrics"
    "{height:calc(1080px - (2 * var(--pad-outer)));min-height:0;align-items:stretch}"
    "[data-da-slide-root] .layout-metrics>.metric"
    "{box-sizing:border-box;min-height:0;max-height:100%;overflow:hidden}"
    "[data-da-slide-root] .layout-metrics .kpi li"
    "{font-size:clamp(13px,1.1vw,16px);line-height:1.35;padding:8px 10px}"
    "[data-da-slide-root] .layout-metrics img"
    "{display:block;width:100%;height:clamp(120px,18vh,190px);object-fit:contain}"
)
RENDER_EDITORIAL_DENSITY_GUARD_CSS = (
    '[data-da-slide-root][data-layout-intent="system-steps"] .section-inner'
    '{height:calc(1080px - (2 * var(--pad-outer)));min-height:0;align-content:start;gap:16px}'
    '[data-da-slide-root][data-layout-intent="system-steps"] .steps'
    '{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:14px!important;min-height:0}'
    '[data-da-slide-root][data-layout-intent="system-steps"] .steps li'
    '{font-size:clamp(12px,.82vw,15px)!important;line-height:1.2!important;padding:5px 7px!important}'
    '[data-da-slide-root][data-layout-intent="metrics-asymmetric"] .section-inner'
    '{height:calc(1080px - (2 * var(--pad-outer)));min-height:0;grid-template-columns:minmax(0,.8fr) minmax(0,1.6fr)!important;gap:18px!important;align-items:stretch}'
    '[data-da-slide-root][data-layout-intent="metrics-asymmetric"] h1,'
    '[data-da-slide-root][data-layout-intent="metrics-asymmetric"] h2'
    '{font-size:clamp(28px,2.6vw,44px)!important;line-height:1.05!important;overflow-wrap:anywhere}'
    '[data-da-slide-root][data-layout-intent="metrics-asymmetric"] li'
    '{font-size:clamp(12px,.82vw,15px)!important;line-height:1.2!important;padding:5px 7px!important}'
    '[data-da-slide-root][data-layout-intent="metrics-asymmetric"] img'
    '{display:block;max-width:100%;height:clamp(110px,16vh,170px)!important;object-fit:contain}'
    '[data-da-slide-root][data-layout-intent="evidence-wall"] .section-inner'
    '{height:calc(1080px - (2 * var(--pad-outer)));min-height:0;align-content:start;gap:14px}'
    '[data-da-slide-root][data-layout-intent="evidence-wall"] .wall'
    '{grid-template-columns:repeat(6,minmax(0,1fr))!important;gap:7px 10px!important;padding:12px!important;align-content:start}'
    '[data-da-slide-root][data-layout-intent="evidence-wall"] .wall li'
    '{font-size:clamp(11px,.72vw,14px)!important;line-height:1.15!important;padding:5px 6px!important;overflow-wrap:anywhere}'
)
RENDER_PRESENTATION_PROOF_GUARD_CSS = (
    '[data-da-slide-root] [data-da-element-key^="headline-"]'
    '{font-size:max(88px,1em)!important}'
    '[data-da-slide-root] [data-da-element-key^="body-"]'
    '{font-size:max(28px,1em)!important;color:#0f172a!important;background:#f8fafc!important}'
)
RENDER_READABLE_BODY_GUARD_CSS = (
    '[data-da-slide-root] [data-da-element-key^="body-"]'
    '{font-size:max(28px,1em)!important;color:#0f172a!important;background:#f8fafc!important}'
)
RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS = (
    '[data-da-slide-root] [data-da-element-key^="headline-"]'
    '{font-size:64px!important;color:#0f172a!important;background:#f8fafc!important}'
    + RENDER_READABLE_BODY_GUARD_CSS
)

# A source-specified grid placement outranks this zero-specificity fallback.
# Unplaced direct body copy must not collapse into one cell of a 12-column grid.
RENDER_AUTO_GRID_BODY_GUARD_CSS = (
    ':where([data-da-slide-root] .section-inner > p){grid-column:1 / -1}'
)

# Iteration 7 uses the same grid with .content and an unplaced marker div.
RENDER_AUTO_GRID_ITEM_GUARD_CSS = (
    ':where([data-da-slide-root] .section-inner > *,[data-da-slide-root] .content > *){grid-column:1 / -1}'
)

LEGACY_MAX_HTML_BYTES = 128_000
MAX_CSS_BYTES = 128_000
MAX_DOM_NODES = 10_000
MAX_SLIDES = 40
MAX_SVG_NODES = 2_000
MAX_ASSETS = 80

_HTML_NS = "{http://www.w3.org/1999/xhtml}"
_SVG_NS = "{http://www.w3.org/2000/svg}"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

_ALLOWED_HTML = {
    "html", "head", "meta", "title", "style", "body", "main", "section", "article", "div", "span", "p",
    "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i", "small", "sup", "sub", "br", "hr",
    "ul", "ol", "li", "dl", "dt", "dd", "figure", "figcaption", "img", "picture", "source", "table", "thead",
    "tbody", "tfoot", "tr", "th", "td", "caption", "blockquote", "code", "pre", "svg", "a",
}
_ALLOWED_SVG = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan", "defs",
    "linearGradient", "radialGradient", "stop", "clipPath", "mask", "use", "title", "desc",
}
_DROP_WITH_CONTENT = {
    "script", "iframe", "object", "embed", "form", "input", "button", "select", "textarea", "video", "audio",
    "portal", "template", "base", "link", "noscript", "frame", "frameset", "foreignObject", "animate", "set",
    "animateMotion", "animateTransform",
}
_SAFE_ATTRS = {
    "class", "id", "style", "role", "alt", "width", "height", "viewBox", "preserveAspectRatio", "d", "x", "y",
    "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "points", "fill", "stroke", "stroke-width",
    "opacity", "transform", "text-anchor", "font-size", "font-weight", "colspan", "rowspan", "scope", "lang",
    "aria-label", "aria-hidden", "aria-describedby", "aria-labelledby", "href", "src",
}
_SAFE_DATA_ATTRS = {
    "data-slot", "data-slot-title", "data-slot-slug", "data-slide-id", "data-slide-purpose", "data-layout-intent",
    "data-composition-family", "data-visual-role", "data-plan-slide-id", "data-evidence-ids",
    "data-calculation-ids", "data-visual-primitive", "data-visual-asset-ref",
    "data-source-slide-ids", "data-source-slide-refs", "data-source-omission-ids", "data-variant", "data-role", "data-source-refs", "data-bind",
    "data-component", "data-chart-kind", "data-data-ref", "data-asset-ref", "data-da-element-key",
    "data-da-persisted-element-id", "data-da-slide-root", "data-da-background",
}
_CHROME_MARKERS = {"deck-nav", "navigation", "paginator", "pagination", "theme-toggle", "mode-toggle", "fullscreen"}
_EDITABLE_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "img", "table", "figure", "svg"}


class HtmlDeckCompileError(ValueError):
    def __init__(self, code: str, message: str, *, issues: list[dict[str, Any]] | None = None) -> None:
        self.code = code
        self.issues = issues or [{"severity": "error", "category": "structure", "code": code, "message": message, "blocking": True}]
        super().__init__(message)


_NUMERIC_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,.]*(?:%|[kKmMbB])?")
_YEAR_TOKEN = re.compile(r"\b20\d{2}\b")
_CLAIM_STOPWORDS = {
    "the", "and", "for", "from", "with", "into", "over", "under", "than", "this", "that",
    "was", "were", "are", "has", "have", "had", "our", "their", "per", "year", "years",
    "usd", "gbp", "eur", "million", "billion", "thousand", "actual", "achieved", "reported",
    "forecast", "projected", "projection", "target", "scenario", "planned", "grew", "growth", "reached",
}
_ACTUAL_STATUS = re.compile(r"\b(?:actual|achieved|reported|realized)\b", re.IGNORECASE)
_FORECAST_STATUS = re.compile(r"\b(?:forecast|projected|projection|target|scenario|planned)\b", re.IGNORECASE)


def _claim_status(value: str) -> str | None:
    if _ACTUAL_STATUS.search(value):
        return "actual"
    if _FORECAST_STATUS.search(value):
        return "forecast"
    return None


def validate_semantic_numeric_claim(text: str, referenced_texts: Iterable[str]) -> None:
    """Reject numeric substitutions hidden behind a valid but wrong fact ID.

    The compiler already validates ID existence. This additional current-version
    check validates the numeric token and its nearby period/category semantics
    against the referenced canonical fact text. It remains generic: fixture
    values and metric names never enter production code.
    """
    claim = " ".join(str(text or "").split())
    sources = [" ".join(str(value or "").split()) for value in referenced_texts if str(value or "").strip()]
    numbers = _NUMERIC_TOKEN.findall(claim)
    if not numbers or not sources:
        return
    combined = " \n ".join(sources)
    for number in numbers:
        if number not in combined:
            raise HtmlDeckCompileError(
                "grounded_numeric_value_mismatch",
                "A numeric claim is not present in its referenced canonical evidence.",
            )
        matching_sources = [source for source in sources if number in source]
        claimed_status = _claim_status(claim)
        if claimed_status:
            local_statuses = {
                status for source in matching_sources
                for status in [_claim_status(source)]
                if status
            }
            if local_statuses and claimed_status not in local_statuses:
                raise HtmlDeckCompileError(
                    "grounded_numeric_status_mismatch",
                    "A numeric claim changed actual-versus-forecast status in its referenced evidence.",
                )
        # Years carry especially important period semantics. A stated year and
        # value must occur as one local claim in the same referenced evidence,
        # in either natural-language order.
        if _YEAR_TOKEN.fullmatch(number):
            continue
        years = _YEAR_TOKEN.findall(claim)
        for year in years:
            local_pair = re.compile(
                rf"(?:\b{re.escape(year)}\b[^\d]{{0,36}}{re.escape(number)}|"
                rf"{re.escape(number)}[^\d]{{0,36}}\b{re.escape(year)}\b)",
                re.IGNORECASE,
            )
            period_bound = any(
                (len(set(_YEAR_TOKEN.findall(source))) == 1 and year in source)
                or bool(local_pair.search(source))
                for source in matching_sources
            )
            if not period_bound:
                raise HtmlDeckCompileError(
                    "grounded_numeric_period_mismatch",
                    "A numeric claim changed the period/value association in its referenced evidence.",
                )
        claim_position = claim.find(number)
        nearby_claim = claim[max(0, claim_position - 28):claim_position + len(number) + 28]
        word_matches = list(re.finditer(r"[A-Za-z][A-Za-z-]{2,}", nearby_claim))
        words = [
            match.group(0).lower()
            for match in sorted(
                word_matches,
                key=lambda match: abs((match.start() + match.end()) / 2 - (claim_position - max(0, claim_position - 28))),
            )
            if match.group(0).lower() not in _CLAIM_STOPWORDS
        ]
        if words:
            label = words[0]
            locally_bound = re.compile(
                rf"(?:\b{re.escape(label)}\b[^\d]{{0,32}}{re.escape(number)}|"
                rf"{re.escape(number)}[^\d]{{0,32}}\b{re.escape(label)}\b)",
                re.IGNORECASE,
            )
            shared_heading = re.compile(rf"^\s*[^:]*\b{re.escape(label)}\b[^:]*:", re.IGNORECASE)
            if not any(locally_bound.search(source) or shared_heading.search(source) for source in matching_sources):
                raise HtmlDeckCompileError(
                    "grounded_numeric_category_mismatch",
                    "A numeric claim changed the category/value association in its referenced evidence.",
                )


def _numeric_semantic_observations(text: str) -> list[tuple[tuple[str, str, str], str]]:
    """Extract conservative cross-slide identities for material numeric claims.

    Only claims with an explicit period and a nearby category word participate;
    this avoids treating unrelated structural counts as contradictions.
    """
    claim = " ".join(str(text or "").split())
    years = _YEAR_TOKEN.findall(claim)
    if not years:
        return []
    status = _claim_status(claim) or "unspecified"
    observations = []
    for match in _NUMERIC_TOKEN.finditer(claim):
        value = match.group(0)
        if _YEAR_TOKEN.fullmatch(value):
            continue
        nearby = claim[max(0, match.start() - 36):match.end() + 36]
        labels = [
            word.lower() for word in re.findall(r"[A-Za-z][A-Za-z-]{2,}", nearby)
            if word.lower() not in _CLAIM_STOPWORDS
        ]
        if labels:
            observations.append(((labels[0], years[0], status), value))
    return observations


@dataclass(frozen=True)
class CompiledHtmlDeck:
    sanitized_html: str
    safe_slide_documents: tuple[str, ...]
    manifest: dict[str, Any]
    issues: tuple[dict[str, Any], ...]
    raw_sha256: str
    sanitized_sha256: str
    compilation_hash: str
    compiler_version: str
    max_html_bytes: int


def whole_deck_html_ceiling(
    *,
    compiler_version: str = COMPILER_VERSION,
    bound_max_html_bytes: int | None = None,
) -> int:
    """Return the configured whole-deck ceiling under an explicit compiler policy.

    The returned value is the common raw-input and post-sanitization ceiling.
    V8 remains pinned to its historical 128,000-byte behavior for immutable
    checkpoints and baselines. A lower current deployment ceiling still narrows
    either policy fail-closed.
    """

    configured = int(settings.instant_html_whole_deck_max_bytes)
    if compiler_version == LEGACY_COMPILER_VERSION:
        if bound_max_html_bytes is not None:
            raise HtmlDeckCompileError(
                "compiler_policy_invalid",
                "Legacy compiler policy cannot carry a mutable whole-deck ceiling.",
            )
        return min(configured, LEGACY_MAX_HTML_BYTES)
    if compiler_version in MODERN_COMPILER_VERSIONS:
        if bound_max_html_bytes is None:
            return configured
        if (
            isinstance(bound_max_html_bytes, bool)
            or not isinstance(bound_max_html_bytes, int)
            or bound_max_html_bytes <= 0
            or bound_max_html_bytes > configured
        ):
            raise HtmlDeckCompileError(
                "compiler_policy_invalid",
                "Bound whole-deck HTML ceiling exceeds the current fail-closed configuration.",
            )
        return bound_max_html_bytes
    raise HtmlDeckCompileError(
        "compiler_version_unsupported",
        "Deck HTML references an unsupported deterministic compiler version.",
    )


def _local_name(tag: object) -> str:
    """Return the namespace-local tag name, tolerating non-element nodes.

    ElementTree represents comments and processing instructions as nodes whose
    ``tag`` is a callable (``ET.Comment`` / ``ET.ProcessingInstruction``)
    instead of a string. Provider HTML may legitimately contain comments, so
    callers must not crash on them; a non-string tag has no local name.
    """
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _sha(value: str | bytes) -> str:
    return sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _strip_provider_fence(raw: str) -> str:
    value = raw.strip().lstrip("\ufeff")
    if value.startswith("```"):
        first_newline = value.find("\n")
        if first_newline < 0 or not value.endswith("```"):
            raise HtmlDeckCompileError("provider_wrapper_invalid", "Provider output contains an incomplete code fence.")
        value = value[first_newline + 1 : -3].strip()
    return value


def _parse_document(raw: str) -> ET.Element:
    try:
        parsed = html5lib.parse(raw, treebuilder="etree", namespaceHTMLElements=True)
    except Exception as exc:
        raise HtmlDeckCompileError("html_parse_failed", "Provider output could not be parsed as HTML5.") from exc
    if parsed is None:
        raise HtmlDeckCompileError("html_parse_failed", "Provider output did not contain an HTML5 document.")
    return parsed


def _inject_rendered_visual_assets(
    root: ET.Element,
    rendered_visual_assets: dict[str, dict[str, Any]],
) -> list[str]:
    """Resolve compiler-owned chart/diagram placeholders before sanitization.

    Provider output may select a validated asset ID, but the application owns
    the SVG bytes and verifies their recorded digest. The inserted tree then
    passes through the normal SVG allowlist and geometry checks.
    """
    resolved: list[str] = []
    for element in root.iter():
        asset_id = element.attrib.get("data-visual-asset-ref")
        if asset_id is None:
            continue
        asset = rendered_visual_assets.get(asset_id)
        if asset is None:
            raise HtmlDeckCompileError(
                "unknown_visual_asset_reference",
                "Deck HTML references an unresolved visual asset.",
            )
        if _local_name(element.tag) not in {"figure", "div"}:
            raise HtmlDeckCompileError(
                "visual_asset_target_invalid",
                "Rendered visual assets may only bind to figure or div primitives.",
            )
        data_url = asset.get("data_url", "")
        prefix = "data:image/svg+xml;base64,"
        if not data_url.startswith(prefix):
            raise HtmlDeckCompileError(
                "visual_asset_payload_invalid",
                "Rendered visual assets must use the canonical SVG data primitive.",
            )
        try:
            payload = base64.b64decode(data_url[len(prefix):], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HtmlDeckCompileError(
                "visual_asset_payload_invalid",
                "Rendered visual asset bytes are malformed.",
            ) from exc
        if _sha(payload) != asset.get("content_sha256"):
            raise HtmlDeckCompileError(
                "visual_asset_digest_mismatch",
                "Rendered visual asset bytes do not match their durable digest.",
            )
        try:
            svg = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise HtmlDeckCompileError(
                "visual_asset_svg_invalid",
                "Rendered visual asset SVG could not be parsed.",
            ) from exc
        if _local_name(svg.tag) != "svg":
            raise HtmlDeckCompileError(
                "visual_asset_svg_invalid",
                "Rendered visual asset payload must contain one SVG root.",
            )
        evidence_ids = [
            str(value) for value in asset.get("evidence_ids", [])
            if isinstance(value, str) and value.strip()
        ]
        if evidence_ids:
            for node in svg.iter():
                if _local_name(node.tag) in {"text", "tspan"} and not node.attrib.get("data-source-refs"):
                    node.attrib["data-source-refs"] = " ".join(evidence_ids)
        for child in list(element):
            element.remove(child)
        element.text = None
        element.append(svg)
        resolved.append(asset_id)
    return resolved


def _safe_url(value: str, *, allow_data_images: bool, allow_fragment: bool = False) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    if allow_fragment and re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_.:-]{0,127}", candidate):
        return True
    lowered = candidate.lower()
    if allow_data_images and lowered.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")):
        return len(candidate) <= 1_500_000
    # Relative and network URLs are never provider-controlled. Approved assets
    # are resolved to an immutable data primitive before this check.
    return False


def _tokens_contain_unsafe_url(tokens: Iterable[Any], *, allow_data_images: bool) -> bool:
    for token in tokens:
        if token.type == "url" and not _safe_url(token.value, allow_data_images=allow_data_images):
            return True
        if token.type == "function":
            if token.lower_name == "url":
                target = tinycss2.serialize(token.arguments).strip().strip("\"'")
                if not _safe_url(target, allow_data_images=allow_data_images):
                    return True
            if _tokens_contain_unsafe_url(token.arguments, allow_data_images=allow_data_images):
                return True
        content = getattr(token, "content", None)
        if content and _tokens_contain_unsafe_url(content, allow_data_images=allow_data_images):
            return True
    return False


def _sanitize_declarations(value: str, *, allow_data_images: bool = False) -> str:
    declarations = tinycss2.parse_declaration_list(value, skip_comments=True, skip_whitespace=True)
    safe: list[Any] = []
    for declaration in declarations:
        if declaration.type != "declaration" or declaration.lower_name in {"behavior", "-moz-binding"}:
            continue
        serialized = tinycss2.serialize(declaration.value).strip()
        lowered = serialized.lower()
        if "expression(" in lowered:
            continue
        if not _tokens_contain_unsafe_url(declaration.value, allow_data_images=allow_data_images):
            safe.append(declaration)
    return tinycss2.serialize(safe).strip()


def _opaque_css_rgb(value: str) -> tuple[int, int, int] | None:
    candidate = value.strip()
    short_hex = re.fullmatch(r"#([0-9a-fA-F]{3})", candidate)
    if short_hex:
        return tuple(int(channel * 2, 16) for channel in short_hex.group(1))  # type: ignore[return-value]
    full_hex = re.fullmatch(r"#([0-9a-fA-F]{6})", candidate)
    if full_hex:
        raw = full_hex.group(1)
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    rgb = re.fullmatch(
        r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)",
        candidate,
        flags=re.IGNORECASE,
    )
    if not rgb:
        return None
    channels = tuple(int(value) for value in rgb.groups())
    return channels if all(0 <= channel <= 255 for channel in channels) else None  # type: ignore[return-value]


def _css_contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    def luminance(color: tuple[int, int, int]) -> float:
        channels = []
        for value in color:
            normalized = value / 255
            channels.append(
                normalized / 12.92
                if normalized <= 0.03928
                else ((normalized + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    first_luminance = luminance(first)
    second_luminance = luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (
        min(first_luminance, second_luminance) + 0.05
    )


def _repair_semantic_foreground_tokens(css: str) -> str:
    """Use an existing readable deck token when a semantic text token is unsafe.

    The repair is deliberately narrow: it never changes a background or invents
    a colour. It only rewrites ``color: var(--token)`` when the provider's own
    opaque root tokens prove that token fails normal-text contrast against one
    of the deck's canonical surfaces and another supplied foreground token is
    safe against every canonical surface.
    """

    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    token_values: dict[str, tuple[int, int, int]] = {}
    for rule in rules:
        if rule.type != "qualified-rule":
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        if "[data-da-slide-root]" not in selector:
            continue
        for declaration in tinycss2.parse_declaration_list(
            rule.content, skip_comments=True, skip_whitespace=True
        ):
            if declaration.type != "declaration" or not declaration.name.startswith("--"):
                continue
            parsed = _opaque_css_rgb(tinycss2.serialize(declaration.value).strip())
            if parsed is not None:
                token_values[declaration.name.lower()] = parsed

    surface_tokens = {
        name: color
        for name, color in token_values.items()
        if any(marker in name for marker in ("surface", "background", "panel", "paper", "canvas", "card"))
    }
    if not surface_tokens:
        return css
    foreground_tokens = {
        name: color
        for name, color in token_values.items()
        if any(marker in name for marker in ("heading", "body", "text", "ink", "foreground", "accent", "muted"))
    }
    readable = {
        name
        for name, color in foreground_tokens.items()
        if all(_css_contrast_ratio(color, surface) >= 4.5 for surface in surface_tokens.values())
    }
    if not readable:
        return css
    preferred_markers = ("heading", "body", "text", "ink", "foreground", "accent", "muted")
    replacement = min(
        readable,
        key=lambda name: (
            next((index for index, marker in enumerate(preferred_markers) if marker in name), len(preferred_markers)),
            name,
        ),
    )
    unsafe = set(foreground_tokens) - readable
    if not unsafe:
        return css

    exact_var = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)", re.IGNORECASE)
    for rule in rules:
        if rule.type != "qualified-rule":
            continue
        declarations = tinycss2.parse_declaration_list(
            rule.content, skip_comments=True, skip_whitespace=True
        )
        changed = False
        for declaration in declarations:
            if declaration.type != "declaration" or declaration.lower_name != "color":
                continue
            serialized = tinycss2.serialize(declaration.value).strip()
            match = exact_var.fullmatch(serialized)
            if match and match.group(1).lower() in unsafe:
                declaration.value = tinycss2.parse_component_value_list(f"var({replacement})")
                changed = True
        if changed:
            rule.content = tinycss2.parse_component_value_list(tinycss2.serialize(declarations))
    return tinycss2.serialize(rules).strip()


def _scope_prelude(
    tokens: list[Any],
    root_selector: str,
    *,
    preserve_root_class_selectors: bool,
) -> list[Any]:
    selector_groups: list[list[Any]] = [[]]
    for token in tokens:
        if token.type == "literal" and token.value == ",":
            selector_groups.append([])
        else:
            selector_groups[-1].append(token)
    scoped: list[str] = []
    for group in selector_groups:
        selector = tinycss2.serialize(group).strip()
        if not selector:
            continue
        if selector in {"html", "body", ":root"}:
            scoped.append(root_selector)
        elif selector.startswith(root_selector):
            scoped.append(selector)
        else:
            scoped.append(f"{root_selector} {selector}")
            # Provider sections become the render-document root. Preserve
            # class/id/attribute/pseudo selectors that target the section
            # itself as well as descendants. V8/V9 retain their exact
            # historical descendant-only scoping for immutable replay.
            if preserve_root_class_selectors and selector[0] in ".#[":
                scoped.append(f"{root_selector}{selector}")
    return tinycss2.parse_component_value_list(", ".join(scoped))


def restore_slide_root_css(css: str) -> str:
    """Keep section selectors applicable after a section becomes an isolated root.

    Retain sanitized designer declarations and remove the application-owned
    typography override. Add aliases only to already scoped section selectors.
    This also supports saved advisory artifacts without changing stored bytes.
    """
    css = css.replace(RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS, "")
    css = css.replace(RENDER_AUTHORED_BACKGROUND_GUARD_CSS, "")
    css = css.replace(RENDER_TABLE_COHERENCE_GUARD_CSS, "")
    rules = tinycss2.parse_stylesheet(css, skip_comments=False, skip_whitespace=False)
    for rule in rules:
        if rule.type != 'qualified-rule':
            continue
        selectors = tinycss2.serialize(rule.prelude).strip().split(',')
        aliases = []
        for selector in selectors:
            match = re.fullmatch(r'\[data-da-slide-root\]\s+section((?:[.#][\w-]+)*)', selector.strip())
            if match:
                alias = 'section[data-da-slide-root]' + match.group(1)
                if alias not in {item.strip() for item in selectors}:
                    aliases.append(alias)
        if aliases:
            rule.prelude = tinycss2.parse_component_value_list(', '.join(selectors + aliases))
    return tinycss2.serialize(rules)


def restore_advisory_document_root_css(document: str) -> str:
    """Derive delivery CSS from a verified saved artifact without changing storage."""
    root = _parse_document(document)
    for node in root.iter():
        if _local_name(node.tag) == 'style' and node.text:
            node.text = restore_slide_root_css(node.text)
    return '<!doctype html>\n' + _serialize(root)


def sanitize_and_scope_css(
    css: str,
    *,
    root_selector: str = "[data-da-slide-root]",
    compiler_version: str = COMPILER_VERSION,
) -> str:
    if len(css.encode("utf-8")) > MAX_CSS_BYTES:
        raise HtmlDeckCompileError("css_budget_exceeded", "Deck CSS exceeds the configured byte budget.")
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    safe_rules: list[Any] = []
    for rule in rules:
        if rule.type == "error":
            raise HtmlDeckCompileError("css_parse_failed", "Deck CSS is malformed.")
        if rule.type == "at-rule":
            if rule.lower_at_keyword in {"import", "font-face", "namespace", "document"}:
                continue
            if rule.lower_at_keyword not in {"media", "supports"} or rule.content is None:
                continue
            nested = tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True)
            for nested_rule in nested:
                if nested_rule.type == "qualified-rule":
                    nested_rule.prelude = _scope_prelude(
                        nested_rule.prelude,
                        root_selector,
                        preserve_root_class_selectors=compiler_version in {
                            ROOT_SCOPING_COMPILER_VERSION,
                            FOREGROUND_GUARD_COMPILER_VERSION,
                            REPLAY_COMPILER_VERSION,
                            ALT_TEXT_COMPILER_VERSION,
                            PREVIOUS_CURRENT_COMPILER_VERSION,
                            DENSE_METRICS_COMPILER_VERSION,
                            EDITORIAL_DENSITY_COMPILER_VERSION,
                            VISUAL_SUBSTANCE_COMPILER_VERSION,
                            PRESENTATION_PROOF_COMPILER_VERSION,
                            READABLE_BODY_COMPILER_VERSION,
                            OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
                            AUTO_GRID_BODY_COMPILER_VERSION,
                            AUTO_GRID_ITEM_COMPILER_VERSION,
                            SVG_TEXT_GROUNDING_COMPILER_VERSION,
                            RECT_GEOMETRY_COMPILER_VERSION,
                            VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
                            SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
                        },
                    )
                    declarations = _sanitize_declarations(tinycss2.serialize(nested_rule.content))
                    nested_rule.content = tinycss2.parse_component_value_list(declarations)
            rule.content = tinycss2.parse_component_value_list(tinycss2.serialize(nested))
            safe_rules.append(rule)
            continue
        if rule.type != "qualified-rule":
            continue
        rule.prelude = _scope_prelude(
            rule.prelude,
            root_selector,
            preserve_root_class_selectors=compiler_version in {
                ROOT_SCOPING_COMPILER_VERSION,
                FOREGROUND_GUARD_COMPILER_VERSION,
                REPLAY_COMPILER_VERSION,
                ALT_TEXT_COMPILER_VERSION,
                PREVIOUS_CURRENT_COMPILER_VERSION,
                DENSE_METRICS_COMPILER_VERSION,
                EDITORIAL_DENSITY_COMPILER_VERSION,
                VISUAL_SUBSTANCE_COMPILER_VERSION,
                PRESENTATION_PROOF_COMPILER_VERSION,
                READABLE_BODY_COMPILER_VERSION,
                OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
                AUTO_GRID_BODY_COMPILER_VERSION,
                AUTO_GRID_ITEM_COMPILER_VERSION,
                SVG_TEXT_GROUNDING_COMPILER_VERSION,
                RECT_GEOMETRY_COMPILER_VERSION,
                VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
                SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
            },
        )
        declarations = _sanitize_declarations(tinycss2.serialize(rule.content))
        rule.content = tinycss2.parse_component_value_list(declarations)
        safe_rules.append(rule)
    sanitized = tinycss2.serialize(safe_rules).strip()
    if compiler_version in {
        FOREGROUND_GUARD_COMPILER_VERSION,
        REPLAY_COMPILER_VERSION,
        ALT_TEXT_COMPILER_VERSION,
        PREVIOUS_CURRENT_COMPILER_VERSION,
        DENSE_METRICS_COMPILER_VERSION,
        EDITORIAL_DENSITY_COMPILER_VERSION,
        VISUAL_SUBSTANCE_COMPILER_VERSION,
        PRESENTATION_PROOF_COMPILER_VERSION,
        READABLE_BODY_COMPILER_VERSION,
        OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
        AUTO_GRID_BODY_COMPILER_VERSION,
        AUTO_GRID_ITEM_COMPILER_VERSION,
        SVG_TEXT_GROUNDING_COMPILER_VERSION,
        RECT_GEOMETRY_COMPILER_VERSION,
        VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
        SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
    }:
        sanitized = f"{sanitized}{RENDER_FOREGROUND_GUARD_CSS}"
    if compiler_version in {
        ALT_TEXT_COMPILER_VERSION,
        SEMANTIC_CONTRAST_COMPILER_VERSION,
        PREVIOUS_CURRENT_COMPILER_VERSION,
        DENSE_METRICS_COMPILER_VERSION,
        EDITORIAL_DENSITY_COMPILER_VERSION,
        VISUAL_SUBSTANCE_COMPILER_VERSION,
        PRESENTATION_PROOF_COMPILER_VERSION,
        READABLE_BODY_COMPILER_VERSION,
        OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
        AUTO_GRID_BODY_COMPILER_VERSION,
        AUTO_GRID_ITEM_COMPILER_VERSION,
        SVG_TEXT_GROUNDING_COMPILER_VERSION,
        RECT_GEOMETRY_COMPILER_VERSION,
        VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
        SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
    }:
        sanitized = f"{sanitized}{RENDER_ACCESSIBLE_SURFACE_GUARD_CSS}"
    if compiler_version in {
        SEMANTIC_CONTRAST_COMPILER_VERSION,
        BANDED_BODY_COMPILER_VERSION,
        PREVIOUS_CURRENT_COMPILER_VERSION,
        DENSE_METRICS_COMPILER_VERSION,
        EDITORIAL_DENSITY_COMPILER_VERSION,
        VISUAL_SUBSTANCE_COMPILER_VERSION,
        PRESENTATION_PROOF_COMPILER_VERSION,
        READABLE_BODY_COMPILER_VERSION,
        OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
        AUTO_GRID_BODY_COMPILER_VERSION,
        AUTO_GRID_ITEM_COMPILER_VERSION,
        SVG_TEXT_GROUNDING_COMPILER_VERSION,
        RECT_GEOMETRY_COMPILER_VERSION,
        VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
        SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
    }:
        sanitized = _repair_semantic_foreground_tokens(sanitized)
    if compiler_version == BANDED_BODY_COMPILER_VERSION:
        sanitized = f"{sanitized}{RENDER_BANDED_BODY_CONTRAST_GUARD_CSS}"
    if compiler_version in {DENSE_METRICS_COMPILER_VERSION, EDITORIAL_DENSITY_COMPILER_VERSION}:
        sanitized = f"{sanitized}{RENDER_METRICS_DENSITY_GUARD_CSS}"
    if compiler_version == EDITORIAL_DENSITY_COMPILER_VERSION:
        sanitized = f"{sanitized}{RENDER_EDITORIAL_DENSITY_GUARD_CSS}"
    if compiler_version == PRESENTATION_PROOF_COMPILER_VERSION:
        sanitized = f"{sanitized}{RENDER_PRESENTATION_PROOF_GUARD_CSS}"
    if compiler_version == READABLE_BODY_COMPILER_VERSION:
        sanitized = f"{sanitized}{RENDER_READABLE_BODY_GUARD_CSS}"
    if compiler_version in {OVERFLOW_SAFE_TEXT_COMPILER_VERSION, AUTO_GRID_BODY_COMPILER_VERSION, AUTO_GRID_ITEM_COMPILER_VERSION, SVG_TEXT_GROUNDING_COMPILER_VERSION, RECT_GEOMETRY_COMPILER_VERSION, VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, PREVIOUS_CURRENT_COMPILER_VERSION_BACKGROUND}:
        sanitized = f"{sanitized}{RENDER_OVERFLOW_SAFE_TEXT_GUARD_CSS}"
    if compiler_version == COMPILER_VERSION:
        sanitized = f"{sanitized}{RENDER_AUTHORED_BACKGROUND_GUARD_CSS}{RENDER_TABLE_COHERENCE_GUARD_CSS}"
    if compiler_version in {AUTO_GRID_BODY_COMPILER_VERSION, AUTO_GRID_ITEM_COMPILER_VERSION, SVG_TEXT_GROUNDING_COMPILER_VERSION, RECT_GEOMETRY_COMPILER_VERSION, VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        sanitized = f"{sanitized}{RENDER_AUTO_GRID_BODY_GUARD_CSS}"
    if compiler_version in {AUTO_GRID_ITEM_COMPILER_VERSION, SVG_TEXT_GROUNDING_COMPILER_VERSION, RECT_GEOMETRY_COMPILER_VERSION, VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        sanitized = f"{sanitized}{RENDER_AUTO_GRID_ITEM_GUARD_CSS}"
    return sanitized


def _remove_node(parent: ET.Element, child: ET.Element, *, keep_tail: bool = True) -> None:
    if keep_tail and child.tail:
        previous = list(parent).index(child) - 1
        if previous >= 0:
            sibling = list(parent)[previous]
            sibling.tail = (sibling.tail or "") + child.tail
        else:
            parent.text = (parent.text or "") + child.tail
    parent.remove(child)


def _sanitize_tree(
    root: ET.Element,
    approved_asset_references: dict[str, str],
    approved_asset_alt_texts: dict[str, str],
    *,
    compiler_version: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    css_blocks: list[str] = []
    issues: list[dict[str, Any]] = []
    node_count = 0
    svg_count = 0
    asset_count = 0
    for parent in list(root.iter()):
        for child in list(parent):
            if not isinstance(child.tag, str):
                # Comments and processing instructions carry no visual content
                # and are not valid slide nodes; drop them entirely.
                _remove_node(parent, child)
                continue
            local = _local_name(child.tag)
            if local in _DROP_WITH_CONTENT:
                _remove_node(parent, child)
                issues.append({"severity": "warning", "category": "security", "code": "active_content_removed", "message": f"Removed prohibited {local} content.", "blocking": False})
                continue
            classes = set((child.attrib.get("class") or "").split())
            if classes & _CHROME_MARKERS or child.attrib.get("data-role") in _CHROME_MARKERS:
                _remove_node(parent, child)
    for element in root.iter():
        node_count += 1
        local = _local_name(element.tag)
        in_svg = isinstance(element.tag, str) and element.tag.startswith(_SVG_NS)
        if in_svg:
            if compiler_version == RECT_GEOMETRY_COMPILER_VERSION and local == "rect":
                # SVG attributes are lengths, not executable arithmetic. Invalid
                # coordinates silently lose bars in Chromium; expose the actual
                # structural failure to the bounded compiler-feedback repair.
                for dimension in ("x", "y", "width", "height", "rx", "ry"):
                    value = element.attrib.get(dimension)
                    if value is None:
                        continue
                    length = re.fullmatch(
                        r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:px|em|ex|ch|rem|cm|mm|Q|in|pt|pc|%)?\s*",
                        value,
                    )
                    if length is None or (dimension in {"width", "height", "rx", "ry"} and float(length[1]) < 0):
                        raise HtmlDeckCompileError(
                            "svg_rect_geometry_invalid",
                            f"SVG rect {dimension} must be a computed valid length; dimensions must be nonnegative. "
                            "Do not place arithmetic expressions in SVG attributes. For an upward bar, use "
                            "positive height and y = baseline minus height, with both numbers precomputed.",
                        )
            svg_count += 1
            if local == "style" and compiler_version in {SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
                # Collect before clearing the unsupported SVG node. These bytes
                # still pass through sanitize_and_scope_css with all other CSS;
                # the raw style element never reaches the rendered document.
                # Historical compiler versions retain their original output.
                css_blocks.append(element.text or "")
            if local not in _ALLOWED_SVG:
                element.clear()
                element.tag = _SVG_NS + "g"
        elif local not in _ALLOWED_HTML:
            element.clear()
            element.tag = _HTML_NS + "div"
        if local == "style":
            css_blocks.append(element.text or "")
            element.text = ""
        for name, value in list(element.attrib.items()):
            attr = _local_name(name)
            lowered = attr.lower()
            if lowered.startswith("on") or lowered in {"srcdoc", "formaction", "contenteditable", "autofocus", "http-equiv"}:
                del element.attrib[name]
                continue
            if attr.startswith("data-da-"):
                # Provider-supplied compiler identities are never authoritative.
                del element.attrib[name]
                continue
            if in_svg and local in {"text", "tspan"} and attr in {"dx", "dy"} and compiler_version == COMPILER_VERSION:
                # Relative offsets are inert SVG geometry. Dropping dy stacks
                # otherwise valid multi-line labels on the same baseline.
                lengths = re.split(r"[\s,]+", value.strip())
                if not 1 <= len(lengths) <= 64 or any(
                    not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:px|em|ex|rem|pt|pc|cm|mm|in|%)?", length)
                    for length in lengths
                ):
                    raise HtmlDeckCompileError("svg_text_offset_invalid", "SVG text offsets must be literal lengths.")
                continue
            if attr not in _SAFE_ATTRS and attr not in _SAFE_DATA_ATTRS:
                del element.attrib[name]
                continue
            if attr == "style":
                sanitized = _sanitize_declarations(value, allow_data_images=False)
                if sanitized:
                    element.attrib[name] = sanitized
                else:
                    del element.attrib[name]
            elif attr in {"href", "src"} or name == _XLINK_HREF:
                if not _safe_url(value, allow_data_images=local in {"img", "source"}, allow_fragment=in_svg):
                    del element.attrib[name]
            elif attr == "data-asset-ref":
                asset_id = value.removeprefix("approved:")
                asset_count += 1
                resolved = approved_asset_references.get(asset_id)
                if resolved is None or not _safe_url(resolved, allow_data_images=True):
                    raise HtmlDeckCompileError("unknown_asset_reference", "Deck HTML references an unresolved or unapproved asset.")
                if local not in {"img", "source"}:
                    raise HtmlDeckCompileError("asset_target_invalid", "Approved assets may only bind to image primitives.")
                element.attrib["src"] = resolved
                element.attrib["data-asset-ref"] = f"approved:{asset_id}"
                if local == "img" and compiler_version in {
                    ALT_TEXT_COMPILER_VERSION,
                    PREVIOUS_CURRENT_COMPILER_VERSION,
                    DENSE_METRICS_COMPILER_VERSION,
                    EDITORIAL_DENSITY_COMPILER_VERSION,
                    VISUAL_SUBSTANCE_COMPILER_VERSION,
                    PRESENTATION_PROOF_COMPILER_VERSION,
                    READABLE_BODY_COMPILER_VERSION,
                    OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
                    AUTO_GRID_BODY_COMPILER_VERSION,
                    AUTO_GRID_ITEM_COMPILER_VERSION,
                    SVG_TEXT_GROUNDING_COMPILER_VERSION,
                    RECT_GEOMETRY_COMPILER_VERSION,
                    VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
                    SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
                } and "alt" not in element.attrib:
                    alt_text = " ".join(str(approved_asset_alt_texts.get(asset_id) or "").split())
                    if alt_text:
                        element.attrib["alt"] = alt_text[:512]
    if node_count > MAX_DOM_NODES:
        raise HtmlDeckCompileError("dom_budget_exceeded", "Deck DOM exceeds the configured node budget.")
    if svg_count > MAX_SVG_NODES:
        raise HtmlDeckCompileError("svg_budget_exceeded", "Deck SVG exceeds the configured node budget.")
    if asset_count > MAX_ASSETS:
        raise HtmlDeckCompileError("asset_budget_exceeded", "Deck exceeds the configured asset budget.")
    if compiler_version in {VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        geometry_failures = _svg_rect_geometry_failures(root)
        if geometry_failures:
            raise HtmlDeckCompileError(geometry_failures[0]["code"], geometry_failures[0]["message"], issues=geometry_failures[:128])
    return css_blocks, issues



def _svg_rect_geometry_failures(root: ET.Element) -> list[dict[str, Any]]:
    """Batch observed invalid lengths and clipped evidence boxes for one repair."""
    parents = {child: parent for parent in root.iter() for child in parent}
    sections = {node: ordinal for ordinal, node in enumerate(
        (node for node in root.iter() if _local_name(node.tag) == "section" and "deck-section" in node.attrib.get("class", "").split()), 1
    )}
    failures = []
    for node in root.iter():
        if node.tag != _SVG_NS + "rect":
            continue
        ancestors, parent = [], parents.get(node)
        while parent is not None:
            ancestors.append(parent)
            parent = parents.get(parent)
        location = {"tagName": "rect", "sectionOrdinal": next((sections[n] for n in ancestors if n in sections), None)}
        def reject(code: str, message: str) -> None:
            failures.append({"severity": "error", "category": "structure", "code": code,
                             "message": message, "blocking": True, **location})
        invalid = False
        for dimension in ("x", "y", "width", "height", "rx", "ry"):
            value = node.attrib.get(dimension)
            if value is None:
                continue
            length = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:px|em|ex|ch|rem|cm|mm|Q|in|pt|pc|%)?\s*", value)
            if length is None or (dimension in {"width", "height", "rx", "ry"} and float(length[1]) < 0):
                invalid = True
                reject("svg_rect_geometry_invalid", f"SVG rect {dimension} must be a computed valid length; dimensions must be nonnegative. Do not place arithmetic expressions in SVG attributes. For an upward bar, use positive height and y = baseline minus height, with both numbers precomputed.")
        svg = next((n for n in ancestors if n.tag == _SVG_NS + "svg"), None)
        if invalid or svg is None or not _has_grounding(svg):
            continue
        # Check the observed untransformed evidence diagram, without guessing
        # transformed geometry or prohibiting deliberate decorative cropping.
        if any(n.attrib.get("transform") for n in [node, *ancestors[:ancestors.index(svg)]]):
            continue
        try:
            vx, vy, vw, vh = map(float, svg.attrib.get("viewBox", "").replace(",", " ").split())
            x, y = float(node.attrib.get("x", "0")), float(node.attrib.get("y", "0"))
            width, height = float(node.attrib["width"]), float(node.attrib["height"])
        except (ValueError, KeyError):
            continue  # Unit-relative geometry still requires browser proof.
        if vw > 0 and vh > 0 and (x < vx or y < vy or x + width > vx + vw or y + height > vy + vh):
            reject("svg_evidence_rect_clipped", "An evidence diagram rectangle extends outside its SVG viewBox. Fit every node and its rounded corners inside the viewport; precompute node widths, gaps and margins before returning. Do not crop a node to make the diagram fit.")
    return failures


def _find_deck_root(root: ET.Element) -> ET.Element:
    candidates = [element for element in root.iter() if _local_name(element.tag) == "main"]
    if len(candidates) != 1:
        raise HtmlDeckCompileError("deck_root_invalid", "A full HTML deck requires exactly one main deck root.")
    return candidates[0]


def _extract_slides(deck_root: ET.Element) -> list[ET.Element]:
    children = list(deck_root)
    precedence = [
        lambda node: _local_name(node.tag) == "section" and "deck-section" in set((node.attrib.get("class") or "").split()),
        lambda node: "data-slot" in node.attrib,
        lambda node: "data-slide" in node.attrib,
        lambda node: _local_name(node.tag) == "article",
    ]
    for predicate in precedence:
        slides = [child for child in children if predicate(child)]
        if slides:
            if any(any(predicate(descendant) for descendant in child.iter() if descendant is not child) for child in slides):
                raise HtmlDeckCompileError("nested_slide_boundary", "Nested slide boundaries are ambiguous.")
            return slides
    raise HtmlDeckCompileError("slides_missing", "No compiler-discoverable slide sections were found.")


def _text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


_PRESENTATIONAL_PHRASES = {
    "overview", "agenda", "evidence", "appendix", "questions", "thank you", "next steps",
    "contents", "introduction", "summary", "shared visual language", "safe title",
    "problem", "solution", "product", "market", "traction", "customers", "competition", "team",
    "roadmap", "financials", "business model", "market opportunity", "competitive landscape",
    "go to market", "how it works", "use of funds", "investment thesis", "unit economics",
}
_FACTUAL_TEXT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th"}
_GROUNDED_INLINE_TAGS = {"span", "strong", "em"}
_GROUNDABLE_TAGS = _FACTUAL_TEXT_TAGS | _GROUNDED_INLINE_TAGS | {"img", "table", "figure", "svg"}
_SLIDE_NUMBER = re.compile(r"^(?:slide\s+)?\d{1,3}(?:\s*/\s*\d{1,3})?$")
_DECORATIVE_TOKEN = re.compile(r"^[|•·—–-]$")


def _has_grounding(element: ET.Element) -> bool:
    return bool((element.attrib.get("data-source-refs") or "").split()) or element.attrib.get("data-bind", "").startswith("metric:")


def _independent_claim_text(element: ET.Element) -> str:
    """Return text this factual node owns, excluding nested factual nodes."""
    parts: list[str] = [element.text or ""]
    for child in element:
        if _local_name(child.tag) not in _FACTUAL_TEXT_TAGS and not _has_grounding(child):
            parts.append(_independent_claim_text(child))
        parts.append(child.tail or "")
    return " ".join("".join(parts).split())


def _unbound_text_is_clearly_presentational(text: str) -> bool:
    """Allow only content-defined non-claims; provider metadata is untrusted."""
    text = text.strip().lower()
    if not text:
        return True
    if text in _PRESENTATIONAL_PHRASES:
        return True
    return bool(_SLIDE_NUMBER.fullmatch(text) or _DECORATIVE_TOKEN.fullmatch(text))


_AUDITED_TYPOGRAPHIC_EQUIVALENTS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
})


def _normalized_claim_identity(value: str) -> str:
    """Normalize representation only; never case, wording, or punctuation."""
    normalized = unicodedata.normalize("NFC", str(value)).translate(_AUDITED_TYPOGRAPHIC_EQUIVALENTS)
    return " ".join(normalized.split())


def _normalized_heading_identity(value: str) -> str:
    """Preserve the conservative PR #238 heading normalization contract."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split()).rstrip(".").strip()


def _exact_source_fact_matches(
    claim: str,
    *,
    lineage: list[str],
    fact_sources: dict[str, list[str]],
    fact_claim_texts: dict[str, list[str]],
) -> list[str]:
    claim_identity = _normalized_heading_identity(claim)
    if len(re.findall(r"\w+", claim_identity, flags=re.UNICODE)) < 2:
        return []
    lineage_set = set(lineage)
    matches: list[str] = []
    for fact_id, trusted_values in fact_claim_texts.items():
        sources = set(fact_sources.get(fact_id, []))
        if not sources or not sources <= lineage_set:
            continue
        if any(_normalized_heading_identity(value) == claim_identity for value in trusted_values):
            matches.append(fact_id)
    return sorted(set(matches))


def _build_fact_identity_index(
    *,
    catalog: Iterable[dict[str, Any]],
    legacy_claim_texts: dict[str, list[str]],
    fact_sources: dict[str, list[str]],
) -> dict[str, list[tuple[str, set[str], str]]]:
    """Index exact trusted text and collapse duplicate entries per fact."""
    by_identity: dict[str, dict[str, tuple[set[str], str]]] = {}

    def add(fact_id: str, text: str, sources: Iterable[str]) -> None:
        identity = _normalized_claim_identity(text)
        if not identity:
            return
        candidate = by_identity.setdefault(identity, {}).get(fact_id)
        if candidate is None:
            by_identity[identity][fact_id] = ({str(source) for source in sources if str(source)}, _sha(text))
        else:
            candidate[0].update(str(source) for source in sources if str(source))

    for entry in catalog:
        fact_id = str(entry.get("factId") or entry.get("id") or "").strip()
        text = str(entry.get("text") or "").strip()
        if fact_id and text:
            add(fact_id, text, entry.get("sourceSlideIds") or [])
    for fact_id, values in legacy_claim_texts.items():
        for value in values:
            add(fact_id, value, fact_sources.get(fact_id, []))
    return {
        identity: [(fact_id, sources, source_hash) for fact_id, (sources, source_hash) in sorted(facts.items())]
        for identity, facts in by_identity.items()
    }


def _unique_heading_prefix_fact_match(
    claim: str,
    *,
    lineage: list[str],
    catalog: Iterable[dict[str, Any]],
) -> tuple[str, set[str], str] | None:
    """Resolve a provider heading that is the exact leading clause of one fact."""
    claim_identity = _normalized_heading_identity(claim)
    if len(re.findall(r"\w+", claim_identity, flags=re.UNICODE)) < 5:
        return None
    lineage_set = set(lineage)
    matches: dict[str, tuple[str, set[str], str]] = {}
    for entry in catalog:
        fact_id = str(entry.get("factId") or entry.get("id") or "").strip()
        trusted_text = str(entry.get("text") or "").strip()
        sources = {str(source) for source in (entry.get("sourceSlideIds") or []) if str(source)}
        trusted_identity = _normalized_heading_identity(trusted_text)
        if (
            fact_id
            and sources
            and sources <= lineage_set
            and trusted_identity.startswith(f"{claim_identity} ")
        ):
            matches[fact_id] = (fact_id, sources, _sha(trusted_text))
    return next(iter(matches.values())) if len(matches) == 1 else None


def _auto_bind_exact_claims(
    slide: ET.Element,
    *,
    lineage: list[str],
    identity_index: dict[str, list[tuple[str, set[str], str]]],
) -> list[dict[str, str]]:
    """Bind unique exact independently-owned claims inside reconciled lineage."""
    lineage_set = set(lineage)
    audit: list[dict[str, str]] = []
    for element in slide.iter():
        if _local_name(element.tag) not in _FACTUAL_TEXT_TAGS or _has_grounding(element):
            continue
        claim = _independent_claim_text(element)
        identity = _normalized_claim_identity(claim)
        if (
            not identity
            or len(re.findall(r"\w+", identity, flags=re.UNICODE)) < 2
            or _unbound_text_is_clearly_presentational(claim)
        ):
            continue
        candidates = identity_index.get(identity) or []
        if len(candidates) != 1:
            continue
        fact_id, fact_lineage, source_hash = candidates[0]
        if not fact_lineage or not fact_lineage <= lineage_set:
            continue
        claim_hash = _sha(claim)
        element.attrib.update({
            "data-source-refs": fact_id,
            "data-da-binding-method": "exact_auto",
            "data-da-claim-text-hash": claim_hash,
            "data-da-source-text-hash": source_hash,
            "data-da-binding-policy": GROUNDING_BINDING_POLICY_VERSION,
            "data-da-normalization-policy": CLAIM_NORMALIZATION_POLICY_VERSION,
        })
        audit.append({"factId": fact_id, "claimTextHash": claim_hash, "sourceTextHash": source_hash})
    return audit


def _slug(value: str, ordinal: int) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized[:80] or f"slide-{ordinal}"


def _lineage_ids(slide: ET.Element, *, allow_missing: bool = False) -> list[str]:
    raw = slide.attrib.get("data-source-slide-ids") or slide.attrib.get("data-source-slide-refs") or ""
    values = [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
    if (not values and not allow_missing) or len(values) != len(set(values)):
        raise HtmlDeckCompileError("source_lineage_invalid", "Every section requires unique ordered source lineage.")
    return values


def _omission_ids(slide: ET.Element) -> list[str]:
    raw = slide.attrib.get("data-source-omission-ids") or ""
    values = [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
    if len(values) != len(set(values)):
        raise HtmlDeckCompileError("source_omission_invalid", "Source omission IDs must be unique and ordered.")
    return values


def _planning_ids(slide: ET.Element, attribute: str) -> list[str]:
    raw = slide.attrib.get(attribute) or ""
    values = [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
    seen: set[str] = set()
    return [value for value in values if not (value in seen or seen.add(value))]


def _validate_visual_plan_binding(
    slides: list[ET.Element],
    visual_slide_briefs: list[dict[str, Any]],
    *,
    resolved_visual_asset_ids: Iterable[str] = (),
    advisory_review: bool = False,
) -> list[dict[str, Any]]:
    """Require provider sections to execute the application-owned AI-VC plan."""
    if not visual_slide_briefs:
        return []
    warnings: list[dict[str, Any]] = []
    if len(slides) != len(visual_slide_briefs):
        if advisory_review:
            return [{
                "severity": "warning",
                "category": "structure",
                "code": "visual_plan_binding_invalid",
                "message": "Generated slide count differs from the AI-VC visual brief count; the renderable deck remains available as an advisory draft.",
                "blocking": False,
            }]
        raise HtmlDeckCompileError(
            "visual_plan_binding_invalid",
            "Generated slide count must match the reconstructed AI-VC deck architecture.",
        )
    seen_ids: set[str] = set()
    resolved_assets = set(resolved_visual_asset_ids)
    for ordinal, (slide, brief) in enumerate(zip(slides, visual_slide_briefs), 1):
        brief_id = str(brief.get("slide_id") or brief.get("slideId") or "").strip()
        primitive = str(brief.get("visual_primitive") or brief.get("visualPrimitive") or "").strip()
        if not brief_id or brief_id in seen_ids or not primitive:
            raise HtmlDeckCompileError(
                "visual_plan_contract_invalid",
                "Visual slide briefs require unique IDs and a visual primitive.",
            )
        seen_ids.add(brief_id)
        declared_id = (slide.attrib.get("data-plan-slide-id") or "").strip()
        declared_primitive = (slide.attrib.get("data-visual-primitive") or "").strip()
        evidence_ids = [str(value) for value in brief.get("evidence_ids") or brief.get("evidenceIds") or []]
        calculation_ids = [str(value) for value in brief.get("calculation_ids") or brief.get("calculationIds") or []]
        declared_evidence = _planning_ids(slide, "data-evidence-ids")
        declared_calculations = _planning_ids(slide, "data-calculation-ids")
        required_assets = [str(value) for value in brief.get("required_asset_ids") or brief.get("requiredAssetIds") or []]
        slide_assets = {
            str(element.attrib.get("data-visual-asset-ref"))
            for element in slide.iter()
            if element.attrib.get("data-visual-asset-ref")
        }
        missing_assets = [asset_id for asset_id in required_assets if asset_id not in slide_assets or asset_id not in resolved_assets]
        executable_required = bool(brief.get("executable_visual_required") or brief.get("executableVisualRequired"))
        executable_missing = executable_required and not required_assets
        copy_budget = brief.get("copy_budget_words") or brief.get("copyBudgetWords")
        visible_word_count = len(" ".join(slide.itertext()).split())
        copy_budget_exceeded = isinstance(copy_budget, int) and visible_word_count > max(copy_budget + 12, int(copy_budget * 1.25))
        binding_mismatch = (
            declared_id != brief_id
            or declared_primitive != primitive
            or declared_evidence != evidence_ids
            or declared_calculations != calculation_ids
        )
        mismatch = binding_mismatch or bool(missing_assets) or executable_missing or copy_budget_exceeded
        if mismatch and advisory_review:
            if missing_assets or executable_missing or copy_budget_exceeded:
                warnings.append({
                    "severity": "warning", "category": "structure",
                    "code": "required_executable_visual_missing" if missing_assets or executable_missing else "visual_copy_budget_exceeded",
                    "message": f"Generated slide {ordinal} does not fully execute its AI-VC visual contract; the rendered design remains available as an internal advisory draft.",
                    "blocking": False, "sectionOrdinal": ordinal, "planSlideId": brief_id,
                    "missingRequiredAssetIds": missing_assets, "visibleWordCount": visible_word_count,
                    "copyBudgetWords": copy_budget,
                })
            else:
                warnings.append({
                    "severity": "warning", "category": "structure", "code": "visual_plan_binding_invalid",
                    "message": f"Generated slide {ordinal} differs from its AI-VC visual brief; the rendered design remains available and the mismatch is retained for internal review.",
                    "blocking": False, "sectionOrdinal": ordinal, "planSlideId": brief_id,
                })
        elif mismatch:
            raise HtmlDeckCompileError(
                "visual_plan_binding_invalid",
                f"Generated slide {ordinal} does not match its AI-VC visual brief. Preserve the exact plan binding, execute required visual assets, and respect its copy budget.",
            )
    return warnings


def _element_role(element: ET.Element) -> tuple[str, str, list[str]]:
    tag = _local_name(element.tag)
    hinted = element.attrib.get("data-role")
    if element.attrib.get("data-component") == "chart":
        return "chart", "chart", ["select", "move", "resize", "change_chart_type", "bind_metric"]
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return hinted or "headline", "text", ["select", "move", "resize", "edit_text", "expand_text", "shorten_text", "style"]
    if tag in {"p", "li", "td", "th"}:
        return hinted or "body", "text", ["select", "move", "resize", "edit_text", "expand_text", "shorten_text", "style"]
    if tag == "img":
        return hinted or "image", "image", ["select", "move", "resize", "replace_asset", "crop_asset"]
    if tag == "table":
        return hinted or "table", "table", ["select", "move", "resize", "bind_metric", "style"]
    if tag == "svg":
        return hinted or "decoration", "vector", ["select", "move", "resize"]
    return hinted or "group", "group", ["select", "move", "resize", "style"]


def _compile_elements(
    slide: ET.Element,
    slide_key: str,
    *,
    persistence_identity_scope: str | None = None,
    allow_svg_text_grounding: bool = False,
    preserve_review_keys: bool = False,
) -> list[dict[str, Any]]:
    counters: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for element in slide.iter():
        tag = _local_name(element.tag)
        if tag not in _EDITABLE_TAGS and element.attrib.get("data-component") not in {"chart", "card", "group"} and not _has_grounding(element):
            continue
        svg_label = allow_svg_text_grounding and tag in {"text", "tspan"} and _has_grounding(element)
        role, element_type, capabilities = (
            ("body", "text", ["select"]) if svg_label else _element_role(element)
        )
        counters[role] = counters.get(role, 0) + 1
        render_key = f"{role}-{counters[role]:02d}"
        identity_seed = (
            f"{persistence_identity_scope}:{slide_key}:{render_key}"
            if persistence_identity_scope
            else f"{slide_key}:{render_key}"
        )
        persisted_id = "htmlel_" + _sha(identity_seed)[:24]
        review_key = element.attrib.get("data-da-element-key")
        element.attrib["data-da-element-key"] = render_key
        element.attrib["data-da-persisted-element-id"] = persisted_id
        entry = {
            "persistedElementId": persisted_id,
            "renderElementKey": render_key,
            "semanticRole": role,
            "elementType": element_type,
            "tagName": tag,
            "capabilities": capabilities,
            "locked": role == "decoration" or svg_label,
            "visible": True,
            "sourceFactIds": [part for part in (element.attrib.get("data-source-refs") or "").split() if part],
            "metricKeys": [element.attrib["data-bind"].removeprefix("metric:")] if element.attrib.get("data-bind", "").startswith("metric:") else [],
            "assetIds": [element.attrib["data-asset-ref"].removeprefix("approved:")] if "data-asset-ref" in element.attrib else [],
            "geometryOverride": {"translateX": 0, "translateY": 0, "width": None, "height": None},
        }
        if element.attrib.get("data-da-binding-method"):
            entry.update({
                "bindingMethod": element.attrib["data-da-binding-method"],
                "claimTextHash": element.attrib["data-da-claim-text-hash"],
                "sourceTextHash": element.attrib["data-da-source-text-hash"],
                "bindingPolicyVersion": element.attrib["data-da-binding-policy"],
                "normalizationPolicyVersion": element.attrib["data-da-normalization-policy"],
            })
        if preserve_review_keys and review_key:
            entry["reviewElementKey"] = review_key
        result.append(entry)
    keys = [item["renderElementKey"] for item in result]
    if len(keys) != len(set(keys)):
        raise HtmlDeckCompileError("compiler_element_key_duplicate", "Compiler generated duplicate element keys.")
    return result


def _apply_metric_bindings(slide: ET.Element, bindings: dict[str, dict[str, Any]]) -> None:
    bg_tokens = _extract_slide_bg_tokens(slide)
    for element in slide.iter():
        binding = element.attrib.get("data-bind", "")
        if not binding.startswith("metric:"):
            continue
        key = binding.removeprefix("metric:")
        metric = bindings.get(key)
        if metric is None:
            raise HtmlDeckCompileError("grounded_metric_binding_missing", "A referenced metric requires deterministic binding data.")
        if element.attrib.get("data-component") == "chart":
            values = metric.get("values")
            labels = metric.get("labels")
            kind = element.attrib.get("data-chart-kind") or metric.get("chartKind")
            if not isinstance(values, list) or not isinstance(labels, list):
                raise HtmlDeckCompileError("chart_binding_invalid", "Chart metric does not provide deterministic values and labels.")
            rendered = ET.fromstring(deterministic_chart_svg(str(kind or ""), values, [str(label) for label in labels], background_tokens=bg_tokens))
            compiler_attributes = {
                name: value for name, value in element.attrib.items()
                if name.startswith("data-da-") or name in {"data-component", "data-bind", "data-chart-kind"}
            }
            element.clear()
            element.tag = rendered.tag
            element.attrib.update(rendered.attrib)
            element.attrib.update(compiler_attributes)
            element.extend(list(rendered))
        else:
            value = _deterministic_metric_value(metric)
            if value is None:
                raise HtmlDeckCompileError("metric_binding_invalid", "Metric binding lacks a deterministic value or calculation.")
            element.text = value
            for child in list(element):
                element.remove(child)


def _extract_slide_bg_tokens(slide: ET.Element) -> dict[str, str]:
    style = slide.attrib.get("style") or ""
    tokens: dict[str, str] = {}
    for declaration in style.split(";"):
        if ":" in declaration:
            key, _, val = declaration.partition(":")
            key = key.strip()
            val = val.strip()
            if key in {"background", "--da-canvas", "--da-ink", "--da-accent"}:
                tokens[key] = val
    return tokens


def _deterministic_metric_value(metric: dict[str, Any]) -> str | None:
    from decimal import Decimal, InvalidOperation

    if "value" in metric:
        return str(metric["value"])
    calculation = metric.get("calculation")
    if not isinstance(calculation, dict) or not isinstance(calculation.get("inputs"), list):
        return None
    try:
        values = [Decimal(str(value)) for value in calculation["inputs"]]
    except (InvalidOperation, ValueError):
        raise HtmlDeckCompileError("metric_calculation_invalid", "Metric calculation inputs must be deterministic decimals.")
    operation = calculation.get("operation")
    if not values:
        raise HtmlDeckCompileError("metric_calculation_invalid", "Metric calculation requires inputs.")
    if operation == "sum":
        result = sum(values, Decimal("0"))
    elif operation == "difference" and len(values) == 2:
        result = values[0] - values[1]
    elif operation == "product":
        result = Decimal("1")
        for value in values:
            result *= value
    elif operation in {"ratio", "percent"} and len(values) == 2 and values[1] != 0:
        result = values[0] / values[1]
        if operation == "percent":
            result *= Decimal("100")
    else:
        raise HtmlDeckCompileError("metric_calculation_invalid", "Metric calculation operation is unsupported or incomplete.")
    normalized = format(result.normalize(), "f")
    return normalized + ("%" if operation == "percent" else "")


def _serialize(element: ET.Element) -> str:
    return html5lib.serialize(element, tree="etree", quote_attr_values="always", omit_optional_tags=False, alphabetical_attributes=True)


def deterministic_chart_svg(kind: str, values: Iterable[str | int | float], labels: Iterable[str], *, background_tokens: dict[str, str] | None = None) -> str:
    from decimal import Decimal, InvalidOperation

    parsed: list[Decimal] = []
    try:
        parsed = [Decimal(str(value)) for value in values]
    except InvalidOperation as exc:
        raise HtmlDeckCompileError("chart_metric_invalid", "Chart values must be deterministic decimals.") from exc
    label_values = list(labels)
    if not parsed or len(parsed) != len(label_values) or kind not in {"bar", "line"}:
        raise HtmlDeckCompileError("chart_binding_invalid", "Chart binding is incomplete or unsupported.")
    maximum = max(max(parsed), Decimal("1"))
    _tokens = background_tokens or {}
    canvas = str(_tokens.get("--da-canvas") or _tokens.get("background") or "")
    ink = str(_tokens.get("--da-ink") or _tokens.get("color") or "")
    accent = str(_tokens.get("--da-accent") or "")
    chart_bg = canvas if canvas.startswith("#") and len(canvas) in {7, 4} else "#ffffff"
    chart_ink = ink if ink.startswith("#") and len(ink) in {7, 4} else "#1f2937"
    chart_accent = accent if accent.startswith("#") and len(accent) in {7, 4} else "#4f46e5"
    grid_color = _blend_hex(chart_bg, chart_ink, 0.15)
    label_color = _blend_hex(chart_bg, chart_ink, 0.45)
    primitives: list[str] = []
    for index, (value, label) in enumerate(zip(parsed, label_values)):
        x = 60 + index * 120
        height = int((value / maximum * Decimal("700")).quantize(Decimal("1")))
        y = 820 - height
        bar_color = _blend_hex(chart_bg, chart_accent, 0.30 + 0.15 * (index % 3))
        primitives.append(f'<rect x="{x}" y="{y}" width="72" height="{height}" fill="{bar_color}"/>')
        primitives.append(f'<text x="{x + 36}" y="860" text-anchor="middle" fill="{label_color}">{escape(str(label))}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" role="img"><rect width="100%" height="100%" fill="{chart_bg}"/>' + "".join(primitives) + "</svg>"


def _blend_hex(base: str, target: str, amount: float) -> str:
    if not base.startswith("#") or len(base) not in {7, 4}:
        return target
    if not target.startswith("#") or len(target) not in {7, 4}:
        return target
    bg = _parse_hex_rgb(base)
    tg = _parse_hex_rgb(target)
    if bg is None or tg is None:
        return target
    amount = max(0.0, min(1.0, amount))
    blended = tuple(int(round(bg[i] + (tg[i] - bg[i]) * amount)) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*blended)


def _parse_hex_rgb(hex_color: str) -> tuple[int, int, int] | None:
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


def _background_treatment_code(background: dict[str, Any]) -> str:
    return str(background.get("treatment") or background.get("harmonization") or "shared")[:120]


def _author_background_tokens(background: dict[str, Any]) -> dict[str, str] | None:
    """Build application-authored slide tokens from an authored background."""
    canvas = str(background.get("canvas") or "").strip()
    if not canvas or not canvas.startswith("#") or len(canvas) not in {7, 4}:
        return None
    ink = str(background.get("ink") or "").strip()
    if not ink:
        return None
    tokens: dict[str, str] = {
        "background": canvas,
        "--da-canvas": canvas,
        "color": ink,
        "--da-ink": ink,
    }
    surface = str(background.get("surface") or "").strip()
    accent = str(background.get("accent") or "").strip()
    if surface and surface.startswith("#") and len(surface) in {7, 4}:
        tokens["--da-surface"] = surface
    if accent and accent.startswith("#") and len(accent) in {7, 4}:
        tokens["--da-accent"] = accent
    return tokens


def _author_slide_tokens(slide: ET.Element, background: dict[str, Any]) -> bool:
    tokens = _author_background_tokens(background)
    if not tokens:
        return False
    existing = (slide.attrib.get("style") or "").rstrip(";")
    style = ";".join(f"{key}:{value}" for key, value in tokens.items())
    slide.attrib["style"] = f"{existing};{style}" if existing else style
    return True


def _apply_authored_slide_background(
    slide: ET.Element,
    visual_slide_briefs: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Attach the visual-intelligence-authored background to one section.

    The background is application-authored (brand-derived, contrast-safe hex
    tokens) and matches the section through its planning identity, not the
    provider. The designer's own layout selectors remain in full force; this
    only supplies the shared canvas, surface, accent and ink tokens the deck
    authoring system chose for the slide.
    """
    briefs = list(visual_slide_briefs or [])
    if not briefs:
        return None
    plan_id = (slide.attrib.get("data-plan-slide-id") or "").strip()
    order = (slide.attrib.get("data-slot") or "").strip()
    candidate = None
    if plan_id:
        for brief in briefs:
            if str(brief.get("slide_id") or "") == plan_id or str(brief.get("slideId") or "") == plan_id:
                candidate = brief
                break
    if candidate is None and order:
        try:
            wanted = int(order, 10)
        except ValueError:
            wanted = None
        if wanted is not None:
            for brief in briefs:
                if brief.get("slide_index") == wanted:
                    candidate = brief
                    break
    if candidate is None:
        return None
    background = candidate.get("background") if isinstance(candidate.get("background"), dict) else {}
    if not _author_slide_tokens(slide, background):
        return None
    return background


def _apply_authored_deck_background(
    slide: ET.Element,
    visual_background_system: dict[str, Any] | None,
    ordinal: int,
) -> dict[str, Any] | None:
    """Apply the deck-level harmonized background by ordinal when no brief exists.

    Source-only fallback decks have no authored slide briefs, so they carry no
    per-slide plan. The deck background system still supplies the required
    field: slide one opens on the distinct cover canvas and every later slide
    shares the harmonized interior canvas.
    """
    if not isinstance(visual_background_system, dict):
        return None
    background = (
        visual_background_system.get("cover")
        if ordinal == 1
        else visual_background_system.get("interior")
    )
    if not isinstance(background, dict):
        return None
    if not _author_slide_tokens(slide, background):
        return None
    return background


def compile_html_deck(
    raw_output: str,
    *,
    selected_source_slide_ids: Iterable[str],
    approved_asset_ids: Iterable[str] = (),
    approved_asset_references: dict[str, str] | None = None,
    approved_asset_alt_texts: dict[str, str] | None = None,
    rendered_visual_assets: dict[str, dict[str, Any]] | None = None,
    visual_slide_briefs: list[dict[str, Any]] | None = None,
    visual_background_system: dict[str, Any] | None = None,
    grounded_fact_ids: Iterable[str] = (),
    grounded_fact_texts: dict[str, str] | None = None,
    grounded_fact_sources: dict[str, list[str]] | None = None,
    grounded_fact_claim_texts: dict[str, list[str]] | None = None,
    grounded_fact_catalog: Iterable[dict[str, Any]] | None = None,
    grounded_fact_traceability: dict[str, dict[str, Any]] | None = None,
    metric_keys: Iterable[str] = (),
    metric_bindings: dict[str, dict[str, Any]] | None = None,
    grounded_metric_traceability: dict[str, dict[str, Any]] | None = None,
    grounding_snapshot_hash: str = "0" * 64,
    compiler_version: str = COMPILER_VERSION,
    persistence_identity_scope: str | None = None,
    max_html_bytes: int | None = None,
    presentation_intent: str = "general",
    draft_claims: Iterable[dict[str, Any]] = (),
    advisory_review: bool = False,
) -> CompiledHtmlDeck:
    # Server-supplied inventory of the saved draft. Provider HTML cannot
    # declare this authority. Missing metadata remains internal to the
    # draft, not proof of correctness or an accepted final deck.
    draft_claims = list(draft_claims)
    reviewed_identities = {(item['slide'], _sha(item['text'])) for item in draft_claims}
    draft_issues = {item['slide']: item['reviewConcern'] for item in draft_claims if item.get('reviewConcern') in {'source_uncertainty', 'factual_correction'}}
    if reviewed_identities and not advisory_review:
        raise HtmlDeckCompileError('advisory_policy_required', 'Incomplete evidence metadata requires the application advisory policy.')
    reviewed_unlinked_claims = []
    max_html_bytes = whole_deck_html_ceiling(
        compiler_version=compiler_version,
        bound_max_html_bytes=max_html_bytes,
    )
    # SVG labels carry evidence without becoming freely editable chart geometry.
    # Historical compiler checkpoints retain their original target contract.
    svg_text_grounding = compiler_version in {SVG_TEXT_GROUNDING_COMPILER_VERSION, RECT_GEOMETRY_COMPILER_VERSION, VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}
    grounded_inline_tags = _GROUNDED_INLINE_TAGS | ({"text", "tspan"} if svg_text_grounding else set())
    groundable_tags = _GROUNDABLE_TAGS | grounded_inline_tags
    if compiler_version in {INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION} and presentation_intent not in {"general", "investor_pitch"}:
        raise HtmlDeckCompileError("presentation_intent_invalid", "A canonical presentation intent is required.")
    raw_bytes = raw_output.encode("utf-8")
    if not raw_bytes or len(raw_bytes) > max_html_bytes:
        raise HtmlDeckCompileError("html_budget_exceeded", "Deck HTML is empty or exceeds the configured byte budget.")
    source_ids = list(selected_source_slide_ids)
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise HtmlDeckCompileError("selected_source_ids_invalid", "Selected source IDs must be non-empty and unique.")
    document = _parse_document(_strip_provider_fence(raw_output))
    resolved_visual_asset_ids = _inject_rendered_visual_assets(
        document,
        dict(rendered_visual_assets or {}),
    )
    approved_ids = set(approved_asset_ids)
    approved_references = dict(approved_asset_references or {})
    approved_alt_texts = dict(approved_asset_alt_texts or {})
    # Keep the legacy allowlist parameter for callers, but an ID alone is not
    # sufficient to resolve content and therefore cannot authorize a URL.
    approved_references = {key: value for key, value in approved_references.items() if key in approved_ids}
    approved_alt_texts = {
        key: value
        for key, value in approved_alt_texts.items()
        if key in approved_ids and isinstance(value, str)
    }
    css_blocks, issues = _sanitize_tree(
        document,
        approved_references,
        approved_alt_texts,
        compiler_version=compiler_version,
    )
    deck_root = _find_deck_root(document)
    slides = _extract_slides(deck_root)
    visual_plan_warnings = _validate_visual_plan_binding(
        slides,
        list(visual_slide_briefs or []),
        resolved_visual_asset_ids=resolved_visual_asset_ids,
        advisory_review=advisory_review,
    )
    if len(slides) > MAX_SLIDES:
        raise HtmlDeckCompileError("slide_budget_exceeded", "Deck exceeds the configured slide budget.")
    sanitized_css = sanitize_and_scope_css(
        "\n".join(css_blocks),
        compiler_version=compiler_version,
    )
    seen_slugs: set[str] = set()
    seen_section_ids: set[str] = set()
    covered: set[str] = set()
    evidence_backed: set[str] = set()
    explicitly_omitted: set[str] = set()
    slide_manifests: list[dict[str, Any]] = []
    auto_binding_audit: list[dict[str, str]] = []
    fact_id_list = [str(value) for value in grounded_fact_ids]
    if len(fact_id_list) != len(set(fact_id_list)):
        raise HtmlDeckCompileError("grounded_fact_ids_invalid", "Grounded fact IDs must be unique.")
    fact_allowlist = set(fact_id_list)
    fact_texts = {
        str(fact_id): str(value)
        for fact_id, value in dict(grounded_fact_texts or {}).items()
        if str(fact_id) in fact_allowlist and isinstance(value, str) and value.strip()
    }
    catalog_entries = [dict(item) for item in (grounded_fact_catalog or []) if isinstance(item, dict)]
    fact_sources = dict(grounded_fact_sources or {})
    fact_claim_texts = {
        str(fact_id): [str(value) for value in values if str(value).strip()]
        for fact_id, values in dict(grounded_fact_claim_texts or {}).items()
        if isinstance(values, list)
    }
    fact_traceability = dict(grounded_fact_traceability or {})
    catalog_entries.extend(
        {"factId": fact_id, "text": text, "sourceSlideIds": list((grounded_fact_sources or {}).get(fact_id, []))}
        for fact_id, text in fact_texts.items()
        if fact_id in fact_traceability
    )
    metric_key_list = [str(value) for value in metric_keys]
    if len(metric_key_list) != len(set(metric_key_list)):
        raise HtmlDeckCompileError("grounded_metric_keys_invalid", "Grounded metric keys must be unique.")
    metric_allowlist = set(metric_key_list)
    bindings = dict(metric_bindings or {})
    metric_traceability = dict(grounded_metric_traceability or {})
    selected_id_set = set(source_ids)

    def canonical_non_slide_fact(fact_id: str) -> bool:
        trace = fact_traceability.get(fact_id) or {}
        source_type = str(trace.get("sourceType") or "").strip()
        source_id = str(trace.get("sourceId") or "").strip()
        return bool(
            source_type not in {"", "unknown", "legacy", "source_slide"}
            and source_id
            and source_id not in selected_id_set
            and not (trace.get("sourceSlideIds") or [])
        )

    def trusted_source_set(
        values: Iterable[Any],
        *,
        duplicate_code: str,
        unknown_code: str,
        subject: str,
    ) -> set[str]:
        supplied = [str(value) for value in values]
        if len(supplied) != len(set(supplied)):
            raise HtmlDeckCompileError(duplicate_code, f"{subject} lineage must be unique.")
        if not set(supplied) <= selected_id_set:
            raise HtmlDeckCompileError(unknown_code, f"{subject} lineage references an unselected source slide.")
        return set(supplied)

    canonical_fact_sources: dict[str, list[str]] = {}
    for fact_id in fact_id_list:
        direct_present = fact_id in fact_sources
        trace_present = fact_id in fact_traceability
        direct_source_set = trusted_source_set(
            fact_sources.get(fact_id, []),
            duplicate_code="grounded_fact_lineage_invalid",
            unknown_code="grounded_fact_lineage_unknown",
            subject="Grounded fact",
        )
        traced_source_set = trusted_source_set(
            (fact_traceability.get(fact_id) or {}).get("sourceSlideIds") or [],
            duplicate_code="grounded_fact_lineage_invalid",
            unknown_code="grounded_fact_lineage_unknown",
            subject="Grounded fact",
        )
        if direct_present and trace_present and direct_source_set != traced_source_set:
            raise HtmlDeckCompileError(
                "grounded_fact_provenance_mismatch",
                "Grounded fact provenance authorities disagree.",
            )
        authoritative_source_set = traced_source_set if trace_present else direct_source_set
        canonical_fact_sources[fact_id] = [
            source_id for source_id in source_ids if source_id in authoritative_source_set
        ]
    fact_sources = canonical_fact_sources
    for entry in catalog_entries:
        fact_id = str(entry.get("factId") or entry.get("id") or "").strip()
        if fact_id not in fact_allowlist or not str(entry.get("text") or "").strip():
            raise HtmlDeckCompileError(
                "grounded_fact_catalog_invalid",
                "Grounded fact catalog entries require an allowed fact and non-empty exact text.",
            )
        catalog_source_set = trusted_source_set(
            entry.get("sourceSlideIds") or [],
            duplicate_code="grounded_fact_lineage_invalid",
            unknown_code="grounded_fact_lineage_unknown",
            subject="Grounded fact catalog",
        )
        if catalog_source_set != set(fact_sources.get(fact_id, [])):
            raise HtmlDeckCompileError(
                "grounded_fact_catalog_provenance_mismatch",
                "Grounded fact catalog lineage must equal reconciled fact lineage.",
            )
        entry["sourceSlideIds"] = list(fact_sources[fact_id])
    fact_identity_index = _build_fact_identity_index(
        catalog=catalog_entries,
        legacy_claim_texts={},
        fact_sources=fact_sources,
    )
    canonical_metric_sources: dict[str, list[str]] = {}
    canonical_metric_traceability: dict[str, dict[str, Any]] = {}
    for metric_key in metric_key_list:
        metric_binding = bindings.get(metric_key) or {}
        trace = metric_traceability.get(metric_key) or {}
        direct_present = metric_key in bindings and "sourceSlideIds" in metric_binding
        trace_present = metric_key in metric_traceability
        direct_source_set = trusted_source_set(
            metric_binding.get("sourceSlideIds") or [],
            duplicate_code="grounded_metric_lineage_invalid",
            unknown_code="grounded_metric_lineage_unknown",
            subject="Grounded metric",
        )
        traced_source_set = trusted_source_set(
            trace.get("sourceSlideIds") or [],
            duplicate_code="grounded_metric_lineage_invalid",
            unknown_code="grounded_metric_lineage_unknown",
            subject="Grounded metric",
        )
        if direct_present and trace_present and direct_source_set != traced_source_set:
            raise HtmlDeckCompileError(
                "grounded_metric_provenance_mismatch",
                "Grounded metric provenance authorities disagree.",
            )
        authoritative_source_set = traced_source_set if trace_present else direct_source_set
        if not authoritative_source_set:
            raise HtmlDeckCompileError(
                "grounded_metric_lineage_missing",
                "Every supplied grounded metric requires exact selected source-slide lineage.",
            )
        canonical_metric_sources[metric_key] = [
            source_id for source_id in source_ids if source_id in authoritative_source_set
        ]
        canonical_metric_traceability[metric_key] = trace if trace_present else metric_binding
    source_fact_ids = {
        source_id: {
            fact_id for fact_id in fact_id_list
            if source_id in set(fact_sources.get(fact_id, []))
        }
        for source_id in source_ids
    }
    source_metric_keys = {
        source_id: {
            metric_key for metric_key in metric_key_list
            if source_id in set(canonical_metric_sources.get(metric_key, []))
        }
        for source_id in source_ids
    }
    numeric_observations: dict[tuple[str, str, str], tuple[str, int]] = {}
    for ordinal, slide in enumerate(slides, 1):
        lineage = _lineage_ids(slide, allow_missing=advisory_review)
        if not set(lineage) <= selected_id_set:
            raise HtmlDeckCompileError("source_lineage_unknown", "A section references an unknown or unauthorized source slide.")
        omissions = _omission_ids(slide)
        if not set(omissions) <= set(lineage):
            raise HtmlDeckCompileError("source_omission_lineage_mismatch", "A source omission must belong to the section lineage.")
        heading = next((node for node in slide.iter() if _local_name(node.tag) in {"h1", "h2", "h3"}), None)
        title = slide.attrib.get("data-slot-title") or (_text(heading) if heading is not None else f"Slide {ordinal}")
        slug = _slug(slide.attrib.get("data-slot-slug") or title, ordinal)
        if slug in seen_slugs:
            slug = f"{slug}-{ordinal}"
        seen_slugs.add(slug)
        section_id = "slide-" + _sha(f"{grounding_snapshot_hash}:{ordinal}:{slug}")[:16]
        if section_id in seen_section_ids:
            raise HtmlDeckCompileError("section_identity_collision", "Compiler section identity collision.")
        seen_section_ids.add(section_id)
        slot = f"{ordinal:02d}"
        slide.attrib.update({
            "data-slot": slot,
            "data-slot-title": title[:200],
            "data-slot-slug": slug,
            "data-slide-id": section_id,
            "data-da-slide-root": section_id,
            "data-source-slide-ids": " ".join(lineage),
        })
        if compiler_version == COMPILER_VERSION:
            applied = _apply_authored_slide_background(slide, visual_slide_briefs)
            if applied is None:
                applied = _apply_authored_deck_background(slide, visual_background_system, ordinal)
            if applied:
                slide.attrib["data-da-background"] = _background_treatment_code(applied)
        slide.attrib.pop("data-source-slide-refs", None)
        for element in slide.iter():
            if _local_name(element.tag) not in {"h1", "h2", "h3"} or _has_grounding(element):
                continue
            claim = _independent_claim_text(element)
            matches = _exact_source_fact_matches(
                claim,
                lineage=lineage,
                fact_sources=fact_sources,
                fact_claim_texts=fact_claim_texts,
            )
            if len(matches) == 1:
                trusted_heading = next(
                    value
                    for value in fact_claim_texts[matches[0]]
                    if _normalized_heading_identity(value) == _normalized_heading_identity(claim)
                )
                element.attrib.update({
                    "data-source-refs": matches[0],
                    "data-da-binding-method": "exact_heading",
                    "data-da-claim-text-hash": _sha(claim),
                    "data-da-source-text-hash": _sha(trusted_heading),
                    "data-da-binding-policy": GROUNDING_BINDING_POLICY_VERSION,
                    "data-da-normalization-policy": CLAIM_NORMALIZATION_POLICY_VERSION,
                })
        for element in slide.iter():
            binding = element.attrib.get("data-bind", "")
            if binding and not binding.startswith("metric:") and not advisory_review:
                raise HtmlDeckCompileError("grounding_binding_invalid", "Data bindings must use an allowed metric key.")
            if _has_grounding(element) and _local_name(element.tag) not in groundable_tags and element.attrib.get("data-component") != "chart":
                # Current whole-deck providers occasionally use a styled div as
                # the leaf text node for one cited feature.  When the div owns
                # only direct text, changing its semantic tag to a paragraph is
                # lossless and makes the citation manifest-backed.  Keep older
                # compiler checkpoints byte-for-byte strict.
                if (
                    compiler_version in {
                        FOREGROUND_GUARD_COMPILER_VERSION,
                        REPLAY_COMPILER_VERSION,
                        ALT_TEXT_COMPILER_VERSION,
                        PREVIOUS_CURRENT_COMPILER_VERSION,
                        DENSE_METRICS_COMPILER_VERSION,
                        EDITORIAL_DENSITY_COMPILER_VERSION,
                        VISUAL_SUBSTANCE_COMPILER_VERSION,
                        PRESENTATION_PROOF_COMPILER_VERSION,
                        READABLE_BODY_COMPILER_VERSION,
                        OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
                        AUTO_GRID_BODY_COMPILER_VERSION,
                        AUTO_GRID_ITEM_COMPILER_VERSION,
                        SVG_TEXT_GROUNDING_COMPILER_VERSION,
                        RECT_GEOMETRY_COMPILER_VERSION,
                        VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
                        SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
                    }
                    and _local_name(element.tag) == "div"
                    and not list(element)
                    and bool(" ".join((element.text or "").split()))
                    and not element.attrib.get("data-bind")
                ):
                    element.tag = "p"
                    continue
                # A provider sometimes puts a fact reference on a neutral
                # layout wrapper. Repair only the provably equivalent shape:
                # one ungrounded factual child whose exact text maps to the
                # same supplied fact IDs, and no wrapper-owned text. Anything
                # ambiguous remains a fail-closed compiler error.
                fact_ids = [value for value in (element.attrib.get("data-source-refs") or "").split() if value]
                factual_children = [
                    child for child in element.iter()
                    if child is not element
                    and _local_name(child.tag) in _FACTUAL_TEXT_TAGS
                    and not _has_grounding(child)
                ]
                # `_independent_claim_text` deliberately descends through a
                # neutral wrapper to find factual content.  Here we need the
                # opposite question: whether the wrapper itself contributes
                # literal text before/between/after its children.
                wrapper_text = " ".join(
                    "".join([element.text or "", *(child.tail or "" for child in element)]).split()
                )
                if len(factual_children) == 1 and not wrapper_text and fact_ids:
                    child = factual_children[0]
                    claim_text = _independent_claim_text(child)
                    claim_identity = _normalized_heading_identity(claim_text)
                    # Block-level facts deliberately are not eligible for the
                    # broad auto-binding index above, because a slide can have
                    # many blocks. Here the provider named exact fact IDs, so
                    # validate every one against its canonical source text and
                    # lineage before moving that binding to the child.
                    trusted_values = {
                        fact_id: list(dict.fromkeys([
                            value
                            for value in [fact_texts.get(fact_id, ""), *fact_claim_texts.get(fact_id, [])]
                            if value
                        ]))
                        for fact_id in fact_ids
                    }
                    exact_matches = [
                        fact_id
                        for fact_id in fact_ids
                        if fact_sources.get(fact_id)
                        and set(fact_sources[fact_id]) <= set(lineage)
                        and any(_normalized_heading_identity(value) == claim_identity for value in trusted_values[fact_id])
                    ]
                    if set(fact_ids) == set(exact_matches):
                        trusted_text = next(
                            value
                            for value in trusted_values[fact_ids[0]]
                            if _normalized_heading_identity(value) == claim_identity
                        )
                        element.attrib.pop("data-source-refs", None)
                        child.attrib["data-source-refs"] = " ".join(fact_ids)
                        child.attrib["data-da-binding-method"] = "structural_wrapper_exact_repair"
                        child.attrib["data-da-claim-text-hash"] = _sha(claim_text)
                        child.attrib["data-da-source-text-hash"] = _sha(trusted_text)
                        child.attrib["data-da-binding-policy"] = GROUNDING_BINDING_POLICY_VERSION
                        child.attrib["data-da-normalization-policy"] = CLAIM_NORMALIZATION_POLICY_VERSION
                        continue
                tag_name = _local_name(element.tag)
                if advisory_review:
                    reviewed_unlinked_claims.append({'slide': ordinal, 'elementKey': element.get('data-da-element-key'),
                        'textSha256': _sha(_independent_claim_text(element)), 'code': 'grounding_target_invalid',
                        'declaredReferences': element.get('data-source-refs', '').split()})
                    element.attrib.pop('data-source-refs', None)
                    element.attrib.pop('data-bind', None)
                    continue
                raise HtmlDeckCompileError(
                    "grounding_target_invalid",
                    "Grounding must be attached to a manifest-backed content element.",
                    issues=[{
                        "severity": "error",
                        "category": "grounding",
                        "code": "grounding_target_invalid",
                        "message": "Grounding must be attached to a manifest-backed content element.",
                        "blocking": True,
                        # This is intentionally structural only: it gives the
                        # provider/replay operator an actionable correction
                        # without recording untrusted claim text in a public
                        # workflow error.
                        "tagName": tag_name,
                        "sectionOrdinal": ordinal,
                    }],
                )
            if (
                _local_name(element.tag) in grounded_inline_tags
                and (element.attrib.get("data-source-refs") or "").split()
                and _unbound_text_is_clearly_presentational(_independent_claim_text(element))
            ):
                # A decorative inline label cannot establish evidence. Drop its
                # unnecessary provider-declared reference rather than rejecting
                # an otherwise fully grounded deck; the later coverage check
                # still fails if this was the only attempted evidence.
                element.attrib.pop("data-source-refs", None)
        # Providers occasionally preserve the exact catalog claim while copying
        # a placeholder or otherwise invalid fact identifier. Repair only the
        # deterministic case where that element's complete claim text maps to
        # one supplied fact whose provenance is wholly inside this section's
        # source lineage. Ambiguous or paraphrased claims remain fail-closed.
        for element in slide.iter():
            declared_refs = [
                value
                for value in (element.attrib.get("data-source-refs") or "").split()
                if value
            ]
            unknown_refs = [value for value in declared_refs if value not in fact_allowlist]
            if not unknown_refs:
                continue
            claim = _independent_claim_text(element)
            if compiler_version in {SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
                # The observed provider output retained the full source-block
                # digest but omitted its type prefix. Restore only this exact
                # request-owned identity; never guess a shortened hash or fact.
                restored = {
                    value: "fact_source_block_" + value
                    for value in unknown_refs
                    if re.fullmatch(r"[0-9a-f]{64}", value)
                    and "fact_source_block_" + value in fact_allowlist
                    and canonical_fact_sources["fact_source_block_" + value]
                    and set(canonical_fact_sources["fact_source_block_" + value]) <= set(lineage)
                }
                if len(restored) == len(set(unknown_refs)):
                    repaired = list(dict.fromkeys(restored.get(value, value) for value in declared_refs))
                    source_hash = _sha(json.dumps(
                        [(fact_id, fact_texts.get(fact_id, "")) for fact_id in repaired],
                        separators=(",", ":"),
                    ))
                    element.attrib.update({
                        "data-source-refs": " ".join(repaired),
                        "data-da-binding-method": "source_block_digest_prefix_repair",
                        "data-da-claim-text-hash": _sha(claim),
                        "data-da-source-text-hash": source_hash,
                        "data-da-binding-policy": GROUNDING_BINDING_POLICY_VERSION,
                        "data-da-normalization-policy": CLAIM_NORMALIZATION_POLICY_VERSION,
                    })
                    auto_binding_audit.extend({
                        "factId": fact_id, "claimTextHash": _sha(claim),
                        "sourceTextHash": source_hash,
                    } for fact_id in dict.fromkeys(restored.values()))
                    continue
            candidates = [
                candidate
                for candidate in (fact_identity_index.get(_normalized_claim_identity(claim)) or [])
                if candidate[1] and candidate[1] <= set(lineage)
            ]
            binding_method = "unknown_id_exact_repair"
            if not candidates and _local_name(element.tag) in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                heading_match = _unique_heading_prefix_fact_match(
                    claim,
                    lineage=lineage,
                    catalog=catalog_entries,
                )
                if heading_match is not None:
                    candidates = [heading_match]
                    binding_method = "unknown_id_heading_prefix_repair"
            if len(candidates) != 1:
                continue
            fact_id, _fact_lineage, source_hash = candidates[0]
            repaired_refs = list(dict.fromkeys([
                fact_id if value in unknown_refs else value
                for value in declared_refs
            ]))
            element.attrib.update({
                "data-source-refs": " ".join(repaired_refs),
                "data-da-binding-method": binding_method,
                "data-da-claim-text-hash": _sha(claim),
                "data-da-source-text-hash": source_hash,
                "data-da-binding-policy": GROUNDING_BINDING_POLICY_VERSION,
                "data-da-normalization-policy": CLAIM_NORMALIZATION_POLICY_VERSION,
            })
            auto_binding_audit.append({
                "factId": fact_id,
                "claimTextHash": _sha(claim),
                "sourceTextHash": source_hash,
            })
        if advisory_review:
            for element in slide.iter():
                declared = (element.get('data-source-refs') or '').split()
                unknown = [ref for ref in declared if ref not in fact_allowlist]
                binding = element.get('data-bind', '')
                invalid_metric = bool(binding) and binding.removeprefix('metric:') not in metric_allowlist
                if unknown or invalid_metric:
                    reviewed_unlinked_claims.append({'slide': ordinal, 'elementKey': element.get('data-da-element-key'),
                        'textSha256': _sha(_independent_claim_text(element)), 'code': 'unknown_evidence_reference',
                        'declaredReferences': unknown, 'declaredBinding': binding if invalid_metric else None})
                    element.attrib['data-source-refs'] = ' '.join(ref for ref in declared if ref in fact_allowlist)
                    if invalid_metric:
                        element.attrib.pop('data-bind', None)
        explicit_facts = {
            fact_id
            for element in slide.iter()
            for fact_id in (element.attrib.get("data-source-refs") or "").split()
        }
        explicit_metrics = {
            element.attrib["data-bind"].removeprefix("metric:")
            for element in slide.iter()
            if element.attrib.get("data-bind", "").startswith("metric:")
        }
        if not explicit_facts <= fact_allowlist:
            diagnostics = None
            if compiler_version in {FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
                diagnostics = []
                for element in slide.iter():
                    unknown = sorted(set((element.attrib.get("data-source-refs") or "").split()) - fact_allowlist)
                    if not unknown:
                        continue
                    identifiers = ", ".join(value[:128] for value in unknown[:4])
                    diagnostics.append({
                        "severity": "error", "category": "grounding", "code": "grounded_fact_unknown",
                        "message": "Unknown data-source-refs: " + identifiers + ". Copy the exact supporting fact IDs from sourceFacts/requiredSourceCoverage; do not construct or truncate block-based IDs. Preserve the claim and every contributing source page.",
                        "blocking": True, "tagName": _local_name(element.tag), "sectionOrdinal": ordinal,
                    })
                    if len(diagnostics) == 128:
                        break
            raise HtmlDeckCompileError("grounded_fact_unknown", "Deck HTML references an unknown grounded fact.", issues=diagnostics)
        if not explicit_metrics <= metric_allowlist:
            raise HtmlDeckCompileError("grounded_metric_unknown", "Deck HTML references an unknown grounded metric.")
        reconciled_sources = {
            source_id for fact_id in explicit_facts for source_id in fact_sources.get(fact_id, [])
        }
        for metric_key in explicit_metrics:
            reconciled_sources.update(canonical_metric_sources.get(metric_key, []))
        lineage = [source_id for source_id in source_ids if source_id in set(lineage) | reconciled_sources]
        slide.attrib["data-source-slide-ids"] = " ".join(lineage)
        bound_entries = _auto_bind_exact_claims(slide, lineage=lineage, identity_index=fact_identity_index)
        auto_binding_audit.extend(bound_entries)
        if compiler_version in {
            ROOT_SCOPING_COMPILER_VERSION,
            FOREGROUND_GUARD_COMPILER_VERSION,
        }:
            # V10 and V11 used the operation identity directly. Preserve that
            # exact historical derivation for immutable checkpoint replay.
            element_identity_scope = persistence_identity_scope
        elif compiler_version in {
            REPLAY_COMPILER_VERSION,
            ALT_TEXT_COMPILER_VERSION,
            PREVIOUS_CURRENT_COMPILER_VERSION,
            DENSE_METRICS_COMPILER_VERSION,
            EDITORIAL_DENSITY_COMPILER_VERSION,
            VISUAL_SUBSTANCE_COMPILER_VERSION,
            PRESENTATION_PROOF_COMPILER_VERSION,
            READABLE_BODY_COMPILER_VERSION,
            OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
            AUTO_GRID_BODY_COMPILER_VERSION,
            AUTO_GRID_ITEM_COMPILER_VERSION,
            SVG_TEXT_GROUNDING_COMPILER_VERSION,
            RECT_GEOMETRY_COMPILER_VERSION,
            VIEWPORT_GEOMETRY_COMPILER_VERSION, INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION,
            SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
        } and persistence_identity_scope:
            # A provider checkpoint can be promoted through more than one
            # compiler without another paid request. Namespace current IDs so
            # a newer compilation cannot collide with the historical rows.
            element_identity_scope = f"{persistence_identity_scope}:{compiler_version}"
        else:
            element_identity_scope = None
        elements = _compile_elements(
            slide,
            section_id,
            persistence_identity_scope=element_identity_scope,
            allow_svg_text_grounding=svg_text_grounding,
            preserve_review_keys=advisory_review,
        )
        referenced_facts = {fact for item in elements for fact in item["sourceFactIds"]}
        referenced_metrics = {metric for item in elements for metric in item["metricKeys"]}
        if not referenced_facts <= fact_allowlist:
            raise HtmlDeckCompileError("grounded_fact_unknown", "Deck HTML references an unknown grounded fact.")
        if any(
            not fact_sources.get(fact_id) and not canonical_non_slide_fact(fact_id)
            for fact_id in referenced_facts
        ):
            raise HtmlDeckCompileError(
                "grounded_fact_lineage_missing",
                "Referenced facts require slide lineage or canonical non-slide provenance.",
            )
        if any(not set(fact_sources[fact_id]) <= set(lineage) for fact_id in referenced_facts):
            raise HtmlDeckCompileError(
                "grounded_fact_lineage_mismatch",
                "Every referenced grounded fact must remain wholly inside canonical section lineage.",
            )
        if not referenced_metrics <= metric_allowlist:
            raise HtmlDeckCompileError("grounded_metric_unknown", "Deck HTML references an unknown grounded metric.")
        if any(not set(canonical_metric_sources.get(metric_key, [])) <= set(lineage) for metric_key in referenced_metrics):
            raise HtmlDeckCompileError(
                "grounded_metric_lineage_mismatch",
                "Every referenced grounded metric must remain wholly inside canonical section lineage.",
            )
        required_source_ids = {
            source_id
            for fact_id in referenced_facts
            for source_id in fact_sources.get(fact_id, [])
        }
        for metric_key in referenced_metrics:
            metric_sources = set(canonical_metric_sources.get(metric_key, []))
            if not metric_sources:
                raise HtmlDeckCompileError("grounded_metric_lineage_missing", "A used grounded metric requires exact source-slide lineage.")
            required_source_ids.update(metric_sources)
        if required_source_ids & set(omissions):
            raise HtmlDeckCompileError(
                "source_omission_has_evidence",
                "A cited source cannot be repaired into lineage while also declared omitted.",
            )
        final_lineage_set = set(lineage) | required_source_ids
        lineage = [source_id for source_id in source_ids if source_id in final_lineage_set]
        slide.attrib["data-source-slide-ids"] = " ".join(lineage)
        covered.update(lineage)
        for source_id in lineage:
            if referenced_facts & source_fact_ids[source_id] or referenced_metrics & source_metric_keys[source_id]:
                evidence_backed.add(source_id)
        for source_id in omissions:
            if source_fact_ids[source_id] or source_metric_keys[source_id]:
                raise HtmlDeckCompileError(
                    "source_omission_has_evidence",
                    "A requested source with supplied facts or metrics cannot be marked omitted.",
                )
            explicitly_omitted.add(source_id)
        for element in slide.iter():
            text = _independent_claim_text(element)
            is_factual_text = _local_name(element.tag) in _FACTUAL_TEXT_TAGS or (
                _local_name(element.tag) in grounded_inline_tags and _has_grounding(element)
            )
            is_presentational = _unbound_text_is_clearly_presentational(text)
            reviewed = (ordinal, _sha(text)) in reviewed_identities
            if reviewed and is_factual_text and not is_presentational and not _has_grounding(element):
                reviewed_unlinked_claims.append({"slide": ordinal, "elementKey": element.attrib.get("data-da-element-key"), "textSha256": _sha(text)})
            if is_factual_text and not is_presentational and not reviewed and re.search(r"(?<![A-Za-z])[-+]?\d[\d,.]*%?", text):
                has_fact = bool((element.attrib.get("data-source-refs") or "").split())
                has_metric = element.attrib.get("data-bind", "").startswith("metric:")
                if not has_fact and not has_metric:
                    raise HtmlDeckCompileError("unsupported_numeric_claim", "Numeric claims require an exact fact or metric binding.")
                if compiler_version == COMPILER_VERSION and has_fact and not has_metric:
                    referenced_texts = [
                        candidate
                        for fact_id in (element.attrib.get("data-source-refs") or "").split()
                        for candidate in [fact_texts.get(fact_id, ""), *fact_claim_texts.get(fact_id, [])]
                        if candidate
                    ]
                    validate_semantic_numeric_claim(text, referenced_texts)
                    for identity, value in _numeric_semantic_observations(text):
                        previous = numeric_observations.get(identity)
                        if previous is not None and previous[0] != value and previous[1] != ordinal:
                            raise HtmlDeckCompileError(
                                "cross_slide_numeric_contradiction",
                                "Slides contain conflicting values for the same category, period and status.",
                            )
                        numeric_observations[identity] = (value, ordinal)
            if (
                is_factual_text and not reviewed
                and not (element.attrib.get("data-source-refs") or "").split()
                and not element.attrib.get("data-bind", "").startswith("metric:")
                and not is_presentational
            ):
                raise HtmlDeckCompileError("unsupported_factual_claim", "Ordinary factual claims require an allowed exact source-fact reference.", issues=[{
                    "severity": "error", "category": "grounding", "code": "unsupported_factual_claim",
                    "message": "This text needs an exact supporting source-fact reference or a reviewed non-factual disposition.",
                    "blocking": True, "sectionOrdinal": ordinal, "tagName": _local_name(element.tag),
                    "elementKey": element.attrib.get("data-da-element-key"), "textSha256": _sha(text),
                }])
            if element.attrib.get("data-component") == "chart" and not element.attrib.get("data-bind", "").startswith("metric:"):
                raise HtmlDeckCompileError("chart_binding_invalid", "Charts require an exact metric binding.")
        _apply_metric_bindings(slide, bindings)
        section_html = _serialize(slide)
        section_hash = _sha(section_html)
        slide_manifests.append({
            "sectionId": section_id,
            "slideKey": section_id,
            "slot": slot,
            "ordinal": ordinal,
            "title": title[:200],
            "slug": slug,
            "purpose": slide.attrib.get("data-slide-purpose") or "general",
            "planSlideId": slide.attrib.get("data-plan-slide-id") or None,
            "visualPrimitive": slide.attrib.get("data-visual-primitive") or None,
            "plannedEvidenceIds": _planning_ids(slide, "data-evidence-ids"),
            "plannedCalculationIds": _planning_ids(slide, "data-calculation-ids"),
            "sourceSlideIds": lineage,
            "omittedSourceSlideIds": omissions,
            "sourceLineage": [{"sourceSlideId": source_id, "order": index, "role": "evidence"} for index, source_id in enumerate(lineage)],
            "htmlContentHash": section_hash,
            "elements": elements,
            "groundingBindingAudit": {
                "bindingPolicyVersion": GROUNDING_BINDING_POLICY_VERSION,
                "normalizationPolicyVersion": CLAIM_NORMALIZATION_POLICY_VERSION,
                "exactAutoBoundElementCount": len(bound_entries),
                "factIds": sorted({entry["factId"] for entry in bound_entries}),
                "claimTextHashes": sorted({entry["claimTextHash"] for entry in bound_entries}),
                "sourceTextHashes": sorted({entry["sourceTextHash"] for entry in bound_entries}),
            },
            "interactiveStatus": "compiled_static",
            "renderProofStatus": "pending",
            "previewImageStatus": "pending",
        })
    if covered != selected_id_set and not advisory_review:
        raise HtmlDeckCompileError("source_coverage_incomplete", "Generated section lineage does not exactly cover selected source slides.")
    # The trusted context, not provider-declared section lineage, determines
    # whether a source has any evidence available to use. Persist an explicit
    # omission for genuinely evidence-empty sources even when the provider did
    # not add the optional HTML marker.
    explicitly_omitted.update(
        source_id
        for source_id in source_ids
        if not source_fact_ids[source_id] and not source_metric_keys[source_id]
    )
    if evidence_backed & explicitly_omitted:
        raise HtmlDeckCompileError("source_evidence_coverage_invalid", "A requested source cannot be both evidenced and omitted.")
    evidence_accounted = evidence_backed | explicitly_omitted
    if evidence_accounted != selected_id_set and not advisory_review:
        raise HtmlDeckCompileError(
            "source_evidence_coverage_incomplete",
            "Every requested source requires a used source fact/metric or an explicit validated no-evidence omission.",
        )
    if advisory_review:
        sanitized_css = restore_slide_root_css(sanitized_css)
    head = next((node for node in document.iter() if _local_name(node.tag) == "head"), None)
    if head is None:
        raise HtmlDeckCompileError("document_head_missing", "HTML5 recovery did not produce a document head.")
    style = ET.SubElement(head, _HTML_NS + "style")
    style.text = sanitized_css
    sanitized_html = "<!doctype html>\n" + _serialize(document)
    if len(sanitized_html.encode("utf-8")) > max_html_bytes:
        raise HtmlDeckCompileError("html_budget_exceeded", "Sanitized deck HTML exceeds the configured byte budget.")
    sanitized_hash = _sha(sanitized_html)
    dependency_identity = {
        "html": sanitized_hash,
        "css": _sha(sanitized_css),
        "compiler": compiler_version,
        "sanitizer": SANITIZER_POLICY_VERSION,
        "grounding": grounding_snapshot_hash,
    }
    if compiler_version in MODERN_COMPILER_VERSIONS:
        dependency_identity["wholeDeckHtmlMaxBytes"] = max_html_bytes
    if compiler_version in {INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        dependency_identity["presentationIntent"] = presentation_intent
    if reviewed_identities:
        dependency_identity['draftClaimInventory'] = sorted(reviewed_identities)
        dependency_identity['evidencePolicy'] = 'advisory-draft.v1'
    dependency_payload = json.dumps(
        dependency_identity, sort_keys=True, separators=(",", ":")
    )
    compilation_hash = _sha(dependency_payload)
    safe_documents = tuple(
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080">'
        f"<title>{escape(str(item['title']))}</title>"
        f"<style>{RENDER_SHELL_CSS}{sanitized_css}</style></head><body>{_serialize(slide)}</body></html>"
        for item, slide in zip(slide_manifests, slides)
    )
    if any(len(document_value.encode("utf-8")) > MAX_RENDER_DOCUMENT_BYTES for document_value in safe_documents):
        raise HtmlDeckCompileError(
            "render_document_budget_exceeded",
            "Sanitized slide render document exceeds the independent renderer byte limit.",
        )
    for item, document_value in zip(slide_manifests, safe_documents):
        item["renderDocumentHash"] = _sha(document_value)
    requested_source_ids = list(source_ids)
    covered_source_ids = [source_id for source_id in requested_source_ids if source_id in covered]
    missing_source_ids = [source_id for source_id in requested_source_ids if source_id not in covered]
    traceability_manifest: list[dict[str, Any]] = []
    for fact_id in fact_id_list:
        trace = fact_traceability.get(fact_id) or {}
        traceability_manifest.append({
            "factId": fact_id,
            "sourceType": str(trace.get("sourceType") or "legacy"),
            "sourceId": str(trace.get("sourceId") or fact_id),
            "sourceSlideIds": fact_sources[fact_id],
        })
    metric_traceability_manifest: list[dict[str, Any]] = []
    for metric_key in metric_key_list:
        trace = canonical_metric_traceability[metric_key]
        metric_traceability_manifest.append({
            "metricKey": metric_key,
            "sourceType": str(trace.get("sourceType") or "unknown"),
            "sourceId": str(trace.get("sourceId") or metric_key),
            "sourceSlideIds": canonical_metric_sources[metric_key],
        })
    manifest = {
        "contractVersion": MANIFEST_CONTRACT_VERSION,
        "outputContract": OUTPUT_CONTRACT,
        "renderMode": RENDER_MODE,
        "parserVersion": PARSER_VERSION,
        "compilerVersion": compiler_version,
        "sanitizerPolicyVersion": SANITIZER_POLICY_VERSION,
        "rendererVersion": RENDERER_VERSION,
        "canvas": CANVAS,
        "contentHash": sanitized_hash,
        "compilationHash": compilation_hash,
        "draftReferenceWarnings": reviewed_unlinked_claims,
        "draftVisualPlanWarnings": visual_plan_warnings,
        "visualPlanCompliance": {
            "status": "failed_advisory" if visual_plan_warnings else "passed",
            "failureCount": len(visual_plan_warnings),
            "resolvedVisualAssetIds": resolved_visual_asset_ids,
        },
        "evidencePolicy": "advisory-draft.v1" if advisory_review else "strict",
        "draftIssueSlides": sorted(draft_issues),
        "groundingSnapshotHash": grounding_snapshot_hash,
        "requestedSourceSlideCount": len(requested_source_ids),
        "generatedSlideCount": len(slide_manifests),
        "sourceCoverage": {
            "requestedSourceSlideIds": requested_source_ids,
            "coveredSourceSlideIds": [source_id for source_id in requested_source_ids if source_id in evidence_backed],
            "evidenceBackedSourceSlideIds": [source_id for source_id in requested_source_ids if source_id in evidence_backed],
            "omittedSourceSlideIds": [source_id for source_id in requested_source_ids if source_id in explicitly_omitted],
            "missingSourceSlideIds": [source_id for source_id in requested_source_ids if source_id not in evidence_accounted],
            "complete": evidence_accounted == selected_id_set,
        },
        "groundedFactTraceability": traceability_manifest,
        "groundedMetricTraceability": metric_traceability_manifest,
        "groundingBindingAudit": {
            "bindingPolicyVersion": GROUNDING_BINDING_POLICY_VERSION,
            "normalizationPolicyVersion": CLAIM_NORMALIZATION_POLICY_VERSION,
            "exactAutoBoundElementCount": len(auto_binding_audit),
            "factIds": sorted({entry["factId"] for entry in auto_binding_audit}),
            "claimTextHashes": sorted({entry["claimTextHash"] for entry in auto_binding_audit}),
            "sourceTextHashes": sorted({entry["sourceTextHash"] for entry in auto_binding_audit}),
        },
        "coverageComplete": True,
        "slides": slide_manifests,
        "issues": issues,
        "interactiveStatus": "compiled_static",
        "renderProofStatus": "pending",
        "previewImageStatus": "pending",
        "renderedVisualAssetIds": sorted(set(resolved_visual_asset_ids)),
    }
    if compiler_version in {INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        manifest["presentationIntent"] = presentation_intent
    return CompiledHtmlDeck(
        sanitized_html=sanitized_html,
        safe_slide_documents=safe_documents,
        manifest=manifest,
        issues=tuple(issues),
        raw_sha256=_sha(raw_bytes),
        sanitized_sha256=sanitized_hash,
        compilation_hash=compilation_hash,
        compiler_version=compiler_version,
        max_html_bytes=max_html_bytes,
    )
