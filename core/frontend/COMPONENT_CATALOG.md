# Component Catalog and Naming Map

This document explains the current purpose of every file under `src/lib/components` so components can be reorganized without guessing from similar names.

Snapshot: 2026-08-22. This is an ownership aid, not proof that a component is safe to delete. Before moving, renaming, or removing a component, check its imports, mounted routes, tests, scripts, compatibility paths, and persisted contracts.

## Status language

- **Mounted and wired**: imported by a current route or by a component mounted on that route.
- **Admin/operator**: belongs to an admin or diagnostic route, not the canonical customer route.
- **Shared primitive**: used inside one or more larger surfaces; it is not a page or shell by itself.
- **Compatibility/older location**: duplicates a newer grouped location or preserves an older import surface. Caller proof is still required before consolidation.
- **Unverified in this pass**: the file exists, but this catalog does not claim a current mounted caller.

## Read this first: the confusing Deck and Shell names

| File | Current function and ownership |
| --- | --- |
| `src/routes/(product)/+layout.svelte` | Owns the authenticated product route frame directly. The product no longer imports the former shared `lib/layouts/AppShell.svelte`. |
| `src/routes/(product)/decks/[deckId]/+layout.svelte` | Canonical four-column deck geometry owner: global sidebar, slide navigator, visualizer, and chat/inspector. |
| `src/lib/components/AppShell.svelte` | Reusable page-level chrome used by product pages. It composes `Sidebar`, `TopBar`, optional utilities, and page content inside the global route layout. It is not the global route layout itself. |
| `src/routes/(product)/decks/[deckId]/+page.server.ts` | Redirect-only compatibility owner for `/decks/[deckId]`; the unreachable overview page and its sole-use `DeckWorkspace.svelte` were removed after caller proof. |
| `src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte` | Canonical customer workspace mounted by `/decks/[deckId]/smart-deck`. It lives under `features`, outside this catalog's component directory. |
| `src/lib/components/decks/GlobalDeckWorkspaceFrame.svelte` | Marks a canonical deck workspace for the `[deckId]` route layout. It deliberately owns no column widths. |
| `src/lib/components/decks/GlobalDeckSidebar.svelte` | Shared first-column tool/navigation rail used by Smart Deck, Smart Edit, and Due Diligence. |
| `src/lib/components/decks/GlobalDeckSlideNavigator.svelte` | Shared second-column slide miniature navigator used by Smart Deck, Smart Edit, and Due Diligence. |
| `src/lib/components/decks/GlobalDeckVisualizer.svelte` | Shared third-column visualizer for the actual generated slide image or persisted render schema. It must not substitute analysis summary text. |
| `src/lib/components/decks/GlobalDeckChatPanel.svelte` | Canonical Smart Deck chat/generation component for the fourth-column chat region. Smart Edit and Due Diligence keep feature-specific chat contracts in the same global region. |
| `src/lib/features/smart-deck/user/SmartDeckWorkspaceFrame.svelte` | Preserved older Smart Deck frame path. The canonical customer workspace now mounts `GlobalDeckWorkspaceFrame`. |
| `src/lib/components/smart-deck/GeneratedSlideRenderer.svelte` | Lowest-level shared renderer for persisted generated slide schemas. The canonical product Smart Deck canvas also imports it. Do not classify it as admin-only. |
| `src/lib/components/PublicAuthShell.svelte` | Layout shell for public authentication screens; unrelated to deck workspace shells. |

### Practical naming rule

When reorganizing, keep three concepts separate:

1. **Product route frame**: `src/routes/(product)/+layout.svelte`.
2. **Deck four-column geometry**: `src/routes/(product)/decks/[deckId]/+layout.svelte`.
3. **Shared deck columns**: `src/lib/components/decks/GlobalDeck*.svelte`.
4. **Customer Smart Deck state**: `src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte`.
5. **Private operator UI**: the separate `deck.admins-main` repository, not this component tree.

`GlobalDeckVisualizer` and `GeneratedSlideRenderer` are customer-product rendering primitives and must remain free of private operator ownership.

## Target Grouping For Refactor

This is the recommended grouping for the current component cleanup.

The main rule is:

- layouts own page structure
- pages own composition
- shared/global components stay small and reusable
- feature components own feature-specific behavior
- compatibility wrappers and proxy shells should be removed over time

## 1. Global application components

Recommended folder intent:

- `src/lib/components/global/`

These should be small app-wide primitives, not page shells.

Examples to converge here:

- `AppLogo.svelte`
- `ProductFooter.svelte`
- `RouteProgress.svelte`
- `ThemeToggle.svelte`
- `WorkspaceAiProviderModal.svelte`
- `StatusBadge.svelte`
- `RiskBadge.svelte`
- `BackendErrorBanner.svelte`

Rule:

- these can appear in many places
- none of them should own a route layout or a page shell

## 2. Product route layouts

Recommended owners:

- `src/routes/(product)/+layout.svelte`
- `src/routes/(product)/dashboard/+layout.svelte`
- `src/routes/(product)/decks/[deckId]/+layout.svelte`
- future route-specific layouts under the product group when the surface has stable shared composition

Important rule:

- route layout files should own composition and geometry
- do not re-create page shells in `src/lib/components` when the route already has a clear layout owner

## 3. Dashboard composition

Recommended folder intent:

- `src/lib/components/dashboard/`

Dashboard should become layout-first.

Meaning:

- add a canonical `src/routes/(product)/dashboard/+layout.svelte` when dashboard composition becomes stable
- keep page composition there instead of scattering dashboard ownership across many independent wrappers

Dashboard components that already belong together:

- `dashboard/CurrentDeckCard.svelte`
- `dashboard/DashboardRightRail.svelte`
- `dashboard/DashboardWelcomeHero.svelte`
- `dashboard/LatestIterationsCard.svelte`
- `dashboard/RecentSlidesPreview.svelte`
- `dashboard/SlidePreviewTile.svelte`
- `dashboard/UploadedDecksPanel.svelte`
- `dashboard/WorkspaceStatsCard.svelte`
- `FirstTimeDashboard.svelte`
- `ReturningUserDashboard.svelte`

Refactor rule:

- dashboard layout owns the arrangement
- dashboard components become blocks inside that arrangement
- avoid introducing another component-level shell to organize the dashboard

## 4. Deck workspace shell

Recommended owner:

- `src/routes/(product)/decks/[deckId]/+layout.svelte`

Recommended shared deck-global folder intent:

- `src/lib/components/decks/`

Canonical shared deck-shell pieces already pointing this direction:

- `decks/GlobalDeckWorkspaceFrame.svelte`
- `decks/GlobalDeckSidebar.svelte`
- `decks/GlobalDeckSlideNavigator.svelte`
- `decks/GlobalDeckVisualizer.svelte`
- `decks/GlobalDeckChatPanel.svelte`

Rule:

- the `[deckId]` layout owns the shell geometry
- shared deck components provide column content only
- feature routes mount their feature-specific pieces into that shell

## 5. Feature-specific deck behavior

Recommended folder intent:

- `src/lib/features/`

This is where route-specific behavior should live when it is not globally reusable.

Examples:

- `features/smart-deck/user/*`
- future `features/smart-edit/*`
- future `features/due-diligence/*`

Rule:

- if a component owns feature logic, request/response behavior, or route-specific state, keep it in `features`
- do not promote it into `components/global` just because multiple files import it

## 6. Admin/operator surfaces

Private admin and super-admin surfaces are intentionally absent from this repository. Their UI, route ownership, and operator-only API clients live in `deck.admins-main` and the separate super-admin control plane.

## 7. Marketing and public auth

Recommended grouped owners:

- `src/lib/components/marketing/`
- `src/lib/components/welcome-v2/`
- `src/lib/components/PublicAuthShell.svelte`

Rule:

- top-level duplicate marketing components should be reduced in favor of the grouped mounted owners

## Layout-First Refactor Plan

## Rule Zero

No more proxy-of-proxy composition.

Meaning:

- do not create a component shell just to mount another component shell
- prefer one clear route layout owner, then mount direct children inside it

## Phase 1: Lock canonical layout owners

Canonical owners should be:

- product frame: `src/routes/(product)/+layout.svelte`
- dashboard frame: future `src/routes/(product)/dashboard/+layout.svelte`
- deck workspace frame: `src/routes/(product)/decks/[deckId]/+layout.svelte`

## Phase 2: Move composition out of generic shells

Targets:

- stop relying on `src/lib/components/AppShell.svelte` for route ownership where route layouts now exist
- stop relying on internal fallback shells for product route composition

## Phase 3: Group by owning surface

Move toward these groupings:

- `components/global/`
- `components/dashboard/`
- `components/decks/`
- `components/due-diligence/`
- `components/marketing/`
- `components/llm/`
- `components/navigation/`
- `components/deckService/brand/`
- `components/deckService/upload/`
- `features/smart-deck/`
- future `features/smart-edit/`
- future `features/due-diligence/`

## Phase 4: Build route-local layouts instead of component shells

Examples:

- dashboard should get a canonical route layout that arranges dashboard blocks
- deck routes should compose directly inside `[deckId]/+layout.svelte`
- report/output pages should use route/page composition, not another general-purpose shell wrapper

## Phase 5: Prune compatibility locations

After imports are moved:

- remove old top-level duplicates
- remove preserved wrappers that no longer own mounted callers
- remove shell components that only exist because the old route structure lacked layouts

## Legacy And Prune Candidates

These are documentation candidates for consolidation or removal. Caller proof is still required before deleting any file.

## High-priority prune/consolidation candidates

- `src/lib/components/AppShell.svelte`
  - old page-level shell
  - should continue shrinking as route layouts take ownership
- `src/lib/components/Sidebar.svelte`
  - coupled to the old `AppShell` page shell
  - keep only if non-deck/non-dashboard routes still truly need it
- `src/lib/components/TopBar.svelte`
  - old page-shell top bar
  - route layouts/pages should increasingly own their own header composition
- `src/lib/features/smart-deck/user/SmartDeckWorkspaceFrame.svelte`
  - explicit prune target
  - the layout should define geometry, not this component

## Older-location duplicate candidates

- `src/lib/components/MarketingFooter.svelte`
- `src/lib/components/MarketingHeader.svelte`
- `src/lib/components/MarketingUtilitiesBar.svelte`
- `src/lib/components/WelcomeActionCard.svelte`

These should converge toward their grouped mounted owners:

- `components/marketing/*`
- `components/welcome-v2/*`

## Retired admin compatibility adapters

`InteractiveDeckShell.svelte`, `deck-shell/*`, and the older `components/smart-deck/SmartDeckWorkspace.svelte` family were removed after their only live ownership moved out of the customer product.

## Dashboard-specific cleanup candidates

- `FirstTimeDashboard.svelte`
- `ReturningUserDashboard.svelte`

These are likely still useful, but dashboard route/layout should own when to mount them rather than leaving dashboard composition implicit in scattered wrappers.

## Recommended Canonical Ownership Summary

Use this as the practical rule while refactoring:

1. Route layout owns structure.
2. Route page owns composition.
3. Shared/global components stay small.
4. Feature logic stays in `features`.
5. Do not create a shell component when a route layout should own the layout.
6. Prune compatibility wrappers once mounted callers are moved.

## Migration Checklist

Use this table as the manual migration checklist while reorganizing components.

Status values:

- `keep` = keep, but move or rename if needed
- `consolidate` = merge into the target grouped location or owner
- `prune` = remove after caller proof confirms it is no longer needed
- `split` = one file currently mixes concerns and should be broken up

| Component or family | Target folder / owner | Owner route or layout | Status | Prune? | Notes |
| --- | --- | --- | --- | --- | --- |
| `src/lib/components/AppShell.svelte` | Route layouts/pages, not a shared shell file | `(product)` pages that still mount it directly | consolidate | yes, eventually | Old page-level shell. Keep shrinking until route layouts own composition directly. |
| `src/lib/components/Sidebar.svelte` | `components/navigation/` or route-local layout usage | old `AppShell` callers | consolidate | maybe | Keep only if still needed outside deck/dashboard layout ownership. |
| `src/lib/components/TopBar.svelte` | route-local headers or `components/navigation/` | old `AppShell` callers | consolidate | maybe | Route layouts/pages should own header composition more directly. |
| `src/lib/layouts/AppShell.svelte` | retired after caller migration | none | prune | yes, completed | The former shared route frame was removed after `(product)` took direct ownership. |
| `src/routes/(product)/decks/[deckId]/+layout.svelte` | keep as canonical deck layout owner | all deck routes | keep | no | Single owner of deck workspace geometry. |
| `src/lib/features/smart-deck/user/SmartDeckWorkspaceFrame.svelte` | deck layout geometry | `[deckId]/+layout.svelte` | prune | yes | Layout should define geometry. This file should disappear after callers are fully removed. |
| `src/lib/components/decks/GlobalDeckWorkspaceFrame.svelte` | `components/decks/` | `[deckId]/+layout.svelte` consumers | keep | no | Marker/contract component only; should not own geometry. |
| `src/lib/components/decks/GlobalDeckSidebar.svelte` | `components/decks/` | `[deckId]/+layout.svelte` | keep | no | Shared first-column deck shell content. |
| `src/lib/components/decks/GlobalDeckSlideNavigator.svelte` | `components/decks/` | `[deckId]/+layout.svelte` | keep | no | Shared second-column deck shell content. |
| `src/lib/components/decks/GlobalDeckVisualizer.svelte` | `components/decks/` | `[deckId]/+layout.svelte` | keep | no | Shared third-column visualizer. Must stay truthful. |
| `src/lib/components/decks/GlobalDeckChatPanel.svelte` | `components/decks/` | deck shell column four | keep | no | Shared Smart Deck chat region; other surfaces may need route-specific variants. |
| `src/lib/components/smart-deck/GeneratedSlideRenderer.svelte` | shared visualizer primitive | Smart Deck and visualizer surfaces | keep | no | Low-level shared renderer. |
| `src/lib/features/smart-deck/user/*` | keep in `features/smart-deck/` | Smart Deck route | keep | no | Feature-owned behavior should stay in `features`. |
| future `src/lib/features/smart-edit/*` | create and migrate route-specific Smart Edit blocks here | Smart Edit route | keep | no | Better target than leaving Smart Edit-only logic in generic `components/`. |
| future `src/lib/features/due-diligence/*` | create and migrate route-specific Due Diligence blocks here | Due Diligence route | keep | no | Same rule as Smart Edit. |
| `src/lib/components/dashboard/*` | keep grouped under dashboard | future `/dashboard/+layout.svelte` | keep | no | Dashboard layout should own arrangement. |
| `src/lib/components/FirstTimeDashboard.svelte` | `components/dashboard/` or dashboard page composition | `/dashboard` | consolidate | maybe | Useful block, but dashboard route should own when it mounts. |
| `src/lib/components/ReturningUserDashboard.svelte` | `components/dashboard/` or dashboard page composition | `/dashboard` | consolidate | maybe | Same as above. |
| future `src/routes/(product)/dashboard/+layout.svelte` | create | `/dashboard` | keep | no | Recommended canonical dashboard layout owner. |
| `src/lib/components/due-diligence/*` | keep grouped under due diligence | report and diligence routes | keep | no | Already grouped well; continue using grouped location. |
| `src/lib/components/deckService/brand/*` | keep grouped | brand-related pages/panels | keep | no | Good grouped location. |
| `src/lib/components/deckService/upload/*` | keep grouped | upload/deck library routes | keep | no | Good grouped location. |
| `src/lib/components/MarketingHeader.svelte` | `components/marketing/` | marketing routes | consolidate | yes, likely | Older top-level duplicate. Prefer grouped mounted owner. |
| `src/lib/components/MarketingFooter.svelte` | `components/marketing/` | marketing routes | consolidate | yes, likely | Older top-level duplicate. Prefer grouped mounted owner. |
| `src/lib/components/MarketingUtilitiesBar.svelte` | `components/marketing/` | marketing routes | consolidate | yes, likely | Older top-level duplicate. Prefer grouped mounted owner. |
| `src/lib/components/WelcomeActionCard.svelte` | `components/welcome-v2/` | welcome routes | consolidate | yes, likely | Older duplicate of grouped welcome ownership. |
| `src/lib/components/ProductFooter.svelte` | `components/global/` | product route frame | keep | no | Shared global product primitive. |
| `src/lib/components/RouteProgress.svelte` | `components/global/` | product route frame | keep | no | Shared global primitive. |
| `src/lib/components/WorkspaceAiProviderModal.svelte` | `components/global/` | multiple product routes | keep | no | Shared modal primitive. |
| `src/lib/components/navigation/ProductSurfaceNav.svelte` | `components/navigation/` | deck/product navigation | keep | no | Canonical navigation owner for deck workspace tabs. |

## Checklist Usage Rule

While refactoring, prefer this order:

1. Identify the route/layout owner.
2. Move composition there first.
3. Move only the reusable child components into grouped folders.
4. Leave feature logic in `features`.
5. Delete proxy shells only after imports and mounted callers are gone.

## Complete component index

### Top-level application and shared components

| File | Function |
| --- | --- |
| `AiAssistantCard.svelte` | Displays an AI assistant prompt, response, or assistant action card. |
| `AppLogo.svelte` | Renders the Deck AIStack logo with reusable size and presentation options. |
| `AppShell.svelte` | Provides page-level sidebar, top bar, optional utilities, surface navigation, and content framing. |
| `AuthSuccessLoader.svelte` | Shows authentication-success progress while the user is redirected into the product. |
| `ChangeReviewPanel.svelte` | Groups proposed slide changes for review and acceptance/rejection actions. |
| `DeckCard.svelte` | Presents a deck summary card for deck lists or dashboard surfaces. |
| `DeckLoaderOverlay.svelte` | Displays a blocking or in-context deck loading overlay. |
| `DiligencePanel.svelte` | Displays diligence findings associated with the selected slide. |
| `DiligenceStageSelector.svelte` | Lets the user select or view the current due-diligence stage. |
| `EmptyState.svelte` | Shared empty-content message with optional guidance or action. |
| `ExportOptionCard.svelte` | Presents one selectable deck export format or option. |
| `ExportPanel.svelte` | Coordinates deck export choices and export actions. |
| `FindingCard.svelte` | Renders one diligence finding, evidence item, or risk finding. |
| `FirstDeckWorkflow.svelte` | Guides a first-time user through creating or uploading the first deck. |
| `FirstTimeDashboard.svelte` | Dashboard composition for users without an established deck history. |
| `JsonLd.svelte` | Injects structured JSON-LD metadata into public pages. |
| `LockedFeatureCard.svelte` | Shows a feature that is unavailable because of plan, permission, or readiness state. |
| `MarketingFooter.svelte` | Top-level marketing footer from the older/shared location; the mounted marketing layout uses `marketing/MarketingFooter.svelte`. |
| `MarketingHeader.svelte` | Top-level marketing header from the older/shared location; the mounted marketing layout uses `marketing/MarketingHeader.svelte`. |
| `MarketingUtilitiesBar.svelte` | Top-level marketing utilities bar from the older/shared location; the mounted marketing layout uses the grouped marketing version. |
| `PageHeader.svelte` | Reusable page title, subtitle, status, and action header. |
| `ProductFooter.svelte` | Global product footer content and links. |
| `PublicAuthShell.svelte` | Frames sign-in, registration, and other public authentication content. |
| `PurposeSelector.svelte` | Lets a user choose the deck goal or use-case purpose. |
| `ReturningUserDashboard.svelte` | Dashboard composition for users with existing decks and activity. |
| `RiskBadge.svelte` | Displays a normalized risk level or severity label. |
| `RouteProgress.svelte` | Shows route navigation/loading progress. |
| `SEO.svelte` | Applies page SEO metadata such as title, description, and social tags. |
| `SampleTemplatesRow.svelte` | Displays a horizontal set of sample deck templates. |
| `Sidebar.svelte` | Main reusable product navigation sidebar used by the component-level `AppShell`. |
| `SlideBlockCard.svelte` | Displays one structured content block within a slide. |
| `SlideBlockList.svelte` | Lists the structured content blocks belonging to a slide. |
| `SlideList.svelte` | Lists deck slides and highlights the selected slide. |
| `SlideViewer.svelte` | Displays the selected slide's structured content in the deck overview. |
| `SmartDeckPropertiesDrawer.svelte` | Drawer for viewing or editing Smart Deck presentation properties. |
| `SmartEditCommandBox.svelte` | Text command input for requesting a Smart Edit operation. |
| `SmartEditPanel.svelte` | Coordinates Smart Edit input, suggestions, and change review. |
| `SmartEditSidebar.svelte` | Sidebar controls and context for the Smart Edit surface. |
| `SmartEditSuggestionCard.svelte` | Displays one proposed Smart Edit suggestion and its actions. |
| `StatusBadge.svelte` | Shared status-label component for normalized state values. |
| `SuggestionCard.svelte` | Displays one general deck or audience suggestion. |
| `ThemeToggle.svelte` | Switches the active visual theme. |
| `TopBar.svelte` | Page-level top navigation and context bar used by the component-level `AppShell`. |
| `UploadDeck.svelte` | Deck-upload workflow composition. |
| `UploadDropzone.svelte` | Drag-and-drop and file-picker input for deck uploads. |
| `UploadFirstDeckCard.svelte` | First-deck upload call-to-action card. |
| `UtilitiesBar.svelte` | Product utility controls such as theme and account/workspace utilities. |
| `WelcomeActionCard.svelte` | Top-level welcome action card from an older/shared location; the grouped welcome flow uses `welcome-v2/WelcomeActionCard.svelte`. |
| `WorkspaceAiProviderModal.svelte` | Modal for viewing or configuring the workspace AI provider. |

### Dashboard components (`dashboard/`)

| File | Function |
| --- | --- |
| `dashboard/CurrentDeckCard.svelte` | Highlights the user's current or most relevant deck. |
| `dashboard/DashboardRightRail.svelte` | Composes secondary dashboard information in the right rail. |
| `dashboard/DashboardWelcomeHero.svelte` | Dashboard welcome/overview hero. |
| `dashboard/LatestIterationsCard.svelte` | Summarizes recent deck iterations or generated versions. |
| `dashboard/RecentSlidesPreview.svelte` | Displays a preview group of recently used or generated slides. |
| `dashboard/SlidePreviewTile.svelte` | Renders one compact slide preview tile. |
| `dashboard/UploadedDecksPanel.svelte` | Dashboard panel listing uploaded decks. |
| `dashboard/WorkspaceStatsCard.svelte` | Shows workspace-level deck or usage statistics. |

### Instant Deck and processing components (`instant-deck/`)

| File | Function |
| --- | --- |
| `instant-deck/SmartDeckProcessingLoader.svelte` | Shows Smart Deck/Instant Deck processing progress and readiness state. |
| `instant-deck/designFallback.ts` | Builds the source-grounded design context used by canonical Smart Deck generation calls. |
| `instant-deck/processingTypes.ts` | Type definitions used by the processing loader and related state. |

### Brand workflow components (`deckService/brand/`)

| File | Function |
| --- | --- |
| `deckService/brand/BrandCardActions.svelte` | Action controls for a detected or selected brand card. |
| `deckService/brand/BrandExtractionStatus.svelte` | Displays brand-extraction progress, completion, or failure. |
| `deckService/brand/BrandLoader.svelte` | Loading presentation for brand discovery/extraction. |
| `deckService/brand/BrandPreviewCard.svelte` | Compact visual preview of extracted brand data. |
| `deckService/brand/BrandProfileCard.svelte` | Full brand profile summary and selection surface. |
| `deckService/brand/BrandSelectorEditor.svelte` | Lets the user select and edit extracted brand settings. |
| `deckService/brand/BrandSignalChips.svelte` | Displays extracted brand signals as compact chips. |
| `deckService/brand/BrandSourceLabels.svelte` | Labels the evidence or files from which brand data was derived. |
| `deckService/brand/BrandStatusBadge.svelte` | Normalized status badge for brand workflow state. |
| `deckService/brand/LogoDropzone.svelte` | Upload input specifically for brand logos. |
| `deckService/brand/PaletteChips.svelte` | Displays the selected or extracted color palette. |
| `deckService/brand/SmartBrandStepPanel.svelte` | Composes one stage of the guided Smart Brand workflow. |
| `deckService/brand/SmartColourSwatch.svelte` | Renders an interactive brand color swatch. |
| `deckService/brand/SmartColourSwatchPlaceholder.svelte` | Placeholder/skeleton for a brand color swatch. |
| `deckService/brand/TypographyPreview.svelte` | Previews extracted or selected brand typography. |

### Feedback component (`deckService/feedback/`)

| File | Function |
| --- | --- |
| `deckService/feedback/SaveConfirmationBanner.svelte` | Confirms that deck edits or workspace changes were persisted. |

### Upload workflow components (`deckService/upload/`)

| File | Function |
| --- | --- |
| `deckService/upload/DeckFileIcon.svelte` | File-type/status icon for an uploaded deck. |
| `deckService/upload/DeckStatusBadge.svelte` | Upload/processing status badge for a deck. |
| `deckService/upload/EmptyDecksState.svelte` | Empty state shown when no uploaded decks exist. |
| `deckService/upload/UploadDeckWidget.svelte` | Complete upload widget coordinating file selection and upload state. |
| `deckService/upload/UploadedDeckRow.svelte` | One uploaded-deck row with status and actions. |
| `deckService/upload/UploadedDecksList.svelte` | List composition for uploaded deck rows. |
| `deckService/upload/UploadedDecksSkeleton.svelte` | Loading skeleton for the uploaded decks list. |
| `deckService/upload/UploadedDocumentRow.svelte` | One non-deck supporting document row and its state. |
| `deckService/upload/upload-deck.types.ts` | Types for the upload widget and upload request/state. |
| `deckService/upload/uploaded-decks-list.types.ts` | Types for uploaded deck list rows, statuses, and actions. |

### Deck library/page components (`decks/`)

| File | Function |
| --- | --- |
| `decks/BackendErrorBanner.svelte` | Displays actionable backend/API errors on deck pages. |
| `decks/Breadcrumbs.svelte` | Deck-route breadcrumb navigation. |
| `decks/CompiledDeckPage.svelte` | Page composition for viewing a compiled deck artifact. |
| `decks/DeckLibraryPage.svelte` | Page composition for browsing and managing the deck library. |
| `decks/GlobalDeckChatPanel.svelte` | Smart Deck chat, whole-deck generation prompt, conversation, and generated-version review controls for column four. |
| `decks/GlobalDeckSidebar.svelte` | Shared first-column deck tool/navigation rail with button and URL-backed item support. |
| `decks/GlobalDeckSlideNavigator.svelte` | Shared searchable slide miniature navigator for column two. |
| `decks/GlobalDeckVisualizer.svelte` | Shared generated slide image/render-schema visualizer for column three. |
| `decks/GlobalDeckWorkspaceFrame.svelte` | Contract marker consumed by the deck-scoped route layout's four-column CSS. |
| `decks/LatestGeneratedDeckCard.svelte` | Highlights the latest generated deck/version and its actions. |

### Due Diligence components (`due-diligence/`)

| File | Function |
| --- | --- |
| `due-diligence/AudienceRecommendationsPanel.svelte` | Displays audience-specific recommendations produced by diligence analysis. |
| `due-diligence/AudienceSelector.svelte` | Selects the target diligence/investor audience. |
| `due-diligence/DdSlideNavigator.svelte` | Due Diligence slide thumbnail and selection navigator. |
| `due-diligence/DiligenceAnalysisPanel.svelte` | Presents structured diligence analysis, findings, evidence, and risks. |
| `due-diligence/DueDiligenceChatPanel.svelte` | Contextual AI chat for diligence questions and evidence. |
| `due-diligence/DueDiligenceSidebar.svelte` | Due Diligence tools/navigation sidebar. |
| `due-diligence/DueDiligenceWorkspaceFrame.svelte` | Layout frame arranging diligence navigation, slide visualization, analysis, and chat. |

### LLM artifact components (`llm/`)

| File | Function |
| --- | --- |
| `llm/ArtifactDetailsDrawer.svelte` | Drawer showing a selected persisted LLM artifact's details. |
| `llm/ArtifactHistoryPanel.svelte` | Lists the history and versions of persisted LLM artifacts. |
| `llm/artifactTypes.ts` | Shared types for artifact history and detail UI. |

### Marketing components (`marketing/`)

This grouped directory is the location imported by the mounted `(marketing)` layout.

| File | Function |
| --- | --- |
| `marketing/CTASection.svelte` | Marketing call-to-action section. |
| `marketing/ComparisonSection.svelte` | Compares the product with alternative workflows or approaches. |
| `marketing/ForVCsSection.svelte` | Marketing section tailored to venture-capital users. |
| `marketing/HeroSection.svelte` | Primary marketing hero section. |
| `marketing/HowItWorksSection.svelte` | Explains the product workflow in steps. |
| `marketing/MarketingCardGrid.svelte` | Reusable grid for marketing feature/use-case cards. |
| `marketing/MarketingFooter.svelte` | Footer mounted by the marketing route-group layout. |
| `marketing/MarketingHeader.svelte` | Header mounted by the marketing route-group layout. |
| `marketing/MarketingPageHero.svelte` | Reusable inner-page marketing hero. |
| `marketing/MarketingUtilitiesBar.svelte` | Marketing-route utility/navigation strip. |
| `marketing/ProductPreviewSection.svelte` | Shows product UI previews or feature demonstrations. |
| `marketing/ShowInterestForm.svelte` | Captures interest/contact submissions. |
| `marketing/UseCaseStrip.svelte` | Compact strip of supported use cases. |

### Product navigation (`navigation/`)

| File | Function |
| --- | --- |
| `navigation/ProductSurfaceNav.svelte` | Navigation between canonical product surfaces for the current deck/workspace. |

### Smart Deck visualization components (`smart-deck/`)

This directory contains rendering primitives still used by the customer product. The former operator workspace family has been removed.

| File | Function |
| --- | --- |
| `smart-deck/GeneratedSlideRenderer.svelte` | Shared renderer that converts persisted slide render schemas into the visible slide design. |
| `smart-deck/InfoBubble.svelte` | Small explanatory tooltip/popover for Smart Deck UI. |

### Smart Edit components (`smart-edit/`)

| File | Function |
| --- | --- |
| `smart-edit/BlockClassificationBadge.svelte` | Labels the classified type/role of a slide content block. |
| `smart-edit/ChangeReviewCard.svelte` | Displays one proposed Smart Edit change for accept/reject review. |

### Small UI primitive (`ui/`)

| File | Function |
| --- | --- |
| `ui/InfoIcon.svelte` | Reusable information icon with accessible labeling. |

### Developer visibility (`visibility/`)

| File | Function |
| --- | --- |
| `visibility/DeveloperVisibilityCard.svelte` | Generic card for developer-only state, diagnostics, or contract visibility. |

### Welcome components (`welcome/` and `welcome-v2/`)

| File | Function |
| --- | --- |
| `welcome/WelcomeWorkspaceEntry.svelte` | Composes the mounted welcome workspace entry and imports the v2 action card. |
| `welcome-v2/WelcomeActionCard.svelte` | Action card used by the grouped welcome workspace flow. |
| `welcome-v2/WelcomeHeroStage.svelte` | Hero/stage presentation for the newer welcome flow. |

## Duplicate and consolidation candidates that still require proof

Do not delete these based on the catalog alone:

- Top-level `MarketingHeader.svelte`, `MarketingFooter.svelte`, and `MarketingUtilitiesBar.svelte` versus the files under `marketing/`. The mounted marketing layout currently imports the grouped files, but remaining direct or external consumers must be checked before removal.
- Top-level `WelcomeActionCard.svelte` versus `welcome-v2/WelcomeActionCard.svelte`. The grouped welcome entry currently imports the v2 file, but remaining callers still need a full check.
- No private admin or super-admin component is permitted in this repository; the separation verifier enforces that boundary.

## Safe reorganization checklist

- [ ] Identify the canonical mounted route that ultimately reaches the component.
- [ ] Search imports in `src/routes`, `src/lib`, tests, scripts, and documentation.
- [ ] Distinguish direct route ownership from an internal shared primitive.
- [ ] Check product, marketing, auth, and compatibility route groups separately.
- [ ] Update aliases/imports and any tests in the same change as a file move.
- [ ] Preserve adapters and redirects until replacement parity is proven.
- [ ] Run Svelte checks/build after moves, then exercise the real mounted route in a browser.
- [ ] Update this catalog when component ownership or locations change.
