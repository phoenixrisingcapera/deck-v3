import { proxyBackendJson } from '$server/backendApi';

export async function POST({ request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(
    fetch,
    cookies,
    '/api/decks',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Could not create the deck upload record.'
  );
}
