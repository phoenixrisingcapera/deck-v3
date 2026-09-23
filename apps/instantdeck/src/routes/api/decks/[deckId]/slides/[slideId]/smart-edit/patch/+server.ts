import { proxyBackendJson } from '$server/backendApi';

export async function POST({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(fetch, cookies, `/api/decks/${params.deckId}/slides/${params.slideId}/smart-edit/patch`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload)
  }, 'Smart Edit patch generation failed.');
}
