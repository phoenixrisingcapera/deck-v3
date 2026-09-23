/**
 * Helpers used by the index + detail pages to format provenance — the
 * `from`, `from_kind`, and `from_path` fields injected by the unionLoader.
 */

export type FromKind = 'parent' | 'app' | 'package' | string;

export interface ProvenanceMeta {
  from: string;
  fromKind: FromKind;
  fromPath?: string;
}

export function readProvenance(data: Record<string, unknown>, fallbackFrom: string): ProvenanceMeta {
  const from = (typeof data.from === 'string' && data.from.trim()) ? data.from : fallbackFrom;
  const fromKind = (typeof data.from_kind === 'string' && data.from_kind.trim()) ? data.from_kind : 'app';
  const fromPath = (typeof data.from_path === 'string' && data.from_path.trim()) ? data.from_path : undefined;
  return { from, fromKind, fromPath };
}

export function fromKindLabel(kind: FromKind): string {
  if (kind === 'parent') return 'Monorepo';
  if (kind === 'app') return 'App';
  if (kind === 'package') return 'Package';
  return String(kind);
}

/** CSS custom property to set on a `from-tag` so it picks up the per-peer color. */
export function threadStyle(slug: string): string {
  return `--from-thread: var(--thread__${slug}, var(--thread__default))`;
}

const DATE_KEYS = [
  'date_first_published',
  'date_authored_initial_draft',
  'date',
  'date_authored_current_draft',
  'date_modified',
  'date_last_updated',
  'date_created',
] as const;

export function pickDate(data: Record<string, unknown>, id: string): Date | null {
  for (const key of DATE_KEYS) {
    const v = data[key];
    if (v instanceof Date && !Number.isNaN(v.getTime())) return v;
  }
  const m = id.match(/(\d{4}-\d{2}-\d{2})/);
  if (m) {
    const d = new Date(m[1]);
    if (!Number.isNaN(d.getTime())) return d;
  }
  return null;
}

export function pickString(data: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const k of keys) {
    const v = data[k];
    if (typeof v === 'string' && v.trim()) return v;
  }
  return undefined;
}

export function fmtDate(d: Date | null, opts: 'short' | 'long' = 'short'): string {
  if (!d) return '—';
  if (opts === 'long') {
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  }
  return d.toISOString().slice(0, 10);
}

/** Top-level subdirectory under context-v/ (e.g. specs, plans, explorations). */
export function pickContextVKind(fromPath: string | undefined): string | null {
  if (!fromPath) return null;
  const segs = fromPath.split('/');
  if (segs.length < 2) return null;
  const head = segs[0];
  const known = ['specs', 'plans', 'explorations', 'blueprints', 'prompts', 'habits', 'conventions', 'reminders'];
  return known.includes(head) ? head : null;
}
