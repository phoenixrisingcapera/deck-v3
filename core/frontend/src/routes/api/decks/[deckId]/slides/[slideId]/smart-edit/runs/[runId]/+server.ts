import { proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/slides/${params.slideId}/smart-edit/runs/${params.runId}`,
    {},
    'Smart Edit run not found.'
  );
}
