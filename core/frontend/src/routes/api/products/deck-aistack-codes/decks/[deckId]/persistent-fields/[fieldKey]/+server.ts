import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/persistent-fields/${params.fieldKey}`),
    { method: 'GET' },
    'Persistent field not found.'
  );
}
