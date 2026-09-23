import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

// Printing uses the published deck's secure renderer capability, exposed by
// the canonical workspace. Keep existing Export navigation out of a dead route.
export const load: PageServerLoad = ({ params }) => {
  redirect(303, `/decks/${encodeURIComponent(params.deckId)}/instant-deck`);
};
