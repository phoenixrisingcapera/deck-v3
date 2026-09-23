import { redirect } from '@sveltejs/kit';

export function load({ url }) {
  // DISABLED: Legacy sign-in landing redirected to the internal admin console.
  // Reason: Public/auth workflow should not send normal users into admin routes.

  // NEW: Keep the legacy URL working, but absorb it into the canonical sign-in alias behavior.
  // Difference: Preserves query params like /sign-in while removing the admin detour.
  throw redirect(308, `/auth/sign-in${url.search}`);
}
