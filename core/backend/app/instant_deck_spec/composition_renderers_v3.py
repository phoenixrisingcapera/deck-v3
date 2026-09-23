"""Compiler-v3 renderers for source-grounded commercial compositions."""

from __future__ import annotations

from html import escape
import re

from .asset_resolution_v3 import ResolvedAssetBundleV3
from .composition_renderers import (
    Palette,
    RENDERERS,
    _attrs,
    _copy,
    _header,
    _style,
    _subhead,
)
from .models import SlideArchetype, SlideSpec


def _asset(slide: SlideSpec, bundle: ResolvedAssetBundleV3, role: str, css_class: str) -> str:
    matches = [
        row
        for row in bundle.manifest.assets
        if slide.slide_id in row.slides_consuming and row.compiler_role == role
    ]
    if len(matches) != 1:
        return ""
    row = matches[0]
    return (
        f'<figure class="c-v3-asset {css_class}" data-da-element-key="{slide.slide_id}-{role}" '
        f'data-asset-id="{escape(row.asset_id)}" data-fit="{row.transformation.fit}" '
        f'data-transformed-sha256="{row.transformed_byte_sha256}">'
        f'<img src="{bundle.data_uri(row.asset_id)}" width="{row.transformed_width}" '
        f'height="{row.transformed_height}" alt="" loading="eager" decoding="sync"></figure>'
    )


def render_cover_v3(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    logo = _asset(slide, bundle, "brand_mark", "c-v3-cover-logo")
    return f'''<section class="deck-slide c-v3-cover" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Investment thesis")}
      <div class="c-v3-cover-rule"></div>
      <div class="c-v3-cover-copy"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="display">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-v3-logo-reserve" data-da-element-key="{slide.slide_id}-logo-reserve">{logo}</div>
      <svg class="c-v3-cover-map" data-da-element-key="{slide.slide_id}-cover-map" data-meaningful-visual="true" viewBox="0 0 700 470" role="img" aria-label="Source-backed commercial pathway"><title>Commercial pathway</title>
        <path d="M45 390 C180 390 170 250 340 250 S520 80 655 80" fill="none" stroke="{palette['accent']}" stroke-width="22"/>
        <circle cx="45" cy="390" r="42" fill="{palette['background']}" stroke="{palette['foreground']}" stroke-width="10"/><circle cx="340" cy="250" r="60" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="15"/><circle cx="655" cy="80" r="48" fill="{palette['accent']}"/>
      </svg>
    </section>'''


def render_problem_v3(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    positions = [(80, 65), (620, 25), (1160, 65), (90, 465), (620, 500), (1150, 465)]
    links, nodes = [], []
    for index, item in enumerate(slide.visual.items):
        x, y = positions[index]
        anchor_y = y + (118 if y < 330 else 0)
        links.append(f'<path d="M{x+180} {anchor_y} L800 330" stroke="{palette["muted"]}" stroke-width="5"/>')
        # Ordinary HTML is preserved by the canonical sanitizer. foreignObject
        # is intentionally unsupported and must not carry factual copy.
        nodes.append(f'<div class="c-v3-problem-node" style="position:absolute;left:{160+x+48}px;top:{320+y}px;width:330px" data-evidence-refs="{escape(",".join(item.evidence_refs))}"><strong>{escape(item.label)}</strong><p>{escape(item.detail or "")}</p></div>')
    return f'''<section class="deck-slide c-v3-problem" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Problem landscape")}<div class="c-head c-v3-problem-head"><h1>{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-v3-problem-system" data-meaningful-visual="true" viewBox="0 0 1600 650" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{''.join(links)}<ellipse cx="800" cy="330" rx="210" ry="112" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="18"/></svg>{''.join(nodes)}
    </section>'''


def render_pathway_v3(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    stages = "".join(
        f'<div class="c-v3-pathway-stage" data-evidence-refs="{escape(",".join(step.evidence_refs))}"><span>{index:02d}</span><strong data-da-element-key="{slide.slide_id}-step-{index}-label" data-da-text-role="label">{escape(step.label)}</strong><p data-da-element-key="{slide.slide_id}-step-{index}-detail" data-da-text-role="body">{escape(step.detail or "")}</p></div>'
        for index, step in enumerate(slide.visual.steps, start=1)
    )
    return f'''<section class="deck-slide c-v3-pathway" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Pathway")}<div class="c-head c-v3-pathway-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-v3-pathway-line" data-meaningful-visual="true" viewBox="0 0 1600 180" role="img" aria-label="Ordered commercial pathway"><title>Ordered commercial pathway</title><path d="M110 120 C480 120 520 40 800 90 S1220 150 1490 55" fill="none" stroke="{palette['accent']}" stroke-width="20" stroke-linecap="round"/><circle cx="110" cy="120" r="28" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="12"/><circle cx="800" cy="90" r="28" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="12"/><circle cx="1490" cy="55" r="28" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="12"/></svg>
      <div class="c-v3-pathway-stages" style="grid-template-columns:repeat({len(slide.visual.steps)},minmax(0,1fr))">{stages}</div><div class="c-v3-pathway-copy">{_copy(slide)}</div>
    </section>'''


def render_business_model(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    items = slide.visual.items
    nodes = []
    arrows = []
    positions = [170 + index * (1260 / max(1, len(items) - 1)) for index in range(len(items))]
    for index, (item, x) in enumerate(zip(items, positions)):
        nodes.append(
            f'<g data-evidence-refs="{escape(",".join(item.evidence_refs))}"><circle cx="{x:.1f}" cy="280" r="118" fill="{palette["background"]}" stroke="{palette["accent"]}" stroke-width="10"/>'
            f'<text x="{x:.1f}" y="270" text-anchor="middle" fill="{palette["foreground"]}" font-size="28" font-weight="800" data-da-element-key="{slide.slide_id}-flow-{index}-label" data-da-text-role="label">{escape(item.label)}</text>'
            f'<text x="{x:.1f}" y="314" text-anchor="middle" fill="{palette["muted"]}" font-size="23" data-da-element-key="{slide.slide_id}-flow-{index}-detail" data-da-text-role="body">{escape(item.detail or "")}</text></g>'
        )
        if index:
            arrows.append(
                f'<path d="M{positions[index-1]+128:.1f} 280 H{x-128:.1f}" stroke="{palette["accent"]}" stroke-width="12" marker-end="url(#{slide.slide_id}-arrow)"/>'
            )
    metric = slide.visual.metrics[0]
    return f'''<section class="deck-slide c-v3-business" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Commercial engine")}<div class="c-head c-v3-commercial-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-v3-business-flow" data-meaningful-visual="true" viewBox="0 0 1600 600" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title><defs><marker id="{slide.slide_id}-arrow" markerWidth="12" markerHeight="12" refX="8" refY="5" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="{palette['accent']}"/></marker></defs>{''.join(arrows)}{''.join(nodes)}</svg>
      <div class="c-v3-paid-mechanism" data-evidence-refs="{escape(",".join(metric.evidence_refs))}"><span data-da-text-role="label" data-da-element-key="{slide.slide_id}-paid-label">PAID MECHANISM</span><strong data-da-text-role="metric-secondary" data-da-element-key="{slide.slide_id}-paid-value">{escape(metric.value)}</strong><p data-da-text-role="body" data-da-element-key="{slide.slide_id}-paid-context">{escape(metric.label)} · {escape(metric.context or '')}</p></div>
      <div class="c-v3-business-copy">{_copy(slide)}</div>
    </section>'''


def render_founder(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    person = slide.visual.people[0]
    portrait = _asset(slide, bundle, "founder_portrait", "c-v3-founder-portrait")
    return f'''<section class="deck-slide c-v3-founder" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Founder credibility")}{portrait}
      <div class="c-v3-founder-copy"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}
        <div class="c-v3-founder-identity" data-evidence-refs="{escape(",".join(person.evidence_refs))}"><strong data-da-text-role="metric-label" data-da-element-key="{slide.slide_id}-founder-name">{escape(person.name)}</strong><span data-da-text-role="label" data-da-element-key="{slide.slide_id}-founder-role">{escape(person.role)}</span></div>
        <div class="c-v3-credential-rail" data-evidence-refs="{escape(",".join(person.evidence_refs))}"><p data-da-text-role="body" data-da-element-key="{slide.slide_id}-credentials">{escape(person.proof)}</p></div>
        <div class="c-v3-founder-statement">{_copy(slide)}</div>
      </div>
    </section>'''


def render_network(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    photo = _asset(slide, bundle, "network_evidence", "c-v3-network-photo")
    positions = [(210, 280), (650, 120), (650, 440), (1110, 280), (1110, 90), (1110, 470), (1430, 280), (360, 520)]
    by_id = {item.id: positions[index] for index, item in enumerate(slide.visual.items)}
    edges = "".join(
        f'<g data-evidence-refs="{escape(",".join(edge.evidence_refs))}"><path d="M{by_id[edge.from_id][0]} {by_id[edge.from_id][1]} L{by_id[edge.to][0]} {by_id[edge.to][1]}" stroke="{palette["accent"]}" stroke-width="8"/><text x="{(by_id[edge.from_id][0]+by_id[edge.to][0])/2:.1f}" y="{(by_id[edge.from_id][1]+by_id[edge.to][1])/2-16:.1f}" text-anchor="middle" fill="{palette["foreground"]}" font-size="22" font-weight="800">{escape(edge.label or "listed")}</text></g>'
        for edge in slide.visual.edges
    )
    nodes = "".join(
        f'<g data-evidence-refs="{escape(",".join(item.evidence_refs))}"><circle cx="{by_id[item.id][0]}" cy="{by_id[item.id][1]}" r="82" fill="{palette["background"]}" stroke="{palette["foreground"]}" stroke-width="7"/><text x="{by_id[item.id][0]}" y="{by_id[item.id][1]-2}" text-anchor="middle" fill="{palette["foreground"]}" font-size="25" font-weight="800" data-da-text-role="label" data-da-element-key="{slide.slide_id}-network-{index}-label">{escape(item.label)}</text><text x="{by_id[item.id][0]}" y="{by_id[item.id][1]+36}" text-anchor="middle" fill="{palette["muted"]}" font-size="21" data-da-text-role="label" data-da-element-key="{slide.slide_id}-network-{index}-detail">{escape(item.value or item.detail or '')}</text></g>'
        for index, item in enumerate(slide.visual.items)
    )
    return f'''<section class="deck-slide c-v3-network" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Network proof")}<div class="c-head c-v3-network-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      {photo}<svg class="c-v3-network-map" data-meaningful-visual="true" viewBox="0 0 1600 620" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{edges}{nodes}</svg>
      <div class="c-v3-network-implication">{_copy(slide)}</div>
    </section>'''


def render_capital(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    metric = slide.visual.metrics[0]
    stages = []
    for index, item in enumerate(slide.visual.items):
        stages.append(
            f'<div class="c-v3-capital-stage" data-evidence-refs="{escape(",".join(item.evidence_refs))}"><span data-da-text-role="label" data-da-element-key="{slide.slide_id}-capital-{index}-phase">{index+1:02d}</span><strong data-da-text-role="metric-label" data-da-element-key="{slide.slide_id}-capital-{index}-label">{escape(item.label)}</strong><p data-da-text-role="body" data-da-element-key="{slide.slide_id}-capital-{index}-detail">{escape(item.detail or '')}</p></div>'
        )
    return f'''<section class="deck-slide c-v3-capital" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Capital to milestone")}<div class="c-head c-v3-capital-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-v3-capital-ask" data-evidence-refs="{escape(",".join(metric.evidence_refs))}"><span data-da-text-role="label">CAPITAL REQUESTED</span><strong data-da-text-role="metric-primary" data-da-element-key="{slide.slide_id}-capital-ask">{escape(metric.value)}</strong><p data-da-text-role="body">{escape(metric.label)} · {escape(metric.context or '')}</p></div>
      <div class="c-v3-capital-flow">{''.join(stages)}<div class="c-v3-capital-outcome"><span data-da-text-role="label">EXPECTED OUTCOME</span><p data-da-text-role="body" data-da-element-key="{slide.slide_id}-capital-outcome">{escape(slide.visual.narrative_function)}</p></div></div>
      <div class="c-v3-capital-copy">{_copy(slide)}</div>
    </section>'''


def render_close(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    return f'''<section class="deck-slide c-v3-close" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "The decision")}<div class="c-v3-close-field"></div>
      <div class="c-v3-close-copy"><span data-da-text-role="label">THESIS → PROOF → DECISION</span><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="display">{escape(slide.headline)}</h1>{_subhead(slide)}<div class="c-v3-close-proof">{_copy(slide)}</div></div>
      <svg class="c-v3-close-mark" data-meaningful-visual="true" viewBox="0 0 400 400" role="img" aria-label="Decision mark"><title>Decision mark</title><circle cx="200" cy="200" r="154" fill="none" stroke="{palette['accent']}" stroke-width="22"/><path d="M112 210 L178 276 L300 126" fill="none" stroke="{palette['foreground']}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </section>'''


_V3_RENDERERS = {
    SlideArchetype.BUSINESS_MODEL_FLOW: render_business_model,
    SlideArchetype.PEOPLE_PROOF: render_founder,
    SlideArchetype.PARTNERSHIP_ECOSYSTEM: render_network,
    SlideArchetype.CAPITAL_PLAN: render_capital,
    SlideArchetype.DECISIVE_CLOSE: render_close,
}


def render_metric_stats(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    del bundle
    # Independent statistics never acquire an invented shared magnitude scale.
    metrics = "".join(f'''<div class="c-v3-stat" data-evidence-refs="{escape(",".join(m.evidence_refs))}"><strong>{escape(m.value)}</strong><span>{escape(m.label)}</span><p>{escape(m.context or "")}</p></div>''' for m in slide.visual.metrics)
    return f'''<section class="deck-slide c-v3-stats" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Source-backed proof")}<div class="c-head"><h1>{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-v3-stat-grid" style="grid-template-columns:repeat({min(2, len(slide.visual.metrics))},minmax(0,1fr))">{metrics}</div>
      <div class="c-v3-stats-copy">{_copy(slide)}</div>
    </section>'''


def render_image_evidence(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    image = _asset(slide, bundle, "source_evidence", "c-v3-evidence-image")
    return f'''<section class="deck-slide c-v3-evidence" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Source evidence")}<div class="c-head c-v3-evidence-head"><h1>{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      {image}<div class="c-v3-evidence-copy">{_copy(slide)}</div>
    </section>'''


RENDERER_REGISTRY_V3 = {
    **{key: (lambda slide, palette, bundle, fn=fn: fn(slide, palette)) for key, fn in RENDERERS.items()},
    **_V3_RENDERERS,
    SlideArchetype.THESIS_COVER: render_cover_v3,
    SlideArchetype.PROBLEM_LANDSCAPE: render_problem_v3,
    SlideArchetype.PROCESS_PATHWAY: render_pathway_v3,
    SlideArchetype.IMAGE_EVIDENCE: render_image_evidence,
    SlideArchetype.METRIC_PROOF: render_metric_stats,
}


def render_slide_v3(slide: SlideSpec, palette: Palette, bundle: ResolvedAssetBundleV3) -> str:
    renderer = RENDERER_REGISTRY_V3.get(slide.archetype)
    if renderer is None:
        raise ValueError(f"compiler_v3_primitive_not_implemented:{slide.archetype.value}")
    return renderer(slide, palette, bundle)


CSS_V3 = r'''
.c-v3-evidence-head{width:1680px}.c-v3-evidence-image{left:96px;top:330px;width:1050px;height:650px}.c-v3-evidence-image img{object-fit:contain}.c-v3-evidence-copy{position:absolute;left:1220px;right:96px;top:360px}

.c-v3-stat-grid{position:absolute;left:96px;right:96px;top:340px;display:grid;gap:32px}.c-v3-stat{border-left:8px solid var(--accent);padding:18px 30px}.c-v3-stat strong,.c-v3-stat span{display:block}.c-v3-stat strong{font-size:80px;line-height:1.3;font-weight:800;overflow-wrap:anywhere}.c-v3-stat span{font-size:30px;font-weight:700}.c-v3-stat p{font-size:28px;margin-top:12px!important}.c-v3-stats-copy{position:absolute;left:96px;right:96px;bottom:58px}
/* Compiler v3: fixed 16:9 commercial composition system. */
.deck-slide{--font-display:'Noto Sans Display','Noto Sans',Arial,sans-serif;--font-body:'Noto Sans',Arial,sans-serif;font-family:var(--font-body)}
.deck-slide h1,.c-v3-paid-mechanism strong,.c-v3-capital-ask strong,.c-v3-founder-identity strong{font-family:var(--font-display);font-style:normal;font-weight:800}
.c-v3-asset{position:absolute;margin:0;overflow:hidden}.c-v3-asset img{display:block;width:100%;height:100%}
.c-v3-cover-rule{position:absolute;left:104px;right:104px;top:130px;height:8px;background:var(--accent)}
.c-v3-cover-copy{position:absolute;left:104px;top:235px;width:1010px}.c-v3-cover-copy h1{font-size:106px;line-height:.96;letter-spacing:-.045em}.c-v3-cover-copy .c-subhead{font-size:34px;margin-top:36px!important;max-width:900px}
.c-v3-logo-reserve{position:absolute;right:90px;top:172px;width:650px;height:220px;display:grid;place-items:center;border-bottom:4px solid var(--accent)}.c-v3-cover-logo{inset:0}.c-v3-cover-logo img{object-fit:contain}
.c-v3-cover-map{position:absolute;right:72px;top:438px;width:700px;height:470px}
.c-v3-problem-head{width:1320px}.c-v3-problem-system{position:absolute;left:160px;top:320px;width:1600px;height:650px}.c-v3-problem-node strong,.c-v3-problem-node p{display:block;margin:0}.c-v3-problem-node strong{font-size:30px;line-height:1.05;color:var(--fg)}.c-v3-problem-node p{font-size:24px;line-height:1.2;color:var(--muted);margin-top:10px!important}
.c-v3-pathway-head{width:1380px}.c-v3-pathway-line{position:absolute;left:160px;top:375px;width:1600px;height:180px}.c-v3-pathway-stages{position:absolute;left:96px;right:96px;top:575px;display:grid;gap:46px}.c-v3-pathway-stage{position:relative;padding-top:58px;border-top:7px solid var(--accent);text-align:center}.c-v3-pathway-stage span{position:absolute;left:50%;top:-39px;transform:translateX(-50%);display:grid;place-items:center;width:72px;height:72px;border-radius:50%;background:var(--bg);border:7px solid var(--accent);font-size:24px;font-weight:800}.c-v3-pathway-stage strong{display:block;font-size:34px}.c-v3-pathway-stage p{font-size:24px;line-height:1.25;color:var(--muted);margin-top:16px!important}.c-v3-pathway-copy{position:absolute;left:96px;right:96px;bottom:58px}.c-v3-pathway-copy .c-copy{max-width:1100px}
.c-v3-commercial-head{width:1250px}.c-v3-business-flow{position:absolute;left:160px;top:330px;width:1600px;height:600px}.c-v3-paid-mechanism{position:absolute;left:700px;bottom:74px;width:520px;text-align:center;padding:20px 30px;border-top:7px solid var(--accent)}.c-v3-paid-mechanism span,.c-v3-paid-mechanism strong,.c-v3-paid-mechanism p{display:block}.c-v3-paid-mechanism span{font-size:20px}.c-v3-paid-mechanism strong{font-size:66px;line-height:1;color:var(--accent);margin:8px 0}.c-v3-paid-mechanism p{font-size:24px}.c-v3-business-copy{position:absolute;left:96px;bottom:62px;width:520px}.c-v3-business-flow text[data-da-text-role="body"]{font-size:24px}
.c-v3-founder-portrait{left:96px;top:260px;width:600px;height:730px;border:10px solid var(--accent)}.c-v3-founder-portrait img{object-fit:cover}.c-v3-founder-copy{position:absolute;left:790px;right:100px;top:170px}.c-v3-founder-copy h1{font-size:82px;line-height:.98;letter-spacing:-.035em}.c-v3-founder-identity{margin-top:66px;padding-bottom:28px;border-bottom:8px solid var(--accent)}.c-v3-founder-identity strong,.c-v3-founder-identity span{display:block}.c-v3-founder-identity strong{font-size:54px}.c-v3-founder-identity span{font-size:24px;color:var(--muted);margin-top:12px}.c-v3-credential-rail{display:grid;grid-template-columns:1fr;gap:44px;margin-top:42px}.c-v3-credential-rail div{border-left:8px solid var(--accent);padding-left:24px}.c-v3-credential-rail b,.c-v3-credential-rail span{display:block}.c-v3-credential-rail b{font-size:54px;line-height:1.05}.c-v3-credential-rail span{font-size:24px;color:var(--muted);margin-top:13px}.c-v3-founder-statement{margin-top:48px;max-width:840px}
.c-v3-network-head{width:1320px}.c-v3-network-photo{left:96px;top:400px;width:590px;height:520px;clip-path:polygon(0 0,100% 0,86% 100%,0 100%)}.c-v3-network-photo img{object-fit:cover}.c-v3-network-map{position:absolute;left:690px;top:360px;width:1160px;height:500px}.c-v3-network-implication{position:absolute;left:760px;right:96px;bottom:44px}
.c-v3-capital-head{width:1320px}.c-v3-capital-ask{position:absolute;left:96px;top:420px;width:620px}.c-v3-capital-ask span,.c-v3-capital-ask strong,.c-v3-capital-ask p{display:block}.c-v3-capital-ask span{font-size:20px}.c-v3-capital-ask strong{font-size:168px;line-height:1.2;color:var(--accent);letter-spacing:-.06em;margin:24px 0}.c-v3-capital-ask p{font-size:25px;color:var(--muted)}.c-v3-capital-flow{position:absolute;left:800px;right:96px;top:400px;display:grid;gap:22px}.c-v3-capital-stage,.c-v3-capital-outcome{position:relative;padding:24px 32px 24px 104px;border-left:10px solid var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent)}.c-v3-capital-stage:after{content:'↓';position:absolute;left:36px;bottom:-36px;color:var(--accent);font-size:42px;font-weight:800;z-index:2}.c-v3-capital-stage span{position:absolute;left:30px;top:30px;font-size:22px}.c-v3-capital-stage strong{display:block;font-size:34px}.c-v3-capital-stage p,.c-v3-capital-outcome p{font-size:24px;color:var(--muted);margin-top:10px!important}.c-v3-capital-outcome span{font-size:22px;font-weight:800}.c-v3-capital-copy{position:absolute;left:96px;bottom:68px;width:610px}
.c-v3-close-field{position:absolute;left:0;top:0;width:32%;height:100%;background:var(--accent)}.c-v3-close-copy{position:absolute;left:210px;top:205px;width:1240px}.c-v3-close-copy>span{font-size:24px;font-weight:800;letter-spacing:.18em}.c-v3-close-copy h1{font-size:112px;line-height:.94;letter-spacing:-.05em;margin-top:52px}.c-v3-close-copy .c-subhead{font-size:40px;color:var(--fg);margin-top:42px!important}.c-v3-close-proof{margin-top:38px;max-width:760px}.c-v3-close-mark{position:absolute;right:100px;bottom:80px;width:370px;height:370px}
'''
