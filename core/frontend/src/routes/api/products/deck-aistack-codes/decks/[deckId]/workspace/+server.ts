import { error, json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { getDeckWorkspaceModel } from '$server/services/generatedWorkspaceService';
import { BACKEND_URL, proxyBackendJson } from '$server/backendApi';

export async function GET({ params, fetch, cookies }) {
  if (BACKEND_URL) {
    return proxyBackendJson(
      fetch,
      cookies,
      deckProductApiPath(`/decks/${params.deckId}/workspace`),
      {},
      'Deck workspace not found.'
    );
  }

  const workspaceResult = await getDeckWorkspaceModel(params.deckId);
  if (!workspaceResult) {
    throw error(404, 'Deck workspace not found');
  }

  return json({
    workspace: workspaceResult.workspace,
    latestConfirmation: workspaceResult.latestConfirmation
  });
}
