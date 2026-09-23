from __future__ import annotations

from html import escape

from app.services.visual_intelligence.models import DiagramSpec


def render_diagram_svg(spec: DiagramSpec, *, width: int = 1200, height: int = 640) -> str:
    """Lay out declared nodes and edges; the LLM never writes executable SVG."""
    if width < 480 or height < 260:
        raise ValueError("Diagram canvas is below the supported minimum")
    count = len(spec.nodes)
    columns = min(4, count)
    rows = (count + columns - 1) // columns
    node_width, node_height = min(230, (width - 100) / columns - 30), 96
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(spec.nodes):
        row, column = divmod(index, columns)
        x = 50 + column * ((width - 100) / columns) + (((width - 100) / columns) - node_width) / 2
        y = 100 + row * ((height - 150) / max(1, rows))
        positions[node.id] = (x, y)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(spec.title)}">',
        '<rect width="100%" height="100%" fill="#0B1020"/>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748B"/></marker></defs>',
        f'<text x="50" y="50" fill="#F8FAFC" font-family="Inter,Arial,sans-serif" font-size="28" font-weight="700">{escape(spec.title)}</text>',
    ]
    for edge in spec.edges:
        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]
        parts.append(f'<line x1="{sx+node_width:.2f}" y1="{sy+node_height/2:.2f}" x2="{tx:.2f}" y2="{ty+node_height/2:.2f}" stroke="#64748B" stroke-width="3" marker-end="url(#arrow)"/>')
    for node in spec.nodes:
        x, y = positions[node.id]
        parts.extend([
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{node_width:.2f}" height="{node_height}" rx="14" fill="#172033" stroke="#36C5F0" stroke-width="2"/>',
            f'<text x="{x+node_width/2:.2f}" y="{y+node_height/2+6:.2f}" text-anchor="middle" fill="#F8FAFC" font-family="Inter,Arial,sans-serif" font-size="17">{escape(node.label)}</text>',
        ])
    parts.append("</svg>")
    return "".join(parts)
