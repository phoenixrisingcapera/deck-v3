import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function POST({ params, fetch, cookies, request }) {
  const action = params.action;
  if (!['retry', 'archive'].includes(action)) {
    return new Response(JSON.stringify({ error: { code: 'media_action_unknown', message: 'Unknown media action.' } }), { status: 404 });
  }
  const body = action === 'archive' ? await request.text() : undefined;
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/media/${params.mediaId}/${action}`),
    { method: 'POST', headers: body ? { 'content-type': 'application/json' } : undefined, body },
    `Media ${action} failed.`
  );
}
