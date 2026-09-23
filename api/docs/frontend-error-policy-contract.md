# Frontend Error Policy Backend Contract

Date: 2026-06-24

## Goal

Support the frontend error policy by making backend/proxy failures explicit and stable enough for the UI to distinguish auth, validation, API-contract, and backend-service errors.

The paired frontend PR is expected to stop hiding backend/proxy errors as empty lists or generic upload failures.

## Contract

Backend product routes should return JSON error responses whenever possible.

Preferred envelope:

```json
{
  "message": "Human-readable error summary.",
  "detail": {
    "message": "Optional detailed message.",
    "failureCategory": "deck_upload_save",
    "requestId": "...",
    "ticketId": "..."
  }
}
```

The frontend reads, in order:

```text
message
detail.message
detail.error
detail.reason
detail as string
error
```

## Status classes

| Status | Meaning | Frontend treatment |
|---:|---|---|
| 400 | Bad input or validation failure | Request needs attention |
| 401 | Missing/expired/invalid session | Sign-in required |
| 403 | Authenticated but not allowed | Access denied |
| 404 | Resource missing | Resource not found |
| 409 | State or contract conflict | API contract mismatch |
| 412 | Precondition/contract failure | API contract mismatch |
| 415 | Unsupported media/contract failure | API contract mismatch |
| 422 | Validation failure | Request needs attention |
| 500+ | Server/storage/database/worker failure | Backend service error |

## Product routes covered first

```text
GET  /api/products/deck-aistack-codes/decks
POST /api/products/deck-aistack-codes/decks/upload
POST /api/products/deck-aistack-codes/decks/{deck_id}/retry
GET  /api/products/deck-aistack-codes/decks/{deck_id}/status
GET  /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
GET  /api/workflow-jobs/{job_id}
GET  /api/products/deck-aistack-codes/decks/{deck_id}/processing
POST /api/products/deck-aistack-codes/decks/{deck_id}/brand/extract
GET  /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile
PATCH /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile
```

## Current backend notes

The upload route already returns structured details for save failures, including:

```json
{
  "message": "Deck upload could not be saved. Check storage, database, and backend logs.",
  "failureCategory": "deck_upload_save",
  "requestId": "...",
  "ticketId": "..."
}
```

This is compatible with the frontend policy.

`workflow-state` is now the canonical workflow readiness/error surface. The
older `/processing` route remains as a compatibility projection and should not
be treated as the primary backend truth.

## Do not do this

Do not make backend routes return successful empty objects for auth/session/storage/database failures.

Wrong:

```json
{
  "decks": []
}
```

for a `401`, `403`, or `503` condition.

Correct:

```json
{
  "message": "Invalid access token"
}
```

with the correct HTTP status.

## Tags

```text
backend
error-policy
api-contract
auth-session
upload
brand-profile
production-readiness
```

## Follow-up

- Add backend tests that assert JSON error envelopes for deck upload, deck list, status, and brand-profile failures.
- Ensure every product route includes a request id in either response headers or JSON detail.
- Ensure failure tickets preserve the same request id shown to users.
