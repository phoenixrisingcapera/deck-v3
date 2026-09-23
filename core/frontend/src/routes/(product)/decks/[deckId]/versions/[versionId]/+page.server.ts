import { error } from '@sveltejs/kit';
import type { DesignBatchDetail } from '@deck-aistack-codes/shared';
import type { DeckGraph } from '$types/domain';

type DeckVersionDetail = DesignBatchDetail & {
  versionId?: string | null;
  versionNumber?: number | null;
  versionName?: string | null;
  sourceSurface?: string | null;
  sourceDesignVersionId?: string | null;
  changeSummary?: string | null;
  acceptedAt?: string | null;
  snapshot?: { slides?: Array<{ slideId: string; title: string; generatedSlide?: { generatedSlideId: string; title: string } | null }> } | null;
};

export async function load({ params, fetch }) {
  const [graphResponse, versionResponse] = await Promise.all([
    fetch(`/api/decks/${params.deckId}`),
    fetch(`/api/decks/${params.deckId}/versions/${params.versionId}`)
  ]);
  const graph = graphResponse.ok ? ((await graphResponse.json()) as DeckGraph) : null;
  if (!graph) throw error(graphResponse.status || 404, 'Deck not found');
  if (!versionResponse.ok) throw error(versionResponse.status, 'Version not found');
  const payload = (await versionResponse.json()) as { version?: DeckVersionDetail; batch?: DeckVersionDetail };
  const version = payload.version ?? payload.batch;
  if (!version) throw error(404, 'Version not found');
  return { graph, version };
}
