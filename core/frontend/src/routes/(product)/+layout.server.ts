import { redirect } from '@sveltejs/kit';

export function load({ locals, url }) {
  // This server layout only guards authenticated product routes.
  // The actual product UI shell must live in `+layout.svelte` or deeper route components.
  if (!locals.sessionUser) {
    const next = `${url.pathname}${url.search}`;
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(next)}`);
  }

  return {};
}
