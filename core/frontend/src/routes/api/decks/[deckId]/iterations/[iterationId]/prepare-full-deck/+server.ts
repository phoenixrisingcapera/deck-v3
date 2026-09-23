import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, parseJson, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function POST({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  const backendUrl = requireBackendUrl();

  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${params.deckId}/workflows/compile-final`)}`, {
    method: 'POST',
    headers: {
      ...requireBackendAuthHeaders(cookies),
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      batchId: payload?.batchId ?? params.iterationId,
      title: payload?.title ?? null,
      latestSlideVersionId: payload?.latestSlideVersionId ?? payload?.slideVersionId ?? null
    })
  });

  const result = await parseJson(response);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(result, 'Could not prepare full deck.'));
  }

  return json(result, { status: response.status });
}
