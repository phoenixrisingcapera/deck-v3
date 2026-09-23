import { type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { proxyBackendJson } from '$server/backendApi';

export const GET: RequestHandler = async ({ params, fetch, cookies }) => {
  return proxyBackendJson(fetch, cookies, deckProductApiPath(`/decks/${params.deckId}/canonical-deck-intelligence`), {}, 'Canonical deck intelligence not found.');
};

export const POST: RequestHandler = async ({ params, fetch, cookies }) => {
  return proxyBackendJson(fetch, cookies, deckProductApiPath(`/decks/${params.deckId}/canonical-deck-intelligence`), { method: 'POST' }, 'Canonical deck intelligence refresh failed.');
};
