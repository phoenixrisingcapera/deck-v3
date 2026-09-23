import { type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export const POST: RequestHandler = async ({ params, fetch, cookies }) => {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/market-research`),
    {
      method: 'POST'
    },
    'Market research failed.'
  );
};
