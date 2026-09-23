# Canonical Source Of Truth Audit 2026-07-07

## Build-Phase Rules

This repo is in an active build/integration phase.

During this phase, use these rules:

1. Do not delete code only because it looks old.
2. Delete code only when there is a concrete integration reason and the replacement is already active.
3. Prefer absorbing overlapping features into one canonical path instead of leaving parallel implementations.
4. New features must declare which existing canonical they extend, replace, or remain compatible with.
5. User experience and admin experience must remain coherent with the same backend source-of-truth objects.

## Current Canonicals

### 1. Processing canonical

Canonical object:
- `workflow-state`

Canonical purpose:
- processing lifecycle truth for upload -> processing -> ready

Compatibility surfaces:
- `/processing`
- older readiness projections

Status:
- stable canonical

### 2. Deck understanding canonical

Canonical object:
- `canonical_deck_intelligence`

Canonical source builder:
- `app/services/llm/canonical_deck_intelligence_service.py`

Canonical upstream inputs:
- `smart_deck_deck_map_analysis`
- `audience_conversion_generated` or `audience_conversion_plan`
- `smart_deck_market_research`

Canonical purpose:
- shared deck intelligence for Smart Deck, Smart Edit, and assistant workflows

Status:
- active canonical, still being integrated into all downstream consumers

### 3. Due Diligence canonical

Canonical backend identity:
- `audience_conversion`

Routes:
- `POST /api/decks/{deck_id}/audience-conversion/analyze`
- `POST /api/decks/{deck_id}/audience-conversion/plan`
- `POST /api/decks/{deck_id}/audience-conversion/generate`
- `GET /api/decks/{deck_id}/audience-conversion/latest`

User-facing label:
- still allowed to appear as Due Diligence / Smart Audit in the frontend

Status:
- active canonical backend identity
- frontend compatibility adapter still exists on the product proxy surface

### 4. Smart Edit canonical

Canonical backend workflow:
- slide-level classify + patch + run lookup routes

Routes:
- `POST /api/decks/{deck_id}/slides/{slide_id}/smart-edit/classify`
- `POST /api/decks/{deck_id}/slides/{slide_id}/smart-edit/patch`
- `GET /api/decks/{deck_id}/slides/{slide_id}/smart-edit/runs/{run_id}`

Canonical purpose:
- reviewable patch generation only
- no silent apply

Status:
- active canonical

Legacy compatibility:
- older `/api/decks/{deck_id}/smart-edit` flow still exists and should be treated as compatibility, not future source of truth

### 5. Smart Deck generation canonical

Canonical backend flow:
- Smart Deck generation workflow routes and generation service

Canonical purpose:
- whole-deck / selected-slide generation using canonical deck intelligence and audience conversion context

Status:
- active canonical

### 6. Market Research canonical

Canonical backend flow:
- `POST /products/deck-aistack-codes/decks/{deck_id}/market-research`

Canonical purpose:
- structured market hypothesis / challenge output

Status:
- active canonical
- still deck-based interpretation, not yet source-grounded external market research

## Stale Or Transitional Canonicals

These should be treated as compatibility or transitional layers, not primary truth:

### A. Due Diligence as a report-first backend identity

Files:
- `app/services/llm/due_diligence_service.py`
- legacy diligence workspace shaping in read-model surfaces

Status:
- transitional

Rationale:
- the real product intent is audience conversion, not static reporting

Action:
- keep only as compatibility until all consumers move fully to audience conversion

### B. Product proxy due-diligence mapping layer

File:
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/due-diligence/+server.ts`

Status:
- compatibility adapter

Rationale:
- frontend label remains “Due Diligence” while backend canonical is now audience conversion

Action:
- preserve while product naming and UI catch up

### C. Legacy Smart Edit suggestion route family

Routes:
- `/api/decks/{deck_id}/smart-edit`
- `/api/decks/{deck_id}/smart-edit/suggestions/{suggestion_id}`

Status:
- compatibility

Action:
- do not extend this as the future patch workflow

## Harmonization Rules

### User experience

User-facing pages should read from these canonicals:

- Smart Deck page -> canonical deck intelligence + Smart Deck workflow
- Smart Edit page -> Smart Edit patch workflow + canonical deck intelligence
- Due Diligence page -> audience conversion workflow, even if label stays “Due Diligence”
- Deck Map -> canonical understanding producer
- Market Research -> canonical market hypothesis producer

### Admin experience

Admin pages should not invent separate workflow truth.

Admin should inspect the same persisted artifacts and workflow outputs as the product pages:

- canonical deck intelligence
- deck map artifacts
- audience conversion artifacts
- market research artifacts
- smart edit workflow artifacts

## Current Gaps To Keep Watching

1. Some compatibility mapping still exists between audience conversion output and the Due Diligence UI model.
2. Market Research is still deck-constrained, not externally grounded.
3. Legacy Smart Edit route family still exists beside the canonical patch workflow.
4. Canonical deck intelligence is now present, but every downstream consumer must continue converging on it.

## Build-Phase Decision Policy

When touching canonical flows in this phase:

1. Identify the current canonical object first.
2. If a new feature overlaps, integrate it into the canonical path.
3. If an old path is still serving compatibility, document it before removal.
4. Do not leave multiple canonicals alive for the same responsibility.
5. If a route or object becomes compatibility-only, mark it explicitly in docs and code comments where useful.

## Recommended Next Cleanup

1. Add explicit canonical deck intelligence inspection surface in admin.
2. Reduce due-diligence compatibility mapping once UI is fully audience-conversion-native.
3. Mark legacy Smart Edit suggestion flow as compatibility-only in docs and route comments.
