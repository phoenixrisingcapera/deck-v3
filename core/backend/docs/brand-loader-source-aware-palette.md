# Brand loader source-aware palette

Date: 2026-06-25

## Goal

Make the brand loader reliable as the first intelligent view in Deck AIStack.

The user may provide any combination of:

```text
deck file
company URL
logo
brand guide
```

The app must produce visible colour swatches and clearly explain where those colours came from.

## Current fix in this PR

### 1. Intake-created swatches

`app/services/brand_loader_service.py` now creates safe default swatches during intake when a brand profile has context but no colours yet.

This prevents a brand context from looking empty before full extraction runs.

The profile now records:

```text
primary_color
secondary_color
accent_color
background_color
text_color
palette_json
source_mode=context_seed
raw_evidence_json.paletteSource
raw_evidence_json.fallbackReason
warnings_json
```

### 2. Idempotent brand-first creation

`app/services/first_batch_rescue_service.py` now reuses an existing brand-first deck for the same workspace, user, source type, and URL instead of creating a new pseudo-deck every click.

This stops the `/decks/new` page from accumulating many duplicate URL-branding decks.

### 3. Source-context distinction

Brand-first decks now explicitly report:

```json
{
  "hasSourceFile": false,
  "reused": true
}
```

This allows the frontend to avoid presenting URL-only brand context as a normal uploaded source deck.

## Intended extraction priority

The production order should be:

```text
1. Logo-derived palette
2. Live URL assets / CSS / theme colours
3. Deck visual palette from thumbnails / slide previews
4. Brand guide palette
5. Context/default fallback palette
```

This PR improves the fallback and state behaviour. Follow-up work should add true deck visual sampling from slide thumbnails and brand-guide documents.

## Backend files touched

```text
app/services/brand_loader_service.py
app/services/first_batch_rescue_service.py
docs/brand-loader-source-aware-palette.md
```

## Acceptance criteria

```text
URL-only first batch produces visible swatches.
Repeated URL first-batch does not create duplicate decks for the same URL.
Fallback swatches are marked as fallback/context defaults.
Backend persists palette provenance in raw_evidence_json.
Backend response distinguishes source-context decks from source-file uploads.
```

## Follow-up

```text
Add SVG logo whitelist consistently with frontend.
Add deck visual palette extraction from slide thumbnails.
Add tests for URL idempotency and fallback swatch persistence.
```

## Canonical current-main contract (2026-07-22)

The authenticated deck-owned endpoints remain the only Brand Profile API:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/brand/extract`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/brand/status`
- `GET/PATCH /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile`

Every profile returned by extract, status, GET, or PATCH exposes the same
role-first `deterministicSwatches` (`label`, `value`) and mapping version
`deck-brand-deterministic-v1`. `rawEvidence.deterministicSwatches` and
`rawEvidence.deterministicMappingVersion` are refreshed from the current
profile colours rather than allowed to retain stale pre-PATCH values. Persisted
raw evidence is refreshed on extraction/enrichment and PATCH so later reloads
agree with the response contract. A PATCH that changes palette fields records
`paletteSource=manual` and resets palette evidence to the manual source while
preserving unrelated website/logo/guideline evidence.

`sourceLabels` reports Website, Logo, Deck, optional Guidelines, and Fallback.
A supplied but unsampleable website is `fallback`, not falsely `available`;
guideline/deck availability is retained for deck-ready UI semantics. Palette
precedence remains logo, website, deck visuals, then deterministic seed.
Absence of a Brand Profile remains non-blocking for source processing and Smart
Deck generation, which retain safe design-token defaults.

All current user-editable extraction fields use
`raw_evidence_json.fieldEvidence` as one shared protection model. Non-null
Brand Profile PATCH and overlapping shell-properties PATCH writes are marked
manual/overridden; null writes are no-ops and create no evidence. Intake,
automatic extraction, website/logo enrichment, and source-pipeline reruns must
check that evidence per field before assignment. Consequently manual company,
URL, logo/favicon, summary, visual direction/style, audience, goal, colour,
palette, and font choices survive later automatic processing. A manually
applied website URL also updates durable `confirmedWebsiteUrl`; URL use remains
explicit and lower precedence than manual, guideline, or logo evidence.

Historical disposition: PR #72 supplied useful explicit source semantics and
PR #66 supplied the swatch-card idea; PR #74 and
`complete-brand-loader-production` supplied deck-visual/status/enrichment
reference behavior. All are stale/conflicting references only and must not be
merged wholesale. Their useful behavior is reconciled here into the canonical
current route/service modules without alternate endpoints or services.
The retained `attach_card_swatches()` legacy callable delegates to the canonical
`deck-brand-deterministic-v1` helper. It no longer writes
`brand-profile-card-v1` evidence. Extraction stores the canonical
`deterministicMappingVersion` and `{label, value}` swatches before its commit,
so a fresh database session reload and post-extraction enrichment preserve the
same evidence.
