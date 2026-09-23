# Deck Upload Flow - Complete Architecture

## Overview
This document explains the complete deck upload flow and identifies the issues causing uploads to fail.

## Architecture

### 1. Frontend Flow
```
Browser (Svelte component)
  ↓
deckServiceClient.ts (uploadFirstDeck)
  ↓
SvelteKit API Route: /api/products/deck-aistack-codes/decks/upload/+server.ts
  ↓
Backend API: POST /api/products/deck-aistack-codes/decks/upload
```

### 2. Backend Routes
There are **TWO** routes that handle deck uploads:

#### Route A: `upload_rescue.py` (Primary - registered first)
- **Path**: `/api/products/deck-aistack-codes/decks/upload`
- **File**: `app/api/routes/upload_rescue.py`
- **Handler**: `upload_deck_rescue()`
- **Purpose**: Rescue/fallback route with full diagnostics

#### Route B: `products.py` (Secondary)
- **Path**: `/api/decks/upload` (relative to product prefix)
- **File**: `app/api/routes/products.py`
- **Handler**: `first_deck_upload()`
- **Purpose**: Main product upload route

**Route Registration Order** (from `app/api/routes/product/__init__.py`):
```python
(upload_rescue_router, "/api"),      # Line 35 - registered FIRST
(products_router, "/api"),           # Line 42 - registered LATER
```

Since `upload_rescue_router` is registered first, it catches the request before `products_router`.

### 3. Upload Flow (upload_rescue.py)

```python
upload_deck_rescue()
  ↓
1. Check upload readiness (Railway vars, storage config)
  ↓
2. Validate file type and size
  ↓
3. Stream upload to temp file
  ↓
4. _ensure_app_db_user(db, current_user)  ← ISSUE HERE
   - Check if user exists by ID
   - Check if user exists by email
   - Create user if not exists
  ↓
5. _workspace_for_user(db, app_user, workspace_id)
   - Get or create workspace
  ↓
6. Move file to storage (local or S3)
  ↓
7. Create Deck record
  ↓
8. Create DeckFile record
  ↓
9. Create DeckInputSource record
  ↓
10. Queue source extraction (background job)
  ↓
11. Return success response
```

### 4. Extractors Location

**Extractors are NOT in `app/agents/extractors/`** (that folder is empty).

Extractors are in:
- `app/services/deck_extractors/` - PDF/text/image extraction
  - `pdf_text_extractor.py`
  - `pdf_image_extractor.py`
  - `pdf_metadata_extractor.py`
  - `pdf_ocr_extractor.py`

- `app/services/brand/brand_extraction.py` - Brand color/logo extraction
- `app/services/deck_processing/source_extraction.py` - Source structure extraction

The empty `app/agents/extractors/` folder is leftover from a refactor and can be safely removed.

### 5. Database Architecture

**Three separate databases** (if configured):
- **Main DB** (`SessionLocal`) - decks, workspaces, files
- **User DB** (`UserSessionLocal`) - users, auth sessions (if `USER_DATABASE_URL` set)
- **Billing DB** (`BillingSessionLocal`) - billing data (if `BILLING_DATABASE_URL` set)

**Current Issue**: If `USER_DATABASE_URL` is set:
- `get_current_user()` loads user from USER database
- `_ensure_app_db_user()` tries to mirror user to MAIN database
- This can cause ID mismatches if user exists in both with different IDs

### 6. Known Issues

#### Issue #1: Duplicate User Email (FIXED)
**Problem**: `_ensure_app_db_user()` was trying to INSERT a user with an email that already exists.

**Fix**: Check for existing user by email before INSERT.

**Status**: Fixed in commit `f59dff2`, deployed in commit `62287c5`.

#### Issue #2: User ID Mismatch (POTENTIAL)
**Problem**: If `USER_DATABASE_URL` is set, the JWT token contains the USER database's user ID, but the deck is created with the MAIN database's user ID.

**Impact**: Decks might be created with the wrong `user_id`, causing access issues.

**Status**: Not yet fixed. Need to verify if `USER_DATABASE_URL` is set in production.

#### Issue #3: Empty `agents/extractors/` Folder
**Problem**: Empty folder causing confusion.

**Status**: Cosmetic issue, no functional impact.

### 7. Diagnostic Steps

After Railway deploys the latest code, run these in Railway console:

```bash
# 1. Trace the upload flow
python scripts/trace_upload_flow.py

# 2. Check user account for duplicates
python scripts/diagnose_user_account.py acp2760@gmail.com

# 3. Check Railway environment variables
python scripts/verify_railway_env.py
```

### 8. Expected Behavior

After fixes are deployed:
1. User uploads deck
2. `upload_rescue.py` handles the request
3. `_ensure_app_db_user()` finds existing user by email (no duplicate error)
4. Deck is created with correct `user_id`
5. File is saved to storage
6. Source extraction is queued
7. User sees "Deck saved" message
8. User can proceed to brand extraction

### 9. Files to Check

**Critical Path Files**:
- `app/api/routes/upload_rescue.py` - Main upload handler
- `app/api/routes/products.py` - Alternative upload handler
- `app/services/deck_processing/workspace_summary_service.py` - `create_first_deck_upload()`
- `app/api/deps.py` - `get_current_user()` authentication
- `app/db/session.py` - Database session factories

**Extractor Files**:
- `app/services/deck_extractors/` - PDF extraction
- `app/services/brand/brand_extraction.py` - Brand extraction
- `app/services/deck_processing/source_extraction.py` - Source extraction

### 10. Next Steps

1. **Wait for Railway deployment** to complete (commit `3a020a7`)
2. **Run diagnostic scripts** in Railway console
3. **Try upload again** - should work now
4. **If still failing**, check Railway logs for the exact error
5. **If user ID mismatch**, we need to fix the database session handling

## Summary

The main issue was the duplicate user email error in `_ensure_app_db_user()`. This has been fixed. The extractors are in the correct location (`services/deck_extractors/`), not in `agents/extractors/`. The empty `agents/extractors/` folder is harmless but can be removed for clarity.

After the latest deployment, uploads should work. If they don't, the diagnostic scripts will reveal the exact issue.
