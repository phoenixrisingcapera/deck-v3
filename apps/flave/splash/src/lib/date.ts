/**
 * Coerce any frontmatter date value to a Date or undefined. Tolerant of the
 * loader's raw-frontmatter fallback path: when schema validation fails, dates
 * arrive as strings. Sorting + formatting code goes through this helper so a
 * single bad value never crashes the page.
 */
export function toDate(v: unknown): Date | undefined {
  if (v instanceof Date) return Number.isNaN(v.getTime()) ? undefined : v;
  if (typeof v === 'number') {
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? undefined : d;
  }
  if (typeof v === 'string') {
    const t = v.trim();
    if (t === '' || t === '[]' || t === '~' || t === 'TBD' || t === 'tbd') return undefined;
    const d = new Date(t);
    return Number.isNaN(d.getTime()) ? undefined : d;
  }
  return undefined;
}

/**
 * Format a Date as e.g. "May 3, 2026" — used in changelog teasers + detail.
 *
 * `timeZone: 'UTC'` is load-bearing, not cosmetic. Frontmatter dates are
 * date-only (`2026-08-15`), which YAML parses to UTC midnight. Rendering
 * that in the build machine's local zone shows the previous day for anyone
 * west of UTC — every date on the site off by one. Formatting in UTC keeps
 * the displayed date identical to the string an author typed.
 *
 * Accepts undefined so callers can pass `toDate(...)` straight through; the
 * lenient-schema fallback (see content.config.ts) means dates are not
 * guaranteed to parse.
 */
export function formatDate(d: Date | undefined): string {
  if (!d) return '';
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

/** Compact ISO yyyy-mm-dd. Used as the dateline above titles. */
export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
