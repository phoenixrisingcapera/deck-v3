import { proxyBackendJson } from '$server/backendApi';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json();
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/suggestions/${params.suggestionId}`,
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        status: payload.status,
        edited_text: payload.edited_text ?? payload.finalText ?? null
      })
    },
    'Suggestion update failed.'
  );
}
