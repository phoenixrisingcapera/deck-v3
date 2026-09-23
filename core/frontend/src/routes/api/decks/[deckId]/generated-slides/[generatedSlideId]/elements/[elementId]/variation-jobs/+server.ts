import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function POST({ params, request, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(
    `${backendUrl}${deckProductApiPath(`/decks/${params.deckId}/generated-slides/${params.generatedSlideId}/elements/${params.elementId}/variation-jobs`)}`,
    {
      method: 'POST',
      headers: {
        ...requireBackendAuthHeaders(cookies),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(await request.json())
    }
  );
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(payload, 'Element variation job failed.'));
  }
  return json(payload, { status: response.status });
}
