import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/exports/${params.exportId}/shares`),
    {},
    'Could not load deck share links.'
  );
}

export async function POST({ params, request, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/exports/${params.exportId}/shares`),
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: await request.text()
    },
    'Could not create deck share link.'
  );
}
