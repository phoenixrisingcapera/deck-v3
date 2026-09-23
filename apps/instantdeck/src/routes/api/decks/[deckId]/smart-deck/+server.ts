import { proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/smart-deck`,
    { method: 'GET' },
    'Smart Deck workspace lookup failed.'
  );
}
