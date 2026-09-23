# Smart Deck Workspace Completion Ledger

Status: implementation in progress

## Completed

- Enabled and persisted the Smart Deck audience selector during preview review.
- Stretched the generated preview to the available workspace width while preserving 16:9 geometry.
- Added presentation typography requirements to Smart Deck generation, critique, repair, and runtime validation.
- Identified canonical workspace AI-key, company-properties, slide-creation, artifact, and vector ownership paths.
- Wired Data to the existing deck/company properties contract.
- Wired AI Tools to Ask AI, Deck Map, Market Research, Smart Edit, Due Diligence, and encrypted Qwen configuration.
- Wired Smart Deck Settings and `/settings` to the reusable provider key/model modal with non-destructive close behavior.
- Enabled filmstrip slide creation through the authenticated slide proxy, persisted workspace refresh, selection, and immediate Smart Deck generation from the same modal brief.
- Added architecture-aligned create-slide presets that map to existing persisted slide roles: Problem, Solution, Traction, Team, and Appendix/Board.
- Added safe revoke/replace controls for the encrypted workspace Qwen key from mounted settings surfaces.
- Enriched the Data panel with canonical brand-profile signals, including saved logo and palette source visibility.
- Added a focused Smart Deck route smoke contract for rail panels, provider modal actions, and create-slide generation flow.

## Architecture Decisions

- Reuse encrypted workspace Qwen credentials; do not add deck-local or embedding-key tables.
- Reuse `DeckBrandProfile` and synchronized `CompanyProfile` through the existing properties endpoint.
- Treat team and board as a saved summary until a reviewed structured-people contract exists.
- Never scrape LinkedIn. User-supplied profile information is manual reference data only.
- Create a real persisted `DeckSlide`, then use the existing Smart Deck generation workflow to design it.
- Keep design rationale in render-schema analytics and `DeckLlmArtifact`; do not create a duplicate rationale table.
- Defer rationale vector-job schema changes until the concurrent workflow migration is merged; the current generated-slide artifact remains durable Core truth.

## Active Work

- Verify frontend proxy, authenticated backend contract, persistence, generation, and reload behavior.

## Follow-Up Todos

- Add structured team/board member arrays only after a canonical backend schema and migration are approved.
- Add manual LinkedIn URL storage with strict validation and no network fetch.
- Add non-blocking generated-rationale vector sync after the active workflow job-type migration lands.
- Expose already-persisted rationale fields explicitly in `GeneratedSlideResponse`.
- Add a safe credential revoke action to the frontend provider proxy.

## Release Gate

- Focused frontend/backend contracts pass.
- Svelte check and production build pass.
- Authenticated Railway smoke proves provider save, company data save, slide creation, generation, reload, and readable preview.
- Scoped commits are pushed to both canonical `main` branches only after verification.

## Verification Evidence

- Smart Deck preview sizing contract: passed all checks.
- Smart Deck tool wiring contract: passed all checks.
- Smart Deck route smoke contract: passed all checks.
- Historical verification for this 2026-07-17 pass: `svelte-check` reported 0 errors and 0 warnings.
- Frontend production adapter build: passed.
- Backend provider, render-schema, quality, and typography tests: 26 passed.
- Local production-route test collection is blocked because the existing backend
  `.venv` lacks `alembic.config`; Railway's complete image is the required route
  and deployment verification environment.

## Additional Cleanup Completed

- Historical note: this pass originally kept route-local compatibility UI.
  The unreachable `/decks/[deckId]` page was later removed after its server
  loader became redirect-only; compatibility behavior now lives solely in
  `src/routes/(product)/decks/[deckId]/+page.server.ts`.
- Fixed pre-existing provider-summary contract drift in
  `src/routes/(product)/dashboard/+page.server.ts` and
  `src/routes/(product)/decks/+page.server.ts` so the returned summary matches the
  current shared `WorkspaceAiProviderSummary` shape.
- Historical result for this 2026-07-17 pass: full frontend `svelte-check` returned 0 errors and 0 warnings.

## 2026-07-27 Sidebar and Navigation Finalization

- The canonical Smart Deck right inspector is permanently mounted at desktop,
  tablet, and mobile breakpoints and defaults to Ask AI.
- Inspector hide/show, AI minimize, persisted-close behavior, and the canonical
  workspace's floating reopen control are removed as obsolete. Design and Map
  remain available as inspector tabs.
- Legacy persisted `research` tool state normalizes to Slides; selecting the
  Research rail item opens the consolidated Market Research area in canonical
  Due Diligence instead of leaving Smart Deck without a visible panel.
- Diligence is temporarily hidden from product navigation and direct Smart Edit
  links. Its route, analysis ownership, compatibility behavior, and internal
  code remain preserved. Due Diligence remains user-facing.
- Due Diligence keeps overview, claims, domains, and risks on its own route; it
  no longer exposes hidden Diligence through a normal client redirect.
- The permanent inspector uses a reserved desktop/tablet column and a separate,
  scroll-reachable mobile row below the canvas. It does not cover canvas,
  filmstrip, or keyboard-focusable workspace controls.
- At tablet and mobile widths, the desktop slide navigator is hidden and the
  canonical filmstrip becomes the docked slide-selection row, including for the
  default Slides tool. Deck Map and other tool panes replace only the center
  canvas region and retain a visible Back to Slides action; they never cover the
  permanent inspector or filmstrip.
