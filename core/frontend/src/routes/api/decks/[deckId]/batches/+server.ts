import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, url, fetch, cookies }) {
  // Legacy route alias for iteration history:
  // `/api/decks/:deckId/batches` maps to the active product contract
  // `/api/products/deck-aistack-codes/decks/:deckId/versions`.
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
  // Legacy route alias for iteration creation:
  // iteration creation is sent through `/api/decks/.../batches` in UI routes, then
  // proxied to `/products/deck-aistack-codes/decks/.../versions`.
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
