from __future__ import annotations

import json
import logging
import math
import re
import socket
import ssl
import xml.etree.ElementTree as ElementTree
from http.client import HTTPConnection, HTTPSConnection, HTTPException as HttpClientException
from hashlib import sha256
from ipaddress import ip_address
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

try:
    import fitz
except Exception as _fitz_import_error:  # pragma: no cover - optional image decoder fallback
    # FIX 5: PyMuPDF was silently falling back. Now we log a warning so operators know
    # that raster palette extraction will be unavailable and all images will fall through
    # to seed-based palettes.
    fitz = None
    logger.warning(
        "PyMuPDF (fitz) is not available; raster image palette extraction is disabled. "
        "Install PyMuPDF to enable logo/favicon color sampling: %s",
        _fitz_import_error,
    )

from app.core.security import generate_id
from app.core.config import settings
from app.db.models import Deck, DeckBrandAsset, DeckBrandProfile, DeckInputSource, DeckSlide, DeckSlideAsset, DeckSlideBlock
from app.schemas.brand_profile import DeckBrandProfilePayload, normalize_branding_json_payload
from app.services.brand.brand_source_labels import build_brand_source_labels, normalize_brand_source_labels
from app.services.brand.deterministic_swatches import with_deterministic_swatch_contract
from app.services.storage.deck_file_service import resolve_upload_path
from app.services.storage.upload_scan import scan_upload_path
from app.services.storage.upload_security import read_limited_upload
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.services.brand.website_context import build_website_context, normalize_website_url

_SVG_HEX_PATTERN = re.compile(
    r'(?:fill|stroke|stop-color)=["\'](#[0-9a-fA-F]{3,8})["\']|(?:fill|stroke|stop-color):\s*(#[0-9a-fA-F]{3,8})'
)
_COLOR_VALUE_PATTERN = re.compile(r"(#[0-9a-fA-F]{3,8}|rgb\([^)]*\)|rgba\([^)]*\))")
_EXPLICIT_BRAND_CSS_PATTERN = re.compile(
    r"--(?P<name>[\w-]+)\s*:\s*(?P<color>#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))",
    flags=re.IGNORECASE,
)
_URL_FETCH_TIMEOUT_SECONDS = 4
_URL_FETCH_TEXT_BYTES = 200_000
_URL_FETCH_IMAGE_BYTES = 512_000
_URL_FETCH_CSS_BYTES = 120_000
_URL_FETCH_ICON_MAX = 8
WEBSITE_BRAND_EVIDENCE_VERSION = "website-brand-evidence.v2"
SOURCE_BRAND_POLICY = "deterministic-source-brand.v1"
_CONFIRMED_WEBSITE_READY_SOURCES = {"url_live_asset", "url_live_colors", "logo_live_asset", "manual"}
MAX_LOGO_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_BRAND_GUIDELINES_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
_GENERIC_BINARY_TYPES = {"", "application/octet-stream"}
LOGO_UPLOAD_TYPES = {
    ".gif": {"image/gif"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}
BRAND_GUIDELINES_UPLOAD_TYPES = {
    ".doc": {"application/msword"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".md": {"text/markdown", "text/plain"},
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _normalize_hex(input_value: str) -> str:
    sanitized = re.sub(r"[^0-9a-fA-F]", "", input_value)[:6]
    return f"#{sanitized.ljust(6, '0').upper()}"


def _hash_string(value: str) -> int:
    hash_value = 0
    for character in value:
        hash_value = (hash_value * 31 + ord(character)) & 0xFFFFFFFF
    return hash_value or 1


def _hash_bytes(value: bytes) -> int:
    hash_value = 0
    for byte in value:
        hash_value = (hash_value * 33 + byte) & 0xFFFFFFFF
    return hash_value or 1


class _PinnedHTTPConnection(HTTPConnection):
    def __init__(self, hostname: str, resolved_ip: str, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout)
        self._resolved_ip = resolved_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._resolved_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(self, hostname: str, resolved_ip: str, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self._resolved_ip = resolved_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection((self._resolved_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _public_request_target(url: str) -> tuple[str, list[str], int, str] | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        return None
    try:
        resolved = {
            entry[4][0]
            for entry in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        }
    except (OSError, UnicodeError):
        return None
    if not resolved:
        return None
    for value in resolved:
        try:
            address = ip_address(value)
        except ValueError:
            return None
        if not address.is_global or address.is_private or address.is_loopback or address.is_link_local:
            return None
    request_path = parsed.path or "/"
    if parsed.query:
        request_path += f"?{parsed.query}"
    return parsed.scheme, sorted(resolved), port, request_path


def _safe_request(
    url: str,
    *,
    timeout_seconds: int = _URL_FETCH_TIMEOUT_SECONDS,
    max_bytes: int = _URL_FETCH_TEXT_BYTES,
    allowed_mime_prefixes: tuple[str, ...] | None = None,
    allow_redirects: bool = True,
) -> tuple[bytes | None, str | None]:
    try:
        current_url = url
        for _redirect in range(4):
            target = _public_request_target(current_url)
            if target is None:
                return None, None
            scheme, resolved_ips, port, request_path = target
            parsed = urlparse(current_url)
            connection_type = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
            host_header = str(parsed.hostname) if port in {80, 443} else f"{parsed.hostname}:{port}"
            connection = None
            response = None
            for resolved_ip in resolved_ips:
                candidate = connection_type(str(parsed.hostname), resolved_ip, port, timeout_seconds)
                try:
                    candidate.request(
                        "GET",
                        request_path,
                        headers={
                            "Host": host_header,
                            "User-Agent": "Deck-AI-Stack-Brand-Sampler/1.0",
                            "Accept": "text/html, text/css, image/*, */*;q=0.8",
                        },
                    )
                    response = candidate.getresponse()
                    connection = candidate
                    break
                except (OSError, TimeoutError, ssl.SSLError, HttpClientException):
                    candidate.close()
            if connection is None or response is None:
                return None, None
            if response.status in {301, 302, 303, 307, 308}:
                if not allow_redirects:
                    connection.close()
                    return None, None
                location = response.getheader("location")
                connection.close()
                if not location:
                    return None, None
                current_url = urljoin(current_url, location)
                continue
            if response.status < 200 or response.status >= 300:
                content_type = response.headers.get("content-type", "").lower()
                connection.close()
                return None, content_type
            content_type = response.headers.get("content-type", "").lower()
            if allowed_mime_prefixes is not None and not any(
                content_type.startswith(prefix) for prefix in allowed_mime_prefixes
            ):
                connection.close()
                return None, content_type

            try:
                payload = bytearray()
                while len(payload) < max_bytes:
                    chunk = response.read(max_bytes - len(payload))
                    if not chunk:
                        break
                    payload.extend(chunk)
                return bytes(payload), content_type
            finally:
                connection.close()
        return None, None
    except (OSError, ValueError, TimeoutError, ssl.SSLError, HttpClientException):
        return None, None


def _normalize_hex_candidate(raw_color: str) -> str | None:
    if not raw_color:
        return None
    value = raw_color.strip().lower()
    if value.startswith("rgb"):
        value = value.replace("rgba(", "").replace("rgb(", "").replace(")", "")
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if len(parts) < 3:
            return None
        try:
            red = max(0, min(255, int(float(parts[0]))))
            green = max(0, min(255, int(float(parts[1]))))
            blue = max(0, min(255, int(float(parts[2]))))
        except ValueError:
            return None
        return _rgb_to_hex(red, green, blue)

    if not value.startswith("#"):
        return None

    normalized = re.sub(r"[^0-9a-fA-F]", "", value)[:6]
    if not normalized:
        return None

    return f"#{normalized.ljust(6, '0').upper()}"


def _extract_colors_from_text(raw_text: str) -> list[str]:
    matches = _COLOR_VALUE_PATTERN.findall(raw_text)
    if not matches:
        return []
    normalized: list[str] = []
    for value in matches:
        normalized_value = _normalize_hex_candidate(value)
        if normalized_value is None:
            continue
        if normalized_value not in normalized:
            normalized.append(normalized_value)
    return normalized


def _palette_from_color_values(values: list[str], seed: int) -> dict[str, str | list[str] | list[dict]] | None:
    samples: list[tuple[int, int, int]] = []
    for value in values:
        try:
            samples.append(_hex_to_rgb(value))
        except ValueError:
            continue
    if not samples:
        return None
    palette = _palette_from_ranked_colors(_rank_rgb_samples(samples), seed)
    palette["candidates"] = values[:12]
    return palette


def _observed_palette_values(palette: dict[str, object]) -> list[str]:
    """Return sampled colours without recycling generated support roles."""
    values = palette.get("observedCandidates")
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(
        normalized
        for value in values
        if isinstance(value, str)
        for normalized in [_normalize_hex_candidate(value)]
        if normalized
    ))


def _preferred_deck_palette_values(
    vector_values: list[str],
    raster_values: list[str],
) -> list[str]:
    """Prefer layout/design ink over colours sampled from slide photography."""
    def normalized(values: list[str]) -> list[str]:
        return list(dict.fromkeys(
            color
            for value in values
            if isinstance(value, str)
            for color in [_normalize_hex_candidate(value)]
            if color
        ))

    observed_vector = normalized(vector_values)
    return observed_vector or normalized(raster_values)


def _source_design_palette(values: list[str], seed: int) -> dict | None:
    """Resolve exact source design ink into one palette, without photo hues."""
    observed = [c for v in values if (c := _normalize_hex_candidate(v))]
    palette = _palette_from_color_values(observed, seed)
    if not palette:
        return None
    colors = list(dict.fromkeys(observed))
    primary = min(colors, key=lambda c: _color_distance(_hex_to_rgb(c), _hex_to_rgb(palette['primary'])))
    light = [c for c in colors if _relative_luminance(_hex_to_rgb(c)) > .65]
    background = max(light, key=observed.count) if light else palette['background']
    def contrast(color):
        a, b = sorted([_relative_luminance(_hex_to_rgb(color)), _relative_luminance(_hex_to_rgb(background))])
        return (b + .05) / (a + .05)
    text = primary if contrast(primary) >= 4.5 else max(colors + ['#000000', '#FFFFFF'], key=contrast)
    palette.update(primary=primary, secondary=background, accent=primary, background=background,
        surface=background, text=text, palette=list(dict.fromkeys([primary, background, text])),
        observedCandidates=colors,
        roleOrigins={role: ('observed_source_design' if value in colors else 'generated_accessibility_role')
            for role, value in {'primary':primary,'secondary':background,'accent':primary,'background':background,'text':text}.items()})
    return palette


class _UrlBrandHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_tags: list[dict[str, str]] = []
        self.link_tags: list[dict[str, str]] = []
        self.style_contents: list[str] = []
        self.style_attributes: list[str] = []
        self.brand_asset_urls: list[str] = []
        self._style_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag == "meta":
            self.meta_tags.append(normalized)
        elif tag == "link":
            self.link_tags.append(normalized)
        elif tag == "style":
            self._style_chunks = []
        else:
            if tag == "img":
                descriptor = " ".join(
                    normalized.get(key, "") for key in ("alt", "class", "id", "data-testid")
                ).lower()
                source = normalized.get("src", "")
                if source and "logo" in descriptor:
                    self.brand_asset_urls.append(source)
            style_value = normalized.get("style")
            if style_value:
                self.style_attributes.append(style_value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self._style_chunks is not None:
            self.style_contents.append(" ".join(self._style_chunks))
            self._style_chunks = None

    def handle_data(self, data: str) -> None:
        if self._style_chunks is not None:
            self._style_chunks.append(data)


def _extract_stylesheet_urls(html_text: str) -> list[str]:
    pattern = re.compile(r"<link[^>]+rel\s*=\s*[\"\']?stylesheet[\"\']?[^>]*>", flags=re.IGNORECASE)
    href_pattern = re.compile(r"href\s*=\s*([\"'])(.*?)\1", flags=re.IGNORECASE)

    links: list[str] = []
    for link_tag in pattern.finditer(html_text):
        href_match = href_pattern.search(link_tag.group(0))
        if not href_match:
            continue
        href = href_match.group(2).strip()
        if href:
            links.append(href)
    return links


def _extract_asset_colors(url: str, *, seed: int) -> tuple[dict[str, str | list[str] | list[dict]] | None, dict]:
    payload, _ = _safe_request(
        url,
        timeout_seconds=_URL_FETCH_TIMEOUT_SECONDS,
        max_bytes=_URL_FETCH_IMAGE_BYTES,
    )
    if not payload:
        return None, {}

    candidate_file = urlparse(url).path.split("/")[-1] or "favicon.png"
    if candidate_file.lower().endswith(".svg") or candidate_file.lower().endswith(".svgz"):
        try:
            svg_palette = _extract_svg_palette(payload.decode("utf-8", errors="ignore"))
            if svg_palette:
                palette = _palette_from_observed_brand_colors(svg_palette)
                if palette is not None:
                    return palette, {"sampledAssetUrl": url, "sampledAssetSha256": sha256(payload).hexdigest()}
        except Exception:
            pass

    raster_palette = _extract_raster_palette(payload, candidate_file)
    if raster_palette is not None:
        return raster_palette, {"sampledAssetUrl": url, "sampledAssetSha256": sha256(payload).hexdigest()}

    return None, {"sampledAssetUrl": url, "sampledAssetSha256": sha256(payload).hexdigest()}


def _finalize_website_evidence(evidence: dict[str, object]) -> dict[str, object]:
    canonical = {
        "contractVersion": WEBSITE_BRAND_EVIDENCE_VERSION,
        "algorithmVersion": "website-palette-v2",
        **evidence,
    }
    canonical["evidenceSha256"] = sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return canonical


def _resolved_brand_roles(palette: dict[str, object]) -> dict[str, dict[str, object]]:
    origins = palette.get("roleOrigins") if isinstance(palette.get("roleOrigins"), dict) else {}
    return {
        role: {"value": palette.get(role), "origin": origins.get(role)}
        for role in ("primary", "secondary", "accent")
    }


def _merge_explicit_website_roles(
    palette: dict[str, object],
    explicit_role_values: dict[str, list[str]],
) -> tuple[dict[str, object], list[str]]:
    """Keep asset primary, but honor semantically named website support roles."""
    merged = dict(palette)
    origins = dict(palette.get("roleOrigins") or {})
    merged_roles: list[str] = []
    for role in ("secondary", "accent"):
        values = explicit_role_values.get(role) or []
        if not values:
            continue
        merged[role] = values[0]
        origins[role] = "observed_website_explicit"
        merged_roles.append(role)
    merged["roleOrigins"] = origins
    merged["palette"] = [merged["primary"], merged["secondary"], merged["accent"], merged["surface"], merged["text"]]
    return merged, merged_roles


def _with_website_asset_provenance(palette: dict[str, object]) -> dict[str, object]:
    mapped = dict(palette)
    origins = dict(palette.get("roleOrigins") or {})
    mapped["roleOrigins"] = {
        role: "observed_website_asset" if origin == "observed_brand_candidate" else origin
        for role, origin in origins.items()
    }
    return mapped


def _palette_from_website_url(website_url: str, *, seed: int) -> tuple[dict[str, str | list[str] | list[dict]] | None, dict]:
    page_payload, _ = _safe_request(
        website_url,
        timeout_seconds=_URL_FETCH_TIMEOUT_SECONDS,
        max_bytes=_URL_FETCH_TEXT_BYTES,
    )
    if not page_payload:
        return None, _finalize_website_evidence(
            {"paletteSource": "url_live_unreachable", "sourceUrl": website_url}
        )

    parser = _UrlBrandHtmlParser()
    page_text = page_payload.decode("utf-8", errors="ignore")
    parser.feed(page_text)

    sample_urls: list[str] = []
    explicit_role_values: dict[str, list[str]] = {"primary": [], "secondary": [], "accent": []}
    stylesheet_hashes: list[dict[str, str]] = []

    for meta in parser.meta_tags:
        meta_name = meta.get("name", "").lower()
        meta_content = meta.get("content", "")
        if meta_name in {"theme-color", "msapplication-tilecolor", "msapplication-navbutton-color"}:
            candidate = _normalize_hex_candidate(meta_content)
            if candidate is not None:
                explicit_role_values["primary"].append(candidate)

    for link in parser.link_tags:
        rel = link.get("rel", "").lower()
        href = link.get("href", "").strip()
        if not href:
            continue
        rel_tokens = rel.split()
        is_icon = (
            "icon" in rel_tokens
            or "shortcut" in rel_tokens and "icon" in rel_tokens
            or any(token.startswith("apple-touch-icon") for token in rel_tokens)
            or "manifest" in rel_tokens
        )
        if not is_icon:
            continue
        sample_urls.append(urljoin(website_url, href))

    # A named logo is an explicit brand asset. Generic hero/OG images are not.
    sample_urls = [urljoin(website_url, value) for value in parser.brand_asset_urls] + sample_urls

    def collect_explicit_css(raw_css: str) -> None:
        for match in _EXPLICIT_BRAND_CSS_PATTERN.finditer(raw_css):
            candidate = _normalize_hex_candidate(match.group("color"))
            if candidate is None:
                continue
            name = match.group("name").lower()
            tokens = [token for token in re.split(r"[-_]+", name) if token]
            # Framework variables (--bs-primary), generic semantic variables
            # (--primary-background), and brand backgrounds are not explicit
            # declarations of brand ink. Require a distinct brand namespace.
            declared_roles = [role for role in ("primary", "secondary", "accent") if role in tokens]
            if (
                "brand" not in tokens
                or len(declared_roles) != 1
                or any(token in {"background", "surface", "canvas"} for token in tokens)
            ):
                continue
            role = declared_roles[0]
            if candidate not in explicit_role_values[role]:
                explicit_role_values[role].append(candidate)

    for block in parser.style_contents:
        collect_explicit_css(block)
    for style_attribute in parser.style_attributes:
        collect_explicit_css(style_attribute)

    for stylesheet_url in _extract_stylesheet_urls(page_text):
        absolute_stylesheet_url = urljoin(website_url, stylesheet_url)
        css_payload, _ = _safe_request(
            absolute_stylesheet_url,
            timeout_seconds=_URL_FETCH_TIMEOUT_SECONDS,
            max_bytes=_URL_FETCH_CSS_BYTES,
            allowed_mime_prefixes=("text/css", "text/plain"),
        )
        if not css_payload:
            continue
        stylesheet_hashes.append(
            {"url": absolute_stylesheet_url, "sha256": sha256(css_payload).hexdigest()}
        )
        try:
            collect_explicit_css(css_payload.decode("utf-8", errors="ignore"))
        except Exception:
            continue

    # Deduplicate sampled URLs and prioritize manifest-like logos / logos and icons.
    prioritized_sample_urls = []
    for sample_url in sample_urls:
        if sample_url in prioritized_sample_urls:
            continue
        prioritized_sample_urls.append(sample_url)
        if len(prioritized_sample_urls) >= _URL_FETCH_ICON_MAX:
            break
    sample_urls = prioritized_sample_urls

    for sample_url in sample_urls:
        palette, evidence = _extract_asset_colors(sample_url, seed=seed)
        if palette is not None:
            palette = _with_website_asset_provenance(palette)
            palette, merged_roles = _merge_explicit_website_roles(palette, explicit_role_values)
            return (
                palette,
                _finalize_website_evidence({
                    "paletteSource": "url_live_asset",
                    "sourceUrl": website_url,
                    "pageContentSha256": sha256(page_payload).hexdigest(),
                    "stylesheetContentHashes": stylesheet_hashes,
                    "explicitRoleValues": explicit_role_values,
                    "explicitRolesMergedWithAsset": merged_roles,
                    "resolvedBrandRoles": _resolved_brand_roles(palette),
                    **evidence,
                    "sampledUrls": sample_urls,
                }),
            )

    explicit_colors = [
        value
        for role in ("primary", "secondary", "accent")
        for value in explicit_role_values[role]
    ]
    if not explicit_colors:
        return None, _finalize_website_evidence({
            "paletteSource": "url_live_no_colors",
            "sourceUrl": website_url,
            "pageContentSha256": sha256(page_payload).hexdigest(),
            "stylesheetContentHashes": stylesheet_hashes,
            "colorValueCount": 0,
            "sampledUrls": sample_urls,
        })

    palette = _palette_from_seed(seed)
    role_origins = {role: "generated_accessibility_role" for role in ("primary", "secondary", "accent", "background", "text")}
    for role in ("primary", "secondary", "accent"):
        if explicit_role_values[role]:
            palette[role] = explicit_role_values[role][0]
            role_origins[role] = "observed_website_explicit"
    palette["palette"] = [palette["primary"], palette["secondary"], palette["accent"], palette["surface"], palette["text"]]
    palette["candidates"] = explicit_colors[:12]
    palette["observedCandidates"] = explicit_colors[:12]
    palette["roleOrigins"] = role_origins

    return (
        palette,
        _finalize_website_evidence({
            "paletteSource": "url_live_colors",
            "sourceUrl": website_url,
            "pageContentSha256": sha256(page_payload).hexdigest(),
            "stylesheetContentHashes": stylesheet_hashes,
            "colorValueCount": len(explicit_colors),
            "explicitRoleValues": explicit_role_values,
            "resolvedBrandRoles": _resolved_brand_roles(palette),
            "sampledUrls": sample_urls[:6],
        }),
    )


def _palette_from_deck_visuals(db: Session, deck: Deck, *, seed: int) -> tuple[dict[str, str | list[str] | list[dict]] | None, dict]:
    vector_color_values: list[str] = []
    raster_color_values: list[str] = []
    sampled_sources: list[dict[str, object]] = []

    slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck.id)
        .order_by(DeckSlide.slide_index.asc())
        .limit(24)
        .all()
    )

    for slide in slides:
        metadata = slide.metadata_json if isinstance(slide.metadata_json, dict) else {}
        vector_colors = metadata.get("vectorColors")
        if isinstance(vector_colors, list):
            normalized_colors = [
                normalized for value in vector_colors
                if isinstance(value, str)
                for normalized in [_normalize_hex_candidate(value)]
                if normalized
            ]
            vector_color_values.extend(normalized_colors)
            if normalized_colors:
                sampled_sources.append({
                    "sourceKind": "pdf_vector_drawing",
                    "slideId": slide.id,
                    "colors": normalized_colors,
                })
        for path_value, source_kind in (
            (slide.rendered_image_path, "rendered_image"),
            (slide.thumbnail_path, "thumbnail"),
        ):
            path = resolve_upload_path(path_value)
            if path is None or not path.exists():
                continue
            payload = path.read_bytes()
            palette = None
            if path.suffix.lower() == ".svg":
                svg_palette = _extract_svg_palette(payload.decode("utf-8", errors="ignore"))
                if svg_palette:
                    palette = _palette_from_color_values(svg_palette, _hash_bytes(payload))
            if palette is None:
                palette = _extract_raster_palette(payload, path.name)
            if palette is None:
                palette = _palette_from_seed(_hash_bytes(payload))
            if palette is None:
                continue

            raster_color_values.extend(_observed_palette_values(palette))
            sampled_sources.append(
                {
                    "sourceKind": source_kind,
                    "slideId": slide.id,
                    "storagePath": path_value,
                }
            )

    assets = (
        db.query(DeckSlideAsset)
        .filter(DeckSlideAsset.deck_id == deck.id, DeckSlideAsset.storage_path.isnot(None))
        .order_by(DeckSlideAsset.created_at.asc())
        .limit(48)
        .all()
    )
    for asset in assets:
        path = resolve_upload_path(asset.storage_path)
        if path is None or not path.exists():
            continue
        payload = path.read_bytes()
        palette = None
        if path.suffix.lower() == ".svg":
            svg_palette = _extract_svg_palette(payload.decode("utf-8", errors="ignore"))
            if svg_palette:
                palette = _palette_from_color_values(svg_palette, _hash_bytes(payload))
        if palette is None:
            palette = _extract_raster_palette(payload, path.name)
        if palette is None:
            palette = _palette_from_seed(_hash_bytes(payload))
        if palette is None:
            continue

        raster_color_values.extend(_observed_palette_values(palette))
        sampled_sources.append(
            {
                "sourceKind": "slide_asset",
                "assetId": asset.id,
                "assetType": asset.asset_type,
                "storagePath": asset.storage_path,
            }
        )

    blocks = (
        db.query(DeckSlideBlock)
        .filter(DeckSlideBlock.deck_id == deck.id)
        .order_by(DeckSlideBlock.slide_id.asc(), DeckSlideBlock.block_index.asc())
        .limit(256)
        .all()
    )
    for block in blocks:
        if block.color_hex:
            normalized = _normalize_hex_candidate(block.color_hex)
            if normalized:
                vector_color_values.append(normalized)
        if block.style_json is not None:
            vector_color_values.extend(_extract_colors_from_text(json.dumps(block.style_json, sort_keys=True)))
        if block.metadata_json is not None:
            vector_color_values.extend(_extract_colors_from_text(json.dumps(block.metadata_json, sort_keys=True)))

    color_values = _preferred_deck_palette_values(vector_color_values, raster_color_values)
    if not color_values:
        return None, {
            "paletteSource": "fallback_deck_seed",
            "fallbackReason": "no_deck_visual_assets",
            "sampledSources": sampled_sources,
        }

    palette = (_source_design_palette(vector_color_values, seed)
        if settings.instant_html_llm_first_beta and vector_color_values
        else _palette_from_color_values(color_values, seed))
    if palette is None:
        return None, {
            "paletteSource": "fallback_deck_seed",
            "fallbackReason": "no_deck_visual_assets",
            "sampledSources": sampled_sources,
        }

    palette["candidates"] = color_values[:12]
    return palette, {
        "paletteSource": "deck_visual",
        "policy": SOURCE_BRAND_POLICY if settings.instant_html_llm_first_beta and vector_color_values else None,
        "selectedEvidenceKind": "vector_or_block" if vector_color_values else "raster_fallback",
        "sampledSources": sampled_sources[:24],
        "sampledColorCount": len(color_values),
    }


def require_supported_brand_upload(
    file_name: str,
    content_type: str | None,
    *,
    upload_types: dict[str, set[str]],
    detail: str,
) -> str:
    suffix = Path(file_name or "").suffix.lower()
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    expected_types = upload_types.get(suffix)
    content_type_allowed = any(
        normalized_content_type in allowed_types for allowed_types in upload_types.values()
    )

    if expected_types is None and not content_type_allowed:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)
    if expected_types is not None and normalized_content_type in _GENERIC_BINARY_TYPES:
        return suffix
    if expected_types is not None and normalized_content_type in expected_types:
        return suffix
    if expected_types is None and content_type_allowed:
        return next(
            extension
            for extension, allowed_types in upload_types.items()
            if normalized_content_type in allowed_types
        )

    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)


async def read_supported_brand_upload(
    upload_file: UploadFile,
    *,
    upload_types: dict[str, set[str]],
    max_size: int,
    type_detail: str,
    too_large_detail: str,
) -> bytes:
    require_supported_brand_upload(
        upload_file.filename or "",
        upload_file.content_type,
        upload_types=upload_types,
        detail=type_detail,
    )
    return await read_limited_upload(
        upload_file,
        max_size=max_size,
        too_large_detail=too_large_detail,
    )


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = _normalize_hex(value).removeprefix("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _deck_font_candidates(db: Session, deck: Deck) -> tuple[list[str], dict[str, object]]:
    """Rank persisted deck fonts by stable weighted text usage."""
    # PDF text blocks are reconstructed from plain text and need not contain
    # styles. The parser preserves exact span-font usage in page metadata.
    page_usage: dict[str, int] = {}
    for slide in db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id).all():
        metadata = slide.metadata_json if isinstance(slide.metadata_json, dict) else {}
        for item in metadata.get('fontUsage', []):
            if not isinstance(item, dict):
                continue
            family = str(item.get('family') or '').strip()
            weight = item.get('weightedUsage')
            if family and isinstance(weight, (int, float)) and weight > 0:
                page_usage[family] = page_usage.get(family, 0) + int(weight)
    if page_usage:
        ranked_fonts = sorted(page_usage, key=lambda name: (-page_usage[name], name.casefold()))
        return ranked_fonts[:5], {'source': 'source_pdf_spans', 'usage': [
            {'family': name, 'weightedUsage': page_usage[name]} for name in ranked_fonts[:12]
        ]}
    blocks = (
        db.query(DeckSlideBlock)
        .filter(DeckSlideBlock.deck_id == deck.id, DeckSlideBlock.font_family.isnot(None))
        .order_by(DeckSlideBlock.slide_id.asc(), DeckSlideBlock.block_index.asc(), DeckSlideBlock.id.asc())
        .all()
    )
    usage: dict[str, dict[str, object]] = {}
    for block in blocks:
        family = " ".join((block.font_family or "").split()).strip(" '\"")
        if not family:
            continue
        key = family.casefold()
        record = usage.setdefault(key, {"family": family, "weight": 0, "blocks": 0, "slides": set()})
        # Stable casing does not depend on database row order or source capitalization.
        if (family.casefold(), family) < (str(record["family"]).casefold(), str(record["family"])):
            record["family"] = family
        text = (block.text or block.normalized_text or block.raw_text or "").strip()
        # Text length rewards actual usage while the cap prevents one paragraph from dominating.
        record["weight"] = int(record["weight"]) + max(1, min(len(text), 240))
        record["blocks"] = int(record["blocks"]) + 1
        cast_slides = record["slides"]
        if isinstance(cast_slides, set):
            cast_slides.add(block.slide_id)

    ranked = sorted(
        usage.values(),
        key=lambda item: (-int(item["weight"]), -int(item["blocks"]), str(item["family"]).casefold()),
    )
    candidates = [str(item["family"]) for item in ranked[:5]]
    evidence_usage = [
        {
            "family": item["family"],
            "weightedUsage": item["weight"],
            "blockCount": item["blocks"],
            "slideCount": len(item["slides"]) if isinstance(item["slides"], set) else 0,
        }
        for item in ranked[:12]
    ]
    return candidates, {"source": "deck_extraction", "usage": evidence_usage}


def _field_evidence(raw_evidence: dict) -> dict[str, dict[str, object]]:
    value = raw_evidence.get("fieldEvidence")
    if not isinstance(value, dict):
        return {}
    return {key: dict(item) for key, item in value.items() if isinstance(key, str) and isinstance(item, dict)}


def confirmed_website_brand_ready(profile: DeckBrandProfile | None) -> bool:
    if profile is None:
        return True
    stored_evidence = getattr(profile, "raw_evidence_json", None)
    raw_evidence = stored_evidence if isinstance(stored_evidence, dict) else {}
    if not raw_evidence.get("confirmedWebsiteUrl"):
        return True
    return (
        getattr(profile, "processing_status", None) == "ready"
        and (str(raw_evidence.get("paletteSource") or "") in _CONFIRMED_WEBSITE_READY_SOURCES
             or _has_canonical_source_brand(raw_evidence))
    )


def _has_canonical_source_brand(evidence: dict) -> bool:
    source = evidence.get('paletteEvidence') or {}
    return (evidence.get('paletteSource') == 'deck_visual'
        and source.get('policy') == SOURCE_BRAND_POLICY
        and source.get('selectedEvidenceKind') == 'vector_or_block')


def website_brand_binding(profile: DeckBrandProfile | None) -> dict[str, object]:
    if profile is None:
        return {}
    stored_evidence = getattr(profile, "raw_evidence_json", None)
    raw_evidence = stored_evidence if isinstance(stored_evidence, dict) else {}
    # v2 keeps confirmed website evidence canonical even when a logo owns the
    # composed palette. Fall back to the v1 location for stored compatibility.
    palette_evidence = raw_evidence.get("websitePaletteEvidence")
    if not isinstance(palette_evidence, dict):
        palette_evidence = raw_evidence.get("paletteEvidence")
    palette_evidence = palette_evidence if isinstance(palette_evidence, dict) else {}
    return {
        "sourceUrl": raw_evidence.get("confirmedWebsiteUrl"),
        "evidenceSha256": palette_evidence.get("evidenceSha256"),
        "palette": list(getattr(profile, "palette_json", None) or []),
        "colors": {
            "primary": getattr(profile, "primary_color", None),
            "secondary": getattr(profile, "secondary_color", None),
            "accent": getattr(profile, "accent_color", None),
            "background": getattr(profile, "background_color", None),
            "text": getattr(profile, "text_color", None),
        },
    }


def _is_manual_field(field_evidence: dict[str, dict[str, object]], field: str) -> bool:
    evidence = field_evidence.get(field, {})
    return evidence.get("source") == "manual" or evidence.get("status") == "overridden"


def _protected_field(field_evidence: dict[str, dict[str, object]], field: str) -> bool:
    source = str(field_evidence.get(field, {}).get("source") or "")
    generated_logo_support_role = source.startswith("logo_") and source.endswith("_generated_accessibility")
    return _is_manual_field(field_evidence, field) or source.startswith("brand_guidelines") or (
        source.startswith("logo_") and not generated_logo_support_role
    )


def _complete_manual_palette(
    profile: DeckBrandProfile | None,
    field_evidence: dict[str, dict[str, object]],
) -> bool:
    if profile is None or not _is_manual_field(field_evidence, "palette"):
        return False
    fields = ("primaryColor", "secondaryColor", "accentColor", "backgroundColor", "textColor")
    attributes = ("primary_color", "secondary_color", "accent_color", "background_color", "text_color")
    return bool(profile.palette_json) and all(
        _is_manual_field(field_evidence, field) and getattr(profile, attribute, None)
        for field, attribute in zip(fields, attributes)
    )


def _palette_from_manual_profile(profile: DeckBrandProfile) -> dict[str, object]:
    background = str(profile.background_color)
    return {
        "primary": str(profile.primary_color),
        "secondary": str(profile.secondary_color),
        "accent": str(profile.accent_color),
        "background": background,
        "surface": "#111C32" if background == "#081225" else "#EEF3FF",
        "text": str(profile.text_color),
        "mutedText": "#8FA1C2" if background == "#081225" else "#516179",
        "palette": list(profile.palette_json or []),
        "candidates": list(profile.palette_json or []),
        "observedCandidates": list(profile.palette_json or []),
        "roleOrigins": {
            role: "manual_override" for role in ("primary", "secondary", "accent", "background", "text")
        },
    }


def _evidence(source: str, confidence: float, *, overridden: bool = False) -> dict[str, object]:
    return {"source": source, "confidence": confidence, "status": "overridden" if overridden else ("fallback" if "fallback" in source or "seed" in source else "extracted")}


BRAND_PROFILE_EDITABLE_FIELDS = {
    "companyName": "company_name",
    "companyWebsiteUrl": "company_website_url",
    "logoUrl": "logo_url",
    "faviconUrl": "favicon_url",
    "brandSummary": "brand_summary",
    "visualDirection": "visual_direction",
    "visualStyle": "visual_style",
    "audienceLabel": "audience_label",
    "primaryGoal": "primary_goal",
    "primaryColor": "primary_color",
    "secondaryColor": "secondary_color",
    "accentColor": "accent_color",
    "backgroundColor": "background_color",
    "textColor": "text_color",
    "palette": "palette_json",
    "fontCandidates": "font_candidates_json",
}


def apply_manual_brand_profile_fields(profile: DeckBrandProfile, payload: dict) -> set[str]:
    """Apply non-null editable values and persist their canonical manual evidence."""
    applied: set[str] = set()
    raw_evidence = dict(profile.raw_evidence_json or {})
    field_evidence = _field_evidence(raw_evidence)
    for field, attribute in BRAND_PROFILE_EDITABLE_FIELDS.items():
        if field not in payload or payload[field] is None:
            continue
        setattr(profile, attribute, payload[field])
        field_evidence[field] = _evidence("manual", 1.0, overridden=True)
        applied.add(field)
    if "companyWebsiteUrl" in applied:
        confirmed = normalize_website_url(profile.company_website_url)
        if confirmed:
            profile.company_website_url = confirmed
            raw_evidence["confirmedWebsiteUrl"] = confirmed
    raw_evidence["fieldEvidence"] = field_evidence
    profile.raw_evidence_json = raw_evidence
    return applied


def _rgb_to_hex(red: float, green: float, blue: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(round(max(0, min(255, red)))),
        int(round(max(0, min(255, green)))),
        int(round(max(0, min(255, blue)))),
    )


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        normalized = value / 255
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    red, green, blue = [channel(value) for value in rgb]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _saturation(rgb: tuple[int, int, int]) -> float:
    maximum = max(rgb) / 255
    minimum = min(rgb) / 255
    if maximum == 0:
        return 0
    return (maximum - minimum) / maximum


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _quantize_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    bucket = 24
    return tuple(min(255, round(value / bucket) * bucket) for value in rgb)


def _rank_rgb_samples(samples: list[tuple[int, int, int]]) -> list[dict]:
    buckets: dict[tuple[int, int, int], int] = {}
    for sample in samples:
        rgb = _quantize_rgb(sample)
        luminance = _relative_luminance(rgb)
        saturation = _saturation(rgb)
        if (luminance > 0.94 or luminance < 0.035) and saturation < 0.12:
            continue
        buckets[rgb] = buckets.get(rgb, 0) + 1

    max_count = max(buckets.values(), default=1)
    ranked: list[dict] = []
    for rgb, count in buckets.items():
        luminance = _relative_luminance(rgb)
        saturation = _saturation(rgb)
        useful_luminance = 1 - abs(luminance - 0.42)
        score = count / max_count + saturation * 0.72 + useful_luminance * 0.34
        ranked.append(
            {
                "rgb": rgb,
                "hex": _rgb_to_hex(*rgb),
                "count": count,
                "luminance": luminance,
                "saturation": saturation,
                "score": score,
                "observed": True,
            }
        )

    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _pick_distant_color(
    candidates: list[dict],
    selected: list[dict],
    fallback: str,
    minimum_distance: float,
) -> dict:
    for candidate in candidates:
        if all(_color_distance(candidate["rgb"], existing["rgb"]) >= minimum_distance for existing in selected):
            return candidate
    for candidate in candidates:
        if all(candidate["hex"] != existing["hex"] for existing in selected):
            return candidate
    fallback_rgb = _hex_to_rgb(fallback)
    return {
        "rgb": fallback_rgb,
        "hex": fallback,
        "count": 1,
        "luminance": _relative_luminance(fallback_rgb),
        "saturation": _saturation(fallback_rgb),
        "score": 0,
        "observed": False,
    }


def _palette_from_ranked_colors(ranked: list[dict], seed: int) -> dict[str, str | list[str] | list[dict]] | None:
    if not ranked:
        return None

    primary = ranked[0]
    secondary = _pick_distant_color(ranked[1:], [primary], _mix_hex(primary["hex"], "#0F172A", 0.72), 72)
    accent = _pick_distant_color(
        ranked[1:],
        [primary, secondary],
        _mix_hex(primary["hex"], "#F8FAFC", 0.58),
        88,
    )
    background = "#081225" if primary["luminance"] > 0.5 else "#F8FAFC"
    surface = "#111C32" if background == "#081225" else "#EEF3FF"
    text = "#E6EEF8" if background == "#081225" else "#0F172A"
    muted_text = "#8FA1C2" if background == "#081225" else "#516179"
    palette = [primary["hex"], secondary["hex"], accent["hex"], surface, text]
    observed_candidates = [item["hex"] for item in ranked[:8]]

    return {
        "primary": primary["hex"],
        "secondary": secondary["hex"],
        "accent": accent["hex"],
        "background": background,
        "surface": surface,
        "text": text,
        "mutedText": muted_text,
        "palette": palette,
        "observedCandidates": observed_candidates,
        "roleOrigins": {
            "primary": "observed_brand_candidate",
            "secondary": "observed_brand_candidate" if secondary.get("observed") else "generated_accessibility_role",
            "accent": "observed_brand_candidate" if accent.get("observed") else "generated_accessibility_role",
            "background": "generated_accessibility_role",
            "text": "generated_accessibility_role",
        },
        "candidates": [
            {
                "hex": item["hex"],
                "confidence": round(min(0.99, item["score"] / max(1, ranked[0]["score"])), 2),
                "luminance": round(item["luminance"], 3),
                "saturation": round(item["saturation"], 3),
            }
            for item in ranked[:8]
        ],
    }


def _palette_from_observed_brand_colors(values: list[str]) -> dict[str, object] | None:
    """Keep exact vector brand colors while generating non-brand support roles."""
    observed = list(dict.fromkeys(value for value in values if _normalize_hex_candidate(value)))
    if not observed:
        return None
    primary = _normalize_hex_candidate(observed[0])
    if primary is None:
        return None
    secondary = _normalize_hex_candidate(observed[1]) if len(observed) > 1 else None
    accent = _normalize_hex_candidate(observed[2]) if len(observed) > 2 else None
    secondary = secondary or _mix_hex(primary, "#0F172A", 0.72)
    accent = accent or _mix_hex(primary, "#8B5CF6", 0.42)
    background = "#081225" if _relative_luminance(_hex_to_rgb(primary)) > 0.5 else "#F8FAFC"
    surface = "#111C32" if background == "#081225" else "#EEF3FF"
    text = "#E6EEF8" if background == "#081225" else "#0F172A"
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "background": background,
        "surface": surface,
        "text": text,
        "mutedText": "#8FA1C2" if background == "#081225" else "#516179",
        "palette": [primary, secondary, accent, surface, text],
        "candidates": observed[:8],
        "observedCandidates": observed[:8],
        "roleOrigins": {
            "primary": "observed_brand_candidate",
            "secondary": "observed_brand_candidate" if len(observed) > 1 else "generated_accessibility_role",
            "accent": "observed_brand_candidate" if len(observed) > 2 else "generated_accessibility_role",
            "background": "generated_accessibility_role",
            "text": "generated_accessibility_role",
        },
    }


def _extract_raster_palette(payload: bytes, file_name: str) -> dict[str, str | list[str] | list[dict]] | None:
    if fitz is None or not payload:
        return None

    suffix = Path(file_name or "").suffix.lower().removeprefix(".")
    filetype = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    try:
        document = fitz.open(stream=payload, filetype=filetype)
    except Exception:
        return None

    try:
        if document.page_count > 0:
            page = document.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=True)
        else:
            pixmap = fitz.Pixmap(document)
    except Exception:
        document.close()
        return None

    samples = pixmap.samples
    channels = pixmap.n
    width = max(1, pixmap.width)
    height = max(1, pixmap.height)
    stride = max(1, (width * height) // 9000)
    rgb_samples: list[tuple[int, int, int]] = []
    edge_buckets: dict[tuple[int, int, int], int] = {}
    all_buckets: dict[tuple[int, int, int], int] = {}
    for pixel_index in range(0, width * height, stride):
        offset = pixel_index * channels
        if offset + 2 >= len(samples):
            continue
        if channels >= 4 and samples[offset + 3] < 96:
            continue
        rgb = (samples[offset], samples[offset + 1], samples[offset + 2])
        rgb_samples.append(rgb)
        bucket = _quantize_rgb(rgb)
        all_buckets[bucket] = all_buckets.get(bucket, 0) + 1
        x = pixel_index % width
        y = pixel_index // width
        if x < max(1, width // 12) or x >= width - max(1, width // 12) or y < max(1, height // 12) or y >= height - max(1, height // 12):
            edge_buckets[bucket] = edge_buckets.get(bucket, 0) + 1

    document.close()
    # Logos are commonly exported on a solid canvas. When one quantized color
    # dominates both the border and the image, treat it as canvas rather than
    # observed brand ink, provided another usable color remains.
    edge_total = sum(edge_buckets.values())
    background_bucket = max(edge_buckets, key=edge_buckets.get) if edge_buckets else None
    if (
        background_bucket is not None
        and edge_buckets[background_bucket] / max(1, edge_total) >= 0.6
        and all_buckets.get(background_bucket, 0) / max(1, len(rgb_samples)) >= 0.35
    ):
        without_canvas = [sample for sample in rgb_samples if _quantize_rgb(sample) != background_bucket]
        if _rank_rgb_samples(without_canvas):
            rgb_samples = without_canvas
    return _palette_from_ranked_colors(_rank_rgb_samples(rgb_samples), _hash_bytes(payload))


def _mix_hex(base: str, target: str, ratio: float) -> str:
    base_rgb = _hex_to_rgb(base)
    target_rgb = _hex_to_rgb(target)
    return _rgb_to_hex(
        base_rgb[0] + (target_rgb[0] - base_rgb[0]) * ratio,
        base_rgb[1] + (target_rgb[1] - base_rgb[1]) * ratio,
        base_rgb[2] + (target_rgb[2] - base_rgb[2]) * ratio,
    )


def _palette_from_seed(seed: int) -> dict[str, str | list[str] | list[dict]]:
    primary = _normalize_hex(hex(seed)[2:])
    secondary = _mix_hex(primary, "#0F172A", 0.72)
    accent = _mix_hex(primary, "#8B5CF6", 0.42)
    background = "#081225" if seed % 2 == 0 else "#F8FAFC"
    surface = "#111C32" if background == "#081225" else "#EEF3FF"
    text = "#E6EEF8" if background == "#081225" else "#0F172A"
    muted_text = "#8FA1C2" if background == "#081225" else "#516179"
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "background": background,
        "surface": surface,
        "text": text,
        "mutedText": muted_text,
        "palette": [primary, secondary, accent, surface, text],
        "observedCandidates": [],
        "roleOrigins": {
            "primary": "generated_seed_role",
            "secondary": "generated_accessibility_role",
            "accent": "generated_accessibility_role",
            "background": "generated_accessibility_role",
            "text": "generated_accessibility_role",
        },
    }


def _expand_short_hex(value: str) -> str:
    raw = value.removeprefix("#")
    if len(raw) == 3:
        return f"#{''.join(character * 2 for character in raw).upper()}"
    return _normalize_hex(raw)


def _svg_length(value: str | None, reference: float) -> float:
    raw = (value or "").strip()
    if not raw:
        return 0
    if raw.endswith("%"):
        return reference * float(raw[:-1]) / 100
    numeric = re.match(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)", raw)
    return float(numeric.group(0)) if numeric else 0


def _extract_svg_palette(svg_markup: str) -> list[str]:
    full_canvas_colors: set[str] = set()
    try:
        root = ElementTree.fromstring(svg_markup)
        view_box = [float(value) for value in re.split(r"[\s,]+", root.attrib.get("viewBox", "").strip()) if value]
        canvas_width = _svg_length(root.attrib.get("width"), 0)
        canvas_height = _svg_length(root.attrib.get("height"), 0)
        if len(view_box) == 4:
            canvas_width, canvas_height = view_box[2], view_box[3]
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] != "rect" or canvas_width <= 0 or canvas_height <= 0:
                continue
            width = _svg_length(element.attrib.get("width"), canvas_width)
            height = _svg_length(element.attrib.get("height"), canvas_height)
            x = _svg_length(element.attrib.get("x", "0"), canvas_width)
            y = _svg_length(element.attrib.get("y", "0"), canvas_height)
            raw_color = element.attrib.get("fill")
            if not raw_color:
                style_fill = re.search(r"(?:^|;)\s*fill\s*:\s*(#[0-9a-fA-F]{3,8})", element.attrib.get("style", ""))
                raw_color = style_fill.group(1) if style_fill else None
            if x <= 0 and y <= 0 and width >= canvas_width * 0.95 and height >= canvas_height * 0.95 and raw_color:
                normalized = _normalize_hex_candidate(raw_color)
                if normalized:
                    full_canvas_colors.add(normalized)
    except (ElementTree.ParseError, ValueError):
        pass

    matches: list[str] = []
    for match in _SVG_HEX_PATTERN.finditer(svg_markup):
        candidate = match.group(1) or match.group(2)
        if not candidate:
            continue
        normalized = _expand_short_hex(candidate)
        if normalized not in full_canvas_colors:
            matches.append(normalized)
    if not matches:
        return list(full_canvas_colors)[:5]

    ordered = list(dict.fromkeys(matches))
    # Glossy/vector logos often declare several white specular stops before the
    # actual mark ink. Declaration order would then make white the "primary"
    # brand colour even though it is only a highlight. When other usable ink
    # exists, keep exact SVG values but rank non-highlight colours by repeated
    # use, saturation, and useful contrast. Logos without highlight stops keep
    # declaration order, preserving explicit simple palettes.
    highlights = [
        color for color in ordered
        if _relative_luminance(_hex_to_rgb(color)) > 0.92
        and _saturation(_hex_to_rgb(color)) < 0.18
    ]
    ink = [color for color in ordered if color not in highlights]
    if not highlights or not ink:
        return ordered[:5]

    counts = {color: matches.count(color) for color in ink}
    max_count = max(counts.values(), default=1)

    def ink_score(color: str) -> float:
        rgb = _hex_to_rgb(color)
        luminance = _relative_luminance(rgb)
        useful_luminance = 1 - abs(luminance - 0.42)
        return counts[color] / max_count + _saturation(rgb) * 0.72 + useful_luminance * 0.34

    ranked = sorted(ink, key=lambda color: (-ink_score(color), ordered.index(color)))
    selected = [ranked[0]]
    for minimum_distance in (90.0, 45.0):
        candidate = next(
            (
                color for color in ranked
                if color not in selected
                and all(
                    _color_distance(_hex_to_rgb(color), _hex_to_rgb(existing)) >= minimum_distance
                    for existing in selected
                )
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
    selected.extend(color for color in ranked if color not in selected)
    return (selected + highlights)[:5]


def _extract_palette_from_logo(
    file_name: str,
    mime_type: str | None,
    payload: bytes,
) -> tuple[dict[str, str | list[str] | list[dict]], dict[str, object]]:
    # SVG declarations are exact source evidence. Rasterizing first quantizes
    # those values (for example #123456 became #183060), which silently changes
    # an official uploaded/logo color before it reaches generation.
    if (mime_type == "image/svg+xml" or file_name.lower().endswith(".svg")) and payload:
        svg_palette = _extract_svg_palette(payload.decode("utf-8", errors="ignore"))
        if svg_palette:
            palette = _palette_from_observed_brand_colors(svg_palette)
            if palette is not None:
                return palette, {
                    "paletteSource": "logo_live_asset",
                    "sampledAssetName": file_name,
                    "sampledColorCount": len(svg_palette),
                }

    raster_palette = _extract_raster_palette(payload, file_name)
    if raster_palette is not None:
        return raster_palette, {
            "paletteSource": "logo_live_asset",
            "sampledAssetName": file_name,
        }

    return _palette_from_seed(_hash_bytes(payload)), {
        "paletteSource": "logo_seed_fallback",
        "fallbackReason": "logo_bytes_unparseable",
        "sampledAssetName": file_name,
    }


def _role_is_observed(palette: dict[str, object], role: str) -> bool:
    origins = palette.get("roleOrigins")
    if not isinstance(origins, dict):
        # Preserve compatibility with existing/mocked palette producers: a
        # supplied role without origin metadata predates role provenance and is
        # treated as observed rather than silently discarded.
        return bool(palette.get(role))
    return str(origins.get(role) or "").startswith("observed_")


def _fill_missing_logo_roles(
    logo_palette: dict[str, object],
    website_palette: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Fill only generated logo support roles; logo primary is immutable."""
    merged = dict(logo_palette)
    origins = dict(logo_palette.get("roleOrigins") or {})
    website_origins = dict(website_palette.get("roleOrigins") or {})
    filled: list[str] = []
    for role in ("secondary", "accent"):
        if _role_is_observed(logo_palette, role) or not _role_is_observed(website_palette, role):
            continue
        value = website_palette.get(role)
        if not isinstance(value, str) or not value:
            continue
        merged[role] = value
        origins[role] = website_origins.get(role, "observed_website_explicit")
        filled.append(role)
    merged["roleOrigins"] = origins
    merged["palette"] = [
        merged["primary"],
        merged["secondary"],
        merged["accent"],
        merged["surface"],
        merged["text"],
    ]
    return merged, filled


def _build_branding_json(
    profile: DeckBrandProfile,
    palette: dict[str, str | list[str]],
    logo: dict[str, str | None],
    company_name: str | None,
    company_url: str | None,
    visual_style: str | None,
    source_mode: str,
) -> dict:
    palette_list = list(palette["palette"]) if isinstance(palette["palette"], list) else []
    primary = str(palette["primary"])
    accent = str(palette["accent"])

    return {
        "brandProfileId": profile.id,
        "company": {
            "name": company_name,
            "websiteUrl": company_url,
        },
        "logo": logo,
        "colors": {
            "primary": primary,
            "secondary": palette.get("secondary"),
            "accent": accent,
            "background": palette.get("background"),
            "surface": palette.get("surface"),
            "text": palette.get("text"),
            "mutedText": palette.get("mutedText"),
            "palette": palette_list,
            "candidates": palette.get("candidates", []),
        },
        "usageRules": {
            "preferredBackground": "dark" if palette.get("background") == "#081225" else "light",
            "useLogoColorsFirst": source_mode in {"logo_upload", "logo_and_url"},
            "avoidLowContrast": True,
            "keepInvestorGrade": True,
            "preserveSourceDeckStructure": True,
        },
        "designHints": {
            "mood": ["premium", "technical", "investor-ready"] if palette.get("background") == "#081225" else ["clean", "editorial", "structured"],
            "visualStyle": visual_style,
            "deckUseCase": "Smart Deck creation",
        },
        "llmInstructions": [
            f"Use {primary} as the lead brand color and {accent} for emphasis only.",
            "Keep the visual system investor-grade and high-contrast.",
            "Preserve the source deck structure unless the selected design mode requests stronger change.",
        ],
    }


def _profile_company_name(deck: Deck, normalized_url: str | None) -> str:
    if deck.brand_profile and deck.brand_profile.company_name:
        return deck.brand_profile.company_name
    if normalized_url:
        host = urlparse(normalized_url).netloc.replace("www.", "")
        slug = host.split(".")[0].replace("-", " ").replace("_", " ").strip()
        if slug:
            return " ".join(part.capitalize() for part in slug.split())
    return deck.title


def _confidence_score(normalized_url: str | None, has_logo: bool) -> float:
    score = 0.68
    if normalized_url:
        score += 0.12
    if has_logo:
        score += 0.16
    return round(min(score, 0.96), 2)


def _source_mode(normalized_url: str | None, has_logo: bool) -> str:
    if normalized_url and has_logo:
        return "logo_and_url"
    if has_logo:
        return "logo_upload"
    if normalized_url:
        return "manual_url"
    return "manual"


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.brand_profile),
            selectinload(Deck.brand_assets),
            selectinload(Deck.input_sources),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def build_brand_asset_public_url(deck_id: str, asset_id: str) -> str:
    return f"/api/products/deck-aistack-codes/decks/{deck_id}/brand-assets/{asset_id}"


def _normalize_local_asset_url(value: str | None) -> str | None:
    if not value:
        return value

    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.startswith(("http://", "https://")):
        return cleaned

    return f"/{cleaned.lstrip('/')}"


def _latest_asset(deck: Deck, asset_type: str) -> DeckBrandAsset | None:
    return next((asset for asset in reversed(deck.brand_assets) if asset.asset_type == asset_type), None)


def _latest_input_source(deck: Deck, source_type: str) -> DeckInputSource | None:
    return next((source for source in reversed(deck.input_sources) if source.source_type == source_type), None)


def _store_brand_upload(
    db: Session,
    deck: Deck,
    upload_file: UploadFile,
    payload: bytes,
    *,
    source_type: str,
    source_label: str,
    asset_type: str,
) -> DeckBrandAsset:
    storage = get_upload_storage()
    suffix = Path(upload_file.filename or "").suffix or ".bin"
    stored_name = f"{generate_id(source_type)}{suffix}"
    stored = storage.write_bytes(stored_name, payload)
    try:
        security_scan = scan_upload_path(stored.path)
        stored = promote_upload(stored)
    except Exception:
        storage.delete(stored.storage_path)
        raise

    source_input = DeckInputSource(
        id=generate_id("source"),
        deck_id=deck.id,
        source_type=source_type,
        label=source_label,
        original_filename=upload_file.filename,
        mime_type=upload_file.content_type,
        storage_path=stored_name,
        status="ready",
    )
    db.add(source_input)
    db.flush()

    asset = DeckBrandAsset(
        id=generate_id("asset"),
        deck_id=deck.id,
        source_input_id=source_input.id,
        asset_type=asset_type,
        source="upload",
        label=upload_file.filename,
        mime_type=upload_file.content_type,
        storage_path=stored_name,
        metadata_json=json.dumps({"securityScan": security_scan}),
    )
    db.add(asset)
    db.flush()
    asset.public_url = build_brand_asset_public_url(deck.id, asset.id)
    db.flush()
    return asset


def _upsert_website_source(db: Session, deck: Deck, normalized_url: str | None) -> None:
    if not normalized_url:
        return

    existing = next(
        (
            source
            for source in reversed(deck.input_sources)
            if source.source_type == "company_website"
            and (source.external_url == normalized_url or source.text_value == normalized_url)
        ),
        None,
    )
    if existing is not None:
        return

    source_input = DeckInputSource(
        id=generate_id("source"),
        deck_id=deck.id,
        source_type="company_website",
        label="Company website",
        external_url=normalized_url,
        text_value=normalized_url,
        status="ready",
    )
    db.add(source_input)
    db.flush()


def _resolve_company_url(deck: Deck, company_url: str | None) -> str | None:
    normalized_request_url = normalize_website_url(company_url)
    if normalized_request_url:
        return normalized_request_url

    if deck.brand_profile and deck.brand_profile.company_website_url:
        normalized_profile_url = normalize_website_url(deck.brand_profile.company_website_url)
        if normalized_profile_url:
            return normalized_profile_url

    website_source = _latest_input_source(deck, "company_website")
    if website_source is None:
        return None

    return normalize_website_url(website_source.external_url or website_source.text_value)


def _resolve_brand_guidelines_asset(deck: Deck) -> DeckBrandAsset | None:
    return _latest_asset(deck, "brand_guide")


def _resolve_logo_asset(deck: Deck) -> DeckBrandAsset | None:
    return _latest_asset(deck, "logo")


def _load_asset_bytes(asset: DeckBrandAsset) -> bytes | None:
    path = resolve_upload_path(asset.storage_path)
    if path is None:
        return None
    if not path.exists():
        return None
    return path.read_bytes()


def get_deck_brand_asset_file(db: Session, deck_id: str, asset_id: str) -> tuple[Path, str] | None:
    asset = (
        db.query(DeckBrandAsset)
        .filter(DeckBrandAsset.id == asset_id, DeckBrandAsset.deck_id == deck_id)
        .first()
    )
    if asset is None or not asset.storage_path:
        return None

    path = resolve_upload_path(asset.storage_path)
    if path is None:
        return None
    if not path.exists():
        return None

    media_type = asset.mime_type or "application/octet-stream"
    if media_type == "image/svg+xml" or path.suffix.lower() == ".svg":
        media_type = "application/octet-stream"
    return path, media_type


def _map_brand_profile(
    profile: DeckBrandProfile,
    *,
    logo_asset: DeckBrandAsset | None = None,
    brand_guidelines_asset: DeckBrandAsset | None = None,
) -> DeckBrandProfilePayload:
    raw_evidence = dict(profile.raw_evidence_json or {})

    logo_url = None
    if logo_asset is not None:
        logo_url = logo_asset.public_url or build_brand_asset_public_url(profile.deck_id, logo_asset.id)
    if logo_url is None:
        logo_url = profile.logo_url
    logo_url = _normalize_local_asset_url(logo_url)

    brand_guidelines_url = None
    if brand_guidelines_asset is not None:
        brand_guidelines_url = brand_guidelines_asset.public_url or build_brand_asset_public_url(profile.deck_id, brand_guidelines_asset.id)
    brand_guidelines_url = _normalize_local_asset_url(brand_guidelines_url)

    status = profile.processing_status or "idle"
    if status not in {"failed", "extracting"} and (
        profile.logo_url or (profile.palette_json and len(profile.palette_json) > 0) or profile.primary_color
    ):
        status = "ready"
    elif status == "ready":
        status = "idle"

    branding_json = normalize_branding_json_payload(profile.branding_json)

    payload = DeckBrandProfilePayload(
        id=profile.id,
        deckId=profile.deck_id,
        status=status,
        companyName=profile.company_name,
        companyWebsiteUrl=profile.company_website_url,
        logoUrl=logo_url,
        faviconUrl=profile.favicon_url,
        brandSummary=profile.brand_summary,
        visualDirection=profile.visual_direction,
        visualStyle=profile.visual_style,
        audienceLabel=profile.audience_label,
        primaryGoal=profile.primary_goal,
        primaryColor=profile.primary_color,
        secondaryColor=profile.secondary_color,
        accentColor=profile.accent_color,
        backgroundColor=profile.background_color,
        textColor=profile.text_color,
        palette=profile.palette_json or [],
        fontCandidates=profile.font_candidates_json or [],
        fieldEvidence=_field_evidence(raw_evidence),
        sourceLabels=normalize_brand_source_labels(raw_evidence if isinstance(raw_evidence, dict) else {}),
        confidenceScore=profile.confidence_score,
        sourceMode=profile.source_mode,
        warnings=profile.warnings_json or [],
        rawEvidence=profile.raw_evidence_json or {},
        brandingJson=branding_json,
        brandGuidelinesFileUrl=brand_guidelines_url,
        brandGuidelinesStatus="ready" if brand_guidelines_asset is not None else None,
        processingStatus=profile.processing_status,
        updatedAt=_iso(profile.updated_at),
    )
    return with_deterministic_swatch_contract(payload)


async def extract_deck_brand(
    db: Session,
    deck_id: str,
    company_url: str | None,
    logo_file: UploadFile | None,
    brand_guidelines_file: UploadFile | None,
) -> DeckBrandProfilePayload | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    has_explicit_inputs = bool(
        (company_url or "").strip()
        or (logo_file is not None and bool(logo_file.filename))
        or (brand_guidelines_file is not None and bool(brand_guidelines_file.filename))
    )
    existing_profile = deck.brand_profile
    if not has_explicit_inputs and existing_profile is not None:
        mapped_profile = _map_brand_profile(
            existing_profile,
            logo_asset=_resolve_logo_asset(deck),
            brand_guidelines_asset=_resolve_brand_guidelines_asset(deck),
        )
        existing_evidence = existing_profile.raw_evidence_json or {}
        # Intake may create a ready seed profile before source slides/blocks are
        # persisted. That profile is not a completed deterministic extraction.
        # Re-run once from source data; subsequent automatic calls remain
        # idempotent and manual/stronger evidence is protected below.
        existing_field_evidence = existing_evidence.get("fieldEvidence")
        confirmed_website = existing_evidence.get("confirmedWebsiteUrl")
        palette_source = str(existing_evidence.get("paletteSource") or "")
        canonical_website_input = _latest_input_source(deck, "company_website")
        canonical_website_url = normalize_website_url(
            (canonical_website_input.external_url or canonical_website_input.text_value)
            if canonical_website_input is not None
            else None
        )
        website_extraction_pending = bool(canonical_website_url) and (
            confirmed_website != canonical_website_url
            or (palette_source not in _CONFIRMED_WEBSITE_READY_SOURCES and not _has_canonical_source_brand(existing_evidence))
        )
        if (
            mapped_profile.status == "ready"
            and isinstance(existing_field_evidence, dict)
            and "fontCandidates" in existing_field_evidence
            and "palette" in existing_field_evidence
            and not website_extraction_pending
            and (not settings.instant_html_llm_first_beta or existing_evidence.get('canonicalExtractionPolicy') == SOURCE_BRAND_POLICY)
        ):
            return mapped_profile

    normalized_url = _resolve_company_url(deck, company_url)
    existing_raw_evidence = dict(existing_profile.raw_evidence_json or {}) if existing_profile is not None else {}
    existing_field_evidence = _field_evidence(existing_raw_evidence)
    warnings: list[str] = []
    logo_asset: DeckBrandAsset | None = None
    brand_guidelines_asset = _resolve_brand_guidelines_asset(deck)
    logo_url: str | None = None
    logo_file_name: str | None = None
    logo_mime_type: str | None = None

    _upsert_website_source(db, deck, normalized_url)

    seed = _hash_string(normalized_url or deck.title or deck.id)
    palette = _palette_from_seed(seed)
    palette_evidence: dict[str, object] = {
        "paletteSource": "fallback_deck_seed",
        "fallbackReason": "no_deck_visual_assets",
    }
    if logo_file is not None and logo_file.filename:
        payload = await read_supported_brand_upload(
            logo_file,
            upload_types=LOGO_UPLOAD_TYPES,
            max_size=MAX_LOGO_UPLOAD_SIZE_BYTES,
            type_detail="Only PNG, JPEG, GIF, and WebP logo uploads are supported",
            too_large_detail="Logo uploads must be 10MB or smaller",
        )
        if payload:
            logo_asset = _store_brand_upload(
                db,
                deck,
                logo_file,
                payload,
                source_type="logo_file",
                source_label="Logo file",
                asset_type="logo",
            )
            logo_url = logo_asset.public_url or build_brand_asset_public_url(deck.id, logo_asset.id)
            logo_file_name = logo_file.filename
            logo_mime_type = logo_file.content_type
            palette, palette_evidence = _extract_palette_from_logo(logo_file.filename or "logo.bin", logo_file.content_type, payload)
    else:
        existing_asset = _latest_asset(deck, "logo")
        if existing_asset is not None:
            payload = _load_asset_bytes(existing_asset)
            if payload:
                logo_asset = existing_asset
                if not existing_asset.public_url:
                    existing_asset.public_url = build_brand_asset_public_url(deck.id, existing_asset.id)
                logo_url = existing_asset.public_url
                logo_file_name = existing_asset.label
                logo_mime_type = existing_asset.mime_type
                palette, palette_evidence = _extract_palette_from_logo(existing_asset.label or "logo.bin", existing_asset.mime_type, payload)

    # A URL is used only after explicit confirmation (this request supplied it).
    # When a logo exists, its primary remains authoritative. The website may
    # only fill secondary/accent roles that logo extraction had to generate.
    website_input = _latest_input_source(deck, "company_website")
    confirmed_input_url = normalize_website_url(
        (website_input.external_url or website_input.text_value)
        if website_input is not None
        else None
    )
    confirmed_url = (
        bool((company_url or "").strip())
        or bool(existing_raw_evidence.get("confirmedWebsiteUrl"))
        or bool(normalized_url and confirmed_input_url == normalized_url)
    )
    website_brand_failed = False
    filled_roles: list[str] = []
    confirmed_website_evidence = existing_raw_evidence.get("websitePaletteEvidence")
    if not isinstance(confirmed_website_evidence, dict):
        confirmed_website_evidence = None
    has_logo_palette = str(palette_evidence.get("paletteSource") or "").startswith("logo_")
    source_palette, source_evidence = (None, {})
    if settings.instant_html_llm_first_beta and not has_logo_palette:
        source_palette, source_evidence = _palette_from_deck_visuals(db, deck, seed=seed)
    if source_palette is not None and source_evidence.get('policy') == SOURCE_BRAND_POLICY:
        # A company URL supplies context, not consent to replace the uploaded
        # deck's observed identity with website navigation or photo colours.
        palette, palette_evidence = source_palette, source_evidence
    elif normalized_url is not None and confirmed_url:
        sampled_palette, sampled_evidence = _palette_from_website_url(normalized_url, seed=seed)
        confirmed_website_evidence = sampled_evidence
        if has_logo_palette:
            if sampled_palette is not None:
                palette, filled_roles = _fill_missing_logo_roles(palette, sampled_palette)
            palette_evidence = {
                **palette_evidence,
                "websiteFilledRoles": filled_roles,
                "websiteRoleFillEvidence": sampled_evidence,
            }
        elif sampled_palette is not None and _role_is_observed(sampled_palette, "primary"):
            palette = sampled_palette
            palette_evidence = sampled_evidence
        elif _complete_manual_palette(existing_profile, existing_field_evidence):
            palette = _palette_from_manual_profile(existing_profile)
            palette_evidence = {
                "paletteSource": "manual",
                "websiteExtractionEvidence": sampled_evidence,
                "fallbackReason": "complete_manual_palette_preserved",
            }
            warnings.append(
                "The confirmed company website did not yield verifiable brand colors; the complete manual brand palette remains active."
            )
        else:
            website_brand_failed = True
            palette_evidence = sampled_evidence
            warnings.append(
                "The confirmed company website did not yield verifiable brand colors. Website brand extraction must succeed before generation uses this profile."
            )
    elif not has_logo_palette:
        deck_visual_palette, deck_visual_evidence = ((source_palette, source_evidence)
            if source_evidence else _palette_from_deck_visuals(db, deck, seed=seed))
        if deck_visual_palette is not None:
            palette = deck_visual_palette
            palette_evidence = deck_visual_evidence
        else:
            warnings.append("No deck visual assets were available, so the palette fell back to deterministic deck seed swatches.")

    if brand_guidelines_file is not None and brand_guidelines_file.filename:
        payload = await read_supported_brand_upload(
            brand_guidelines_file,
            upload_types=BRAND_GUIDELINES_UPLOAD_TYPES,
            max_size=MAX_BRAND_GUIDELINES_UPLOAD_SIZE_BYTES,
            type_detail="Only PDF, DOC, DOCX, TXT, and Markdown brand guidelines uploads are supported",
            too_large_detail="Brand guidelines uploads must be 25MB or smaller",
        )
        if payload:
            brand_guidelines_asset = _store_brand_upload(
                db,
                deck,
                brand_guidelines_file,
                payload,
                source_type="brand_guide",
                source_label="Brand guide",
                asset_type="brand_guide",
            )

    if normalized_url is None and logo_asset is None and logo_file is None:
        warnings.append("No website URL or logo file was available, so the palette was derived from deck metadata only.")
    if brand_guidelines_asset is None and brand_guidelines_file is None:
        warnings.append("No brand guidelines file was attached, so typography and usage hints remain heuristic.")
    # FIX 5: surface PyMuPDF unavailability to the user so they know raster palette
    # extraction (from uploaded logos/favicons) was skipped.
    if fitz is None:
        warnings.append(
            "PyMuPDF is not installed on the server, so raster image color extraction is disabled. "
            "Logo and favicon palettes may fall back to seed-based swatches."
        )

    source_mode = _source_mode(normalized_url, logo_url is not None)
    confidence_score = _confidence_score(normalized_url, logo_url is not None)
    website_context = build_website_context(normalized_url)
    company_name = _profile_company_name(deck, normalized_url)
    # FIX: favicon_url was built by appending /favicon.ico to the full URL (including path),
    # producing broken URLs like https://example.com/about/us/favicon.ico.
    # Now we build it from the scheme + netloc only.
    if normalized_url:
        parsed_favicon = urlparse(normalized_url)
        favicon_url = f"{parsed_favicon.scheme}://{parsed_favicon.netloc}/favicon.ico"
    else:
        favicon_url = None
    visual_style = "Modern, technical, premium" if palette.get("background") == "#081225" else "Clean, editorial, structured"
    brand_summary = (
        website_context["brand_summary"]
        if website_context is not None
        else "Brand profile prepared from the uploaded deck and logo signals."
    )
    if logo_url:
        brand_summary = f"{brand_summary} Logo-derived palette added for review."
    if brand_guidelines_asset is not None:
        brand_summary = f"{brand_summary} Brand guidelines are attached for downstream design review."

    profile = deck.brand_profile
    if profile is None:
        profile = DeckBrandProfile(
            id=generate_id("brand"),
            deck_id=deck.id,
        )
        db.add(profile)

    automatic_fields = {
        "companyName": ("company_name", company_name, "url_context" if normalized_url else "deck_extraction", 0.72),
        "companyWebsiteUrl": ("company_website_url", normalized_url, "url_confirmed", 0.95),
        "logoUrl": ("logo_url", None if website_brand_failed else logo_url or favicon_url, "logo_live_asset" if logo_url else "url_favicon", 0.86 if logo_url else 0.55),
        "faviconUrl": ("favicon_url", None if website_brand_failed else favicon_url, "url_favicon", 0.65),
        "brandSummary": ("brand_summary", brand_summary, "url_context" if website_context else "deck_extraction", 0.68),
        "visualDirection": ("visual_direction", website_context["visual_direction"] if website_context is not None else "Use a restrained investor-grade visual system with high signal density and low ornamental noise.", "url_context" if website_context else "deck_extraction", 0.68),
        "visualStyle": ("visual_style", visual_style, str(palette_evidence.get("paletteSource", "deck_extraction")), 0.68),
        "audienceLabel": ("audience_label", deck.audience, "deck_extraction", 0.8),
        "primaryGoal": ("primary_goal", deck.purpose, "deck_extraction", 0.8),
    }
    field_evidence = dict(existing_field_evidence)
    for field, (attribute, value, source, confidence) in automatic_fields.items():
        if value is not None and not _protected_field(field_evidence, field):
            setattr(profile, attribute, value)
            field_evidence[field] = _evidence(source, confidence)
    color_values = {
        "primaryColor": ("primary_color", str(palette["primary"]), "primary"),
        "secondaryColor": ("secondary_color", str(palette["secondary"]), "secondary"),
        "accentColor": ("accent_color", str(palette["accent"]), "accent"),
        "backgroundColor": ("background_color", str(palette["background"]), "background"),
        "textColor": ("text_color", str(palette["text"]), "text"),
    }
    palette_source = str(palette_evidence.get("paletteSource", "fallback_deck_seed"))
    palette_confidence = 0.86 if palette_source.startswith("logo_") else 0.78 if palette_source.startswith("url_live") else 0.72 if palette_source == "deck_visual" else 0.35
    role_origins = palette.get("roleOrigins") if isinstance(palette.get("roleOrigins"), dict) else {}
    role_sources: dict[str, str] = {}
    for field, (attribute, value, role) in color_values.items():
        role_origin = str(role_origins.get(role) or "")
        field_source = (
            "url_live_explicit_brand"
            if role_origin == "observed_website_explicit"
            else "url_live_asset"
            if role_origin == "observed_website_asset"
            else f"{palette_source}_generated_accessibility"
            if role_origin == "generated_accessibility_role"
            else palette_source
        )
        role_sources[role] = field_source
        field_is_protected = _protected_field(field_evidence, field)
        if field_is_protected:
            role_sources[role] = str(field_evidence.get(field, {}).get("source") or field_source)
        if not website_brand_failed and not field_is_protected:
            setattr(profile, attribute, value)
            field_evidence[field] = _evidence(field_source, palette_confidence)
    # The composed palette must reflect protected/manual role values even when
    # another generated support role is legitimately filled from the website.
    for role, attribute in (
        ("primary", "primary_color"),
        ("secondary", "secondary_color"),
        ("accent", "accent_color"),
        ("background", "background_color"),
        ("text", "text_color"),
    ):
        persisted_value = getattr(profile, attribute, None)
        if persisted_value:
            palette[role] = persisted_value
    palette_field_is_protected = _protected_field(field_evidence, "palette")
    palette_evidence_source = str(field_evidence.get("palette", {}).get("source") or "")
    preserve_exact_palette = _is_manual_field(field_evidence, "palette") or palette_evidence_source.startswith("brand_guidelines")
    if preserve_exact_palette and profile.palette_json:
        palette["palette"] = list(profile.palette_json)
    else:
        palette["palette"] = [palette["primary"], palette["secondary"], palette["accent"], palette["surface"], palette["text"]]
    if website_brand_failed and not _protected_field(field_evidence, "palette"):
        profile.palette_json = []
        for field, (attribute, _value, _role) in color_values.items():
            if not _protected_field(field_evidence, field):
                setattr(profile, attribute, None)
    composed_palette_replaceable = bool(filled_roles) and not _is_manual_field(field_evidence, "palette") and not palette_evidence_source.startswith("brand_guidelines")
    if not website_brand_failed and (not palette_field_is_protected or composed_palette_replaceable):
        profile.palette_json = list(palette["palette"]) if isinstance(palette["palette"], list) else []
        field_evidence["palette"] = _evidence(
            f"{palette_source}_with_website_roles" if filled_roles else palette_source,
            palette_confidence,
        )

    deck_fonts, typography_evidence = _deck_font_candidates(db, deck)
    if not _protected_field(field_evidence, "fontCandidates"):
        profile.font_candidates_json = deck_fonts or ["Manrope", "General Sans"]
        field_evidence["fontCandidates"] = _evidence("deck_extraction" if deck_fonts else "fallback_safe_fonts", 0.76 if deck_fonts else 0.3)
    profile.confidence_score = confidence_score
    profile.source_mode = source_mode
    profile.warnings_json = warnings
    deck_source_ready = bool(deck.input_sources or deck.slides)
    profile.raw_evidence_json = {
        **existing_raw_evidence,
        "canonicalExtractionPolicy": SOURCE_BRAND_POLICY if settings.instant_html_llm_first_beta else None,
        "confirmedWebsiteUrl": normalized_url if confirmed_url else existing_raw_evidence.get("confirmedWebsiteUrl"),
        "websiteUrl": normalized_url,
        "logoAssetId": logo_asset.id if logo_asset is not None else None,
        "logoFileName": logo_file_name,
        "brandGuideAssetId": brand_guidelines_asset.id if brand_guidelines_asset is not None else None,
        "paletteSource": palette_evidence.get("paletteSource", "url_or_deck_seed"),
        "paletteCandidates": palette.get("candidates", []),
        "paletteEvidence": palette_evidence,
        "websitePaletteEvidence": confirmed_website_evidence,
        "paletteRoleSources": role_sources,
        "typographyEvidence": typography_evidence,
        "fieldEvidence": field_evidence,
        "deckSourceReady": deck_source_ready,
        "sourceLabels": build_brand_source_labels(
            website_url=normalized_url,
            logo_asset_id=logo_asset.id if logo_asset is not None else None,
            deck_source_ready=deck_source_ready,
            brand_guidelines_asset_id=brand_guidelines_asset.id if brand_guidelines_asset is not None else None,
            palette_source=str(palette_evidence.get("paletteSource", "url_or_deck_seed")),
            sampled_urls=palette_evidence.get("sampledUrls") if isinstance(palette_evidence.get("sampledUrls"), list) else [],
        ),
    }
    profile.processing_status = "failed" if website_brand_failed else "ready"
    profile.branding_json = {} if website_brand_failed else _build_branding_json(
        profile=profile,
        palette=palette,
        logo={
            "assetId": logo_asset.id if logo_asset is not None else None,
            "url": profile.logo_url or logo_url or favicon_url,
            "mimeType": logo_mime_type,
            "fileName": logo_file_name,
        },
        company_name=company_name,
        company_url=normalized_url,
        visual_style=visual_style,
        source_mode=_source_mode(normalized_url, bool(profile.logo_url or logo_url)),
    )

    if logo_asset is not None:
        logo_asset.metadata_json = json.dumps(
            {
                "extracted_colors": profile.palette_json,
                "primary_color": profile.primary_color,
                "secondary_color": profile.secondary_color,
                "accent_color": profile.accent_color,
                "candidate_colors": palette.get("candidates", []),
            }
        )
        if not logo_asset.public_url:
            logo_asset.public_url = build_brand_asset_public_url(deck.id, logo_asset.id)
    if brand_guidelines_asset is not None and brand_guidelines_asset.metadata_json is None:
        brand_guidelines_asset.metadata_json = json.dumps({"status": "attached", "role": "brand_reference"})
    if brand_guidelines_asset is not None and not brand_guidelines_asset.public_url:
        brand_guidelines_asset.public_url = build_brand_asset_public_url(deck.id, brand_guidelines_asset.id)

    # Persist canonical deterministic evidence in the same transaction as the
    # extracted profile. Applying it only to the response after commit made a
    # fresh session reload depend on route-time repair rather than stored truth.
    mapped = with_deterministic_swatch_contract(
        _map_brand_profile(profile, logo_asset=logo_asset, brand_guidelines_asset=brand_guidelines_asset)
    )
    profile.raw_evidence_json = mapped.rawEvidence

    # FIX 6: db.commit() had no error handling, so a commit failure (connection lost,
    # constraint violation, disk full) would produce a raw 500 with no context.
    # Now we catch, log, rollback, and re-raise as a ValueError so the route handler
    # can return a proper 400.
    try:
        db.commit()
    except Exception as commit_error:
        db.rollback()
        logger.exception(
            "Failed to commit brand profile for deck %s: %s",
            deck_id,
            commit_error,
        )
        raise ValueError(f"Failed to persist brand profile: {commit_error}") from commit_error
    db.refresh(profile)
    return _map_brand_profile(profile, logo_asset=logo_asset, brand_guidelines_asset=brand_guidelines_asset)


def get_deck_brand_profile(db: Session, deck_id: str) -> DeckBrandProfilePayload | None:
    deck = _load_deck(db, deck_id)
    if deck is None or deck.brand_profile is None:
        return None
    return _map_brand_profile(
        deck.brand_profile,
        logo_asset=_resolve_logo_asset(deck),
        brand_guidelines_asset=_resolve_brand_guidelines_asset(deck),
    )


def update_deck_brand_profile(db: Session, deck_id: str, payload: dict) -> DeckBrandProfilePayload | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    profile = deck.brand_profile
    if profile is None:
        profile = DeckBrandProfile(
            id=generate_id("brand"),
            deck_id=deck.id,
            company_name=payload.get("companyName") or deck.title,
            brand_summary="Manual brand profile created from the Smart Deck brand editor.",
            visual_direction="Use the approved brand palette and typography with a clear executive hierarchy.",
            visual_style="Modern, technical, confident",
            audience_label=deck.audience,
            primary_goal=deck.purpose,
            primary_color="#3B82F6",
            secondary_color="#0F172A",
            accent_color="#8B5CF6",
            background_color="#081225",
            text_color="#E6EEF8",
            palette_json=["#3B82F6", "#0F172A", "#8B5CF6", "#081225", "#E6EEF8"],
            font_candidates_json=["Inter", "Arial"],
            confidence_score=0.5,
            source_mode="manual",
            warnings_json=[],
            raw_evidence_json={"paletteSource": "manual"},
            processing_status="ready",
        )
        deck.brand_profile = profile
        db.add(profile)

    applied_manual_fields = apply_manual_brand_profile_fields(profile, payload)
    for incoming_key, model_field in {"confidenceScore": "confidence_score", "sourceMode": "source_mode"}.items():
        if incoming_key in payload and payload.get(incoming_key) is not None:
            setattr(profile, model_field, payload[incoming_key])
    if "warnings" in payload and payload.get("warnings") is not None:
        profile.warnings_json = payload["warnings"]

    raw_evidence = dict(profile.raw_evidence_json or {})
    palette_fields = {
        "primaryColor",
        "secondaryColor",
        "accentColor",
        "backgroundColor",
        "textColor",
        "palette",
    }
    if palette_fields.intersection(applied_manual_fields):
        raw_evidence["paletteSource"] = "manual"
        raw_evidence["paletteEvidence"] = {"paletteSource": "manual"}
        if "companyWebsiteUrl" not in applied_manual_fields:
            profile.processing_status = "ready"
    if "companyWebsiteUrl" in applied_manual_fields:
        profile.processing_status = "extracting"
        raw_evidence["paletteSource"] = "website_extraction_pending"
        raw_evidence.pop("paletteEvidence", None)
    source_label_evidence = dict(raw_evidence)
    source_label_evidence.pop("sourceLabels", None)
    raw_evidence["sourceLabels"] = normalize_brand_source_labels(source_label_evidence)
    profile.raw_evidence_json = raw_evidence

    company_url = normalize_website_url(profile.company_website_url)
    palette = {
        "primary": profile.primary_color or "#3B82F6",
        "secondary": profile.secondary_color or "#0F172A",
        "accent": profile.accent_color or "#8B5CF6",
        "background": profile.background_color or "#081225",
        "surface": "#111C32" if (profile.background_color or "#081225") == "#081225" else "#EEF3FF",
        "text": profile.text_color or ("#E6EEF8" if (profile.background_color or "#081225") == "#081225" else "#0F172A"),
        "mutedText": "#8FA1C2" if (profile.background_color or "#081225") == "#081225" else "#516179",
        "palette": profile.palette_json or [color for color in [profile.primary_color, profile.secondary_color, profile.accent_color, profile.background_color, profile.text_color] if color],
    }

    profile.branding_json = _build_branding_json(
        profile=profile,
        palette=palette,
        logo={
            "assetId": profile.raw_evidence_json.get("logoAssetId") if profile.raw_evidence_json else None,
            "url": profile.logo_url,
            "mimeType": None,
            "fileName": profile.raw_evidence_json.get("logoFileName") if profile.raw_evidence_json else None,
        },
        company_name=profile.company_name,
        company_url=company_url,
        visual_style=profile.visual_style,
        source_mode=profile.source_mode or "manual",
    )
    # Persist the exact current swatch evidence so reload, status, extraction,
    # and PATCH responses cannot disagree after role colours are edited.
    mapped = with_deterministic_swatch_contract(_map_brand_profile(profile))
    profile.raw_evidence_json = mapped.rawEvidence
    db.commit()
    db.refresh(profile)
    return _map_brand_profile(
        profile,
        logo_asset=_resolve_logo_asset(deck),
        brand_guidelines_asset=_resolve_brand_guidelines_asset(deck),
    )
