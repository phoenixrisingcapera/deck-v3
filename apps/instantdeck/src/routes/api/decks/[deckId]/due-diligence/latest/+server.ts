import { error, json } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}/api/decks/${params.deckId}/due-diligence/latest`, {
    headers: requireBackendAuthHeaders(cookies)
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(result, 'Due diligence report not found.'));
  }
  return json(result, { status: response.status });
}
