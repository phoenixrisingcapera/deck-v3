import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, parseJson, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  const choice = String(payload?.choice ?? '');
  const backendUrl = requireBackendUrl();

  const path = choice === 'generated_version' || choice === 'original'
    ? deckProductApiPath(`/decks/${params.deckId}/versions/${params.iterationId}/slide-decisions/${params.slideId}`)
    : null;

  if (!path) {
    throw error(400, 'choice must be generated_version or original.');
  }

  const response = await fetch(`${backendUrl}${path}`, {
    method: 'PATCH',
    headers: {
      ...requireBackendAuthHeaders(cookies),
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      choice,
      generatedSlideVersionId: payload?.generatedSlideVersionId ?? payload?.generatedVersionId ?? null
    })
  });
  const result = await parseJson(response);

  if (!response.ok) {
    throw error(response.status, extractErrorMessage(result, 'Could not save iteration slide decision.'));
  }

  return json(result, { status: response.status });
}
