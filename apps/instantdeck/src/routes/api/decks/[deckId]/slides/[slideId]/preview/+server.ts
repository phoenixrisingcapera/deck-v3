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

  const response = await fetch(`${BACKEND_URL}/api/decks/${params.deckId}/slides/${params.slideId}/preview`, {
    method: 'GET',
    headers
  });

  if (!response.ok) {
    throw error(response.status, 'Slide preview could not be loaded.');
  }

  const passthrough = new Headers();
  const contentType = response.headers.get('content-type');
  const cacheControl = response.headers.get('cache-control');
  const etag = response.headers.get('etag');
  const lastModified = response.headers.get('last-modified');

  if (contentType) passthrough.set('content-type', contentType);
  if (cacheControl) passthrough.set('cache-control', cacheControl);
  if (etag) passthrough.set('etag', etag);
  if (lastModified) passthrough.set('last-modified', lastModified);

  return new Response(response.body, {
    status: response.status,
    headers: passthrough
  });
};
