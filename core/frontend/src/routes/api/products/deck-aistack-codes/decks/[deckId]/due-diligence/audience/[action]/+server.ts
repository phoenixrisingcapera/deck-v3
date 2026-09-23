import { error, type RequestHandler } from '@sveltejs/kit';
import { proxyBackendJson } from '$server/backendApi';

const postActions = new Set(['analyze', 'plan', 'generate-smart-deck-instructions']);

export const GET: RequestHandler = async ({ params, fetch, cookies }) => {
  if (params.action !== 'latest') throw error(405, 'This audience diligence action requires POST.');
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/due-diligence/audience/latest`,
    {},
    'Latest audience diligence result could not be loaded.'
  );
};

export const POST: RequestHandler = async ({ params, request, fetch, cookies }) => {
  if (!params.action || !postActions.has(params.action)) throw error(404, 'Unknown audience diligence action.');
  const body = await request.text();
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/products/deck-aistack-codes/decks/${params.deckId}/due-diligence/audience/${params.action}`,
    { method: 'POST', headers: { 'content-type': 'application/json' }, body },
    'Audience diligence action failed.'
  );
};
