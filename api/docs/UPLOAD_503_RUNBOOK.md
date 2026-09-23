# Upload 503 Runbook

## Symptom

Frontend upload fails with:

```text
/api/products/deck-aistack-codes/decks/upload -> 503
```

If the JSON response body contains:

```json
{
  "failureCategory": "deck_upload_save"
}
```

then the request reached the backend product upload route, but the backend could not persist the uploaded source deck through the save pipeline.

## First checks

Use the response `requestId` and `ticketId` to inspect Railway backend logs and failure tickets.

Then run the backend checklist:

```bash
DATABASE_URL=sqlite:// PYTHONPATH=. python scripts/verify_upload_readiness_contract.py
```

For a live production service, also check the protected admin readiness endpoint:

```text
GET /api/admin/deployment-readiness
```

For backend-only upload pipeline verification, trigger:

```text
POST /api/admin/railway-upload-smoke-test?cleanup=true
```

The endpoint creates a synthetic deck upload through the real persistence path and
returns acceptance flags. A successful response shape is:

```json
{
  "ok": true,
  "status": "passed",
  "ranInsideBackend": true,
  "acceptance": {
    "uploadReturnsSuccess": true,
    "responseIncludesDeckId": true,
    "workspaceSummaryContainsDeck": true,
    "statusIsUploaded": true,
    "nextActionIsCreateSmartDeck": true,
    "accepted": true
  }
}
```

Set `cleanup=true` to soft-delete the smoke deck after the run.

The response also includes `deckId` and `workspaceSummary` so you can quickly inspect visibility.

The response includes:

```text
checks.uploadPersistence
checks.storage
checks.database
checks.requiredEnv
checks.workerQueue
```

## Required production variables

The upload path depends on these variable groups.

| Area | Accepted env names |
|---|---|
| Database | `DATABASE_URL`, `DATABASE_PRIVATE_URL`, `DATABASE_PUBLIC_URL`, `POSTGRES_URL`, `POSTGRES_PRIVATE_URL`, `POSTGRES_PUBLIC_URL`, `RAILWAY_DATABASE_URL` |
| Auth secret | `AUTH_SECRET_KEY` |
| Auth key id | `AUTH_SECRET_KEY_ID` |
| Workspace AI encryption key | `WORKSPACE_AI_FERNET_KEY` |
| Workspace AI encryption key version | `WORKSPACE_AI_FERNET_KEY_VERSION` |
| CORS/frontend origin | `ALLOWED_ORIGINS`, `CORS_ORIGIN`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL` |
| Upload scan command | `UPLOAD_SECURITY_SCAN_COMMAND` |
| Storage backend | `DECK_AISTACK_STORAGE_PROVIDER`, `UPLOAD_STORAGE_BACKEND` |
| S3 bucket | `S3_BUCKET_NAME`, `AWS_S3_BUCKET_NAME`, `UPLOAD_STORAGE_S3_BUCKET`, `RAILWAY_BUCKET_NAME` |
| S3 endpoint | `AWS_ENDPOINT_URL`, `UPLOAD_STORAGE_S3_ENDPOINT`, `RAILWAY_BUCKET_ENDPOINT` |
| S3 region | `AWS_DEFAULT_REGION`, `UPLOAD_STORAGE_S3_REGION`, `RAILWAY_BUCKET_REGION` |
| S3 access key | `AWS_ACCESS_KEY_ID`, `UPLOAD_STORAGE_S3_ACCESS_KEY`, `RAILWAY_BUCKET_ACCESS_KEY` |
| S3 secret key | `AWS_SECRET_ACCESS_KEY`, `UPLOAD_STORAGE_S3_SECRET_KEY`, `RAILWAY_BUCKET_SECRET_KEY` |

## Railway bucket connectivity

For Railway S3-compatible bucket storage, production should normally use:

```text
UPLOAD_STORAGE_BACKEND=s3
```

and the Railway bucket connector should inject the AWS-style variables.

The storage health check performs a real safe test of:

1. write object
2. promote object
3. head object
4. get object
5. signed GET URL
6. signed PUT URL
7. delete object

If this fails, the upload route can still accept the file stream but will fail when the source file is saved/promoted.

## Acceptance criteria for the upload fix

A successful production upload should:

1. return HTTP `200` or `201` from `/api/products/deck-aistack-codes/decks/upload`;
2. include `deck_id` or `deckId`;
3. show the deck in `/api/products/deck-aistack-codes/workspace-summary`;
4. set canonical deck state/status to `uploaded`;
5. include `next_action: create_smart_deck`;
6. include a Smart Deck start URL for `/workflows/source-extraction`.

## What not to do

Do not fix this by adding another frontend proxy layer.

Do not fall back to local storage in production.

Do not bypass upload scanning in production.

Do not hide `deck_upload_save` by navigating to Smart Deck before the file has been persisted.
