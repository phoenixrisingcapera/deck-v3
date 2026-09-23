"""Deterministic fixed-geometry compiler for seven composition families."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json

from .composition_renderers import CSS as COMPOSITION_CSS
from .composition_renderers import RENDERERS
from .models import DeckSpec, NormalizedSourcePackage, SlideSpec
from .validation import DeckSpecValidationError, validate_deck_spec


COMPILER_VERSION = "instant-deck-composition-compiler.v1"
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080


class DeckSpecCompilationError(ValueError):
    def __init__(self, code: str, detail: str, *, slide_id: str | None = None):
        self.code = code
        self.detail = detail
        self.slide_id = slide_id
        super().__init__(f"{code}:{slide_id or 'deck'}:{detail}")


@dataclass(frozen=True, slots=True)
class CompiledSlide:
    slide_id: str
    position: int
    archetype: str
    section_html: str
    render_document: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class CompiledDeck:
    schema_version: str
    compiler_version: str
    source_package_id: str
    slides: tuple[CompiledSlide, ...]
    document_html: str
    content_sha256: str
    manifest: dict


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _role_colours(package: NormalizedSourcePackage) -> dict[str, str]:
    return {role.role_id: role.colour for role in package.brand.roles}


def _palette(spec: DeckSpec, slide: SlideSpec, package: NormalizedSourcePackage) -> dict[str, str]:
    roles = _role_colours(package)
    background = roles[slide.composition.background_role]
    accent = roles[slide.composition.accent_role]
    paper = roles[spec.art_direction.paper_role]
    ink = roles[spec.art_direction.ink_role]
    foreground = paper if background == ink else ink
    muted = "#D8D4CC" if foreground == paper else "#4C4944"
    return {
        "background": background,
        "foreground": foreground,
        "accent": accent,
        "muted": muted,
        "paper": paper,
        "ink": ink,
    }


BASE_CSS = r"""
*{box-sizing:border-box}html,body{margin:0;padding:0;background:#111}body{font-family:Arial,Helvetica,sans-serif}.deck-document{display:block}.deck-slide{position:relative;width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--fg);padding:78px 96px}.deck-slide h1,.deck-slide p{margin:0}.eyebrow{position:absolute;left:96px;top:62px;color:var(--accent);font-size:24px;line-height:1.1;font-weight:800;letter-spacing:.18em;text-transform:uppercase}.position{position:absolute;right:96px;top:58px;color:var(--fg);font-size:24px;line-height:1;font-weight:800}
"""


def _document(title: str, sections: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{escape(title)}</title><meta name=\"viewport\" content=\"width=1920,height=1080\">"
        f"<style>{BASE_CSS}{COMPOSITION_CSS}</style></head><body><main class=\"deck-document\">{sections}</main></body></html>"
    )


def compile_deck_spec(spec: DeckSpec, source_package: NormalizedSourcePackage) -> CompiledDeck:
    try:
        validate_deck_spec(spec, source_package)
    except DeckSpecValidationError as exc:
        raise DeckSpecCompilationError("semantic_validation_failed", str(exc)) from exc

    compiled_slides: list[CompiledSlide] = []
    for slide in spec.slides:
        renderer = RENDERERS.get(slide.archetype)
        if renderer is None:
            raise DeckSpecCompilationError(
                "primitive_not_implemented",
                f"{slide.archetype.value} is outside the seven-composition-family slice.",
                slide_id=slide.slide_id,
            )
        section = renderer(slide, _palette(spec, slide, source_package))
        render_document = _document(f"{spec.deck_title} — {slide.position}", section)
        compiled_slides.append(CompiledSlide(
            slide_id=slide.slide_id,
            position=slide.position,
            archetype=slide.archetype.value,
            section_html=section,
            render_document=render_document,
            content_sha256=sha256(render_document.encode("utf-8")).hexdigest(),
        ))

    document_html = _document(spec.deck_title, "".join(slide.section_html for slide in compiled_slides))
    manifest = {
        "schemaVersion": spec.schema_version,
        "compilerVersion": COMPILER_VERSION,
        "sourcePackageId": source_package.package_id,
        "sourcePackageSha256": sha256(_canonical_bytes(source_package.model_dump(mode="json", by_alias=True))).hexdigest(),
        "deckSpecSha256": sha256(_canonical_bytes(spec.model_dump(mode="json", by_alias=True))).hexdigest(),
        "slides": [
            {"slideId": slide.slide_id, "position": slide.position, "archetype": slide.archetype, "contentSha256": slide.content_sha256}
            for slide in compiled_slides
        ],
    }
    content_sha256 = sha256(document_html.encode("utf-8")).hexdigest()
    manifest["contentSha256"] = content_sha256
    return CompiledDeck(
        schema_version=spec.schema_version,
        compiler_version=COMPILER_VERSION,
        source_package_id=source_package.package_id,
        slides=tuple(compiled_slides),
        document_html=document_html,
        content_sha256=content_sha256,
        manifest=manifest,
    )
