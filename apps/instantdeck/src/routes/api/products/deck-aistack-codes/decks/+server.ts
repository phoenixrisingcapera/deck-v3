import { createWorkspaceDeck, loadWorkspaceDecks } from '$server/services/deckCollectionService';

export async function GET({ fetch, cookies }) {
  return loadWorkspaceDecks(fetch, cookies);
}

export async function POST({ request, fetch, cookies }) {
  return createWorkspaceDeck(request, fetch, cookies);
}
