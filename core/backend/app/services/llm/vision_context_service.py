from __future__ import annotations

import base64

from app.db.models import Deck, DeckSlide
from app.services.storage.artifact_storage import get_upload_storage


def public_asset_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/api/", "/uploads/", "/static/", "data:")):
        return path
    if path.startswith("/home/") or path.startswith("/tmp/"):
        return None
    return f"/{path.lstrip('/')}"


def model_image_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "data:")):
        return path
    storage_path = path.removeprefix("/uploads/").lstrip("/")
    try:
        resolved = get_upload_storage().resolve_path(storage_path)
        if resolved is None or not resolved.is_file():
            return None
        payload = resolved.read_bytes()
        if len(payload) > 10 * 1024 * 1024:
            return None
        suffix = resolved.suffix.lower()
        mime_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
        return f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
    except Exception:
        return None


def collect_slide_image_urls(deck: Deck, *, slide_id: str | None = None, limit: int = 4) -> list[str]:
    candidates: list[str] = []
    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    for slide in slides:
        if slide_id and slide.id != slide_id:
            continue
        for raw_path in (getattr(slide, "preview_image_url", None), getattr(slide, "thumbnail_path", None)):
            url = model_image_url(raw_path)
            if not url or url in candidates:
                continue
            candidates.append(url)
            if len(candidates) >= limit:
                return candidates
    return candidates


def build_visual_context(deck: Deck, *, slide_id: str | None = None, limit: int = 4) -> dict:
    image_urls = collect_slide_image_urls(deck, slide_id=slide_id, limit=limit)
    return {
        "enabled": bool(image_urls),
        "imageUrls": image_urls,
        "slideId": slide_id,
        "imageCount": len(image_urls),
    }


def prompt_safe_visual_context(visual_context: dict) -> dict:
    """Keep attachment metadata in text prompts without duplicating image data."""
    return {key: value for key, value in visual_context.items() if key != "imageUrls"}
