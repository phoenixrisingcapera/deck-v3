import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function DELETE({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/exports/${params.exportId}/shares/${params.shareId}`),
    { method: 'DELETE' },
    'Could not revoke deck share link.'
  );
}
