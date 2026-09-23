import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ params, fetch, cookies }) {
  // Retry is a backend workflow command. The frontend must not infer or mutate
  // worker state directly.
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/retry`),
    { method: 'POST' },
    'Could not retry Smart Deck processing.'
  );
}
