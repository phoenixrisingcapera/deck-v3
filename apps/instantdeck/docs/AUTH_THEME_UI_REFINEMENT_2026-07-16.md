# Auth and Theme UI Refinement 2026-07-16

Tag: `v2026.07.16-auth-theme-ui`

## Scope

This release refines the mounted sign-in experience and keeps the established
theme control reachable on canonical product surfaces. It does not introduce
alternate routes, change theme tokens, or modify authentication behavior.

## Mounted Changes

- `/auth/sign-in` continues to mount
  `src/routes/(marketing)/auth/sign-in/+page.svelte` and the shared
  `src/lib/components/PublicAuthShell.svelte`.
- The auth shell now uses a centered, bounded desktop layout and a responsive
  single-column mobile layout instead of expanding across the available page.
- The sign-in email placeholder is `Your email`; a company email address is not
  implied or required by the interface.
- `/welcome` now mounts the established product
  `src/lib/components/AppShell.svelte`, preserving its existing top-bar
  `ThemeToggle` rather than presenting a parallel product surface.
- `src/lib/layouts/MobileAppGate.svelte` mounts the same `ThemeToggle` when the
  desktop workspace is replaced by the mobile guidance card.

## Contracts

- Sign-in remains `POST /api/auth/sign-in` through `src/lib/api/auth.ts` and
  `src/routes/api/auth/sign-in/+server.ts`.
- The server auth service continues to own backend authentication and cookie
  persistence. The primary backend origin variable remains
  `DECK_AISTACK_BACKEND_URL`.
- Theme state remains owned by `src/lib/stores/theme`; no design token or theme
  persistence logic changed in this release.
- No compatibility routes or redirects changed.

## Verification

- `npm run check`: passed with zero errors and zero warnings.
- `npm run test:utilities-placement`: passed.
- `npm run verify:product-surfaces`: passed with zero required failures.
- `git diff --check`: passed.
