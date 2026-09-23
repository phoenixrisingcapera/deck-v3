import { error, json } from '@sveltejs/kit';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function GET({ fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}/api/workspace/dashboard`, {
    headers: requireBackendAuthHeaders(cookies)
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw error(response.status, extractErrorMessage(payload, 'Could not check whether slides are ready.'));
  }

  return json(payload, { status: response.status });
}
