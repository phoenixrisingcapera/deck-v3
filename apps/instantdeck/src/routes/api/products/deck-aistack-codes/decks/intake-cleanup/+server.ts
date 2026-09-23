import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ fetch, cookies, request }) {
  const payload = await request.json().catch(() => ({}));
  // Cleanup is routed through the backend so session scoping and soft-delete
  // safeguards stay server-owned.
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath('/decks/intake-cleanup'),
    {
      method: 'POST',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(payload),
    },
    'Could not clean up stale intake decks.'
  );
}
