import { proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/saved-response-exports/${params.exportId}`,
    {},
    'Could not load saved response export preview.'
  );
}
