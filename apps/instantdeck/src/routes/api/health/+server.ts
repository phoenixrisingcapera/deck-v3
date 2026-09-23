import { json } from '@sveltejs/kit';
import { BACKEND_URL } from '$server/backendUrl';

export async function GET({ fetch }) {
  let backendOk = false;
  let backendError: string | null = null;

  if (BACKEND_URL) {
    try {
      const res = await fetch(`${BACKEND_URL}/`, {
        signal: AbortSignal.timeout(6000)
      });
      backendOk = res.ok;
      if (!res.ok) {
        backendError = `Backend returned ${res.status}`;
      }
    } catch (err) {
      backendError = err instanceof Error ? err.message : 'Backend unreachable';
    }
  } else {
    backendError = 'DECK_AISTACK_BACKEND_URL not configured';
  }

  return json({
    ok: backendOk,
    service: 'deck-aistack-codes-sveltekit-backend',
    backend: {
      configured: !!BACKEND_URL,
      reachable: backendOk,
      error: backendError
    }
  });
}
