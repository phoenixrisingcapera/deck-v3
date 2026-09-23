"""Asset-aware composition extension for compiler v2.

All seven v1 renderers remain the canonical structural grammar.  V2 adds only
the two source-asset placements already selected by PlannerDeckSpec v3.
"""

from __future__ import annotations

from html import escape

from .asset_resolution_v2 import ResolvedAssetBundleV2
from .composition_renderers import Palette, RENDERERS
from .models import SlideArchetype, SlideSpec


def _manifest_item_for_slide(slide: SlideSpec, bundle: ResolvedAssetBundleV2):
    items = [row for row in bundle.manifest.assets if slide.slide_id in row.slides_consuming]
    if len(items) > 1:
        from .asset_resolution_v2 import AssetResolutionError

        raise AssetResolutionError(
            "multiple_assets_for_unsupported_slide", slide.slide_id, asset_id=slide.asset_refs[0]
        )
    return items[0] if items else None


def _asset_figure(slide: SlideSpec, bundle: ResolvedAssetBundleV2) -> str:
    item = _manifest_item_for_slide(slide, bundle)
    if item is None:
        return ""
    uri = bundle.data_uri(item.asset_id)
    common = (
        f'data-asset-id="{escape(item.asset_id)}" '
        f'data-original-sha256="{item.original_byte_sha256}" '
        f'data-transformed-sha256="{item.transformed_byte_sha256}" '
        f'data-fit="{item.transformation.fit}"'
    )
    image = (
        f'<img src="{uri}" width="{item.transformed_width}" '
        f'height="{item.transformed_height}" alt="" loading="eager" decoding="sync"/>'
    )
    if item.planner_role == "brand_mark" and slide.archetype == SlideArchetype.THESIS_COVER:
        return f'<figure class="c-v2-source-asset c-v2-brand-asset" {common}>{image}</figure>'
    if item.planner_role == "portrait" and slide.archetype == SlideArchetype.SYSTEM_MAP:
        return f'<figure class="c-v2-source-asset c-v2-portrait-asset" {common}>{image}</figure>'
    from .asset_resolution_v2 import AssetResolutionError

    raise AssetResolutionError(
        "asset_role_archetype_mismatch",
        f"{item.planner_role}:{slide.archetype.value}",
        asset_id=item.asset_id,
    )


def render_slide_v2(
    slide: SlideSpec,
    palette: Palette,
    bundle: ResolvedAssetBundleV2,
) -> str:
    renderer = RENDERERS[slide.archetype]
    section = renderer(slide, palette)
    figure = _asset_figure(slide, bundle)
    if not figure:
        return section
    if slide.archetype == SlideArchetype.THESIS_COVER:
        section = section.replace(
            'class="deck-slide c-cover ',
            'class="deck-slide c-cover c-v2-cover-with-asset ',
            1,
        )
    elif slide.archetype == SlideArchetype.SYSTEM_MAP:
        section = section.replace(
            'class="deck-slide c-system"',
            'class="deck-slide c-system c-v2-system-with-asset"',
            1,
        )
    if not section.endswith("</section>"):
        from .asset_resolution_v2 import AssetResolutionError

        raise AssetResolutionError("renderer_section_contract_invalid", slide.slide_id)
    return section[: -len("</section>")] + figure + "</section>"


CSS_V2 = r"""
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 · compiler-v2 asset audit */
.deck-slide{--font-display:'Noto Sans Display','Noto Sans',Arial,sans-serif;--font-body:'Noto Sans',Arial,sans-serif;font-family:var(--font-body)}
.c-head h1,.c-cover h1,.c-insight h1,.c-metric-monument strong,.c-secondary-metric strong,.c-shift-state>strong{font-family:var(--font-display);font-style:normal;font-weight:800}
.c-metric-monument strong{line-height:1}
.c-v2-source-asset{position:absolute;margin:0;overflow:hidden;z-index:2}
.c-v2-source-asset img{display:block;width:100%;height:100%}
.c-v2-cover-with-asset .c-cover-copy{width:1030px;z-index:3}
.c-v2-brand-asset{right:72px;top:198px;width:650px;height:760px;display:grid;place-items:center}
.c-v2-brand-asset:before{content:'';position:absolute;inset:76px 0 0 76px;border-left:10px solid var(--accent);border-bottom:10px solid var(--accent);z-index:-1}
.c-v2-brand-asset img{object-fit:contain}
.c-v2-system-with-asset .c-head{width:1140px}
.c-v2-system-with-asset .c-system-visual{left:72px;top:326px;width:1210px;height:680px}
.c-v2-portrait-asset{right:92px;top:326px;width:440px;height:640px;border:8px solid var(--accent);background:var(--bg)}
.c-v2-portrait-asset img{object-fit:contain}
"""
