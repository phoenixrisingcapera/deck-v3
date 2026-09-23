import { invoke } from '@tauri-apps/api/core';
import type { Transport, HttpMethod, ApiError, JobEventHandler } from './types';

const SIDECAR_BASE = 'http://127.0.0.1:8765';

export class LocalTransport implements Transport {
  async request<T = unknown>(method: HttpMethod, path: string, body?: unknown): Promise<T> {
    try {
      return await invoke<T>('api_dispatch', { method, path, body: body ?? null });
    } catch (e) {
      if (typeof e === 'object' && e !== null && 'status' in e && 'code' in e) {
        throw e as ApiError;
      }
      const message = typeof e === 'string' ? e : (e as Error)?.message ?? 'Unknown transport error';
      throw { status: 500, code: 'transport_error', message } satisfies ApiError;
    }
  }

  /**
   * SSE streams go direct from the webview to the FastAPI sidecar — bypassing
   * the Rust dispatcher avoids reimplementing chunked HTTP forwarding. The
   * sidecar's CORS allowlist already covers tauri:// and http://localhost origins.
   */
  subscribeEvents(jobId: string, onEvent: JobEventHandler): () => void {
    const url = `${SIDECAR_BASE}/memos/${encodeURIComponent(jobId)}/events`;
    const es = new EventSource(url);

    es.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        // Ignore malformed events rather than killing the stream.
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects on transient errors. If the sidecar truly
      // died, the bus will close on its end and our stream will go silent —
      // the caller's UI signals that via the absence of events, not via this hook.
    };

    return () => {
      es.close();
    };
  }
}
