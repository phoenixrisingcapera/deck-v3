# Global Product Layout Implementation Plan

Date: 2026-07-31  
Scope: `src/routes/(product)`  
Status: implementation checklist; no application code changed in this pass  
Companion diagnosis: `GLOBAL_PRODUCT_LAYOUT_DIAGNOSIS_2026-07-31.md`

## Goal

Make Instant Deck, Smart Deck, Smart Edit, Due Diligence, Diligence, and Export
feel like one DeckAiStack product by giving them one inherited deck-workspace
chrome and one viewport contract.

"Same layout" means the same outer identity, navigation, rail geometry, tokens,
status area, height rules, and responsive behavior. It does not mean forcing
every feature to use the same internal content columns.

## Target contract

Every deck workspace route must have:

1. exactly one product route frame;
2. exactly one deck identity/surface navigation header;
3. exactly one shared tool-rail geometry;
4. exactly one bounded content viewport;
5. exactly one compact workspace status/utilities row;
6. no page-level `100vh`, document scroll, or viewport-fixed panel chrome;
7. page-local scrolling only inside navigator, content/canvas, and inspector regions.

## Proposed shared primitives

Names are implementation suggestions, not authorization to create parallel
product surfaces.

### `ProductRouteFrame`

Owner: `src/routes/(product)/+layout.svelte`; admin uses the separate
`src/lib/components/admin/AdminAppShell.svelte`

Responsibilities:

- authenticated product viewport;
- route progress and mobile gate;
- global semantic color, spacing, elevation, and focus tokens;
- product-page versus deck-workspace footer policy;
- no deck-specific tool state.

### `classifyProductLayoutMode(pathname)`

Owner: a small shared layout module, consumed by the inherited product layout.

Suggested result:

```ts
type ProductLayoutMode = 'page' | 'deck-workspace' | 'deck-document';
```

- `deck-workspace`: Smart Deck, Smart Edit, Due Diligence, and Diligence.
- `deck-document`: Export and other deck-scoped document/report pages.
- `page`: Dashboard, deck library, settings, billing, and other normal pages.

This replaces the duplicated route regular expressions in
`lib/layouts/AppShell.svelte`.

### `DeckWorkspaceChrome`

Owner: `src/routes/(product)/decks/[deckId]/+layout.svelte`.

Responsibilities:

- deck title and workspace identity;
- `ProductSurfaceNav` mounted once;
- dashboard return;
- shared workspace slot with `minmax(0, 1fr)` containment;
- layout-mode data attributes and shared CSS variables;
- no Smart Deck generation or feature-specific state.

### `GlobalDeckSidebar`

Owner: shared component used by Smart Deck, Smart Edit, and Due Diligence.

Responsibilities:

- one rail width token;
- one icon/button/focus/tooltip/active-state contract;
- surface-specific items supplied as data;
- URL-backed active panel where appropriate;
- no backend business logic.

The canonical Smart Deck, Smart Edit, and Due Diligence callers now use
`src/lib/components/decks/GlobalDeckSidebar.svelte`. The older rail files remain
preserved until browser parity and remaining external caller checks are complete.

### `GlobalDeckWorkspaceFrame`

Owner: `src/lib/components/decks/GlobalDeckWorkspaceFrame.svelte`, with actual
column widths and responsive tracks owned by `decks/[deckId]/+layout.svelte`.

Suggested regions:

```text
tool-rail | navigator | primary-content | inspector
```

Variants may hide or resize regions, but all use shared tokens:

```css
--deck-tool-rail-width: 72px;
--deck-navigator-width: 280px;
--deck-inspector-width: 360px;
--deck-toolbar-height: 52px;
--deck-status-height: 42px;
```

The exact values should be confirmed through browser comparison, then declared
once rather than repeated across route CSS.

## Route matrix after migration

| Canonical entry | Shared outer chrome | Page-owned primary content | Initial-state invariant |
| --- | --- | --- | --- |
| `/decks/[deckId]/smart-deck` | Deck workspace | Slide navigator, rendered canvas, inspector, generation review | Restore the user's normal Smart Deck tool preference |
| `/decks/[deckId]/smart-deck?instant=1` | Same Deck workspace | Same rendered canvas and inspector | Start session in `slides`; auto-generate once; do not overwrite normal saved tool preference |
| `/decks/[deckId]/smart-edit` | Same Deck workspace | Selected-slide canvas, element/text tools, reviewable variation | Select a version containing the requested slide |
| `/decks/[deckId]/due-diligence` | Same Deck workspace | Evidence visualizer and analysis panel | Analysis remains outside visible generated slide copy |
| `/decks/[deckId]/diligence` | Same Deck workspace | Detailed report/analysis content | No automatic provider call merely from opening |
| `/decks/[deckId]/export` | Same deck identity and tokens, document variant | Export formats, saved exports, download state | No nested `100vh` shell or duplicate top bar |

## Implementation phases

### Phase 0 — capture the current mounted baseline

- [ ] Add route-level screenshots for Smart Deck, Instant Deck, Smart Edit, Due Diligence, Diligence, and Export at 1440x900.
- [ ] Record DOM counts for product footer, surface navigation, utility bar, top bar, and tool rail.
- [ ] Add an ownership test that distinguishes `lib/layouts/AppShell.svelte` from `lib/components/AppShell.svelte`.
- [ ] Record the current nested-scroll behavior before changing CSS.
- [ ] Keep the existing screenshot as the Instant Deck failure fixture.

Acceptance:

- [ ] The test fails when a page adds a second global shell or surface navigation.
- [ ] The test identifies the mounted route tree, not comments or disabled blocks.

### Phase 1 — centralize product layout mode

- [x] Replace duplicate workspace-route regular expressions with `classifyProductLayoutMode`.
- [x] Include Smart Deck, Smart Edit, Due Diligence, Diligence, and Export in an explicit mode matrix.
- [x] Remove the unused `fullHeightDeckWorkspaceRoute` local only after caller/reference proof.
- [x] Add `data-layout-mode` to the global product frame for CSS and tests.
- [x] Keep normal product pages in document-scrolling `page` mode.

Acceptance:

- [x] One function decides layout mode.
- [x] Query parameters such as `instant=1` do not create a second route layout.

### Phase 2 — establish one viewport owner

- [x] Keep `100dvh` only on the inherited global product frame.
- [x] Change deck-layout and route-layout descendants to `height: 100%; min-height: 0`.
- [x] Replace the Smart Deck route-local `min-height: calc(100vh - 1px)` contract.
- [x] Ensure `[deckId]/+layout.svelte` allocates header plus `minmax(0, 1fr)` content.
- [ ] Convert the Smart Deck fixed retry banner into a workspace-grid or anchored overlay region.
- [ ] Audit every deck child for `100vh`, fixed offsets, and page-level scrolling.

Acceptance:

- [ ] No document scrollbar on desktop editor routes.
- [ ] Global header, compact status row, and workspace fit within one viewport.
- [ ] Navigator, content, and inspector can scroll independently.

### Phase 3 — define workspace footer policy

- [x] In `deck-workspace` mode, render one compact status/utilities row.
- [x] Do not stack the full legal footer below an editor canvas.
- [x] In `page` and `deck-document` modes, keep the normal legal footer where appropriate.
- [x] Preserve billing/privacy/terms access through the compact workspace menu or another explicit shared location.

Acceptance:

- [x] Editor routes have one global bottom row; page-owned filmstrips remain inside the bounded workspace.
- [x] Legal links remain reachable and keyboard accessible.

### Phase 4 — move common deck chrome to the deck layout

- [x] Refactor `[deckId]/+layout.svelte` into the single deck-workspace geometry owner.
- [x] Mount deck identity and `ProductSurfaceNav` exactly once.
- [x] Define shared header, border, background, and four-column geometry tokens.
- [x] Add a child content slot that cannot exceed the allocated viewport.
- [ ] Ensure compatibility redirects never mount this workspace themselves.

Acceptance:

- [ ] Smart Deck, Smart Edit, Due Diligence, Diligence, and Export show the same deck identity and surface tabs.
- [ ] No child page recreates a global deck top bar.

### Phase 5 — make Instant Deck a Smart Deck state, not a visual fork

- [x] On `instant=1`, initialize the session-local `activeTool` to `slides`.
- [x] Do not persist that forced entry state over the user's normal Smart Deck preference.
- [x] Keep the same `SmartDeckWorkspaceFrame`, canvas, navigator, inspector, and responsive rules.
- [x] Keep automatic whole-deck generation idempotent and start it once.
- [ ] Show Instant Deck mode as a status/intent label inside the shared toolbar, not as a different page composition.
- [x] Keep Deck Map available through an explicit user action.

Acceptance:

- [x] Opening Instant Deck always shows the canvas-first workspace.
- [x] Returning to normal Smart Deck restores the user's prior tool preference.
- [x] Refreshing Instant Deck does not enqueue duplicate whole-deck jobs.

### Phase 6 — migrate the canonical surfaces incrementally

#### Smart Deck

- [x] Keep `UserSmartDeckWorkspace` as the coordinator.
- [x] Mount `GlobalDeckWorkspaceFrame` and let the deck-scoped route own the actual grid tracks.
- [x] Use `GlobalDeckSidebar`, `GlobalDeckSlideNavigator`, `GlobalDeckVisualizer`, and `GlobalDeckChatPanel` for the four canonical columns.
- [ ] Remove route-local global chrome only after the deck layout owns parity.

#### Smart Edit

- [ ] Stop using the page-level component `AppShell` as an outer workspace owner.
- [x] Reuse the global sidebar, slide navigator, visualizer, and deck-layout grid while preserving selected-slide/version logic.
- [x] Keep Smart Edit's element/text/design controls page-owned in an overlay tool panel.

#### Due Diligence

- [x] Reuse the global sidebar, slide navigator, visualizer, and outer frame geometry.
- [x] Keep evidence visualizer and analysis workspace page-owned.
- [x] Keep report insights separate from generated slide render-schema text.

#### Diligence

- [ ] Use the same outer deck chrome in a report-oriented frame variant.
- [ ] Preserve its distinct analysis ownership and route.

#### Export

- [ ] Remove the nested default-`100vh` component-shell behavior.
- [ ] Use the shared deck identity and a document/content variant.
- [ ] Preserve all real export contracts and saved-export state.

Acceptance:

- [ ] Each migration passes before the next surface starts.
- [ ] Old shell components remain preserved until all imports and parity are proven.

### Phase 7 — unify responsive behavior

- [ ] Desktop: shared rail, optional navigator, dominant content, optional inspector.
- [ ] Tablet: shared rail plus content; navigator and inspector become mutually exclusive drawers.
- [ ] Mobile: compact header, full-width content, bottom navigator, full-screen tool sheets.
- [ ] Use the same breakpoints across Smart Deck, Smart Edit, and Due Diligence.
- [ ] Test 1440, 1024, 768, 414, 390, and 320 pixel widths.

Acceptance:

- [ ] No clipped primary actions or unreachable inspector controls.
- [ ] Exactly one primary slide-navigation surface is visible per breakpoint.
- [ ] Focus remains visible when panels change form.

### Phase 8 — runtime and visual proof

- [x] Run `npm run check`.
- [ ] Run the production build.
- [x] Run focused layout, responsive-panel, and Instant Deck ownership contracts.
- [ ] Add Playwright assertions for route transitions and shell persistence.
- [ ] Compare screenshots for every route and breakpoint.
- [ ] Verify the actual deployed route after merge; a local build alone is not production proof.

Required Playwright assertions:

- [ ] One `ProductSurfaceNav`.
- [ ] One workspace status/utilities row.
- [ ] At most one legal footer according to layout mode.
- [ ] One shared tool rail on deck workspaces.
- [ ] `document.documentElement.scrollHeight === document.documentElement.clientHeight` on desktop editor routes.
- [ ] Instant Deck enters `slides` while normal Smart Deck preference remains unchanged.
- [ ] Route transitions preserve deck identity without duplicating chrome.

## Primary files expected to change during implementation

Shared layout ownership:

- `src/routes/(product)/+layout.svelte`
- `src/lib/components/admin/AdminAppShell.svelte`
- `src/lib/styles/layout.css`
- `src/routes/(product)/decks/[deckId]/+layout.svelte`
- `src/lib/components/decks/GlobalDeckWorkspaceFrame.svelte`
- `src/lib/components/decks/GlobalDeckSidebar.svelte`
- `src/lib/components/decks/GlobalDeckSlideNavigator.svelte`
- `src/lib/components/decks/GlobalDeckVisualizer.svelte`
- `src/lib/components/decks/GlobalDeckChatPanel.svelte`
- `src/lib/components/navigation/ProductSurfaceNav.svelte`
- `src/lib/components/ProductFooter.svelte`

Deck workspace surfaces:

- `src/routes/(product)/decks/[deckId]/smart-deck/+layout.svelte`
- `src/routes/(product)/decks/[deckId]/smart-deck/+page.svelte`
- `src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte`
- `src/lib/features/smart-deck/user/SmartDeckWorkspaceFrame.svelte`
- `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte`
- `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte`
- `src/lib/components/due-diligence/DueDiligenceWorkspaceFrame.svelte`
- `src/routes/(product)/decks/[deckId]/diligence/+page.svelte`
- `src/routes/(product)/decks/[deckId]/export/+page.svelte`

Tests:

- mounted-route ownership contracts;
- layout-mode unit tests;
- Playwright shell/overflow/route-transition coverage;
- visual regression fixtures for the canonical routes.

## Explicit non-goals

- No new `/instant-deck` mounted editor.
- No new alternate Smart Deck, Smart Edit, Due Diligence, or Export page.
- No backend API, worker, persistence, or render-schema rewrite merely to fix layout.
- No broad deletion of page-level `components/AppShell.svelte`, old rails, or preserved compatibility components before all callers and parity are proven. The former layout shell was retired only after its two route-layout callers were migrated.
- No claim that the product is unified until the canonical deployed routes pass browser comparison.

## Recommended first implementation slice

The safest first PR should include only:

1. centralized layout-mode classification;
2. global workspace footer policy;
3. `height: 100%; min-height: 0` containment through the inherited deck route;
4. removal of Smart Deck's child `100vh` behavior;
5. Instant Deck session-local `activeTool='slides'` entry invariant;
6. focused ownership and overflow tests.

This slice addresses the supplied screenshot without prematurely migrating all
surface-specific grids in one risky change.

## Local execution evidence — 2026-07-31

- `npm run test:deck-workspace-layout`: passed all 12 ownership and region checks.
- `npm run test:smart-deck-responsive-panels`: passed all 19 responsive-region checks.
- `npm run test:instant-deck`: passed all 20 lifecycle and idempotency checks.
- `npm run check`: passed.
- `npm run test:global-product-nav`: two existing contract failures remain outside this slice:
  the script expects an older active-path implementation, and Smart Edit already
  contains a direct Diligence link.
- `npm run build`: currently blocked by concurrent local route cleanup. During
  two build attempts, SvelteKit-generated nodes referenced route files removed
  while compilation was running (`decks/[deckId]/export` first, then the
  top-level compatibility `smart-deck`). This layout slice did not delete or
  restore those routes. Re-run after the route move/prune operation is stable.
- Browser screenshots and deployed-route verification remain open; static
  checks are not runtime visual proof.

### Four-column global component migration

- `test:deck-workspace-layout`: passed 14 route ownership and four-column checks.
- `test:smart-deck-responsive-panels`: passed all 19 responsive-region checks.
- Smart Deck tool wiring, conversation, brand, miniature, visual ownership,
  Smart Edit phase-zero, and utilities-placement contracts passed after their
  canonical file references were updated.
- Full `npm run check` remains blocked by concurrent route-folder cleanup that
  leaves generated `RouteParams` without the former `deckId`/`iterationId`
  segments. This migration's changed Svelte files produced warnings but no new
  type errors in a filtered check.
- Browser parity remains required before removing preserved rail/frame adapters.
