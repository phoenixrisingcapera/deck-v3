# Security Audit

Date: 2026-07-14
Repository: `deck-frontend-rescue`
Branch: `main`
Reviewed commit: current remediation commit (see latest git history)
Tag: current product-surface security remediation tag (see latest git tags)

## Scope And Method

This review covered the current frontend source, SvelteKit server hooks, route
guards, authentication/session code, API proxy routes, deck access paths,
security headers, environment configuration, and the production Dockerfile.
The review included static source inspection, dependency status checks from the
working tree, `git diff --check`, and a production build.

This is a frontend audit. Backend authorization, rate limits, persistence,
token validation, and database ownership constraints must also be verified in
the backend repository before treating the system as fully secure.

## Remediated Findings

## Product Surface Verification

The canonical user surfaces are mounted and wired as follows:

- **Smart Deck:** `/decks/[deckId]/smart-deck` loads the persisted graph,
  workflow/readiness state, workspace payload, batches, and preferences. It
  mounts `UserSmartDeckWorkspace` when ready and retains a graph-backed degraded
  shell otherwise. Its action bar links to Smart Edit, Due Diligence, and
  Export.
- **Smart Edit:** `/decks/[deckId]/smart-edit` loads graph, iterations,
  editable fields, selected field state, and workflow diagnostics. It supports
  slide/block selection, suggestion generation, and accept/reject persistence.
- **Due Diligence:** `/decks/[deckId]/due-diligence` loads graph, audience
  conversion results, run history, and design batches. It supports audience
  switching and explicit review runs, with a degraded workspace when the
  backend is unavailable.
- **Diligence compatibility:** `/decks/[deckId]/diligence` is redirect-only and
  preserves the deck identity while sending users to `/decks/llm-report`.
- **Compatibility redirects:** `/smart-deck` and `/smart-edit` resolve to the
  active deck's canonical surface; `/decks/[deckId]/audience` resolves to Due
  Diligence; `/insights` now resolves to the latest deck's canonical LLM Report
  surface or `/dashboard` when no deck is available.
- **Authorization boundary:** the product layout requires a session, and the
  shared hook now requires sessions for both `/api/decks/*` and product-scoped
  `/api/products/deck-aistack-codes/decks/*` requests.

- **Critical: hardcoded callback credentials.** Removed the predictable test
  email/password fallback from `src/lib/server/auth/authService.ts`. Callback
  authentication now requires a supplied identity and credential.
- **Critical: readable session-user cookie.** Replaced base64-only session user
  data with AES-256-GCM encryption and authentication in
  `src/lib/server/auth/session.ts`. Production requires `AUTH_SECRET_KEY` or
  `DECK_AISTACK_CREDENTIAL_SECRET`.
- **Critical: admin authorization gap.** The shared admin route group and the
  nested admin layout now require a super-admin/admin role or `admin:access`.
  Super-admin routes retain their stricter super-admin-only guard.
- **High: incomplete CSP.** `src/hooks.server.ts` now sets baseline policies
  for default, script, style, image, connection, font, worker, form, frame,
  object, and base sources.
- **High: open redirect through `next`.** Sign-in and sign-up accept only
  same-origin relative paths and reject protocol-relative, control-character,
  and JavaScript-style values.
- **Medium: unauthenticated deck API boundary.** Deck API requests now require
  an authenticated session before reaching route handlers. Per-deck ownership
  remains a backend responsibility enforced by the bearer token; the frontend
  does not trust a client-controlled deck owner value.
- **Low: auth health information disclosure.** The public health response no
  longer exposes cookie names, endpoint inventory, or detailed cookie
  configuration.
- **Low: fabricated connected-account fallback.** The fallback identity in
  `src/routes/api/settings/account/connected-accounts/+server.ts` is disabled;
  account settings now require the backend.
- **Medium: optional-auth brand profile read.** Brand-profile GET now requires
  the authenticated backend bearer token.
- **Medium: spoofable forwarded IP headers.** The public-interest proxy no
  longer forwards client-supplied `x-forwarded-for` or `x-real-ip` values.
- **Medium: backend error payload exposure.** Proxy responses no longer return
  the complete backend error payload as `detail`.
- **Low: CSRF defense-in-depth.** API mutations now reject an explicit
  cross-origin `Origin`; same-origin and server-to-server requests remain
  supported.
- **Low: stale authorization snapshot.** Successful backend session validation
  now refreshes the encrypted session-user cookie.
- **Low: container reproducibility/runtime scope.** Docker now uses `npm ci`
  and copies only the production dependency set and built adapter output.
- **Medium: CSP inline execution allowance.** SvelteKit page CSP now uses
  nonce mode, and the server fallback no longer adds `unsafe-inline`.
- **Medium: authentication error disclosure.** Auth failures now return generic
  public messages and never include backend exception text or provider details.
- **Low: unbounded JSON mutation bodies.** API JSON mutations reject declared
  bodies larger than 256 KiB; auth payloads also have bounded email, name, and
  credential fields.

## Remaining Findings

### Backend-Dependent

1. **No automated cross-user IDOR integration test.** Frontend routing now
   requires authentication and forwards the bearer token, but the backend must
   still reject user B accessing user A's deck. Add a two-user test against the
   deployed backend for graph, Smart Edit, Due Diligence, export, and product
   API paths.

## Audit Outcome

The previously identified critical authentication fallback, readable session
snapshot, admin guard, incomplete CSP, open redirect, auth error disclosure,
and unbounded JSON-body issues are addressed.
The Smart Deck, Smart Edit, and Due Diligence user surfaces are mounted and
wired to their route loaders and API paths. The current code is not
vulnerability-free until the backend cross-user ownership test is completed.

Deck ID tampering is not considered fixed solely by the frontend gate. The
backend must enforce that the bearer-token subject can access the requested
deck, and this must be tested with two different users and two different deck
IDs.

## Verification

- `npm run build`: passed after the current hardening changes.
- `npm run verify:production-workflow`: passed with no blockers or warnings.
- `npm run verify:product-surfaces -- --strict`: passed for all required
  canonical product surfaces; optional warnings are limited to retired/admin
  verifier observations and compatibility proxies.
- `npm run test:upload-contract`: passed.
- `npm run test:core-deck-workflow`: passed.
- `npm run test:auth-polling`: passed.
- `npm run test:api-error-contract`: passed.
- `npm run test:constants-contract`: passed.
- `npm audit --omit=dev`: 0 known dependency vulnerabilities.
- `git diff --check`: passed.
- `npm run check`: reports existing type errors and 1 unused CSS warning in
  unrelated admin/super-admin surfaces and the unused utility selector. No
  errors were reported in the three canonical user surface files.
- `.env` is ignored and was not included in the commit.
- The local branch was reviewed against `origin/main` before publishing.

## Recommended Next Actions

1. Add and run a backend two-user authorization test for every deck-scoped
   read/write path used by Smart Deck, Smart Edit, Due Diligence, and Export.
2. Add route-specific JSON schemas and rate limits in the backend for billing,
   provider configuration, interest submissions, and AI operations.
