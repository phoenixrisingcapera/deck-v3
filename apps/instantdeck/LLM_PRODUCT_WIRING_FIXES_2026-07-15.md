# LLM Product Wiring Fixes 2026-07-15

This change set documents the mounted product-surface fixes applied to the
frontend for Smart Deck and Smart Edit.

## Scope

- preserve backend `llmArtifacts` on the canonical deck graph
- let mounted Smart Edit hydrate from persisted workflow runs
- derive Smart Edit audience from deck context instead of hardcoding one value
- preserve real Smart Edit suggestion status when replaying saved runs

## Files

- `src/lib/contracts/types.ts`
- `src/lib/server/services/deckService.ts`
- `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte`

## Notes

- Smart Deck artifact history now comes from persisted backend product data
  instead of being dropped during graph normalization.
- Smart Edit now reloads the latest saved run for the selected block or slide
  when that run already exists in the deck graph.
- Audience normalization remains compatibility-oriented because deck records
  still mix human labels and canonical audience ids.

## Verification

- `npm run check` was started twice and timed out in this environment before a
  full result returned.
- The change was verified by code-path tracing against the mounted route and the
  existing backend run endpoints.

## 2026-07-27 findings 1–7 frontend slice

- Canonical Due Diligence no longer references the preserved disabled 410 proxy routes.
- Smart Edit uses the authenticated slide-redesign run contract for ordinary selected-slide work and validates deck/slide/version/element identity before Save.
- Due Diligence sends a client exchange key, normalizes camel/snake-case workspace history, and reloads persisted history when the backend supplies it.
- Full-deck generation sends typed `provenance` rather than embedding provenance JSON in prompt text and renders the returned candidate deck.
- Market Research opens saved-first, renders citations and explicit no-source state, and only links credential-free absolute HTTP(S) URLs.
- The existing `POST .../smart-edit/summary` remains the only Smart Edit summary owner.

### Backend contract required

The reconciled contract uses backend schema names exactly: slide redesign sends
`taskContext: "standard" | "background_vision"` and reads
`visionExecution: { status, executed }`; generation provenance uses
`mode: "due_diligence_full_deck"`, `audience`, optional `audienceArtifactId`, and
`diligenceArtifactIds`; Due Diligence reloads `conversation.messages` keyed by
`messageId`; Market Research sources expose `publishedDate` and sections expose
`citationIds`. Backend extensions must deploy with this frontend for runtime
completion.

## 2026-07-31 Instant Deck LLM production diagnosis

### Verdict

Instant Deck has a real OpenAI generation path, but it was not end-to-end proven
at the start of this diagnosis. The first authenticated production upload reached
`/processing?instant=1`, then workflow-state returned HTTP 500 before an Instant
worker processed the run. Upload success, processing animation, source
miniatures, and an unsaved `Version 1` label are not LLM-generation proof.

Three release blockers were found and fixed locally:

- the upload proxy now forwards `preferred_workspace=instant_deck` to FastAPI;
- `/instant-deck` now gates on explicit `canOpenInstantDeck` readiness;
- timed-out jobs keep status `timed_out` but expose public phase `failed_final`,
  preventing workflow-state response validation from returning HTTP 500.

### Canonical runtime trace

```text
/decks/new (Instant default)
  -> upload proxy preserves preferred_workspace
  -> FastAPI persists DeckFile.metadata_json.preferredWorkspace
  -> source pipeline and source DB publication
  -> dedicated instant_deck_generation worker
  -> dedicated Instant prompt package -> OpenAI Responses API
  -> schema_validation -> preview_render -> db_publisher
  -> workflow-state canOpenInstantDeck=true
  -> /instant-deck renders generated-only slides and saved Version 1
```

The concrete provider call is owned by backend `openai_provider.py`. The
generation service compiles the dedicated Instant prompt recipe, validates each
render schema, persists generated slides/design versions, and allocates the first
complete generated artifact as backend-owned Version 1.

### Railway worker diagnosis

Secret values were not read into this document. Effective key presence and
equivalence were checked without exposing values.

| Service | Assigned work | Configuration result |
| --- | --- | --- |
| `deck-backend-api` | Upload and workflow-state | Database, storage, encryption, OpenAI/provider/model present |
| `worker-source-pipeline` | Ingestion, extraction, miniatures, brand, context | Database/storage present; source-stage defaults active |
| `worker-instant-deck-generation` | Whole-deck LLM generation | Database, storage, encryption, OpenAI key/provider/model present |
| `worker-schema-validation` | Render-schema validation | Database/storage present; provider key not required |
| `worker-preview-render` | Preview/renderability publication | Database/storage present; provider key not required |
| `worker-db-publisher` | Publish `preview_ready` | Database/storage present; OpenAI not used |

All services were healthy and aligned to backend `f98c8c1` during the first
test. No audited worker emitted a processed-job event for that attempt because
the frontend proxy dropped the Instant preference and workflow-state then failed.
The source worker has broader ownership than the ideal dedicated topology, but
the Instant generation, schema, preview, and publisher services have the runtime
configuration required for their assigned stages.

### Acceptance checklist before final deploy/test

| Requirement | Status |
| --- | --- |
| Instant Deck is the upload default | Complete |
| Upload intent reaches backend | Fixed locally; deploy required |
| Source publication queues Instant generation | Complete when intent is persisted |
| Dedicated Instant prompt and OpenAI `gpt-5` are selected | Complete by code/health trace |
| Generation-worker variables are present | Complete by non-secret Railway audit |
| Processing waits through preview publication | Complete locally; deploy required |
| Instant route excludes source-only slides | Complete by mapper/contract trace |
| Complete output persists as Version 1 | Focused tests pass; production proof pending |
| Fresh upload visibly renders a redesigned deck | Not proven yet |

### Known limitations and residual risks

- Whole-deck generation currently accepts at most 20 selected source slides. The
  proof deck must contain 20 slides or fewer.
- Version 1 is allocated after complete per-slide generation but before separate
  schema, preview, and publisher jobs finish. UI readiness must therefore remain
  `canOpenInstantDeck`.
- Preview publication currently records a renderability manifest; the frontend
  renders generated schema rather than requiring a preview image URL.
- Backend and frontend idempotency keys differ. The normal path avoids a second
  request by waiting for backend readiness and reusing the complete persisted
  Instant version; this still requires online observation.
- The July 27 typed `provenance` statement is stale for mounted Instant Deck.
  Instant generation uses its dedicated mode/context; diligence provenance is a
  separate Due Diligence full-deck concern.

### Final production evidence

Pending deployment and one fresh deck of 20 slides or fewer. Completion requires:

1. persisted `preferredWorkspace=instant_deck`;
2. source, generation, schema, preview, and publisher jobs complete;
3. generated slides cover every source slide;
4. workflow-state reports `canOpenInstantDeck=true`;
5. `/instant-deck` visibly renders generated design schema, not source slides;
6. workspace and `/versions` identify the persisted result as Version 1.
