# UI Polish, Accessibility, CSP, and Dashboard - 2026-07-17

## PR

[#94](https://github.com/phoenixrisingcapera/deck-Aistack-front-new/pull/94)

## Tag

`v2026.07.17-ui-polish-accessibility-csp`

## Changes

### CSP Compliance
- Disabled external Google Fonts `<link>` and `<preconnect>` in `app.html`
- Font tokens retain local Inter/IBM Plex/System fallbacks
- New verifier: `scripts/verify-font-csp-contract.mjs` (4 checks)

### Smart Deck Accessibility
- Inspector panel: proper `role=tablist` / `role=tab` / `role=tabpanel` with roving tabindex and arrow-key navigation
- AI Assistant: collapsible generation-context `<details>`, sticky version-actions footer, primary-button gradient for Apply
- TopBar: `aria-pressed` on mode buttons, `role=status` with `aria-live=polite` for save state, screen-reader-only share feedback
- Slide Navigator: wired to persisted create-slide flow with loading state, `aria-current` on active slide

### Dashboard
- Readable status labels (underscores → spaces, title case)
- Configure AI link when provider is unconfigured
- Responsive width (`min(100%, 1440px)`), wrapped health header

### Workspace
- Debug provenance controls gated behind `canSeeDebug` visibility
- Tool wiring verifier extended with slide-navigator and provenance checks

## Verification

- `svelte-check`: 0 errors, 0 warnings
- Smart Deck tool wiring contract: 13/13 passed
- Font CSP contract: 4/4 passed
- `git diff --check` passed
- Railway deploy succeeded
- Production: frontend root HTTP 200

## Rollback

Revert the merge commit.
