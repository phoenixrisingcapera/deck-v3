# Product Navigation Release 2026-07-16

Tag: `v2026.07.16-navigation-fix`

## Scope

This release clarifies the mounted product navigation without adding alternate
welcome, dashboard, or marketing surfaces.

## Navigation Changes

- Labels the signed-in sidebar destination as `Dashboard` and routes it to
  `/dashboard`.
- Aligns the Dashboard navigation active state with the canonical dashboard
  route.
- Makes the product logo the intentional route to the public home page at `/`.
- Keeps first-time workspace routing owned by the canonical `/dashboard` to
  `/welcome` redirect.
- Keeps product-route error recovery inside the signed-in route family instead
  of falling through to the marketing page.
- Cancels stale error-page redirect timers after the user leaves the error
  surface.

## Verification

- `npm run test:dashboard-contract`: passed.
- `git diff --check`: passed.

## Route Ownership

- Public home: `/`
- Returning-user dashboard: `/dashboard`
- First-time workspace: `/welcome`
