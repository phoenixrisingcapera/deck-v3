import { error } from '@sveltejs/kit';
import type { DesignBatchPreview } from '@deck-aistack-codes/shared';
import type { DeckGraph } from '$types/domain';

export type DeckVersionPreview = DesignBatchPreview & {
  versionId?: string | null;
  versionNumber?: number | null;
  versionName?: string | null;
  sourceSurface?: string | null;
  changeSummary?: string | null;
  acceptedAt?: string | null;
};

export async function load({ params, fetch, url }) {
  const [graphResponse, versionsResponse] = await Promise.all([
    fetch(`/api/decks/${params.deckId}`),
    fetch(`/api/decks/${params.deckId}/versions?limit=50`)
  ]);
  const graph = graphResponse.ok ? ((await graphResponse.json()) as DeckGraph) : null;
  if (!graph) throw error(graphResponse.status || 404, 'Deck not found');
  if (!versionsResponse.ok) throw error(versionsResponse.status, 'Could not load deck versions.');
  const payload = (await versionsResponse.json()) as { versions?: DeckVersionPreview[]; batches?: DeckVersionPreview[] };

  return {
    graph,
    versions: payload.versions ?? payload.batches ?? [],
    requestedDesignVersionId: url.searchParams.get('designVersionId'),
    requestedGeneratedSlideId: url.searchParams.get('generatedSlideId'),
    requestedArtifactId: url.searchParams.get('artifactId')
  };
}
