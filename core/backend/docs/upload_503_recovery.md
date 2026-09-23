# Upload 503 Recovery

## Goal

Reduce blank 503 upload failures before Smart Deck processing starts.

## Problem

Production showed:

```text
POST /api/products/deck-aistack-codes/decks/upload -> 503
```

The surrounding Railway logs showed authentication, deck list, status, and brand-profile requests succeeding. That means the application is alive, but the upload save path can still fail before the deck is persisted.

## Expected recovery behaviour

The upload path should:

1. Validate file type and size.
2. Save the uploaded source file to the configured storage backend when possible.
3. If remote promotion fails after local cache save, return a saved deck with a storage warning instead of a hard 503.
4. If storage configuration is missing or unusable before save, return a structured error with a clear failure category.
5. Return enough diagnostic information for the frontend to show a useful message and for Railway logs to correlate the failure.

## Diagnostics exposed

Upload failures should include:

```text
failureCategory
errorName
requestId
ticketId
storageBackend
storageWarning
```

## Manual test

1. Upload a PDF/PPTX.
2. Confirm a non-empty deck id is returned.
3. Confirm upload warning is visible if remote storage promotion fails.
4. Confirm a 503 response includes a failureCategory and requestId.
5. Confirm Create Smart Deck is not attempted unless upload succeeded.
