from __future__ import annotations

import logging
from html.parser import HTMLParser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SECONDS = 4
_FETCH_MAX_BYTES = 120_000


class _MetaTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_tags: list[dict[str, str]] = []
        self.title_text: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag == "meta":
            self.meta_tags.append(normalized)
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data


def _fetch_html(url: str) -> str | None:
    try:
        # Local import avoids a module cycle while consolidating every brand
        # website read through the DNS-pinned, redirect-revalidating transport.
        from app.services.brand.brand_extraction import _safe_request

        payload, content_type = _safe_request(
            url,
            timeout_seconds=_FETCH_TIMEOUT_SECONDS,
            max_bytes=_FETCH_MAX_BYTES,
            allowed_mime_prefixes=("text/html", "application/xhtml"),
        )
        if not payload:
            return None
        return payload.decode("utf-8", errors="ignore")
    except (ValueError, TimeoutError) as fetch_error:
        logger.warning("Website context fetch failed for %s: %s", url, fetch_error)
        return None
    except Exception as fetch_error:
        logger.warning("Unexpected website context fetch error for %s: %s", url, fetch_error)
        return None


def _extract_meta_values(html_text: str) -> dict[str, str | None]:
    parser = _MetaTagParser()
    parser.feed(html_text)

    og_title = None
    og_description = None
    theme_color = None
    og_image = None
    twitter_description = None

    for meta in parser.meta_tags:
        meta_property = meta.get("property", "").lower()
        meta_name = meta.get("name", "").lower()
        meta_content = meta.get("content", "").strip()
        if not meta_content:
            continue
        if meta_property == "og:title" and og_title is None:
            og_title = meta_content
        if meta_property == "og:description" and og_description is None:
            og_description = meta_content
        if meta_property == "og:image" and og_image is None:
            og_image = meta_content
        # FIX 4: Twitter cards normally use name="twitter:description", not property.
        if meta_name == "twitter:description" and twitter_description is None:
            twitter_description = meta_content
        if meta_name == "theme-color" and theme_color is None:
            theme_color = meta_content
        if meta_name == "description" and og_description is None:
            og_description = meta_content

    title = parser.title_text.strip() or None

    return {
        "title": title,
        "og_title": og_title,
        "og_description": og_description,
        "twitter_description": twitter_description,
        "theme_color": theme_color,
        "og_image": og_image,
    }


def normalize_website_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None

    candidate = raw_url.strip()
    if not candidate:
        return None

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc:
        return None

    return candidate.rstrip("/")


def build_website_context(raw_url: str | None) -> dict | None:
    normalized = normalize_website_url(raw_url)
    if normalized is None:
        return None

    parsed = urlparse(normalized)
    host = parsed.netloc.lower().replace("www.", "")
    slug = host.split(".")[0].replace("-", " ").replace("_", " ").strip()
    company_hint = " ".join(part.capitalize() for part in slug.split()) or host

    # FIX 4: try to fetch real website metadata (og:title, og:description, theme-color, etc.)
    # instead of always returning a generic placeholder. Falls back to deterministic values
    # if the fetch fails (timeout, network error, non-HTML response).
    html_text = _fetch_html(normalized)
    if html_text is not None:
        meta_values = _extract_meta_values(html_text)
        effective_title = meta_values.get("og_title") or meta_values.get("title") or company_hint
        effective_description = (
            meta_values.get("og_description")
            or meta_values.get("twitter_description")
            or ""
        )
        brand_summary = (
            f"{effective_title}: {effective_description}"
            if effective_description
            else f"Website context suggests a premium, structured company presence centered on {effective_title}."
        )
        visual_direction = (
            "Use a restrained investor-grade visual system with clear hierarchy and minimal decorative noise."
        )
        return {
            "normalized_url": normalized,
            "host": host,
            "company_hint": effective_title,
            "contact_email_hint": f"hello@{host}" if "." in host else None,
            "brand_summary": brand_summary,
            "visual_direction": visual_direction,
            "themeColor": meta_values.get("theme_color"),
            "ogImage": meta_values.get("og_image"),
            "fetchedFromWebsite": True,
        }

    # DISABLED: this was the only path. Now it is the fallback when the website is unreachable.
    return {
        "normalized_url": normalized,
        "host": host,
        "company_hint": company_hint,
        "contact_email_hint": f"hello@{host}" if "." in host else None,
        "brand_summary": f"Website context suggests a premium, structured company presence centered on {company_hint}.",
        "visual_direction": "Use a restrained investor-grade visual system with clear hierarchy and minimal decorative noise.",
        "fetchedFromWebsite": False,
    }
