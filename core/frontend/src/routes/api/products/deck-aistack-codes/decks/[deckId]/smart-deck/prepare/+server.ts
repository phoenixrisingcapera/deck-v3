import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { fetchBackendJsonOrThrow } from '$server/deckWorkflowProxy';

export async function POST({ params, fetch, cookies }) {
  const payload = await fetchBackendJsonOrThrow(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/smart-deck/prepare`),
    'Could not prepare Smart Deck.',
    {
      method: 'POST'
    }
  );

  return json(payload);
}
