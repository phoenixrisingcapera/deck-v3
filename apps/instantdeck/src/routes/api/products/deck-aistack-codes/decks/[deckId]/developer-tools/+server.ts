import { json, type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { fetchBackendJsonOrThrow } from '$server/deckWorkflowProxy';

export const GET: RequestHandler = async ({ params, url, fetch, cookies }) => {
  const surface = url.searchParams.get('surface');
  const path = deckProductApiPath(`/decks/${params.deckId}/developer-tools${surface ? `?surface=${encodeURIComponent(surface)}` : ''}`);
  const payload = await fetchBackendJsonOrThrow(fetch, cookies, path, 'Could not load developer tools.');
  return json(payload);
};

export const POST: RequestHandler = async ({ params, request, fetch, cookies }) => {
  const payload = await request.json().catch(() => ({}));
  const response = await fetchBackendJsonOrThrow(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/developer-tools/events`),
    'Could not record developer-tools event.',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    }
  );
  return json(response);
};
