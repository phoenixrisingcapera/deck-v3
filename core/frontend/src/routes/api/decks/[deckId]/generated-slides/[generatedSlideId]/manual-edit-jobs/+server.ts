import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export async function POST({ params, request, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/generated-slides/${params.generatedSlideId}/manual-edit-jobs`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(await request.json())
    },
    'Manual layout edit could not be saved.'
  );
}
