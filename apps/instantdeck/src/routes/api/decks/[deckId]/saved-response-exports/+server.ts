import { proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/saved-response-exports`,
    {},
    'Could not load saved response exports.'
  );
}

export async function POST({ params, request, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/saved-response-exports`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: await request.text()
    },
    'Could not save response export.'
  );
}
