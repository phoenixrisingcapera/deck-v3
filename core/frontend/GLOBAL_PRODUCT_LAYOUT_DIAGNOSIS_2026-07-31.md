# Global Product Layout Diagnosis

Date: 2026-07-31  
Scope: `src/routes/(product)`  
Status: diagnosis only; no application code changed  
Evidence: supplied Instant Deck screenshot, mounted Svelte route tree, inherited layouts, and current workspace components

## Executive finding

The product does have inherited SvelteKit layouts, but it does not have one
clear owner for deck-workspace chrome and viewport geometry.

The current browser tree combines four different layout systems:

1. `(product)/+layout.svelte` mounts the global route shell and global footer.
2. `decks/[deckId]/+layout.svelte` mounts the deck identity and product-surface navigation.
3. Individual pages mount different local shells, rails, top bars, grids, and overflow rules.
4. `smart-deck/+layout.svelte` creates another viewport boundary using `100vh` even though the route already lives inside a bounded product viewport.

The result is a product that shares URLs and data but does not share one visual
frame. Smart Deck, Smart Edit, Due Diligence, Export, and the Instant Deck entry
therefore look like separate applications.

## Why the supplied Instant Deck view looks different

Instant Deck is not a separate mounted page. The canonical URL is:

`/decks/[deckId]/smart-deck?instant=1`

`ProductSurfaceNav.svelte` correctly points Instant Deck to that URL, and the
Smart Deck page mounts the same `UserSmartDeckWorkspace.svelte` used by normal
Smart Deck.

The screenshot differs for two concrete reasons:

### 1. Instant Deck restores a persisted tool instead of opening the canvas

`UserSmartDeckWorkspace.svelte` initializes `activeTool` from persisted
workspace preferences. The `instantMode` flag changes generation mode and the
automatic whole-deck generation lifecycle, but it does not force a canvas-first
initial tool.

In the supplied screenshot, the persisted tool is `deck_map`. That branch
replaces the slide navigator/canvas area with the expanded `DeckMapPanel`, while
the normal inspector remains mounted. This is why the Instant Deck entry appears
to be a Deck Analysis page rather than the same Smart Deck workspace.

Status: **mounted and wired, but degraded by restored route state**.

### 2. The workspace height is calculated by competing owners

The global shell already owns a `100dvh` viewport and reserves rows for product
utilities and the legal footer. The deck layout then reserves a header row.
Inside that remaining area, `smart-deck/+layout.svelte` declares
`min-height: calc(100vh - 1px)`.

The child therefore asks for almost an entire viewport after the parent has
already consumed header and footer space. The document or an internal region
must overflow, which produces the clipped, crowded, and vertically displaced
composition visible in the screenshot.

Status: **mounted but degraded**.

## Mounted ownership map

| Layer | Current owner | What it currently owns | Diagnosis |
| --- | --- | --- | --- |
| Authenticated product layout | `src/routes/(product)/+layout.svelte` | Backend banner and `lib/layouts/AppShell.svelte` | Correct inheritance point, incomplete global workspace contract |
| Global product frame | `src/lib/layouts/AppShell.svelte` | Route progress, mobile gate, utilities, legal footer | Always mounts footer rows; workspace route classification is duplicated and incomplete |
| Global layout CSS | `src/lib/styles/layout.css` | `100dvh`, shell rows, `.app-shell`, `.editor-viewport`, overflow | Contains both page and editor rules, with overlapping definitions |
| Deck subtree layout | `src/routes/(product)/decks/[deckId]/+layout.svelte` | Deck identity, surface navigation, dashboard return | Correct shared route owner, but does not own the complete deck workspace frame |
| Surface navigation | `src/lib/components/navigation/ProductSurfaceNav.svelte` | Smart Deck, Instant Deck, Smart Edit, Due Diligence, Export links | Mounted and wired; Instant Deck correctly remains a query-mode entry |
| Smart Deck route layout | `src/routes/(product)/decks/[deckId]/smart-deck/+layout.svelte` | Background and route-local viewport boundary | `100vh` conflicts with inherited bounded height |
| Smart Deck workspace | `UserSmartDeckWorkspace.svelte` and `SmartDeckWorkspaceFrame.svelte` | App rail, top bar, navigator, canvas, inspector, filmstrip, tool panels | Rich mounted workspace, but it owns global-looking chrome locally |
| Smart Edit page | `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte` | Nested component `AppShell`, Smart Edit rail, canvas, editor, inspector | Uses a different four/five-column contract and an extra shell wrapper |
| Due Diligence page | `src/routes/(product)/decks/[deckId]/due-diligence/+page.svelte` and `DueDiligenceWorkspaceFrame.svelte` | Due Diligence rail, miniature rail, evidence visualizer, analysis panel | Separate rail width, column model, and breakpoint policy |
| Export page | `src/routes/(product)/decks/[deckId]/export/+page.svelte` | Nested component `AppShell`, top bar, export content | Excluded from full-height route classification and inherits a default `100vh` shell |
| Component shell | `src/lib/components/AppShell.svelte` | Sidebar/top bar/content wrapper for many pages | A second shell abstraction with a similar name but different responsibility |
| Product footer | `src/lib/components/ProductFooter.svelte` | Utilities bar plus legal footer | Always rendered, including full-height editor workspaces |

## Confirmed structural breakpoints

### Critical: there are two different `AppShell` abstractions

- `src/lib/layouts/AppShell.svelte` is the inherited global route frame.
- `src/lib/components/AppShell.svelte` is a page-level sidebar/top-bar wrapper.

Smart Edit and Export mount the component shell inside the inherited layout;
Smart Deck and Due Diligence do not. Even when options hide parts of the nested
shell, the ownership model differs by page.

### Critical: route-local `100vh` violates the inherited layout contract

`smart-deck/+layout.svelte` must consume the parent slot with `height: 100%` and
`min-height: 0`. It must not create another viewport.

The same rule applies to every page-level shell nested under `(product)`:
children consume allocated space; only the global product frame owns viewport
height.

### Critical: Instant Deck does not define a visual-entry invariant

The `instant=1` lifecycle controls generation but not initial workspace
composition. Persisted `activeTool=deck_map` can replace the canvas on entry.
Instant Deck needs a session-local rule that starts in `slides` without erasing
the user's normal saved Smart Deck tool preference.

### Major: full-height route classification is duplicated and incomplete

`lib/layouts/AppShell.svelte` declares both `fullHeightDeckWorkspaceRoute` and
`fullHeightWorkspaceRoute` with the same regular expression. One is unused.
The list includes Smart Deck, Smart Edit, and Due Diligence, but excludes
Export and the distinct Diligence analysis surface.

Layout mode should be decided once by a shared route classifier or explicit
layout data, not by repeated regular expressions.

### Major: shared-looking rails are separate implementations

- Smart Deck uses `SmartDeckAppRail` at 72px.
- Smart Edit uses `SmartEditSidebar` inside its own grid.
- Due Diligence uses `DueDiligenceSidebar` in a 64px column.

The controls may differ, but their geometry, active state, icons, focus style,
and navigation behavior should come from one shared deck-workspace rail.

### Major: each workspace defines its own incompatible grid

- Smart Deck: `72px 280px minmax(0, 1fr) 360px` plus top bar and filmstrip rows.
- Smart Edit: `72px 280px minmax(0, 1fr) 340px`, expanding to five columns for tools.
- Due Diligence: `64px 96px minmax(0, 1fr) 360px`.

These should be variants of one named grid contract rather than unrelated page
CSS. The canvas/content region must remain the dominant `minmax(0, 1fr)` area.

### Major: the global footer has no editor-specific policy

`ProductFooter.svelte` renders both utilities and legal content. On a
full-height editor this creates two persistent bottom rows, while the inner
workspace also owns a filmstrip or action row. The screenshot shows this
stacking clearly.

The global layout should keep a compact status/utilities row for workspaces and
reserve the full legal footer for document-style product pages.

### Major: fixed and absolute child chrome escapes the layout

For example, the Smart Deck retry banner is `position: fixed` with a hard-coded
right offset. It is positioned against the browser viewport, not the shared
deck-workspace grid, so it can collide with the global header, inspector, or
responsive layouts.

## Correct architecture decision

A single monolithic layout for every product page would also be incorrect.
Dashboard, settings, deck library, and a full-screen deck editor do not need the
same internal grid.

The correct hierarchy is two shared layout levels:

```text
(product)/+layout.svelte
  ProductRouteFrame
    auth, theme, backend banner, route progress
    global product tokens
    page-mode or workspace-mode footer policy

    decks/[deckId]/+layout.svelte
      DeckWorkspaceChrome
        one deck identity
        one product-surface navigation
        one shared workspace viewport
        one compact global status/utilities row

        child surface
          Smart Deck and Instant Deck
          Smart Edit
          Due Diligence
          Diligence analysis
          Export
```

The deck layout owns common chrome and physical containment. Each child owns
only its feature-specific navigator, canvas/content, inspector, and actions.

## What should remain unchanged

- Instant Deck remains `/smart-deck?instant=1`; do not create another editor route.
- Smart Deck, Smart Edit, Due Diligence, and Export retain their canonical URLs.
- Existing loaders, API proxies, backend endpoints, workers, persistence, and render-schema contracts are not layout responsibilities.
- Compatibility routes remain redirects only.
- Existing local work and disabled historical blocks must not be pruned as part of layout work without separate caller proof.

## Status summary

- `(product)` global shell: **mounted but degraded**.
- Deck-scoped layout: **mounted but incomplete as a global workspace owner**.
- Smart Deck: **mounted and wired, layout degraded**.
- Instant Deck: **mounted through Smart Deck, state and layout degraded**.
- Smart Edit: **mounted and wired, layout inconsistent**.
- Due Diligence: **mounted and wired, layout inconsistent**.
- Export: **mounted and wired, nested-shell and scrolling inconsistent**.

This diagnosis supersedes the physical-containment portion of
`SMART_DECK_REAL_SVELTE_DEPTH_PLAN_2026-07-22.md`: the route-local Smart Deck
layout now exists, but its current `100vh` contract is not compatible with the
inherited global frame. The earlier canonical-route ownership remains valid.
