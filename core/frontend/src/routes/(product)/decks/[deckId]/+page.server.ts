import { redirect } from '@sveltejs/kit';

export async function load({ params, url }) {
  throw redirect(307, `/decks/${params.deckId}/smart-deck${url.search}`);
}
