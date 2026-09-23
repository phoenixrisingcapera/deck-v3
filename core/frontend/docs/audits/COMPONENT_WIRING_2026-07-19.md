# Component Wiring Audit - 2026-07-19

This audit covers the canonical mounted DeckAiStack product spine. Compatibility
routes remain redirects and are not alternate owners.

## Canonical route status

| Route | Mounted owner | Contract | Status |
|---|---|---|---|
| `/welcome` | `WelcomeWorkspaceEntry.svelte` | workspace summary and first-deck intake | mounted and wired |
| `/dashboard` | route-owned dashboard | workspace dashboard read model | mounted and wired |
| `/decks` | `DeckLibraryPage.svelte` | deck list | mounted and wired; unavailable filters remain hidden |
| `/decks/new` | route-owned intake | authenticated upload proxy | mounted and wired |
| `/decks/[deckId]/processing` | route-owned processing page | workflow state and job polling | mounted and wired |
| `/decks/[deckId]/smart-deck` | `UserSmartDeckWorkspace.svelte` | deck graph, generation, tools, persisted preferences | mounted and wired |
| `/decks/[deckId]/smart-edit` | route-owned Smart Edit page | persisted Smart Edit runs | mounted and wired |
| `/decks/[deckId]/due-diligence` | route-owned diligence page | durable diligence workflow | mounted and wired |
| `/decks/[deckId]/export` | `ExportPanel.svelte` | export records and generation | mounted but degraded; admin release remains explicit |

## Audited files

### `UserSmartDeckWorkspace.svelte`

- Purpose: owns the mounted Smart Deck shell and tool selection.
- Entry points: route props, `activateTool`, generation and slide callbacks.
- Inputs: persisted deck graph, shell preferences, brand profile, and properties.
- Outputs: mounted tool panels, canonical route navigation, persisted preferences.
- Coupling: `SmartDeckAppRail`, `SmartDeckMediaPanel`, Smart Edit, Due Diligence,
  workspace and product proxies.

### `SmartDeckMediaPanel.svelte` and `deckMedia.ts`

- Purpose: own the user-facing deck media library and translate it to the
  authenticated product API.
- Entry points: list, upload, retry, and archive actions.
- Inputs: deck ID, PNG/JPEG/WebP files, media role.
- Outputs: persisted media records and bounded single-timer status polling.
- Coupling: same-origin `/api/products/deck-aistack-codes/decks/{deckId}/media`
  proxies and backend media workflow jobs.

### Deck Map and Market Research panels

- Purpose: launch durable intelligence commands from the mounted inspector.
- Entry points: existing run actions in `DeckMapPanel.svelte` and
  `MarketResearchPanel.svelte`.
- Inputs: deck ID and current authenticated session.
- Outputs: accepted workflow receipts, canonical job polling, then persisted
  artifact reload through `invalidateAll()`.
- Coupling: `smartDeckUserApi.ts`, `workflow.client.ts`, product proxies, and
  backend workflow-job output.

### Export route and `ExportPanel.svelte`

- Purpose: expose real export generation and honest release state.
- Inputs: deck graph and persisted export records.
- Outputs: generated review artifacts; no download action while admin release is
  locked.
- Compatibility: unsupported inclusion controls remain visibly preserved in
  source but disabled.

## Verification

- `npm run check`: 0 errors, 0 warnings.
- Smart Deck tool wiring contract: passed.
- Durable Deck intelligence contract: passed.
- Truthful product copy contract: passed.
- Product surface contract: required before release after merging current main.
