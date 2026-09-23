import { error, type RequestHandler } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, parseJson, requireBackendUrl } from '$server/backendApi';

export const GET: RequestHandler = async ({ params, fetch, cookies }) => {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}/api/products/deck-aistack-codes/decks/${params.deckId}/exports/${params.exportId}/download`, {
    headers: requireBackendAuthHeaders(cookies)
  });

  if (!response.ok) {
    const payload = await parseJson(response);
    throw error(response.status, extractErrorMessage(payload, 'Could not download export.'));
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/octet-stream',
      'content-disposition': response.headers.get('content-disposition') ?? `attachment; filename="deck-aistack-export-${params.exportId}.txt"`,
      'cache-control': 'private, no-store'
    }
  });
};
