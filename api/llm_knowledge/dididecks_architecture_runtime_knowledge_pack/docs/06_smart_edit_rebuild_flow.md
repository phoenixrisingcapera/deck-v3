# Smart Edit and Rebuild Flow

Smart Edit is the place where a user changes reusable business values.

Rebuild is the place where affected slides and blocks are safely updated.

## Smart Edit flow

1. Load editable fields.
2. User selects a field.
3. Backend returns current value and usages.
4. User enters new value.
5. Frontend requests preview.
6. Backend returns affected slides/blocks.
7. User applies or rejects.

## Rebuild flow

1. Create change request.
2. Create rebuild job.
3. Update field and affected blocks.
4. Run guardrails if AI/layout change is involved.
5. Create version.
6. Write audit log.
7. Refresh exports when needed.

## Expected endpoints

```txt
GET  /api/products/dididecks/decks/{deckId}/editable-fields
GET  /api/products/dididecks/decks/{deckId}/fields/{fieldKey}
POST /api/products/dididecks/decks/{deckId}/changes/preview
POST /api/products/dididecks/decks/{deckId}/changes/apply
GET  /api/products/dididecks/rebuild-jobs/{jobId}
```
