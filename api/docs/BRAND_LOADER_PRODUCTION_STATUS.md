# Brand Loader Production Status

The brand loader supports three input modes:

1. website only
2. logo only
3. website plus logo

## Implemented backend capabilities

The backend now owns the production brand path under:

```text
/api/products/deck-aistack-codes/decks/{deck_id}/brand/*
```

Implemented routes:

```text
POST /api/products/deck-aistack-codes/decks/{deck_id}/brand/extract
GET  /api/products/deck-aistack-codes/decks/{deck_id}/brand/status
GET  /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile
PATCH /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile
GET  /api/products/deck-aistack-codes/decks/{deck_id}/brand-assets/{asset_id}
```

## Website-only mode

Implemented:

- URL normalization
- homepage fetch
- metadata inspection
- favicon/icon/OG image discovery
- CSS and inline style color sampling
- CSS stylesheet sampling
- palette ranking
- raw evidence storage on the brand profile
- structured profile response
- status route for polling/debugging

## Logo-only mode

Implemented:

- multipart logo upload
- file type validation
- upload size limit
- upload scan hook
- persisted brand asset
- durable storage through configured upload storage provider
- logo palette extraction where supported
- structured profile response
- status route for polling/debugging

## Website plus logo mode

Implemented:

- combines website source context with uploaded logo
- uploaded logo remains the preferred visual source
- website remains the company/source context
- profile source mode records combined extraction

## Backend persistence

Existing models used:

- `DeckBrandProfile`
- `DeckBrandAsset`
- `DeckInputSource`

This is the backend equivalent of the originally planned `BrandProfile`, `BrandAsset`, and a lightweight source/run trail.

## Status tracking

`GET /brand/status` returns:

- overall status
- progress percent
- brand profile id
- source mode
- stage list
- persisted asset list
- warnings
- raw evidence
- current brand profile

This gives the frontend a polling/debug surface even while extraction is direct request/response.

## Remaining future upgrade

Screenshot-based extraction is still a future worker-level enhancement. It should not block the brand loader because current extraction already uses homepage HTML, metadata, CSS, icon/logo assets, uploaded logos, storage, and profile evidence.

A future Playwright worker can add:

- screenshot asset capture
- visible hero/header color extraction
- computed style extraction
- screenshot evidence records
