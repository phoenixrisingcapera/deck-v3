import { json } from '@sveltejs/kit';
import { extractErrorMessage, parseJson, requireBackendUrl, proxyBackendJson } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const path = deckProductApiPath(`/decks/${params.deckId}/brand-profile`);
  const response = await fetch(`${backendUrl}${path}`, {
    method: 'GET',
    headers: requireBackendAuthHeaders(cookies)
  }).catch(() => null);

  if (!response || [401, 403, 404].includes(response.status)) {
    return json({ brandProfile: null, degraded: true }, { status: 200 });
  }
  const payload = await parseJson(response);
  if (!response.ok) {
    return json(
      { brandProfile: null, degraded: true, message: extractErrorMessage(payload, 'Brand profile could not be loaded.') },
      { status: 200 }
    );
  }
  return json(payload, { status: response.status });
}

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/brand-profile`),
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Brand profile update failed.'
  );
}
