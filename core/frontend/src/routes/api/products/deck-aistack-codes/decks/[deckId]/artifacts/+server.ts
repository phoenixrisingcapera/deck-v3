import { type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export const GET: RequestHandler = async ({ params, url, fetch, cookies }) => {
  const search = new URLSearchParams();
  const artifactType = url.searchParams.get('artifact_type');
  const limit = url.searchParams.get('limit');
  if (artifactType) search.set('artifact_type', artifactType);
  if (limit) search.set('limit', limit);
  const suffix = search.size ? `?${search.toString()}` : '';
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/artifacts${suffix}`),
    {},
    'LLM report artifacts not found.'
  );
};
