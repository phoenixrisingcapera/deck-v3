/**
 * hProperties passthrough.
 *
 * lfm computes presentational attributes — `class` on eyebrows, subheadings and
 * callouts, `id` on headings — and hangs them on `node.data.hProperties`. A
 * renderer that ignores them silently drops styling lfm already worked out,
 * which is what happened here until 2026-08-21: `$$ Eyebrow` produced a bare
 * `<p>` with its `eyebrow` class thrown away.
 *
 * Reading them rather than recomputing is the same discipline as heading ids:
 * one place decides, the render layer obeys.
 */
export function hProps(node: unknown): Record<string, unknown> {
  const p = (node as { data?: { hProperties?: Record<string, unknown> } })?.data?.hProperties;
  return p && typeof p === 'object' ? { ...p } : {};
}

export type Citation = {
  identifier: string;
  hex: string;
  index: number;
  title?: string;
  url?: string;
  source?: string;
};

/** Look up a footnote reference in the citation map lfm attaches to tree.data. */
export function citationFor(data: unknown, identifier: string): Citation | undefined {
  const ordered = (data as { citations?: { ordered?: Citation[] } })?.citations?.ordered;
  if (!Array.isArray(ordered)) return undefined;
  return ordered.find((c) => c.identifier === identifier);
}

export function allCitations(data: unknown): Citation[] {
  const ordered = (data as { citations?: { ordered?: Citation[] } })?.citations?.ordered;
  return Array.isArray(ordered) ? ordered : [];
}
