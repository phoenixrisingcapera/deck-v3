import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { fetchBackendJsonOrThrow } from '$server/deckWorkflowProxy';

export async function POST({ params, fetch, cookies }) {
  const payload = await fetchBackendJsonOrThrow(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/workflows/source-extraction`),
    'Could not start source extraction workflow.',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({})
    }
  );

  return json(payload);
}
