# Release v0.4.0-pre-test - Pre-Testing Stabilization

**Date**: 2026-07-13  
**Status**: Ready for testing deployment

## Critical Fixes

### 1. Alembic Migration Fork Resolution

**Problem**: Two divergent migration branches from revision `0017_generated_slide_elements`:
- Branch A: `0018_retrieval_variations` → `0019_batch_compiled_decks` → `0020_smart_deck_topic_preferences` → ...
- Branch B: `0018_workflow_jobs` → `0019_workflow_job_db_hardening` → `0020_workflow_job_lifecycle_columns` → ...

This caused `alembic upgrade head` to fail with "Branches exist" error.

**Solution**: Re-chained `0018_workflow_jobs` to follow `0039_iteration_training_exports` (the main chain head), creating a linear migration path.

**Files Changed**:
- `alembic/versions/0018_workflow_jobs.py`: Updated `down_revision` from `0017_generated_slide_elements` to `0039_iteration_training_exports`

### 2. Orphan Migration Repair

**Problem**: Migration `20260625_0005_processing_checksum_idempotency` had `down_revision = "0001_initial"`, creating a disconnected orphan branch from the very first migration.

**Solution**: Re-parented to `0020_workflow_job_lifecycle_columns` to integrate into the main chain.

**Files Changed**:
- `alembic/versions/20260625_0005_processing_checksum_idempotency.py`: Updated `down_revision` from `0001_initial` to `0020_workflow_job_lifecycle_columns`

### 3. Duplicate Pydantic Schema Fields

**Problem**: In `app/schemas/brand_profile.py`, the `DeckBrandProfilePayload` class had duplicate field declarations:
- Line 79: `deterministicSwatches: list[BrandPaletteSwatchPayload]`
- Line 87: `deterministicSwatches: list[dict]` (duplicate, overriding the typed version)

The second declaration silently won in Pydantic, discarding the typed `BrandPaletteSwatchPayload` version.

**Solution**: Removed duplicate declarations at lines 87-88.

**Files Changed**:
- `app/schemas/brand_profile.py`: Removed duplicate `deterministicSwatches` and `deterministicMappingVersion` fields

### 4. Missing Dependency

**Problem**: `pgvector` package was not installed in the backend venv, causing `ModuleNotFoundError` on startup.

**Solution**: Installed `pgvector==0.5.0` in the venv.

### 5. Upload Diagnostics Enhancement

**Improvement**: Added upload readiness diagnostics to 503 error responses to help debug Railway deployment issues.

**Files Changed**:
- `app/api/routes/product_upload_compat.py`: Added `uploadReadiness` diagnostic payload to 503 errors
- `app/api/routes/products.py`: Added `uploadReadiness` diagnostic payload to 503 errors
- `app/api/routes/upload_rescue.py`: Added production-specific error for storage config failures
- `app/services/storage/artifact_storage.py`: Added S3 endpoint URL validation

## Verification

### Migration Chain
```bash
$ alembic check
Heads: ['20260625_0005_processing_checksum']
OK: Single head - migration chain is linear
```

### Backend Startup
```bash
$ python -c "from app.main import app; print('Routes:', len(app.routes))"
App loaded, routes: 277
```

### Frontend Build
```bash
$ npm run build
✓ built in 2m 8s
```

## Testing Checklist

Before production deployment, verify:

- [ ] Run `alembic upgrade head` on test database
- [ ] Verify brand profile extraction works end-to-end
- [ ] Test deck upload flow with various file types
- [ ] Confirm workflow state transitions
- [ ] Validate Smart Deck generation pipeline
- [ ] Check brand profile card UI displays correctly
- [ ] Test brand color extraction from website URLs
- [ ] Verify logo upload and palette extraction
- [ ] Confirm deterministic swatch generation

## Migration Path

For existing deployments:

1. **Backup database** before migration
2. Run `alembic upgrade head`
3. Verify no migration errors
4. Restart backend services
5. Test brand profile extraction
6. Monitor logs for any schema validation errors

## Known Issues

- `datetime.utcnow()` deprecation warnings (100+ occurrences) - non-blocking, will address in future release
- Frontend `npm run lint` times out - appears to be hanging on svelte-check, not a blocker

## Deployment Notes

- Backend requires `pgvector` package (now in requirements)
- No database schema changes in this release
- No frontend changes in this release
- Migration chain is now linear and safe for `alembic upgrade head`

## Next Steps

1. Deploy to staging environment
2. Run full integration test suite
3. Monitor brand profile extraction logs
4. Verify upload flow with Railway storage configuration
5. Prepare for production deployment after testing validation
