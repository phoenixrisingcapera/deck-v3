import { proxyBackendJson } from '$server/backendApi';

export async function POST({ params, request, fetch, cookies }) {
  // Legacy fallback kept for older callers that still post to
  // `/api/decks/:deckId/finalize`. It remains routed to the legacy backend
  // endpoint to preserve compatibility while batch-specific flows use
  // `/api/decks/:deckId/batches/:batchId/prepare-full-deck`.
  const payload = await request.json().catch(() => ({}));
  return proxyBackendJson(
    fetch,
    cookies,
    `/api/decks/${params.deckId}/finalize`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    },
    'Final deck compilation failed.'
  );
}
