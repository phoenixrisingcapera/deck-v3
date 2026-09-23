const DEBUG_FETCH_VALUES = new Set(['1', 'true', 'yes', 'on']);

export function shouldLogFetch() {
  return DEBUG_FETCH_VALUES.has(String(import.meta.env.VITE_DEBUG_FETCH ?? '').toLowerCase());
}

export function logFetchDebug(message: string, context?: Record<string, unknown>) {
  if (!shouldLogFetch()) return;
  console.debug(message, context ?? {});
}

export function logFetchWarning(message: string, context?: Record<string, unknown>) {
  if (!shouldLogFetch()) return;
  console.warn(message, context ?? {});
}
