import { getTransport, type ApiError } from '$lib/transport';
import { settings } from '$lib/stores/settings.svelte';

/**
 * State for the source-approval surface.
 *
 * The analyst's verdict on each candidate is the whole product here: the
 * approved set is what the orchestrator's membership gate enforces
 * downstream, so anything that reaches `Sources.md` with a non-rejected
 * verdict becomes citable and anything else does not.
 *
 * Every candidate shown originates from a search index (SearXNG) or from
 * the analyst pasting a URL. No language model proposes a source — that
 * is the invariant the whole design rests on.
 */

export type Verdict = '' | 'approved' | 'rejected';

export interface SourceRow {
  url: string;
  title: string;
  publisher: string;
  published_date: string;
  sections: string[];
  rank: number;
  verdict: Verdict;
  verdict_reason: string;
  note: string;
  /**
   * A verdict written by the validator rather than by a person — e.g.
   * "HTTP 200 (body verified)", "timeout", "403". Kept for display but
   * deliberately NOT treated as an analyst verdict: the validator answers
   * "does this resolve?", which is exactly the question this whole feature
   * exists to stop confusing with "did we approve it?".
   */
  machineVerdict?: string;
  /** `internal_only` must never be silently downgraded — it governs
   *  whether a source may be cited outside the firm. */
  sensitivity: string;
  /**
   * The source's frontmatter exactly as it was read, so a write can
   * round-trip keys this UI does not model. The GET endpoint preserves
   * hand-added keys on purpose; without this the write path discarded
   * them, which is how 93 sources lost `sensitivity` and 8 of them lost
   * `internal_only`.
   */
  raw?: Record<string, unknown>;
  /** Present on search results — which query surfaced this. */
  found_via?: string;
  /** Already in the corpus. Flagged, never hidden. */
  known?: boolean;
}

/** Verdicts a person can set. Anything else on disk is a machine verdict. */
const ANALYST_VERDICTS = new Set(['approved', 'rejected', 'denied', 'excluded']);

function splitVerdict(raw: string): { verdict: Verdict; machineVerdict?: string } {
  const v = (raw ?? '').trim().toLowerCase();
  if (!v) return { verdict: '' };
  if (v === 'approved') return { verdict: 'approved' };
  if (ANALYST_VERDICTS.has(v)) return { verdict: 'rejected' };
  return { verdict: '', machineVerdict: raw };
}

export interface Candidate {
  url: string;
  title: string;
  content: string;
  published_date?: string;
  known?: boolean;
  found_via?: string;
}

export interface RecoveryCandidate {
  recovered_url: string;
  matched_title: string;
  claimed_title: string;
  jaccard: number;
  via_provider: string;
}

export const DENY_REASONS = [
  'dead link',
  'paywalled',
  'wrong entity',
  'low quality',
  'off topic',
  'not a source (index/feed)',
] as const;

/**
 * Every request routed through the Rust dispatcher must carry `repoPath` —
 * it is what `forward_to_sidecar` uses to lazy-spawn the sidecar, and it is
 * stripped before the body reaches FastAPI. Omitting it fails validation at
 * the Rust layer, never reaching Python.
 */
function withRepo<T extends Record<string, unknown>>(body: T): T & { repoPath: string } {
  return { ...body, repoPath: settings.repoPath ?? '' };
}

function blankRow(url: string, partial: Partial<SourceRow> = {}): SourceRow {
  return {
    url,
    title: '',
    publisher: '',
    published_date: '',
    sections: [],
    rank: 1,
    sensitivity: 'citable_externally',
    verdict: '',
    verdict_reason: '',
    note: '',
    ...partial,
  };
}

function errText(e: unknown): string {
  const err = e as ApiError;
  return err?.message ?? String(e);
}

class SourcesState {
  firm = $state<string | null>(null);
  deal = $state<string | null>(null);

  rows = $state<SourceRow[]>([]);
  meta = $state<Record<string, unknown>>({});
  body = $state('');
  mode = $state('aggregated');
  origin = $state<string | null>(null);
  loadedPath = $state<string | null>(null);

  loading = $state(false);
  saving = $state(false);
  error = $state<string | null>(null);

  // Autosave. 80+ sources is not one sitting's work, and a manual-save-only
  // surface loses a session to a closed window. Every mutation schedules a
  // debounced write; the UI shows which of these three states it is in so
  // "is my work safe" is never a guess.
  dirty = $state(false);
  lastSavedAt = $state<string | null>(null);
  autosaveError = $state<string | null>(null);
  private saveTimer: ReturnType<typeof setTimeout> | null = null;
  private static readonly DEBOUNCE_MS = 1200;

  // Search panel
  query = $state('');
  searching = $state(false);
  searchAvailable = $state(true);
  searchReason = $state<string | null>(null);
  candidates = $state<Candidate[]>([]);

  // Per-URL transient UI state, keyed by url.
  previews = $state<Record<string, string>>({});
  /** URLs whose cheap-tier metadata lookup is in flight. */
  fetchingMeta = $state<Set<string>>(new Set());
  private inFlightMeta = 0;
  private static readonly META_CONCURRENCY = 3;
  busyUrl = $state<string | null>(null);
  recoveries = $state<Record<string, RecoveryCandidate | { failed: string }>>({});

  approvedCount = $derived(this.rows.filter((r) => r.verdict === 'approved').length);
  rejectedCount = $derived(this.rows.filter((r) => r.verdict === 'rejected').length);
  unreviewedCount = $derived(this.rows.filter((r) => r.verdict === '').length);
  reviewedCount = $derived(this.rows.length - this.unreviewedCount);
  /** Index of the first unreviewed row — where to resume a part-done list. */
  firstUnreviewedIndex = $derived(this.rows.findIndex((r) => r.verdict === ''));

  saveState = $derived(
    this.saving ? 'saving' : this.dirty ? 'unsaved' : this.lastSavedAt ? 'saved' : 'clean',
  );

  /** URLs already in the list — used to flag duplicate search results. */
  private urlSet = $derived(new Set(this.rows.map((r) => r.url.trim())));

  async load(firm: string, deal: string) {
    this.firm = firm;
    this.deal = deal;
    this.loading = true;
    this.error = null;
    try {
      const res = await getTransport().request<{
        exists: boolean;
        origin: string | null;
        path: string;
        meta: Record<string, unknown>;
        sources: Record<string, unknown>[];
        body: string;
        mode?: string;
      }>(
        'GET',
        `/firms/${encodeURIComponent(firm)}/deals/${encodeURIComponent(deal)}/sources`,
        // A GET still needs a body here: repoPath travels in it, not in a
        // query string, because that is what the dispatcher reads.
        withRepo({}),
      );

      this.rows = (res.sources ?? []).map((s) =>
        blankRow(String(s.url ?? ''), {
          title: String(s.title ?? ''),
          publisher: String(s.publisher ?? ''),
          published_date: String(s.published_date ?? ''),
          sections: Array.isArray(s.sections) ? (s.sections as string[]) : [],
          rank: Number(s.rank ?? 1) || 1,
          sensitivity: String(s.sensitivity ?? 'citable_externally'),
          raw: s,
          ...splitVerdict(String(s.verdict ?? '')),
          verdict_reason: String(s.verdict_reason ?? ''),
          note: String(s.note ?? ''),
        }),
      );
      this.meta = res.meta ?? {};
      this.body = res.body ?? '';
      this.mode = res.mode ?? 'aggregated';
      this.origin = res.origin;
      this.loadedPath = res.path;
    } catch (e) {
      this.error = errText(e);
    } finally {
      this.loading = false;
    }
  }

  setVerdict(url: string, verdict: Verdict, reason = '') {
    this.rows = this.rows.map((r) =>
      r.url === url ? { ...r, verdict, verdict_reason: verdict === 'rejected' ? reason : '' } : r,
    );
    this.touch();
  }

  approveAllUnreviewed() {
    this.rows = this.rows.map((r) => (r.verdict === '' ? { ...r, verdict: 'approved' } : r));
    this.touch();
  }

  remove(url: string) {
    this.rows = this.rows.filter((r) => r.url !== url);
    this.touch();
  }

  /** Mark unsaved and schedule a debounced autosave. */
  touch() {
    this.dirty = true;
    if (this.saveTimer) clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => void this.autosave(), SourcesState.DEBOUNCE_MS);
  }

  private async autosave() {
    if (!this.firm || !this.deal || !this.dirty) return;
    const ok = await this.write(false, { autosave: true });
    // A failed autosave must NOT clear `dirty` — the work is still only in
    // memory, and telling the analyst it is saved would be the one lie this
    // surface cannot afford.
    this.autosaveError = ok ? null : this.error;
  }

  /** Write immediately, e.g. before navigating away. */
  async flush() {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
    if (this.dirty) await this.autosave();
  }

  /** Add a URL by paste. Returns false when it is already in the list. */
  add(url: string, partial: Partial<SourceRow> = {}): boolean {
    const clean = url.trim();
    if (!clean || this.urlSet.has(clean)) return false;
    this.rows = [...this.rows, blankRow(clean, { verdict: 'approved', ...partial })];
    this.touch();
    // Fire-and-forget so the row appears instantly; the title fills in a
    // beat later. Skipped when the caller already supplied one (search
    // results arrive with a title from the index).
    if (!partial.title) void this.fetchMetadata(clean);
    return true;
  }

  hasUrl(url: string): boolean {
    return this.urlSet.has(url.trim());
  }

  // ---- Metadata -----------------------------------------------------------

  /**
   * Fold a fetch response into the row. The single merge point for both
   * the paste path and Preview, so the two cannot drift.
   *
   * Fill-the-blanks, never replace: a scraped <title> is frequently worse
   * than what a person typed (SEO suffixes, site names, truncation), and
   * making the merge additive is also what makes re-fetching idempotent.
   */
  applyFetchedMetadata(
    url: string,
    res: { title?: string; published_at?: string; excerpt?: string },
  ) {
    let changed = false;
    this.rows = this.rows.map((r) => {
      if (r.url !== url) return r;
      const next = { ...r };
      if (!next.title && res.title) { next.title = res.title; changed = true; }
      if (!next.published_date && res.published_at) {
        next.published_date = res.published_at;
        changed = true;
      }
      return next;
    });
    if (changed) this.touch();
  }

  /**
   * The cheap tier: metadata + excerpt, no body stored.
   *
   * Fired on paste so a row can name itself. Without it `add()` leaves
   * title empty and the UI falls back to the hostname — 80 rows reading
   * "cbinsights.com" are unscannable, and re-search is dead because
   * attempt_url_recovery needs a title.
   *
   * Concurrency-gated: pasting ten links in a row should not fire ten
   * simultaneous Jina calls.
   */
  async fetchMetadata(url: string) {
    if (!this.firm || !this.deal) return;
    if (this.fetchingMeta.has(url)) return;

    while (this.inFlightMeta >= SourcesState.META_CONCURRENCY) {
      await new Promise((r) => setTimeout(r, 120));
    }
    this.inFlightMeta += 1;
    this.fetchingMeta = new Set([...this.fetchingMeta, url]);
    try {
      const res = await getTransport().request<{
        ok: boolean;
        title?: string;
        published_at?: string;
        excerpt?: string;
      }>('POST', '/actions/fetch-source', withRepo({
        url,
        firm: this.firm,
        deal: this.deal,
        metadata_only: true,
      }));
      if (res.ok) this.applyFetchedMetadata(url, res);
    } catch {
      // A failed lookup leaves the row showing its host — degraded, but
      // still reviewable and approvable. Never block on metadata.
    } finally {
      this.inFlightMeta -= 1;
      const next = new Set(this.fetchingMeta);
      next.delete(url);
      this.fetchingMeta = next;
    }
  }

  // ---- Search -----------------------------------------------------------

  async search(term?: string) {
    const q = (term ?? this.query).trim();
    if (!q || !this.firm || !this.deal) return;
    this.searching = true;
    this.error = null;
    try {
      const res = await getTransport().request<{
        available: boolean;
        reason: string | null;
        candidates: Candidate[];
      }>('POST', '/actions/search-sources', withRepo({ query: q, max_per_term: 10 }));
      this.searchAvailable = res.available;
      this.searchReason = res.reason;
      this.candidates = res.candidates ?? [];
    } catch (e) {
      this.error = errText(e);
    } finally {
      this.searching = false;
    }
  }

  /** Seed candidates from the deck-derived terms, with no query typed. */
  async seedFromDeal() {
    if (!this.firm || !this.deal) return;
    this.searching = true;
    try {
      const res = await getTransport().request<{
        available: boolean;
        reason: string | null;
        candidates: Candidate[];
      }>('POST', '/actions/search-sources', withRepo({ firm: this.firm, deal: this.deal }));
      this.searchAvailable = res.available;
      this.searchReason = res.reason;
      this.candidates = res.candidates ?? [];
    } catch (e) {
      this.error = errText(e);
    } finally {
      this.searching = false;
    }
  }

  // ---- Per-source actions ----------------------------------------------

  async preview(url: string) {
    if (this.previews[url]) {
      const { [url]: _drop, ...rest } = this.previews;
      this.previews = rest;
      return;
    }
    this.busyUrl = url;
    try {
      // firm/deal let the sidecar file the fetched content as a per-source
      // markdown file instead of us rendering it once and dropping it.
      // title/publisher seed the frontmatter from what the analyst already
      // curated, rather than whatever the page's <title> happens to say.
      const row = this.rows.find((r) => r.url === url);
      const res = await getTransport().request<{
        ok: boolean;
        markdown?: string;
        error?: string;
        saved_to?: string | null;
        title?: string;
        published_at?: string;
        excerpt?: string;
      }>(
        'POST',
        '/actions/fetch-source',
        withRepo({
          url,
          firm: this.firm ?? undefined,
          deal: this.deal ?? undefined,
          title: row?.title || undefined,
          publisher: row?.publisher || undefined,
        }),
      );
      // Preview corrects a bad title too — the metadata was already
      // fetched, so discarding it here is what produced the a16z bug.
      if (res.ok) this.applyFetchedMetadata(url, res);
      this.previews = {
        ...this.previews,
        [url]: res.ok ? (res.markdown ?? '') : `Could not fetch: ${res.error ?? 'unknown error'}`,
      };
    } catch (e) {
      this.previews = { ...this.previews, [url]: `Could not fetch: ${errText(e)}` };
    } finally {
      this.busyUrl = null;
    }
  }

  /**
   * Re-search for the real URL behind a dead or drifted citation. The third
   * option beside approve and deny: the article is real, the link is not.
   */
  async recover(url: string) {
    const row = this.rows.find((r) => r.url === url);
    if (!row) return;
    if (!row.title.trim()) {
      this.recoveries = {
        ...this.recoveries,
        [url]: { failed: 'No title on this source — recovery searches by title.' },
      };
      return;
    }
    this.busyUrl = url;
    try {
      const res = await getTransport().request<
        { ok: true } & RecoveryCandidate | { ok: false; reason: string }
      >('POST', '/actions/recover-source', withRepo({
        title: row.title,
        url: row.url,
        publisher: row.publisher || undefined,
      }));
      this.recoveries = {
        ...this.recoveries,
        [url]: res.ok ? (res as RecoveryCandidate) : { failed: (res as { reason: string }).reason },
      };
    } catch (e) {
      this.recoveries = { ...this.recoveries, [url]: { failed: errText(e) } };
    } finally {
      this.busyUrl = null;
    }
  }

  /** Accept a recovered URL in place of the original. */
  acceptRecovery(originalUrl: string) {
    const rec = this.recoveries[originalUrl];
    if (!rec || 'failed' in rec) return;
    this.rows = this.rows.map((r) =>
      r.url === originalUrl
        ? { ...r, url: rec.recovered_url, verdict: 'approved', verdict_reason: '' }
        : r,
    );
    const { [originalUrl]: _drop, ...rest } = this.recoveries;
    this.recoveries = rest;
    this.touch();
  }

  dismissRecovery(url: string) {
    const { [url]: _drop, ...rest } = this.recoveries;
    this.recoveries = rest;
  }

  // ---- Commit -----------------------------------------------------------

  /** An explicit checkpoint. Always backs up, unlike an autosave. */
  async saveDraft(): Promise<boolean> {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
    return this.write(false, { autosave: false });
  }

  /**
   * Approve the set and flip the deal into codified mode. This is what makes
   * the membership gate bite on the run that follows.
   */
  async approveAndCommit(): Promise<boolean> {
    return this.write(true);
  }

  private async write(codify: boolean, opts: { autosave?: boolean } = {}): Promise<boolean> {
    if (!this.firm || !this.deal) return false;
    this.saving = true;
    this.error = null;
    try {
      const payload = {
        firm: this.firm,
        deal: this.deal,
        meta: this.meta,
        body: this.body,
        // Spread the original frontmatter first so unmodelled keys
        // survive; the fields this UI owns then override. A write must
        // never be able to delete a field just because the UI does not
        // render it.
        sources: this.rows.map((r) => ({
          ...(r.raw ?? {}),
          url: r.url,
          title: r.title,
          publisher: r.publisher,
          published_date: r.published_date,
          sections: r.sections,
          rank: r.rank,
          sensitivity: r.sensitivity,
          verdict: r.verdict || r.machineVerdict || '',
          verdict_reason: r.verdict_reason,
          note: r.note,
        })),
      };
      if (codify) {
        await getTransport().request('POST', '/actions/approve-sources', withRepo(payload));
        this.mode = 'codified';
      } else {
        await getTransport().request(
          'POST',
          `/firms/${encodeURIComponent(this.firm)}/deals/${encodeURIComponent(this.deal)}/sources`,
          withRepo({
            meta: this.meta,
            sources: payload.sources,
            body: this.body,
            mode: this.mode,
            autosave: opts.autosave ?? false,
          }),
        );
      }
      // Only a write that actually landed may clear the dirty flag.
      this.dirty = false;
      this.lastSavedAt = new Date().toISOString();
      return true;
    } catch (e) {
      this.error = errText(e);
      return false;
    } finally {
      this.saving = false;
    }
  }

  reset() {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
    this.dirty = false;
    this.lastSavedAt = null;
    this.autosaveError = null;
    this.rows = [];
    this.candidates = [];
    this.previews = {};
    this.recoveries = {};
    this.query = '';
    this.error = null;
    this.origin = null;
    this.loadedPath = null;
  }
}

export const sources = new SourcesState();
