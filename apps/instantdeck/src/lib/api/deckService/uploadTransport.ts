// Bounded, idempotency-safe upload transport retry.
//
// The browser retries ONLY genuine safe transport failures and always resends
// the SAME `x-request-id` so the backend upload-request identity deduplicates
// the replay (a fresh upload action never inherits an old terminal workflow).
//
//   - Retryable: connection rejected by the network stack (fetch rejection),
//     request timeout, and gateway/unavailable 502/503/504 where the request
//     never reached a durable application handler.
//   - Terminal (never retried): 4xx client errors, plain 500 (the application
//     may have committed the upload before failing), and malformed success
//     bodies. Retrying those would mask client bugs or duplicate server work.

export const UPLOAD_TRANSPORT_RETRYABLE_STATUSES: ReadonlySet<number> = new Set([502, 503, 504]);
export const UPLOAD_MAX_TRANSPORT_RETRIES = 2;
export const UPLOAD_TRANSPORT_RETRY_DELAYS_MS: readonly number[] = [1000, 3000];
export const UPLOAD_TRANSPORT_TIMEOUT_MS = 30_000;

export const UPLOAD_UNKNOWN_OUTCOME_MESSAGE =
  'Upload outcome is unknown because the connection ended before a response. Check your decks before starting another upload.';

export type UploadTransportReadResponse<T> = (response: Response) => Promise<T>;

export type UploadTransportOptions<T> = {
  requestId: string;
  buildBody: () => BodyInit;
  endpointPath: string;
  readResponse: UploadTransportReadResponse<T>;
  fetchImpl?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
  sleep?: (ms: number) => Promise<void>;
  maxRetries?: number;
  delaysMs?: readonly number[];
  timeoutMs?: number;
};

function delayValue(delaysMs: readonly number[], attempt: number): number {
  return delaysMs[attempt] ?? delaysMs[delaysMs.length - 1] ?? 3000;
}

export function isTransportTimeoutError(error: unknown): boolean {
  return error instanceof Error && error.name === 'TimeoutError' && /timed out/i.test(error.message);
}

export async function postUploadWithTransportRetry<T>(options: UploadTransportOptions<T>): Promise<T> {
  const {
    requestId,
    buildBody,
    endpointPath,
    readResponse,
    fetchImpl = fetch,
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    maxRetries = UPLOAD_MAX_TRANSPORT_RETRIES,
    delaysMs = UPLOAD_TRANSPORT_RETRY_DELAYS_MS,
    timeoutMs = UPLOAD_TRANSPORT_TIMEOUT_MS
  } = options;

  for (let attempt = 0; ; attempt += 1) {
    let response: Response;
    try {
      // The identical request identity travels with every attempt so backend
      // idempotency turns a resend into a replay of the same upload, never a
      // duplicate deck or workflow.
      response = await fetchImpl(endpointPath, {
        method: 'POST',
        credentials: 'include',
        headers: { 'x-request-id': requestId },
        body: buildBody(),
        signal: AbortSignal.timeout(timeoutMs)
      });
    } catch {
      // Fetch rejection covers network errors and the AbortSignal timeout:
      // the request may or may not have reached the server, so the only safe
      // resend is one carrying the same request identity.
      if (attempt < maxRetries) {
        await sleep(delayValue(delaysMs, attempt));
        continue;
      }
      throw new Error(UPLOAD_UNKNOWN_OUTCOME_MESSAGE);
    }

    if (UPLOAD_TRANSPORT_RETRYABLE_STATUSES.has(response.status) && attempt < maxRetries) {
      await sleep(delayValue(delaysMs, attempt));
      continue;
    }

    // 4xx, plain 500, and malformed success bodies are terminal: parse and
    // surface them immediately instead of resending an ambiguous request.
    return await readResponse(response);
  }
}
