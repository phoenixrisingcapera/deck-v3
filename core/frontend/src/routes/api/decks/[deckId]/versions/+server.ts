import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, url, fetch, cookies }) {
  const rawLimit = Number(url.searchParams.get('limit') ?? '50');
  const limit = Number.isFinite(rawLimit) ? rawLimit : 50;
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/versions?limit=${limit}`),
    {},
    'Could not load deck versions.'
  );
}
