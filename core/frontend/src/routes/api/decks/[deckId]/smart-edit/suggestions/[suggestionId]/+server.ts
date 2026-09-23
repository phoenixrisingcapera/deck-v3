import { proxyBackendJson } from '$server/backendApi';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json();
  return proxyBackendJson(fetch, cookies, `/api/decks/${params.deckId}/smart-edit/suggestions/${params.suggestionId}`, {
    method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload)
  }, 'Smart Edit suggestion update failed.');
}
