import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/soft-delete`),
    { method: 'POST' },
    'Could not remove the deck.'
  );
}
