import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { loadDeckGraph } from '$server/services/deckService';
import { BACKEND_URL, proxyBackendJson } from '$server/backendApi';
import { readSessionUser } from '$lib/server/auth/session';

export async function GET({ params, fetch, cookies }) {
  if (!readSessionUser(cookies)) throw error(401, 'Authentication required.');
  if (!params.deckId || params.deckId.includes('/') || params.deckId.includes('..')) {
    throw error(400, 'Invalid deck ID.');
  }

  if (BACKEND_URL) {
    return proxyBackendJson(
      fetch,
      cookies,
      deckProductApiPath(`/decks/${params.deckId}/graph`),
      {},
      'Deck not found.'
    );
  }

  const graph = await loadDeckGraph(params.deckId, { enableInspectionFallback: true });
  if (!graph) throw error(404, 'Deck not found');
  return json(graph);
}
