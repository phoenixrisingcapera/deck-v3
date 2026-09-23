# Font CSP Release

Date: 2026-07-17

## Summary

The frontend no longer requests the Google Fonts Inter stylesheet at runtime.
That stylesheet was blocked by the production Content Security Policy, which
allows styles and fonts from self-hosted sources only.

The release keeps the existing restrictive CSP unchanged and uses the local
font fallback chain already defined in `src/lib/styles/tokens.css`.

## Scope

- Disabled the Google Fonts stylesheet and preconnect links in `src/app.html`.
- Preserved the historical markup as comments with the reason it is disabled.
- Added `scripts/verify-font-csp-contract.mjs` to prevent the external font
  dependency or a wider CSP from returning silently.

## Verification

- `node scripts/verify-font-csp-contract.mjs`
- `npm run check`
- `npm run build`
- Local Playwright runtime smoke against the built Node adapter

The browser smoke returned HTTP 200 with zero Google Fonts requests and zero
Content Security Policy console errors.

## Runtime Impact

The frontend uses its existing local fallback stack: Inter when installed,
followed by IBM Plex Sans, platform UI fonts, Segoe UI, and sans-serif. No API,
backend, database, authentication, or persisted deck contract changes are part
of this release.

## Rollback

Revert the release commit. Do not re-enable the external stylesheet unless the
security and privacy decision explicitly includes the required `style-src` and
`font-src` hosts.
