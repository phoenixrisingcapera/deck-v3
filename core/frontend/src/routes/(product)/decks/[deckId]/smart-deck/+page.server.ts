import { redirect } from '@sveltejs/kit';
import { loadSmartDeckPage } from '$server/load-smart-deck-page';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, fetch, locals }) => {
  if (url.searchParams.get('instant') === '1') {
    const search = new URLSearchParams(url.searchParams);
    search.delete('instant');
    const suffix = search.size > 0 ? `?${search.toString()}` : '';
    throw redirect(303, `/decks/${params.deckId}/instant-deck${suffix}`);
  }

  // Product owns the Smart Deck route. Keep deck-scoped visibility here by
  // default, and reserve deep diagnostics for explicit developer-tool modes.
  // The shared loader checks /processing before mounting the workspace.
  return loadSmartDeckPage(params, url, fetch, locals);
};
