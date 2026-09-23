import { error } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function GET({ params, fetch, cookies }) {
  const response = await fetch(`${requireBackendUrl()}${deckProductApiPath(`/decks/${params.deckId}/media/${params.mediaId}/content`)}`, { headers: requireBackendAuthHeaders(cookies) });
  if (!response.ok || !response.body) throw error(response.status, 'Media content could not be loaded.');
  return new Response(response.body, { headers: { 'content-type': response.headers.get('content-type') || 'application/octet-stream', 'cache-control': 'private, no-store' } });
}
