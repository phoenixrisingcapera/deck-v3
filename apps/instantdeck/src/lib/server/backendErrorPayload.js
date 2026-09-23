// @ts-check

/** @param {unknown} value */
function asRecord(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? /** @type {Record<string, unknown>} */ (value) : null;
}

/** @param {unknown[]} values */
function firstString(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

/**
 * Keep validation arrays in `detail`, never in canonical `error`. Structured
 * backend errors are reduced to an explicit browser-safe allowlist while the
 * canonical fields are guaranteed and normalized.
 *
 * @param {unknown} payload
 * @param {number} status
 * @param {string} fallbackMessage
 */
export function normalizeBackendErrorPayload(payload, status, fallbackMessage) {
  const record = asRecord(payload);
  const structured = asRecord(record?.error) ?? asRecord(record?.detail);
  const message = firstString(
    structured?.message,
    structured?.error,
    structured?.reason,
    record?.message,
    typeof record?.error === 'string' ? record.error : null,
    typeof record?.detail === 'string' ? record.detail : null
  ) ?? fallbackMessage;
  const recoverableByStatus = [408, 409, 425, 429, 502, 503, 504].includes(status);

  return {
    code: firstString(structured?.code) ?? `http_${status}`,
    message,
    recoverable: typeof structured?.recoverable === 'boolean' ? structured.recoverable : recoverableByStatus
  };
}

/**
 * @param {unknown} payload
 * @param {number} status
 * @param {string} fallbackMessage
 * @param {string | null} requestId
 */
export function buildBackendErrorResponsePayload(payload, status, fallbackMessage, requestId) {
  const record = asRecord(payload);
  return {
    ok: false,
    error: normalizeBackendErrorPayload(payload, status, fallbackMessage),
    ...(Array.isArray(record?.detail) ? { detail: record.detail } : {}),
    requestId
  };
}
