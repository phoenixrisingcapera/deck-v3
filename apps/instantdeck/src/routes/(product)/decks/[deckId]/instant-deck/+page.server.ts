import { loadInstantDeckPage } from '$server/load-instant-deck-page';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, fetch, parent }) => loadInstantDeckPage({
  deckId: params.deckId,
  url,
  fetcher: fetch,
  parent
});
