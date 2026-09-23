import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { BACKEND_URL, extractErrorMessage } from '$server/backendApi';
import { normalizeWorkspaceSummary } from '$server/services/workspaceSummaryService';

export async function GET({ fetch, cookies }) {
  if (BACKEND_URL) {
    const response = await fetch(`${BACKEND_URL}${deckProductApiPath('/workspace-summary')}`, {
      headers: requireBackendAuthHeaders(cookies)
    });
    const data = await response.json().catch(() => null);
    const requestId = response.headers.get('x-request-id');

    if (!response.ok) {
      throw error(response.status, extractErrorMessage(data, 'Could not load workspace summary.'));
    }

    return json(normalizeWorkspaceSummary(data), {
      status: response.status,
      headers: requestId ? { 'x-request-id': requestId } : undefined
    });
  }

  throw error(503, 'A backend URL is required for persisted workspace summary.');
}
