import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/design-versions/${params.versionId}/restore`),
    { method: 'POST' },
    'Design version restore failed.'
  );
}
