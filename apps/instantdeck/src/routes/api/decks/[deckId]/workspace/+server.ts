import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import {
  getDeckWorkspacePreferences,
  updateDeckWorkspacePreferences,
} from '$server/services/shellWorkspaceService';
import { BACKEND_URL, proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  if (BACKEND_URL) {
    return proxyBackendJson(
      fetch,
      cookies,
      deckProductApiPath(`/decks/${params.deckId}/workspace/preferences`),
      {},
      'Deck workspace preferences not found.'
    );
  }

  const workspace = await getDeckWorkspacePreferences(params.deckId, cookies);
  if (!workspace) {
    throw error(404, 'Deck workspace preferences not found');
  }

  return json({
    deckId: params.deckId,
    workspace
  });
}

export async function PATCH({ params, request, fetch, cookies }) {
  const payload = await request.json();
  if (BACKEND_URL) {
    return proxyBackendJson(
      fetch,
      cookies,
      deckProductApiPath(`/decks/${params.deckId}/workspace/preferences`),
      {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload)
      },
      'Deck workspace preferences not found.'
    );
  }

  const workspace = await updateDeckWorkspacePreferences(params.deckId, payload, cookies);

  return json({
    deckId: params.deckId,
    workspace
  });
}
