import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ params, fetch, cookies }) {
  // Legacy route alias for canonical iteration detail:
  // `/api/decks/.../batches/:batchId` reuses the existing front-end route but
  // fetches from `/products/deck-aistack-codes/decks/:deckId/versions/:batchId`.
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/versions/${params.batchId}`),
    {},
    'Iteration not found.'
  );
}
