import { json, type RequestHandler } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';
import { INSTANT_HTML_RENDERER_ORIGIN } from '$lib/server/instantHtmlRendererOrigin';
import { assertInstantHtmlRenderUrl } from '$lib/config/instantHtmlRendererOrigin.js';

export const POST: RequestHandler = async ({ fetch, cookies, params, url }) => {
  const backendUrl = requireBackendUrl();
  const scope = url.searchParams.get('scope') === 'full_deck' ? 'full_deck' : 'section';
  const path = `/api/products/deck-aistack-codes/decks/${encodeURIComponent(params.deckId ?? '')}/html-artifacts/${encodeURIComponent(params.artifactId ?? '')}/slides/${encodeURIComponent(params.generatedSlideId ?? '')}/capability?scope=${scope}`;
  const response = await fetch(`${backendUrl}${path}`, {
    method: 'POST',
    headers: requireBackendAuthHeaders(cookies)
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    return json({ message: extractErrorMessage(payload, 'Generated slide capability could not be created.') }, { status: response.status });
  }
  if (!payload || typeof payload !== 'object' || typeof payload.renderUrl !== 'string') {
    return json({ message: 'Generated slide capability did not include a render URL.' }, { status: 502 });
  }
  try {
    payload.renderUrl = assertInstantHtmlRenderUrl(payload.renderUrl, INSTANT_HTML_RENDERER_ORIGIN);
  } catch (error) {
    return json({ message: error instanceof Error ? error.message : 'Generated slide renderer configuration is invalid.' }, { status: 503 });
  }
  return json(payload, { headers: { 'cache-control': 'private, no-store' } });
};
