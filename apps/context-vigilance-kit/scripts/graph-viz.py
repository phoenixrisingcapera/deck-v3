#!/usr/bin/env python3
"""
graph-viz.py

Render the Graphiti knowledge graph as a single self-contained HTML file —
no login, no Cypher, no CDN. Open the file and look at the graph.

Why this is a tracked script
----------------------------
A version of this was built ad hoc on 2026-08-15 as two heredocs in a session
scratchpad. It worked, it was shown, and then the scratchpad was cleaned and
it was gone — including the generator. That is the failure mode the tree's
CLAUDE.md warns about: a thing that lives only in a session transcript is not
codified. This is the codified version.

What it shows
-------------
  * Entities, colored by the ontology in ingest-changelogs-to-graphiti.py
    (Repo / Capability / Convention / Tool / Person).
  * Node radius scales with degree, so hubs are visually obvious.
  * RELATES_TO edges. Edges with `invalid_at` set are drawn red and dashed —
    facts Graphiti recorded as true and later learned had stopped being true.
    That bi-temporal distinction is the thing a vector index cannot express,
    so it gets the loudest visual treatment.
  * Hover a node for its summary; hover an edge for its fact and validity
    window. Click a legend row to filter a type in or out. Drag to rearrange,
    scroll to zoom.

Scale
-----
The full graph is thousands of nodes and does not lay out usefully in a
browser. Default is the top --limit entities by degree, which keeps the
hubs and drops one-off leaves. Raise it if you want more, but past ~600
nodes the force simulation stops being readable.

The force simulation is hand-rolled (~60 lines of vanilla JS) rather than
pulling d3 from a CDN, because "self-contained" is the entire point — this
file has to still work when it is emailed, archived, or opened offline.

Safe to run while an ingest is in flight; every query is read-only.

Usage:
    python scripts/graph-viz.py
    python scripts/graph-viz.py --limit 400 --out /tmp/graph.html
    python scripts/graph-viz.py --group-id lossless-changelog --open
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KIT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import graphiti_clients as gc  # noqa: E402

DEFAULT_GROUP_ID = "lossless-changelog"

TYPE_COLORS = {
    "Repo": "#f59e0b",
    "Capability": "#3b82f6",
    "Convention": "#a855f7",
    "Tool": "#10b981",
    "Person": "#ec4899",
    "Entity": "#94a3b8",
}


def fetch(group_id: str, limit: int) -> tuple[list[dict], list[dict]]:
    """Pull the top-`limit` entities by degree plus the edges among them."""
    from neo4j import GraphDatabase

    settings = gc.GraphitiSettings.from_env()
    password = os.getenv("NEO4J_PASSWORD", "losslessgraph")
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, password)
    )

    node_query = """
    MATCH (n:Entity {group_id: $g})
    OPTIONAL MATCH (n)-[r:RELATES_TO {group_id: $g}]-()
    WITH n, count(r) AS degree
    ORDER BY degree DESC
    LIMIT $limit
    RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
           labels(n) AS labels, degree
    """
    edge_query = """
    MATCH (a:Entity {group_id: $g})-[r:RELATES_TO {group_id: $g}]->(b:Entity)
    WHERE a.uuid IN $uuids AND b.uuid IN $uuids
    RETURN a.uuid AS source, b.uuid AS target, r.fact AS fact,
           r.name AS name, toString(r.valid_at) AS valid_at,
           toString(r.invalid_at) AS invalid_at
    """

    with driver.session() as session:
        nodes = [dict(r) for r in session.run(node_query, g=group_id, limit=limit)]
        uuids = [n["uuid"] for n in nodes]
        edges = [dict(r) for r in session.run(edge_query, g=group_id, uuids=uuids)]
    driver.close()

    for node in nodes:
        # The ontology label is whichever label is not the generic 'Entity'.
        node["type"] = next(
            (l for l in node["labels"] if l != "Entity"), "Entity"
        )
        node.pop("labels", None)
    return nodes, edges


def render(nodes: list[dict], edges: list[dict], group_id: str) -> str:
    counts: dict[str, int] = {}
    for n in nodes:
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    superseded = sum(1 for e in edges if e.get("invalid_at"))

    payload = json.dumps(
        {"nodes": nodes, "edges": edges, "colors": TYPE_COLORS}, ensure_ascii=False
    )
    legend = "".join(
        f'<div class="lg" data-t="{t}"><i style="background:{TYPE_COLORS.get(t, "#94a3b8")}"></i>'
        f"<span>{t}</span><b>{c}</b></div>"
        for t, c in sorted(counts.items(), key=lambda kv: -kv[1])
    )

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Graphiti — {group_id}</title>
<style>
  :root {{ --bg:#0b1020; --fg:#e6edf7; --dim:#8b9bb4; --panel:#151c33; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; overflow:hidden; }}
  header {{ position:fixed; top:0; left:0; right:0; padding:10px 16px; z-index:5;
            background:linear-gradient(180deg,rgba(11,16,32,.96),rgba(11,16,32,0)); }}
  h1 {{ margin:0; font-size:15px; font-weight:600; letter-spacing:.2px; }}
  .sub {{ color:var(--dim); font-size:12px; }}
  #legend {{ position:fixed; top:56px; left:16px; z-index:5; background:var(--panel);
             border:1px solid #24304f; border-radius:10px; padding:8px; min-width:190px; }}
  .lg {{ display:flex; align-items:center; gap:8px; padding:4px 6px; border-radius:6px; cursor:pointer; }}
  .lg:hover {{ background:#1d2745; }}
  .lg.off {{ opacity:.35; }}
  .lg i {{ width:11px; height:11px; border-radius:50%; flex:none; }}
  .lg span {{ flex:1; }}
  .lg b {{ color:var(--dim); font-weight:500; }}
  .note {{ margin-top:6px; padding:6px; border-top:1px solid #24304f; color:var(--dim); font-size:12px; }}
  .note s {{ color:#ef4444; text-decoration:none; }}
  #tip {{ position:fixed; z-index:9; max-width:340px; background:#0f1730; color:var(--fg);
          border:1px solid #2b3a63; border-radius:8px; padding:9px 11px;
          font-size:12.5px; pointer-events:none; opacity:0; transition:opacity .1s; }}
  #tip h4 {{ margin:0 0 4px; font-size:13px; }}
  #tip .m {{ color:var(--dim); margin-top:5px; font-size:11.5px; }}
  canvas {{ display:block; }}
</style>
<header>
  <h1>Graphiti knowledge graph — <span style="color:#7aa2f7">{group_id}</span></h1>
  <div class="sub">{len(nodes)} entities · {len(edges)} relationships · {superseded} superseded</div>
</header>
<div id="legend">{legend}
  <div class="note"><s>— — —</s> red dashed = fact that stopped being true</div>
</div>
<div id="tip"></div>
<canvas id="c"></canvas>
<script>
const DATA = {payload};
const cv = document.getElementById('c'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
let W, H, DPR = devicePixelRatio || 1;
function size() {{
  W = innerWidth; H = innerHeight;
  cv.width = W * DPR; cv.height = H * DPR;
  cv.style.width = W + 'px'; cv.style.height = H + 'px';
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
}}
size(); addEventListener('resize', () => {{ size(); }});

const byId = new Map();
const maxDeg = Math.max(1, ...DATA.nodes.map(n => n.degree || 0));
DATA.nodes.forEach((n, i) => {{
  const a = (i / DATA.nodes.length) * Math.PI * 2;
  n.x = W/2 + Math.cos(a) * Math.min(W, H) * 0.32 + (Math.sin(i * 7.13) * 40);
  n.y = H/2 + Math.sin(a) * Math.min(W, H) * 0.32 + (Math.cos(i * 3.71) * 40);
  n.vx = n.vy = 0;
  n.r = 4 + 13 * Math.sqrt((n.degree || 0) / maxDeg);
  n.on = true;
  byId.set(n.uuid, n);
}});
const links = DATA.edges.map(e => ({{ ...e, s: byId.get(e.source), t: byId.get(e.target) }}))
                        .filter(l => l.s && l.t);

// --- force simulation: repulsion + spring + centering, cooled over time ---
let alpha = 1;
function step() {{
  const active = DATA.nodes.filter(n => n.on);
  for (let i = 0; i < active.length; i++) {{
    const a = active[i];
    for (let j = i + 1; j < active.length; j++) {{
      const b = active[j];
      let dx = b.x - a.x, dy = b.y - a.y, d2 = dx*dx + dy*dy || 1;
      if (d2 > 90000) continue;                 // ignore distant pairs — O(n²) guard
      const f = (900 * alpha) / d2, d = Math.sqrt(d2);
      const ux = dx/d*f, uy = dy/d*f;
      a.vx -= ux; a.vy -= uy; b.vx += ux; b.vy += uy;
    }}
  }}
  for (const l of links) {{
    if (!l.s.on || !l.t.on) continue;
    let dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
    const d = Math.hypot(dx, dy) || 1, f = (d - 90) * 0.0025 * alpha;
    const ux = dx/d*f, uy = dy/d*f;
    l.s.vx += ux; l.s.vy += uy; l.t.vx -= ux; l.t.vy -= uy;
  }}
  for (const n of active) {{
    n.vx += (W/2 - n.x) * 0.0008 * alpha;
    n.vy += (H/2 - n.y) * 0.0008 * alpha;
    if (n !== drag) {{ n.x += (n.vx *= 0.82); n.y += (n.vy *= 0.82); }}
  }}
  if (alpha > 0.02) alpha *= 0.997;
}}

let view = {{ k: 1, x: 0, y: 0 }}, drag = null, hover = null;
function draw() {{
  ctx.clearRect(0, 0, W, H);
  ctx.save(); ctx.translate(view.x, view.y); ctx.scale(view.k, view.k);
  for (const l of links) {{
    if (!l.s.on || !l.t.on) continue;
    const dead = !!l.invalid_at;
    ctx.beginPath();
    ctx.setLineDash(dead ? [5, 4] : []);
    ctx.strokeStyle = dead ? 'rgba(239,68,68,.75)' : 'rgba(122,162,247,.20)';
    ctx.lineWidth = (dead ? 1.4 : 0.9) / view.k;
    ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke();
  }}
  ctx.setLineDash([]);
  for (const n of DATA.nodes) {{
    if (!n.on) continue;
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.284);
    ctx.fillStyle = DATA.colors[n.type] || '#94a3b8';
    ctx.globalAlpha = hover && hover !== n ? 0.5 : 1;
    ctx.fill();
    if (hover === n) {{ ctx.lineWidth = 2/view.k; ctx.strokeStyle = '#fff'; ctx.stroke(); }}
    ctx.globalAlpha = 1;
    if (n.r > 8 || hover === n) {{
      ctx.fillStyle = '#dce6f7'; ctx.font = `${{Math.max(9, 11/view.k)}}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(n.name.slice(0, 26), n.x, n.y - n.r - 3);
    }}
  }}
  ctx.restore();
}}
(function loop() {{ step(); draw(); requestAnimationFrame(loop); }})();

const toWorld = e => ({{ x: (e.clientX - view.x)/view.k, y: (e.clientY - view.y)/view.k }});
function pick(p) {{
  let best = null, bd = 1e9;
  for (const n of DATA.nodes) {{
    if (!n.on) continue;
    const d = Math.hypot(n.x - p.x, n.y - p.y);
    if (d < n.r + 4 && d < bd) {{ bd = d; best = n; }}
  }}
  return best;
}}
cv.addEventListener('mousemove', e => {{
  const p = toWorld(e);
  if (drag) {{ drag.x = p.x; drag.y = p.y; alpha = Math.max(alpha, 0.25); return; }}
  const n = pick(p); hover = n;
  cv.style.cursor = n ? 'pointer' : 'grab';
  if (n) {{
    tip.innerHTML = `<h4>${{esc(n.name)}}</h4><div>${{esc(n.summary || '')}}</div>`
      + `<div class="m">${{n.type}} · ${{n.degree}} connections</div>`;
    tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - 356) + 'px';
    tip.style.top  = Math.min(e.clientY + 14, innerHeight - 130) + 'px';
    return;
  }}
  const l = pickEdge(p);
  if (l) {{
    tip.innerHTML = `<h4>${{esc(l.name || 'RELATES_TO')}}</h4><div>${{esc(l.fact || '')}}</div>`
      + `<div class="m">valid ${{(l.valid_at||'?').slice(0,10)}}`
      + (l.invalid_at ? ` · <span style="color:#ef4444">invalid ${{l.invalid_at.slice(0,10)}}</span>` : '')
      + `</div>`;
    tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - 356) + 'px';
    tip.style.top  = Math.min(e.clientY + 14, innerHeight - 130) + 'px';
  }} else tip.style.opacity = 0;
}});
function pickEdge(p) {{
  for (const l of links) {{
    if (!l.s.on || !l.t.on) continue;
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, L2 = dx*dx + dy*dy || 1;
    let t = ((p.x - l.s.x)*dx + (p.y - l.s.y)*dy) / L2;
    t = Math.max(0, Math.min(1, t));
    if (Math.hypot(p.x - (l.s.x + t*dx), p.y - (l.s.y + t*dy)) < 4/view.k) return l;
  }}
  return null;
}}
cv.addEventListener('mousedown', e => {{
  const n = pick(toWorld(e));
  if (n) drag = n; else {{ pan = {{ x: e.clientX - view.x, y: e.clientY - view.y }}; }}
}});
let pan = null;
addEventListener('mousemove', e => {{ if (pan) {{ view.x = e.clientX - pan.x; view.y = e.clientY - pan.y; }} }});
addEventListener('mouseup', () => {{ drag = null; pan = null; }});
cv.addEventListener('wheel', e => {{
  e.preventDefault();
  const s = Math.exp(-e.deltaY * 0.0012), p = toWorld(e);
  view.k *= s; view.x = e.clientX - p.x * view.k; view.y = e.clientY - p.y * view.k;
}}, {{ passive: false }});

document.querySelectorAll('.lg').forEach(el => el.addEventListener('click', () => {{
  const t = el.dataset.t; el.classList.toggle('off');
  const off = el.classList.contains('off');
  DATA.nodes.forEach(n => {{ if (n.type === t) n.on = !off; }});
  alpha = Math.max(alpha, 0.4);
}}));
function esc(s) {{ return String(s || '').replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]); }}
</script>
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    p.add_argument("--limit", type=int, default=300,
                   help="Top N entities by degree (default 300).")
    p.add_argument("--out", type=Path,
                   default=KIT_ROOT / ".graphiti-state" / "graph.html")
    p.add_argument("--open", action="store_true", help="Open it when done.")
    args = p.parse_args()

    gc.load_env_chain(KIT_ROOT)
    nodes, edges = fetch(args.group_id, args.limit)
    if not nodes:
        print(f"error: no entities in group_id={args.group_id!r}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(nodes, edges, args.group_id), encoding="utf-8")

    superseded = sum(1 for e in edges if e.get("invalid_at"))
    print(f"  wrote {args.out}")
    print(f"  {len(nodes)} entities · {len(edges)} edges · {superseded} superseded")
    if args.open:
        subprocess.run(["open", str(args.out)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
