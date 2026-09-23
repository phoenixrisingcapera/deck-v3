# Smart Deck Retry Recovery

## Goal

Keep retry aligned with the durable workflow queue instead of rewinding deck
state independently.

## Current behavior

The retry surface now reuses the same durable workflow enqueue path as the
canonical source-processing command.

Updated:

```text
app/api/routes/deck_retry_rescue.py
app/api/routes/products.py
```

The retry routes now:

- call `queue_source_extraction(...)`
- return workflow-backed visibility with the response
- return clearer 409 errors for validation problems such as missing source file
- avoid pretending success by only mutating deck state

## Response contract

Successful retry response includes:

```text
ok
deckId
processing
visibility
nextAction
```

Failed retry response includes:

```text
message
deckId
visibility
retryable
```

## Frontend dependency

The frontend should treat retry as a compatibility alias. The primary source of
truth remains:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`

## Verification

Run:

```bash
python -m compileall -q app scripts
```
