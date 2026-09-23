import { error, type RequestHandler } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';
import { BACKEND_URL } from '$server/backendUrl';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export const GET: RequestHandler = async ({ params, fetch, cookies }) => {
  if (!BACKEND_URL) {
    throw error(503, 'Backend URL is not configured.');
  }

  const headers = new Headers();
  for (const [key, value] of Object.entries(requireBackendAuthHeaders(cookies))) {
    headers.set(key, String(value));
  }
  headers.set('x-request-id', `fe-${randomUUID()}`);

  const { deckId, slideId, assetId } = params;
  if (!deckId || !slideId || !assetId) {
    throw error(400, 'Deck, slide, and asset identifiers are required.');
  }

  const response = await fetch(
    `${BACKEND_URL}/api/decks/${encodeURIComponent(deckId)}/slides/${encodeURIComponent(slideId)}/assets/${encodeURIComponent(assetId)}`,
    { method: 'GET', headers }
  );

  if (!response.ok) {
    throw error(response.status, 'Slide asset could not be loaded.');
  }

  const passthrough = new Headers();
  for (const name of ['content-type', 'cache-control', 'etag', 'last-modified']) {
    const value = response.headers.get(name);
    if (value) passthrough.set(name, value);
  }
  passthrough.set('cache-control', 'private, no-store');

  return new Response(response.body, {
    status: response.status,
    headers: passthrough
  });
};
