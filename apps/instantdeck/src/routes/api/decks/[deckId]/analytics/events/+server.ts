import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { fetchBackendJsonOrThrow } from '$server/deckWorkflowProxy';

export async function POST({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  const response = await fetchBackendJsonOrThrow(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/analytics/events`),
    'Could not record product analytics event.',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    }
  );

  return json(response);
}
