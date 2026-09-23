import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, parseJson, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  const choice = String(payload?.choice ?? '');
  const backendUrl = requireBackendUrl();

  // Frontend sends the UI-specific decision payload to this legacy `/api/decks/.../batches/...` route.
  // Bridge it to the active product contract at `/api/products/deck-aistack-codes/decks/.../versions/...`.
  const path = choice === 'generated_version' || choice === 'original'
    ? deckProductApiPath(`/decks/${params.deckId}/versions/${params.batchId}/slide-decisions/${params.slideId}`)
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
      // Contract mapping: `choice` stays unchanged, backend `choice` accepts
      // `generated_version` or `original` with an optional `generatedSlideVersionId`.
      choice,
      generatedSlideVersionId: payload?.generatedSlideVersionId ?? payload?.generatedVersionId ?? null
    })
  });
  const result = await parseJson(response);

  if (!response.ok) {
    throw error(response.status, extractErrorMessage(result, 'Could not save slide decision.'));
  }

  return json(result, { status: response.status });
}
