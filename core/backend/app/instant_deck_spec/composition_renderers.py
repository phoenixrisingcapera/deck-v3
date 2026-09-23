"""Seven-family fixed-geometry renderers used by the offline compiler."""

from __future__ import annotations

from html import escape
from typing import Callable

from .models import SlideArchetype, SlideSpec


Palette = dict[str, str]


def _attrs(slide: SlideSpec) -> str:
    return (
        f'data-slide-id="{escape(slide.slide_id)}" data-archetype="{escape(slide.archetype.value)}" '
        f'data-evidence-refs="{escape(",".join(slide.evidence_refs))}" '
        f'data-source-slide-ids="{escape(",".join(slide.source_slide_ids))}"'
    )


def _style(palette: Palette) -> str:
    return f"--bg:{palette['background']};--fg:{palette['foreground']};--accent:{palette['accent']};--muted:{palette['muted']}"


def _header(slide: SlideSpec, label: str) -> str:
    return (
        f'<div class="eyebrow" data-da-element-key="{slide.slide_id}-eyebrow" data-da-text-role="label">{escape(label)}</div>'
        f'<div class="position" data-da-element-key="{slide.slide_id}-position" data-da-text-role="label">{slide.position:02d}</div>'
    )


def _subhead(slide: SlideSpec) -> str:
    return (
        f'<p class="c-subhead" data-da-element-key="{slide.slide_id}-subhead" data-da-text-role="subhead">{escape(slide.subhead)}</p>'
        if slide.subhead else ""
    )


def _copy(slide: SlideSpec) -> str:
    return "".join(
        f'<p class="c-copy c-copy-{escape(block.emphasis)}" data-da-element-key="{slide.slide_id}-{escape(block.id)}" '
        f'data-da-text-role="body" data-evidence-refs="{escape(",".join(block.evidence_refs))}">{escape(block.text)}</p>'
        for block in slide.copy_blocks
    )


def render_cover(slide: SlideSpec, palette: Palette) -> str:
    return f'''<section class="deck-slide c-cover c-cover-{escape(slide.composition.focal_alignment)}" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Investment thesis")}<div class="c-cover-rule"></div>
      <div class="c-cover-copy"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="display">{escape(slide.headline)}</h1>{_subhead(slide)}{_copy(slide)}</div>
      <svg class="c-cover-map" data-meaningful-visual="true" viewBox="0 0 620 620" role="img" aria-label="Home to community to action thesis"><title>Home to community to action</title>
        <path d="M70 470 C190 470 190 300 315 300 S450 120 560 120" fill="none" stroke="{palette['accent']}" stroke-width="22"/>
        <circle cx="70" cy="470" r="52" fill="{palette['background']}" stroke="{palette['foreground']}" stroke-width="12"/><circle cx="315" cy="300" r="72" fill="{palette['background']}" stroke="{palette['accent']}" stroke-width="18"/><circle cx="560" cy="120" r="54" fill="{palette['accent']}"/>
        <text x="70" y="558" text-anchor="middle" fill="{palette['foreground']}" font-size="24" font-weight="800">HOME</text><text x="315" y="404" text-anchor="middle" fill="{palette['foreground']}" font-size="24" font-weight="800">COMMUNITY</text><text x="560" y="208" text-anchor="middle" fill="{palette['foreground']}" font-size="24" font-weight="800">ACTION</text>
      </svg>
    </section>'''


def render_problem(slide: SlideSpec, palette: Palette) -> str:
    positions = [(150, 148), (710, 78), (1270, 155), (235, 520), (800, 604), (1360, 510)]
    anchors = [(620, 294), (742, 226), (982, 294), (650, 438), (800, 478), (965, 430)]
    if slide.composition.variant.value == "diagonal_flow":
        positions = [(100 + index * 278, 90 + index * 82) for index in range(len(slide.visual.items))]
        anchors = [(650 + index * 60, 260 + index * 35) for index in range(len(slide.visual.items))]
    links: list[str] = []
    nodes: list[str] = []
    for index, item in enumerate(slide.visual.items):
        x, y = positions[index]
        ax, ay = anchors[index]
        refs = escape(",".join(item.evidence_refs))
        links.append(f'<path d="M{x} {y} L{ax} {ay}" stroke="{palette["muted"]}" stroke-width="5"/>')
        nodes.append(
            f'<g data-evidence-refs="{refs}"><circle cx="{x}" cy="{y}" r="18" fill="{palette["accent"]}"/>'
            f'<text x="{x + 34}" y="{y - 4}" fill="{palette["foreground"]}" font-size="32" font-weight="800" data-da-element-key="{slide.slide_id}-problem-{index}-label" data-da-text-role="label">{escape(item.label)}</text>'
            f'<text x="{x + 34}" y="{y + 35}" fill="{palette["muted"]}" font-size="24" data-da-element-key="{slide.slide_id}-problem-{index}-detail" data-da-text-role="body">{escape(item.detail or "")}</text></g>'
        )
    drawing = f'{"".join(links)}<ellipse cx="800" cy="352" rx="214" ry="126" fill="{palette["background"]}" stroke="{palette["accent"]}" stroke-width="20"/>{"".join(nodes)}<text x="800" y="342" text-anchor="middle" fill="{palette["foreground"]}" font-size="28" font-weight="800">SHARED</text><text x="800" y="382" text-anchor="middle" fill="{palette["foreground"]}" font-size="28" font-weight="800">TENSION</text>'
    return f'''<section class="deck-slide c-problem" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Problem landscape")}<div class="c-head c-problem-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-problem-visual" data-meaningful-visual="true" viewBox="0 0 1600 740" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{drawing}</svg>
    </section>'''


def render_insight(slide: SlideSpec, palette: Palette) -> str:
    proof = "".join(
        f'<div class="c-insight-proof" data-evidence-refs="{escape(",".join(item.evidence_refs))}"><span data-da-element-key="{slide.slide_id}-insight-{index}-label" data-da-text-role="label">{escape(item.label)}</span><p data-da-element-key="{slide.slide_id}-insight-{index}-detail" data-da-text-role="body">{escape(item.detail or "")}</p></div>'
        for index, item in enumerate(slide.visual.items)
    )
    return f'''<section class="deck-slide c-insight c-insight-{escape(slide.composition.variant.value)}" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Key insight")}<div class="c-insight-assertion"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="display">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-insight-spine"></div><div class="c-insight-proofs">{proof}</div>
    </section>'''


def render_pathway(slide: SlideSpec, palette: Palette) -> str:
    count = len(slide.visual.steps)
    points: list[tuple[float, float]] = []
    for index in range(count):
        if slide.composition.variant.value == "stacked":
            points.append((270 + (index % 2) * 1040, 100 + index * (430 / max(1, count - 1))))
        else:
            points.append((130 + index * (1340 / max(1, count - 1)), 390 - index * (190 / max(1, count - 1))))
    path = " ".join(("M" if index == 0 else "L") + f" {x:.1f} {y:.1f}" for index, (x, y) in enumerate(points))
    parts = [f'<path d="{path}" fill="none" stroke="{palette["accent"]}" stroke-width="20" stroke-linecap="round"/>']
    for index, (step, (x, y)) in enumerate(zip(slide.visual.steps, points), start=1):
        parts.append(
            f'<g data-evidence-refs="{escape(",".join(step.evidence_refs))}"><circle cx="{x}" cy="{y}" r="58" fill="{palette["background"]}" stroke="{palette["accent"]}" stroke-width="16"/><text x="{x}" y="{y + 11}" text-anchor="middle" fill="{palette["foreground"]}" font-size="30" font-weight="800">{index:02d}</text>'
            f'<text x="{x}" y="{y + 112}" text-anchor="middle" fill="{palette["foreground"]}" font-size="32" font-weight="800" data-da-element-key="{slide.slide_id}-step-{index}-label" data-da-text-role="label">{escape(step.label)}</text><text x="{x}" y="{y + 154}" text-anchor="middle" fill="{palette["muted"]}" font-size="26" data-da-element-key="{slide.slide_id}-step-{index}-detail" data-da-text-role="body">{escape(step.detail or "")}</text></g>'
        )
    return f'''<section class="deck-slide c-pathway" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Pathway")}<div class="c-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-pathway-visual" data-meaningful-visual="true" viewBox="0 0 1600 650" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{''.join(parts)}</svg><div class="c-bottom-copy">{_copy(slide)}</div>
    </section>'''


def render_timeline(slide: SlideSpec, palette: Palette) -> str:
    parts: list[str] = []
    if slide.composition.variant.value == "stacked":
        for index, step in enumerate(slide.visual.steps, start=1):
            y = 100 + (index - 1) * (430 / max(1, len(slide.visual.steps) - 1)); x = 160 + index * 120
            parts.append(f'<g data-evidence-refs="{escape(",".join(step.evidence_refs))}"><path d="M{x} {y} H1500" stroke="{palette["muted"]}" stroke-width="3"/><rect x="{x}" y="{y - 40}" width="148" height="80" fill="{palette["accent"]}"/><text x="{x + 74}" y="{y + 10}" text-anchor="middle" fill="{palette["background"]}" font-size="26" font-weight="800">PHASE {index:02d}</text><text x="{x + 190}" y="{y - 2}" fill="{palette["foreground"]}" font-size="34" font-weight="800" data-da-element-key="{slide.slide_id}-milestone-{index}-label" data-da-text-role="label">{escape(step.label)}</text><text x="{x + 190}" y="{y + 40}" fill="{palette["muted"]}" font-size="25" data-da-element-key="{slide.slide_id}-milestone-{index}-detail" data-da-text-role="body">{escape(step.detail or "")}</text></g>')
    else:
        parts.append(f'<path d="M42 590 H1558" stroke="{palette["foreground"]}" stroke-width="5"/>')
        for index, step in enumerate(slide.visual.steps, start=1):
            x = 120 + (index - 1) * (1360 / max(1, len(slide.visual.steps) - 1)); height = 176 + index * 76
            parts.append(f'<g data-evidence-refs="{escape(",".join(step.evidence_refs))}"><rect x="{x - 76:.1f}" y="{590 - height:.1f}" width="152" height="{height}" fill="{palette["accent"]}" opacity="{0.48 + index * .15:.2f}"/><text x="{x:.1f}" y="{622 - height:.1f}" text-anchor="middle" fill="{palette["background"]}" font-size="28" font-weight="800">{index:02d}</text><text x="{x:.1f}" y="650" text-anchor="middle" fill="{palette["foreground"]}" font-size="32" font-weight="800" data-da-element-key="{slide.slide_id}-milestone-{index}-label" data-da-text-role="label">{escape(step.label)}</text><text x="{x:.1f}" y="694" text-anchor="middle" fill="{palette["muted"]}" font-size="25" data-da-element-key="{slide.slide_id}-milestone-{index}-detail" data-da-text-role="body">{escape(step.detail or "")}</text></g>')
    return f'''<section class="deck-slide c-timeline" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Milestones")}<div class="c-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-timeline-visual" data-meaningful-visual="true" viewBox="0 0 1600 760" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{''.join(parts)}</svg>
    </section>'''


def _number(text: str) -> float:
    raw = "".join(character for character in text if character.isdigit() or character in ".,")
    if not raw: return 1.0
    try: return max(float(raw.replace(".", "").replace(",", ".")), .01)
    except ValueError: return 1.0


def render_metric(slide: SlideSpec, palette: Palette) -> str:
    metrics = slide.visual.metrics; primary = metrics[0]; maximum = max(_number(metric.value) for metric in metrics)
    secondaries = "".join(f'<div class="c-secondary-metric" data-evidence-refs="{escape(",".join(metric.evidence_refs))}"><strong data-da-element-key="{slide.slide_id}-metric-{index}-value" data-da-text-role="metric-secondary">{escape(metric.value)}</strong><span data-da-element-key="{slide.slide_id}-metric-{index}-label" data-da-text-role="label">{escape(metric.label)}</span></div>' for index, metric in enumerate(metrics[1:], start=2))
    bars = "".join(f'<g data-evidence-refs="{escape(",".join(metric.evidence_refs))}"><rect x="0" y="{index * 102 + 36}" width="{210 + 780 * (_number(metric.value) / maximum):.1f}" height="54" fill="{palette["accent"]}" opacity="{1-index*.13:.2f}"/><text x="20" y="{index * 102 + 26}" fill="{palette["foreground"]}" font-size="25" font-weight="800">{escape(metric.value)} · {escape(metric.label)}</text></g>' for index, metric in enumerate(metrics))
    proof = '<div class="c-metric-center-rule"></div>' if slide.composition.variant.value == "centered_monument" else f'<svg class="c-metric-bars" data-meaningful-visual="true" viewBox="0 0 1020 430" role="img" aria-label="Metric magnitude bars"><title>Metric magnitude bars</title>{bars}</svg>'
    return f'''<section class="deck-slide c-metric c-metric-{escape(slide.composition.variant.value)} c-metric-align-{escape(slide.composition.focal_alignment)}" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Source-backed proof")}<div class="c-head c-metric-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-metric-monument" data-evidence-refs="{escape(",".join(primary.evidence_refs))}"><strong data-da-element-key="{slide.slide_id}-metric-primary-value" data-da-text-role="metric-primary">{escape(primary.value)}</strong><span data-da-element-key="{slide.slide_id}-metric-primary-label" data-da-text-role="metric-label">{escape(primary.label)}</span><small data-da-element-key="{slide.slide_id}-metric-primary-context" data-da-text-role="body">{escape(primary.context or "")}</small></div>
      {proof}<div class="c-metric-rail">{secondaries}</div><div class="c-metric-copy">{_copy(slide)}</div>
    </section>'''


def render_system(slide: SlideSpec, palette: Palette) -> str:
    orbit = [(800, 330), (290, 150), (1310, 150), (300, 540), (1300, 540), (800, 650), (800, 70), (500, 350)] if slide.composition.variant.value == "orbit" else [(180, 330), (580, 120), (580, 520), (1080, 120), (1080, 330), (1080, 540), (1480, 330), (840, 330)]
    positions = {item.id: orbit[index] for index, item in enumerate(slide.visual.items)}
    edges = "".join(f'<g data-evidence-refs="{escape(",".join(edge.evidence_refs))}"><path d="M{positions[edge.from_id][0]} {positions[edge.from_id][1]} L{positions[edge.to][0]} {positions[edge.to][1]}" stroke="{palette["accent"]}" stroke-width="8" opacity=".72"/><circle cx="{positions[edge.to][0]}" cy="{positions[edge.to][1]}" r="12" fill="{palette["accent"]}"/></g>' for edge in slide.visual.edges)
    nodes = "".join(f'<g data-evidence-refs="{escape(",".join(item.evidence_refs))}"><circle cx="{positions[item.id][0]}" cy="{positions[item.id][1]}" r="{100 if index==0 else 78}" fill="{palette["background"]}" stroke="{palette["foreground"]}" stroke-width="6"/><text x="{positions[item.id][0]}" y="{positions[item.id][1]+9}" text-anchor="middle" fill="{palette["foreground"]}" font-size="{25 if index==0 else 23}" font-weight="800" data-da-element-key="{slide.slide_id}-node-{index}-label" data-da-text-role="label">{escape(item.label)}</text><text x="{positions[item.id][0]}" y="{positions[item.id][1] + (138 if index==0 else 116)}" text-anchor="middle" fill="{palette["muted"]}" font-size="22" data-da-element-key="{slide.slide_id}-node-{index}-detail" data-da-text-role="label">{escape(item.detail or "")}</text></g>' for index, item in enumerate(slide.visual.items))
    return f'''<section class="deck-slide c-system" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "System map")}<div class="c-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <svg class="c-system-visual" data-meaningful-visual="true" viewBox="0 0 1600 760" role="img" aria-label="{escape(slide.visual.narrative_function)}"><title>{escape(slide.visual.narrative_function)}</title>{edges}{nodes}</svg>
    </section>'''


def render_shift(slide: SlideSpec, palette: Palette) -> str:
    groups: dict[str, list] = {}
    for item in slide.visual.items: groups.setdefault(item.group or "", []).append(item)
    names = list(groups)
    def block(items: list, prefix: str) -> str:
        return "".join(f'<div class="c-shift-item" data-evidence-refs="{escape(",".join(item.evidence_refs))}"><span data-da-element-key="{slide.slide_id}-{prefix}-{index}-label" data-da-text-role="label">{escape(item.label)}</span><p data-da-element-key="{slide.slide_id}-{prefix}-{index}-detail" data-da-text-role="body">{escape(item.detail or "")}</p></div>' for index,item in enumerate(items))
    return f'''<section class="deck-slide c-shift c-shift-{escape(slide.composition.variant.value)}" data-da-slide-root {_attrs(slide)} style="{_style(palette)}">
      {_header(slide, "Comparison shift")}<div class="c-head c-shift-head"><h1 data-da-element-key="{slide.slide_id}-headline" data-da-text-role="headline">{escape(slide.headline)}</h1>{_subhead(slide)}</div>
      <div class="c-shift-stage"><div class="c-shift-state c-shift-current"><strong>{escape(names[0])}</strong>{block(groups[names[0]], 'current')}</div><div class="c-shift-arrow">→</div><div class="c-shift-state c-shift-future"><strong>{escape(names[1])}</strong>{block(groups[names[1]], 'future')}</div></div>
    </section>'''


RENDERERS: dict[SlideArchetype, Callable[[SlideSpec, Palette], str]] = {
    SlideArchetype.THESIS_COVER: render_cover,
    SlideArchetype.PROBLEM_LANDSCAPE: render_problem,
    SlideArchetype.KEY_INSIGHT: render_insight,
    SlideArchetype.PROCESS_PATHWAY: render_pathway,
    SlideArchetype.TIMELINE_MILESTONES: render_timeline,
    SlideArchetype.METRIC_PROOF: render_metric,
    SlideArchetype.SYSTEM_MAP: render_system,
    SlideArchetype.COMPARISON_SHIFT: render_shift,
}


CSS = r"""
.c-subhead{font-size:28px;line-height:1.25;color:var(--muted);margin-top:18px!important;max-width:1000px}.c-copy{font-size:25px;line-height:1.32}.c-copy-primary{font-weight:700}.c-copy-secondary,.c-copy-quiet{color:var(--muted)}.c-head{position:absolute;left:96px;top:142px;width:1240px}.c-head h1{font-family:Georgia,'Times New Roman',serif;font-size:68px;line-height:1.02;letter-spacing:-.03em}.c-bottom-copy{position:absolute;left:96px;bottom:58px}.c-bottom-copy .c-copy{max-width:920px}
.c-cover{padding:166px 104px 88px}.c-cover-rule{position:absolute;left:104px;top:130px;width:1712px;height:8px;background:var(--accent)}.c-cover-copy{position:absolute;left:104px;top:238px;width:1120px}.c-cover h1{font-family:Georgia,'Times New Roman',serif;font-size:106px;line-height:.96;letter-spacing:-.045em}.c-cover .c-subhead{font-size:34px;margin-top:38px!important;max-width:900px}.c-cover-map{position:absolute;right:80px;bottom:46px;width:610px;height:610px}.c-cover-right .c-cover-copy{left:730px}.c-cover-right .c-cover-map{left:80px;right:auto}.c-cover-center .c-cover-copy{left:260px;width:1400px;text-align:center}.c-cover-center .c-cover-map{display:none}
.c-problem-head{width:1120px}.c-problem-visual{position:absolute;left:160px;top:320px;width:1600px;height:740px}.c-insight-assertion{position:absolute;left:120px;top:190px;width:1570px}.c-insight h1{font-family:Georgia,'Times New Roman',serif;font-size:98px;line-height:.96;letter-spacing:-.045em;max-width:1520px}.c-insight-spine{position:absolute;left:120px;right:120px;top:610px;height:12px;background:var(--accent)}.c-insight-proofs{position:absolute;left:120px;right:120px;top:676px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:54px}.c-insight-proof{border-top:2px solid var(--muted);padding-top:20px}.c-insight-proof span{font-size:30px;font-weight:800}.c-insight-proof p{font-size:25px;color:var(--muted);margin-top:12px!important}.c-insight-edge_to_edge .c-insight-assertion{left:96px;top:170px;width:1728px}.c-insight-edge_to_edge .c-insight-spine{top:540px;height:110px;left:0;right:0;opacity:.95}.c-insight-edge_to_edge .c-insight-proofs{top:700px}
.c-pathway-visual{position:absolute;left:160px;top:340px;width:1600px;height:650px}.c-timeline-visual{position:absolute;left:160px;top:310px;width:1600px;height:760px}
.c-metric-head{width:1040px}.c-metric-monument{position:absolute;left:100px;top:410px;width:760px}.c-metric-monument strong{display:block;font-family:Georgia,'Times New Roman',serif;font-size:190px;line-height:.82;letter-spacing:-.06em;color:var(--accent)}.c-metric-monument span{display:block;font-size:38px;font-weight:800;margin-top:24px}.c-metric-monument small{display:block;font-size:25px;color:var(--muted);margin-top:18px}.c-metric-bars{position:absolute;right:92px;top:430px;width:950px;height:430px}.c-metric-rail{position:absolute;right:100px;bottom:84px;display:flex;gap:38px}.c-secondary-metric{border-top:7px solid var(--accent);padding-top:16px;min-width:190px}.c-secondary-metric strong{display:block;font:64px/1 Georgia,'Times New Roman',serif}.c-secondary-metric span{display:block;font-size:22px;color:var(--muted);margin-top:10px}.c-metric-copy{position:absolute;left:100px;bottom:70px;width:760px}.c-metric-right_focal .c-metric-monument,.c-metric-align-right .c-metric-monument{left:auto;right:100px}.c-metric-right_focal .c-metric-bars,.c-metric-align-right .c-metric-bars{right:auto;left:80px}.c-metric-right_focal .c-metric-rail,.c-metric-align-right .c-metric-rail{right:auto;left:100px}.c-metric-right_focal .c-metric-copy,.c-metric-align-right .c-metric-copy{left:auto;right:100px}.c-metric-centered_monument .c-metric-head{left:300px;width:1320px;text-align:center}.c-metric-centered_monument .c-metric-monument{left:380px;top:390px;width:1160px;text-align:center}.c-metric-centered_monument .c-metric-center-rule{position:absolute;left:430px;right:430px;top:710px;height:10px;background:var(--accent)}.c-metric-centered_monument .c-metric-rail{left:430px;right:430px;bottom:90px;justify-content:center}.c-metric-centered_monument .c-metric-copy{display:none}
.c-system-visual{position:absolute;left:160px;top:300px;width:1600px;height:760px}.c-shift-head{width:1320px}.c-shift-stage{position:absolute;left:96px;right:96px;top:430px;bottom:70px;display:grid;grid-template-columns:40fr 160px 60fr;align-items:stretch}.c-shift-state{position:relative;padding:58px 62px;overflow:hidden}.c-shift-state>strong{display:block;font:54px/1 Georgia,'Times New Roman',serif;margin-bottom:48px}.c-shift-current{background:var(--fg);color:var(--bg);clip-path:polygon(0 0,86% 0,100% 100%,0 100%);padding-right:100px}.c-shift-current .c-shift-item p{color:var(--bg);opacity:.72}.c-shift-future{padding-left:76px}.c-shift-future:before{content:'';position:absolute;left:0;top:0;width:14px;height:100%;background:var(--accent)}.c-shift-arrow{display:grid;place-items:center;color:var(--accent);font-size:110px;font-weight:800;transform:translateX(-14px)}.c-shift-item{max-width:610px;padding:0 0 28px}.c-shift-item+.c-shift-item{margin-top:20px}.c-shift-item span{display:block;font-size:32px;font-weight:800}.c-shift-item p{font-size:25px;color:var(--muted);margin-top:10px!important}.c-shift-diagonal_flow .c-shift-stage{transform:skewX(-6deg);grid-template-columns:1fr 140px 1fr}.c-shift-diagonal_flow .c-shift-state>*{transform:skewX(6deg)}
"""
