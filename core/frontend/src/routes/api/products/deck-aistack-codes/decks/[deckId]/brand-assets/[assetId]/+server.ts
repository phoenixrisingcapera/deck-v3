import { error } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, parseJson, requireBackendUrl } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${params.deckId}/brand-assets/${params.assetId}`)}`, {
    headers: requireBackendAuthHeaders(cookies)
  });

  if (!response.ok) {
    const payload = await parseJson(response);
    throw error(response.status, extractErrorMessage(payload, 'Brand asset not found.'));
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/octet-stream',
      'content-disposition':
        response.headers.get('content-disposition') ?? `inline; filename="brand-asset-${params.assetId}"`,
      'cache-control': 'private, no-store'
    }
  });
}
