import { type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export const POST: RequestHandler = async ({ request, fetch, cookies }) => {
  const payload = await request.json();
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath('/ai/orchestrate'),
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'AI orchestration failed.'
  );
};
