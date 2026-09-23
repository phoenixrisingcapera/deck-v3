import { type RequestHandler } from '@sveltejs/kit';
import { proxyBackendJson } from '$server/backendApi';

export const GET: RequestHandler = async ({ params, url, fetch, cookies }) => {
  const audience = url.searchParams.get('audience');
  const audienceQuery = audience ? `?audience=${encodeURIComponent(audience)}` : '';
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/due-diligence${audienceQuery}`,
    {},
    'Due diligence workspace not found.'
  );
};

// Compatibility: retain POST on `/due-diligence` for older callers, but proxy it
// to the canonical backend run command used by the mounted product page.
export const POST: RequestHandler = async ({ params, request, fetch, cookies }) => {
  const body = await request.text();
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/due-diligence/run`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body
    },
    'Failed to run due diligence review.'
  );
};
