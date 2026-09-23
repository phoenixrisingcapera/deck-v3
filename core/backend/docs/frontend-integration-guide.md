# Frontend Integration Guide: Science-Backed Pipeline

## Overview

This guide explains how the frontend should integrate with the new science-backed deterministic deck pipeline API endpoints.

## API Endpoints

### Base URL
```
/api/products/deck-aistack-codes/decks
```

### Authentication
All endpoints require Bearer token authentication:
```
Authorization: Bearer <jwt_token>
```

## Endpoints

### 1. Get Processing Status

**GET** `/{deck_id}/processing`

Returns the single source of truth for what stage the deck is in.

**Response:**
```json
{
  "deckId": "deck_123",
  "sourceVersionId": "version_123",
  "status": "ready",
  "extractionStatus": "completed",
  "currentStage": "materialized",
  "slideCount": 10,
  "blockCount": 45,
  "assetCount": 15,
  "hasThumbnails": true,
  "hasStructuredJson": true,
  "hasEmbeddings": false,
  "canOpenSmartDeck": true,
  "canOpenSmartEdit": true,
  "canOpenDueDiligence": true,
  "nextAction": null,
  "warningsJson": [],
  "errorsJson": [],
  "lastExtractionAt": "2026-07-15T10:30:00Z",
  "lastGenerationAt": null,
  "updatedAt": "2026-07-15T10:30:00Z"
}
```

**Usage:**
- Poll this endpoint during upload/processing
- Use `canOpenSmartDeck`, `canOpenSmartEdit`, `canOpenDueDiligence` to enable/disable UI buttons
- Use `nextAction` to show user guidance

### 2. Get Structured JSON

**GET** `/{deck_id}/structured-json`

Returns the full deck structure with slides, blocks, and assets.

**Response:**
```json
{
  "deckId": "deck_123",
  "title": "My Pitch Deck",
  "status": "ready",
  "sourceVersionId": "version_123",
  "slideCount": 10,
  "slides": [
    {
      "id": "slide_1",
      "slideNumber": 1,
      "title": "Title Slide",
      "role": "title",
      "thumbnailPath": "/storage/thumbnails/slide_1.png",
      "renderedImagePath": "/storage/rendered/slide_1.png",
      "widthPoints": 720,
      "heightPoints": 540,
      "blockCount": 3,
      "blocks": [
        {
          "id": "block_1",
          "blockKey": "slide_1.block_0",
          "blockType": "text",
          "blockKind": "headline",
          "text": "My Company",
          "positionJson": {
            "x": 80,
            "y": 120,
            "width": 560,
            "height": 80
          },
          "styleJson": {
            "fontFamily": "Inter",
            "fontSize": "48px",
            "fontWeight": "bold",
            "color": "#111827"
          },
          "confidence": 1.0
        }
      ]
    }
  ]
}
```

**Usage:**
- Render slide thumbnails in the deck map
- Display slide list in the editor
- Use `blockKey` for persistent field binding

### 3. Get Editor View

**GET** `/{deck_id}/editor-view`

Returns the editor view with positions, styles, and persistent field keys.

**Response:**
```json
{
  "deckId": "deck_123",
  "title": "My Pitch Deck",
  "status": "ready",
  "sourceVersionId": "version_123",
  "slideCount": 10,
  "slides": [
    {
      "id": "slide_1",
      "slideNumber": 1,
      "title": "Title Slide",
      "role": "title",
      "thumbnailPath": "/storage/thumbnails/slide_1.png",
      "renderedImagePath": "/storage/rendered/slide_1.png",
      "widthPoints": 720,
      "heightPoints": 540,
      "blockCount": 3,
      "blocks": [
        {
          "id": "block_1",
          "blockKey": "slide_1.block_0",
          "blockType": "text",
          "blockKind": "headline",
          "text": "My Company",
          "positionJson": {
            "x": 80,
            "y": 120,
            "width": 560,
            "height": 80
          },
          "styleJson": {
            "fontFamily": "Inter",
            "fontSize": "48px",
            "fontWeight": "bold",
            "color": "#111827"
          },
          "confidence": 1.0,
          "persistentFieldKey": "slide_1.headline",
          "isEditable": true,
          "isGenerated": false
        }
      ]
    }
  ]
}
```

**Usage:**
- Render editable slides in the editor
- Use `persistentFieldKey` for Smart Edit targeting
- Use `isEditable` to show/hide edit controls
- Use `isGenerated` to show AI-generated badges

### 4. Reprocess Source

**POST** `/{deck_id}/reprocess-source`

Triggers re-extraction of the source deck.

**Request:**
```json
{}
```

**Response:**
```json
{
  "message": "Source reprocessing started",
  "jobId": "version_456"
}
```

**Usage:**
- Show "Reprocess" button in the UI
- Poll `/processing` endpoint for status updates

### 5. Prepare Smart Deck Context

**POST** `/{deck_id}/smart-deck-context`

Prepares the workspace context for Smart Deck generation.

**Request:**
```json
{}
```

**Response:**
```json
{
  "workspaceId": "workspace_123",
  "sourceVersion": "original_source_v1",
  "slideCount": 10,
  "blockCount": 45
}
```

**Usage:**
- Call before starting Smart Deck generation
- Ensures workspace is ready for LLM

### 6. Smart Edit Preview

**POST** `/{deck_id}/smart-edit/preview`

Creates a change request preview for a Smart Edit transformation.

**Request:**
```json
{
  "scope": "block",
  "targetBlockId": "block_123",
  "instruction": "Make this headline more compelling",
  "audience": "VC Partner"
}
```

**Response:**
```json
{
  "changeRequestId": "cr_123",
  "status": "preview",
  "scope": "block",
  "instruction": "Make this headline more compelling"
}
```

**Usage:**
- Show Smart Edit dialog when user clicks a block
- Send instruction to backend
- Show preview diff to user

### 7. Smart Edit Apply

**POST** `/{deck_id}/smart-edit/apply`

Applies an accepted Smart Edit change request.

**Request:**
```json
{
  "changeRequestId": "cr_123"
}
```

**Response:**
```json
{
  "changeRequestId": "cr_123",
  "status": "accepted",
  "appliedAt": "2026-07-15T10:35:00Z"
}
```

**Usage:**
- Show "Apply" button after user reviews preview
- Call this endpoint when user accepts
- Refresh editor view after apply

### 8. Get Change Request

**GET** `/change-requests/{change_request_id}`

Returns a change request by ID.

**Response:**
```json
{
  "id": "cr_123",
  "deckId": "deck_123",
  "changeType": "smart_edit_block",
  "status": "accepted",
  "description": "Make this headline more compelling",
  "inputJson": {
    "scope": "block",
    "targetBlockId": "block_123",
    "instruction": "Make this headline more compelling"
  },
  "outputJson": null,
  "createdAt": "2026-07-15T10:30:00Z",
  "acceptedAt": "2026-07-15T10:35:00Z",
  "rejectedAt": null
}
```

**Usage:**
- Show change request details in history
- Track audit trail

### 9. Run Due Diligence

**POST** `/{deck_id}/due-diligence/run`

Runs Due Diligence analysis for a deck.

**Request:**
```json
{
  "audience": "VC Partner",
  "focusAreas": ["market_size", "team", "traction"]
}
```

**Response:**
```json
{
  "runId": "ar_123",
  "status": "running",
  "audience": "VC Partner"
}
```

**Usage:**
- Show "Run Due Diligence" button
- Poll `/{deck_id}/due-diligence/{run_id}` for status

### 10. Get Due Diligence Run

**GET** `/{deck_id}/due-diligence/{run_id}`

Returns a Due Diligence run by ID.

**Response:**
```json
{
  "id": "ar_123",
  "deckId": "deck_123",
  "status": "completed",
  "createdAt": "2026-07-15T10:30:00Z",
  "completedAt": "2026-07-15T10:35:00Z"
}
```

**Usage:**
- Show diligence results
- Display findings list

### 11. Send Finding to Smart Edit

**POST** `/{deck_id}/due-diligence/findings/{finding_id}/send-to-smart-edit`

Sends a diligence finding to Smart Edit.

**Request:**
```json
{}
```

**Response:**
```json
{
  "changeRequestId": "cr_456",
  "status": "preview",
  "findingId": "finding_123"
}
```

**Usage:**
- Show "Fix this" button on each finding
- Open Smart Edit dialog with pre-filled instruction

## Frontend Integration Patterns

### Pattern 1: Upload Flow

```typescript
// 1. Upload file
const uploadResponse = await fetch('/api/upload', {
  method: 'POST',
  body: formData,
});

// 2. Poll processing status
const pollProcessing = async (deckId: string) => {
  while (true) {
    const response = await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/processing`);
    const state = await response.json();
    
    if (state.status === 'ready') {
      return state;
    }
    
    if (state.status === 'failed') {
      throw new Error('Processing failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
};

// 3. Load editor when ready
const state = await pollProcessing(deckId);
if (state.canOpenSmartDeck) {
  loadEditor(deckId);
}
```

### Pattern 2: Smart Edit Flow

```typescript
// 1. User clicks block
const selectedBlock = {
  id: 'block_123',
  blockKey: 'slide_1.headline',
  text: 'My Company',
};

// 2. Show Smart Edit dialog
const showSmartEditDialog = (block: Block) => {
  // Display dialog with instruction input
};

// 3. Create preview
const createPreview = async (instruction: string) => {
  const response = await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/smart-edit/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope: 'block',
      targetBlockId: selectedBlock.id,
      instruction,
    }),
  });
  
  return await response.json();
};

// 4. Show preview diff
const showPreviewDiff = (preview: Preview) => {
  // Display before/after diff
};

// 5. Apply changes
const applyChanges = async (changeRequestId: string) => {
  await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/smart-edit/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ changeRequestId }),
  });
  
  // Refresh editor
  refreshEditor(deckId);
};
```

### Pattern 3: Due Diligence Flow

```typescript
// 1. Run Due Diligence
const runDueDiligence = async (audience: string) => {
  const response = await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/due-diligence/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audience }),
  });
  
  return await response.json();
};

// 2. Poll for results
const pollResults = async (runId: string) => {
  while (true) {
    const response = await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/due-diligence/${runId}`);
    const run = await response.json();
    
    if (run.status === 'completed') {
      return run;
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
};

// 3. Show findings
const showFindings = (findings: Finding[]) => {
  // Display findings list with "Fix this" buttons
};

// 4. Send finding to Smart Edit
const sendToSmartEdit = async (findingId: string) => {
  const response = await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/due-diligence/findings/${findingId}/send-to-smart-edit`, {
    method: 'POST',
  });
  
  const result = await response.json();
  // Open Smart Edit dialog with changeRequestId
};
```

## Error Handling

### Common Error Responses

```json
{
  "detail": "Deck not found"
}
```

```json
{
  "detail": "Deck processing state not found"
}
```

```json
{
  "detail": "Change request not found"
}
```

### Error Handling Pattern

```typescript
const handleApiError = async (response: Response) => {
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'API request failed');
  }
  return response.json();
};
```

## State Management

### Recommended State Shape

```typescript
interface DeckState {
  deckId: string;
  processing: MaterializedDeckState;
  deckMap: DeckMap | null;
  editorView: EditorView | null;
  selectedBlock: Block | null;
  smartEditPreview: Preview | null;
  dueDiligenceRun: DueDiligenceRun | null;
}
```

### State Updates

```typescript
// After upload
deckState.processing = await fetchProcessingStatus(deckId);

// After extraction completes
deckState.deckMap = await fetchStructuredJson(deckId);
deckState.editorView = await fetchEditorView(deckId);

// After Smart Edit apply
deckState.editorView = await fetchEditorView(deckId);

// After Due Diligence
deckState.dueDiligenceRun = await fetchDueDiligenceRun(deckId, runId);
```

## Performance Considerations

1. **Polling Interval**: Use 1-2 seconds for processing status
2. **Caching**: Cache editor view and structured JSON
3. **Lazy Loading**: Load slides on demand for large decks
4. **Debouncing**: Debounce Smart Edit preview requests

## Testing

Test the integration with:

```bash
# Run backend tests
python -m pytest tests/test_science_backed_pipeline.py -v

# Run frontend tests
npm run test
```
