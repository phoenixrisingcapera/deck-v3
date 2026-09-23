/**
 * Client-side backend health check.
 *
 * Runs once on app mount to verify the backend is reachable.
 * Stores result in a simple module-level singleton so multiple
 * components can read it without prop drilling.
 */

let checked = false;
let healthy: boolean | null = null;
let listeners: Array<(h: boolean | null) => void> = [];

export function getBackendHealth(): boolean | null {
  return healthy;
}

export function onBackendHealthChange(fn: (h: boolean | null) => void): () => void {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

function notify() {
  for (const fn of listeners) fn(healthy);
}

/**
 * Ping the backend health endpoint once.
 * Uses a short timeout so the UI is not blocked.
 */
export async function checkBackendHealth(): Promise<boolean | null> {
  if (checked) return healthy;
  checked = true;

  try {
    const res = await fetch('/api/health', {
      method: 'GET',
      signal: AbortSignal.timeout(8000)
    });
    healthy = res.ok;
  } catch {
    healthy = false;
  }

  notify();
  return healthy;
}
