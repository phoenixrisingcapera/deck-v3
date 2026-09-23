import { type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export const GET: RequestHandler = async ({ params, fetch, cookies }) => {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/diligence-workspace`),
    {},
    'LLM report reader context not found.'
  );
};
