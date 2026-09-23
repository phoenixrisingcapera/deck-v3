import type { HandleFetch } from '@sveltejs/kit';
import { logFetchDebug, logFetchWarning } from '$lib/debug/fetchLogging';

export const handleFetch: HandleFetch = async ({ request, fetch }) => {
  const startedAt = performance.now();
  try {
    const response = await fetch(request);
    logFetchDebug('Fetch finished loading', {
      url: request.url,
      method: request.method,
      status: response.status,
      durationMs: Math.round(performance.now() - startedAt)
    });
    return response;
  } catch (error) {
    logFetchWarning('Fetch failed loading', {
      url: request.url,
      method: request.method,
      durationMs: Math.round(performance.now() - startedAt),
      error: error instanceof Error ? error.message : String(error)
    });
    throw error;
  }
};
