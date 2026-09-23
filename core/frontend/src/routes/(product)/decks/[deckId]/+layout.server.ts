import { error } from '@sveltejs/kit';
import type { DesignBatchPreview } from '@deck-aistack-codes/shared';
import type { DeckGraph } from '$types/domain';

export async function load({ params, fetch, url }) {
  // Keep the compatibility layout contract stable while avoiding serial graph
  // and iteration requests on every canonical child route.
  const instantDeckOnly = /\/instant-deck(?:\/|$)/.test(url.pathname);
  const [graphResponse, batchesResponse] = await Promise.all([
    fetch(`/api/decks/${params.deckId}`),
    instantDeckOnly ? Promise.resolve(null) : fetch(`/api/decks/${params.deckId}/iterations?limit=8`)
  ]);
  const graph = graphResponse.ok ? ((await graphResponse.json()) as DeckGraph) : null;
  if (!graph && graphResponse.status === 404) throw error(404, 'Deck not found');

  const batchesPayload = batchesResponse?.ok
    ? ((await batchesResponse.json()) as { batches?: DesignBatchPreview[] })
    : { batches: [] };

  return {
    graph,
    latestBatches: batchesPayload.batches ?? [],
    deckGraphAvailable: graph !== null,
    deckGraphStatus: graphResponse.status || null,
    deckGraphRequestId: graphResponse.headers.get('x-request-id'),
    latestBatchesAvailable: instantDeckOnly ? true : Boolean(batchesResponse?.ok),
    latestBatchesStatus: batchesResponse?.status || null,
    latestBatchesRequestId: batchesResponse?.headers.get('x-request-id') ?? null,
    inspection: undefined
  };
}
