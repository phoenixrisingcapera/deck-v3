import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json();
  return proxyBackendJson(
    fetch,
    cookies,
    // Compatibility adapter: the backend session-state command is the sole writer.
    deckProductApiPath(`/decks/${params.deckId}/smart-deck/session-state`),
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Smart Deck selection update failed.'
  );
}
