import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ params, fetch, cookies, request }) {
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/changes/apply`),
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Field change apply failed.'
  );
}
