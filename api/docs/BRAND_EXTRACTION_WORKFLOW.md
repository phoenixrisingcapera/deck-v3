# Brand Extraction Workflow - Complete Architecture

## Overview
This document explains the complete brand extraction workflow and how the restored brand agent integrates with the system.

## What Was Fixed

### 1. Brand Agent Restored
**Location**: `app/agents/brand_agent.py`

The brand agent was moved from `legacy/` to the active agents folder and fully documented with inline comments.

**Purpose**: LLM-based analysis of slide content to extract brand signals (voice, values, visual style, etc.)

**Functions**:
- `run_brand_agent()` - Main entry point for brand analysis
- `_find_brand_relevant_slides()` - Filters slides for brand-related content
- `_fallback_brand()` - Provides minimal brand data when LLM fails

### 2. Brand Agent Integration
**Location**: `app/services/deck_processing/brand_extraction.py`

The brand agent is now integrated into the brand extraction workflow:

```
run_brand_extraction_for_deck()
  ↓
1. Query input sources (website URLs, logos)
  ↓
2. Query brand assets (uploaded files)
  ↓
3. Extract brand profile using deterministic methods
   (URL scraping, logo color extraction)
  ↓
4. NEW: Enhance with LLM-based slide content analysis
   - Query all slides for the deck
   - Extract text content from slides
   - Call brand agent to analyze slide content
   - Merge agent results into brand profile
  ↓
5. Enrich profile with additional metadata
  ↓
6. Return complete brand profile
```

## Complete Workflow Files

### Upload Flow
```
1. Frontend Upload
   File: deck-frontend-rescue/src/routes/api/products/deck-aistack-codes/decks/upload/+server.ts
   - Receives browser upload
   - Proxies to backend with auth headers

2. Backend Upload Handler
   File: app/api/routes/upload_rescue.py
   - Line 219: upload_deck_rescue() - main handler
   - Line 263: _ensure_app_db_user() - handles duplicate emails
   - Line 288-298: Creates Deck record
   - Line 302-314: Creates DeckFile record

3. Authentication
   File: app/api/deps.py
   - Line 87-109: get_current_user() - validates JWT, loads user

4. Database Sessions
   File: app/db/session.py
   - SessionLocal: main database
   - UserSessionLocal: user database (if USER_DATABASE_URL set)
```

### Source Extraction Flow
```
1. Worker Handler
   File: app/workers/runtime/source_pipeline_runtime.py
   - Line 77: handle_source_extraction()
   - Extracts PDF structure, text, images
   - Creates DeckSlide records

2. PDF Extraction
   File: app/services/deck_processing/source_extraction.py
   - extract_pdf_deck_structure() - main extraction
   - Uses extractors from app/services/deck_extractors/
```

### Brand Extraction Flow
```
1. Worker Handler
   File: app/workers/runtime/source_pipeline_runtime.py
   - Line 225: handle_brand_extraction()
   - Calls run_brand_extraction_for_deck()

2. Brand Extraction Service
   File: app/services/deck_processing/brand_extraction.py
   - run_brand_extraction_for_deck() - orchestrates brand extraction
   - _enhance_brand_profile_with_slide_analysis() - NEW: calls brand agent

3. Brand Profile Persistence
   File: app/services/brand/brand_profile_persistence.py
   - upsert_brand_profile() - creates/updates DeckBrandProfile
   - Extracts colors from URL, logo, deck visuals

4. Brand Agent (LLM Analysis)
   File: app/agents/brand_agent.py
   - run_brand_agent() - analyzes slide content
   - Extracts: brand name, tagline, voice, visual style, values
   - Results merged into branding_json

5. Brand Enrichment
   File: app/services/brand/brand_enrichment.py
   - enrich_brand_profile_after_extract()
   - Downloads remote logos, extracts typography
```

## Extractors Location

**PDF Extractors**: `app/services/deck_extractors/`
- `pdf_text_extractor.py` - Text extraction
- `pdf_image_extractor.py` - Image extraction
- `pdf_metadata_extractor.py` - Page metadata
- `pdf_ocr_extractor.py` - OCR text extraction

**Brand Extractors**: `app/services/brand/`
- `brand_extraction.py` - Main brand extraction (URL, logo, colors)
- `brand_enrichment.py` - Post-extraction enrichment
- `brand_profile_persistence.py` - Database persistence
- `website_context.py` - Website URL normalization

**Empty Folder Removed**: `app/agents/extractors/` was empty and has been removed.

## How Brand Extraction Works Now

### Step 1: Deterministic Extraction
When a deck is uploaded with a website URL or logo:
1. System fetches the website HTML
2. Extracts colors from CSS, meta tags, favicons
3. If logo uploaded, extracts colors from logo
4. Creates DeckBrandProfile with extracted colors
5. Sets primary, secondary, accent, background, text colors

### Step 2: LLM-Based Enhancement (NEW)
After deterministic extraction:
1. System queries all slides for the deck
2. Extracts text content from each slide
3. Calls brand agent with slide data
4. Brand agent uses LLM to analyze content:
   - Identifies brand name from slide titles/text
   - Extracts tagline/slogan
   - Identifies brand voice (professional, innovative, etc.)
   - Identifies visual style (minimalist, bold, corporate, etc.)
   - Extracts brand values (innovation, sustainability, etc.)
   - Identifies color hints mentioned in text
5. Agent results merged into brand profile's branding_json
6. Brand profile now has both deterministic colors AND LLM-extracted brand signals

### Step 3: Enrichment
After brand profile created:
1. System downloads remote logo from website
2. Extracts typography from website CSS
3. Attaches card swatches for UI display
4. Updates brand profile with enriched data

## Brand Profile Structure

### Manual field protection

`DeckBrandProfile.raw_evidence_json.fieldEvidence` is the canonical field-level
provenance store. Both Brand Profile PATCH and overlapping shell-properties
PATCH record every applied non-null user value as `source=manual`,
`status=overridden`, and `confidence=1.0`. This includes company identity and
URL, writable logo/favicon values, summary, visual direction/style, audience,
goal, role colours, palette, and fonts. Null PATCH values are ignored: they do
not clear persisted values or create evidence.

Automatic intake, extraction, and enrichment consult the same map before each
field assignment. Manual/overridden fields survive reruns. Explicit URL
confirmation remains durable, and automatic precedence remains manual, then
guideline/logo evidence, confirmed URL, deck extraction, and safe fallback.

```python
DeckBrandProfile {
    # Deterministic colors (from URL/logo)
    primary_color: "#1a73e8"
    secondary_color: "#5f6368"
    accent_color: "#ea4335"
    background_color: "#ffffff"
    text_color: "#202124"
    
    # Complete palette
    palette_json: ["#1a73e8", "#5f6368", "#ea4335", ...]
    
    # LLM-extracted brand signals (NEW)
    branding_json: {
        "companyName": "Deck AIStack",
        "tagline": "AI-powered deck analysis",
        "brandVoice": ["professional", "innovative"],
        "visualStyle": ["minimalist", "modern"],
        "brandValues": ["innovation", "efficiency"],
        "agentConfidence": 0.85,
        "agentSource": "slide_content_analysis",
        "colors": {
            "palette": ["#1a73e8", ...],
            "candidates": [...]
        },
        "usageRules": {...},
        "designHints": {...},
        "llmInstructions": "Use #1a73e8 as primary brand color..."
    }
    
    # Metadata
    company_website_url: "https://deck.aistack.codes"
    logo_url: "/path/to/logo.png"
    processing_status: "ready"
}
```

## Testing the Workflow

After Railway deploys the latest code:

1. **Upload a deck with website URL**
   ```
   POST /api/products/deck-aistack-codes/decks/upload
   - deck: (file)
   - website_url: "https://deck.aistack.codes"
   ```

2. **Check brand extraction status**
   ```
   GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
   ```
   Look for `brandExtractionReady: true`

3. **View brand profile**
   ```
   GET /api/products/deck-aistack-codes/decks/{deck_id}/brand-profile
   ```
   Should show both deterministic colors AND LLM-extracted brand signals

4. **Check brand agent results**
   In the brand profile response, look for:
   - `branding_json.agentConfidence` - confidence score
   - `branding_json.agentSource` - should be "slide_content_analysis"
   - `branding_json.brandVoice` - extracted voice attributes
   - `branding_json.brandValues` - extracted values

## Files Modified

1. **app/agents/brand_agent.py** - Restored from legacy with full documentation
2. **app/services/deck_processing/brand_extraction.py** - Integrated brand agent
3. **app/agents/extractors/** - Empty folder removed

## Next Steps

1. Wait for Railway to deploy commit `c7065eb`
2. Upload a deck with website URL
3. Check that brand extraction completes successfully
4. Verify brand profile includes both colors and LLM-extracted signals
5. If issues persist, check Railway logs for errors

## Summary

The brand agent has been successfully restored and integrated into the brand extraction workflow. It now provides LLM-based analysis of slide content to complement deterministic URL/logo-based extraction. The complete workflow is:

1. Upload deck → 2. Extract source → 3. Extract brand (URL + LLM) → 4. Enrich brand → 5. Ready for Smart Deck

All extractors are in their correct locations:
- PDF extractors: `app/services/deck_extractors/`
- Brand extractors: `app/services/brand/`
- Brand agent: `app/agents/brand_agent.py`
