/**
 * Source mapping.
 *
 * remark stamps `position` on every node it parses, so plain prose can be
 * mapped back to a source range and edited in place. lfm's *synthesized* nodes
 * (callouts, citations, heading blocks) carry no position — measured 2026-08-20
 * across all nine plugins, none of which set it. That asymmetry is D-23, and it
 * is why the Compose pane edits prose directly but only selects components.
 *
 * Emitting nothing when position is absent is the correct behaviour: a stale
 * range is worse than none, per lfm's own comment in lfm-heading-blocks.ts.
 */
export type SrcAttrs = Record<string, number>;

export function srcAttrs(node: unknown): SrcAttrs {
  const pos = (node as { position?: { start?: { offset?: number }; end?: { offset?: number } } })
    ?.position;
  const start = pos?.start?.offset;
  const end = pos?.end?.offset;
  if (typeof start !== 'number' || typeof end !== 'number') return {};
  return { 'data-src-start': start, 'data-src-end': end };
}
