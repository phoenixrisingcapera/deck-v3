import { getTransport, type ApiError } from '$lib/transport';
import type { Outline } from '$lib/types';

class OutlinesState {
  outlines = $state<Outline[]>([]);
  loading = $state(false);
  error = $state<string | null>(null);
  loadedFor = $state<string | null>(null);

  async load(repoPath: string, force = false) {
    if (!force && this.loadedFor === repoPath && this.outlines.length > 0) {
      return;
    }

    this.loading = true;
    this.error = null;

    try {
      const res = await getTransport().request<{ outlines: Outline[] }>(
        'GET',
        '/outlines',
        { repoPath }
      );
      this.outlines = res.outlines;
      this.loadedFor = repoPath;
    } catch (e) {
      const err = e as ApiError;
      this.error = err.message ?? 'Failed to load outlines';
      this.outlines = [];
    } finally {
      this.loading = false;
    }
  }

  reset() {
    this.outlines = [];
    this.loadedFor = null;
    this.error = null;
  }
}

export const outlines = new OutlinesState();
