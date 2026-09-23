import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/generated-slides/${params.generatedSlideId}/code`),
    { method: 'GET' },
    'Generated slide code lookup failed.'
  );
}
