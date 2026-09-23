import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json();
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/smart-deck/preferences`),
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Smart Deck preferences update failed.'
  );
}
