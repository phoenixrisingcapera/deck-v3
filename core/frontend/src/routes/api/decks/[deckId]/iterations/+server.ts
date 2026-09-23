import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, url, fetch, cookies }) {
  const rawLimit = Number(url.searchParams.get('limit') ?? '20');
  const limit = Number.isFinite(rawLimit) ? rawLimit : 20;
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/versions?limit=${limit}`),
    {},
    'Could not load deck iterations.'
  );
}

export async function POST({ params, request, fetch, cookies }) {
  const payload = await request.json();
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/versions`),
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Could not create deck iteration.'
  );
}
