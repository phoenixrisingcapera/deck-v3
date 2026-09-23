import { type RequestHandler } from '@sveltejs/kit';
import { proxyBackendJson } from '$server/backendApi';

export const POST: RequestHandler = async ({ params, request, fetch, cookies }) => {
  const body = await request.text();
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/due-diligence/chat`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body
    },
    'Failed to send the due diligence message.'
  );
};
