# PR 4 — Upload + processing state machine

## Canonical deck states

Backend deck lifecycle status is restricted to this vocabulary:

- pending
- uploaded
- processing
- ready
- failed

Worker or job-specific labels such as `queued`, `running`, `completed`,
`failed_retryable`, `failed_final`, `blocked`, and `timed_out` remain valid on
durable `workflow_jobs`. They must not replace the canonical deck lifecycle
state fields.

## State ownership

app/services/deck_state_machine_service.py owns deck state transitions.

It provides:

- DeckState
- canonical_deck_state
- processing_run_status_to_deck_state
- assert_valid_deck_state_transition
- transition_deck_state
- response decorators for deck-list payloads

## Allowed transitions

| From | To |
|---|---|
| pending | uploaded, processing, failed |
| uploaded | processing, ready, failed |
| processing | uploaded, ready, failed |
| ready | uploaded, processing, failed |
| failed | uploaded, processing |

Self-transitions are allowed so existing production records can be normalized safely. Invalid transitions raise InvalidDeckStateTransition.

## Audit persistence

Every status-changing transition writes a DeckSaveConfirmation event with event_type deck_state_transition and entity_type deck.

The event metadata stores the previous raw state, previous canonical state, target state, reason, and caller metadata. This gives production a durable transition audit without introducing a migration in this PR.

## Frontend contract

Frontend consumers should read deck lifecycle from backend fields only:

- status
- state
- deckStatus

These fields must all use the same canonical state.

Processing visibility uses this distinction:

- processing.status = workflow job status
- processing.runStatus = workflow job status
- processing.state = canonical deck state

The canonical product workflow endpoint is:

GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state

The compatibility processing projection is:

GET /api/products/deck-aistack-codes/decks/{deck_id}/processing

`workflow-state` is the source of truth. `/processing` is a compatibility
projection that returns canonical top-level status/state/deckStatus plus
workflow-job detail.

## Legacy read mapping

Existing persisted values are mapped on read:

| Legacy | Canonical |
|---|---|
| saved, source_saved | uploaded |
| queued, running, parsing, structuring, extracting_blocks, classifying_blocks, analysing, adapting | processing |
| completed, reviewed | ready |
| dead_letter, error | failed |

All new deck writes should use transition_deck_state.

## Files touched

- app/services/deck_state_machine_service.py
- app/services/deck_processing_queue_service.py
- app/services/deck_processing_visibility_service.py
- app/services/workspace_summary_service.py
- app/services/upload_service.py
- app/services/deck_service.py
- app/api/routes/products.py
- app/api/routes/product_upload_compat.py
- app/schemas/common.py
- app/schemas/deck.py
- app/schemas/workspace_summary.py
- tests/test_deck_state_machine_service.py

## Frontend wiring note

The frontend should stop deriving UI status from local upload labels such as saved, queued, or completed.

Use upload response state/status/deckStatus, deck list status, `workflow-state`
top-level state/status, and the Smart Deck readiness gate `nextAction ==
open_smart_deck` with top-level ready state.

Workflow-job stage labels remain useful for progress copy, but not for deck
lifecycle state.
