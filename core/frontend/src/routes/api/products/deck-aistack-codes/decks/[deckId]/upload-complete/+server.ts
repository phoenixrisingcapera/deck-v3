import { proxyBackendJson } from '$server/backendApi';

export async function POST({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/upload-complete`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Could not confirm the object-storage upload.'
  );
}
