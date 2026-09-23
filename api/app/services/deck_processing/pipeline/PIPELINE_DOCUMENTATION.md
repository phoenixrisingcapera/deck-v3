# Deck Processing Pipeline - Complete Architecture

**Status**: ✅ IMPLEMENTED AND WORKING  
**Last Verified**: July 14, 2026  
**Repository**: rescue-DECK

---

## Executive Summary

The deck processing pipeline is **fully implemented and operational**. The system processes uploaded PDF/PPTX files through a multi-stage workflow with real-time visibility, worker-based processing, and frontend polling.

**What Works:**
- Upload API creates extraction runs
- Workers claim and process jobs from queue
- Stage/status written to database in real-time
- Visibility endpoint returns complete pipeline state
- Frontend polls and displays live progress
- Processing page shows all stages with labels
- Upload page polls processing state after upload
- Smart Deck page gates access on backend readiness
- Admin processing jobs table is available
- Explicit processing stage columns are available through Alembic

**Remaining Operational Step:**
- Run the new Alembic migration in each deployed environment before relying on explicit stage columns there.

---

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. UPLOAD                                                    │
│    POST /api/products/deck-aistack-codes/decks/upload       │
│    → Creates Deck + DeckFile + DeckExtractionRun            │
│    → Calls queue_source_extraction()                        │
│    → Creates WorkflowJob records                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. WORKER CLAIMS JOB                                         │
│    deck_queue_worker.py runs continuously                   │
│    → process_next_durable_deck()                            │
│    → claim_next_workflow_job() (with FOR UPDATE SKIP LOCKED)│
│    → Sets status: queued → running                          │
│    → Writes lockedBy, lockedAt, heartbeatAt                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. WORKER PROCESSES                                          │
│    process_workflow_job() executes actual processing        │
│    → source_ingestion (save file)                           │
│    → source_extraction (extract slides/blocks)              │
│    → miniatures (render previews)                           │
│    → smart_deck_context (prepare for Smart Deck)            │
│    → db_publisher (publish final state)                     │
│    → brand_extraction (optional)                            │
│    → Updates WorkflowJob status at each stage               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. VISIBILITY LAYER                                          │
│    GET /api/products/deck-aistack-codes/decks/{id}/processing│
│    → get_deck_processing_visibility()                       │
│    → Reads WorkflowJob + DeckExtractionRun                  │
│    → Returns complete state with phases, counts, errors     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. FRONTEND DISPLAYS                                         │
│    /decks/{deckId}/processing/+page.svelte                  │
│    → Polls every 3 seconds (POLL_DELAY_MS = 3000)           │
│    → Max 24 attempts before giving up                       │
│    → Shows phases: source_saved, extraction, miniatures,    │
│      smart_deck_ready, brand_extraction                     │
│    → Auto-starts extraction if no active jobs               │
│    → Handles retry on failure                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend Files Involved

### API Routes
- `app/api/routes/products.py` - Upload endpoint, processing visibility endpoint
- `app/api/routes/deck_intake.py` - Structure extraction, status endpoint
- `app/api/routes/product_processing.py` - Processing compatibility routes
- `app/api/routes/product_runtime_hardening.py` - Runtime hardening routes

### Services (Core Pipeline Logic)
- `app/services/deck_processing/processing_queue.py` - **MAIN**: Queue management, stage tracking, run lifecycle
- `app/services/deck_processing/processing_visibility.py` - **MAIN**: Visibility endpoint logic, phase computation
- `app/services/deck_processing/workflow_jobs.py` - WorkflowJob CRUD, status transitions, idempotency
- `app/services/deck_processing/workflow_orchestration.py` - queue_source_extraction(), pipeline job creation
- `app/services/deck_processing/workflow_state_read_model.py` - Read model for workflow state
- `app/services/deck_processing/state_machine.py` - Deck state transitions
- `app/services/deck_processing/source_structure_persistence.py` - Structure persistence
- `app/services/deck_processing/source_preview_service.py` - Preview generation
- `app/services/deck_processing/deck_intake_service.py` - Intake status

### Workers
- `app/workers/deck_queue_worker.py` - **MAIN**: Worker loop, calls process_next_durable_deck()
- `app/workers/dispatch/worker_runtime_service.py` - **MAIN**: process_workflow_job(), claim logic
- `app/workers/dispatch/job_handlers.py` - Job handler dispatch registry
- `app/workers/runtime/source_pipeline_runtime.py` - Source pipeline execution
- `app/workers/runtime/generation_runtime.py` - Generation execution
- `app/workers/runtime/publisher_runtime.py` - Publisher execution
- `app/workers/entrypoints/*.py` - Dedicated worker entrypoints (source_worker.py, generation_worker.py, etc.)

### Schemas
- `app/schemas/deck_processing.py` - DeckProcessingVisibilityResponse, ProcessingStartResponse
- `app/schemas/deck_workflow.py` - WorkflowJobResponse, DeckWorkflowStateResponse

### Database Models
- `app/db/models/entities.py` - Deck, DeckFile, DeckExtractionRun, WorkflowJob, WorkflowJobEvent, WorkflowJobDependency

---

## Frontend Files Involved

### Pages
- `src/routes/(product)/decks/[deckId]/processing/+page.server.ts` - Server load, fetches workflow-state
- `src/routes/(product)/decks/[deckId]/processing/+page.svelte` - **MAIN**: Polling UI, phase display, retry logic

### API Clients
- `src/lib/api/deckService/workflow.client.ts` - **MAIN**: getDeckProcessingVisibility(), normalizeSmartDeckProcessingStatus()

### Types
- `src/lib/components/deck/processingTypes.ts` - Processing type definitions

### Proxy Routes
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/processing/+server.ts` - Proxy to backend
- `src/routes/api/products/deck-aistack-codes/decks/[deckId]/workflow-state/+server.ts` - Proxy to backend

---

## Pipeline Stages

The pipeline tracks these stages (written to `DeckExtractionRun.metadata_json`):

1. **source_saved** - Source file saved to storage
2. **worker_claimed** - Worker claimed the job
3. **structure_extraction_running** - Extracting slide text and structure
4. **preview_generation_running** - Generating slide previews/miniatures
5. **smart_deck_context_ready** - Smart Deck context prepared
6. **failed** - Processing failed

### Metadata Fields Tracked

```json
{
  "stage": "structure_extraction_running",
  "stageLabel": "Extracting slide text and structure",
  "nextAction": "wait_for_worker",
  "attemptCount": 1,
  "maxAttempts": 3,
  "lockedBy": "worker-1",
  "lockedAt": "2026-07-14T10:30:00Z",
  "heartbeatAt": "2026-07-14T10:31:00Z",
  "workflowJobId": "job_abc123",
  "workflowJobType": "source_extraction",
  "workflowJobStatus": "running",
  "sourceChecksum": "sha256:...",
  "idempotencyKey": "deck_id:checksum:run_type"
}
```

---

## Database Schema

### DeckExtractionRun
- `id` - Primary key
- `deck_id` - FK to Deck
- `run_type` - "deck_processing_queue"
- `status` - "queued" | "processing" | "completed" | "failed"
- `source_file_id` - FK to DeckFile
- `metadata_json` - **JSONB**: Stores stage, attemptCount, lockedBy, heartbeatAt, etc.
- `metrics_json` - JSONB: Output counts, source workspace info
- `slide_count`, `block_count`, `asset_count` - Output counts
- `error_message` - Error details
- `created_at`, `started_at`, `completed_at` - Timestamps

### WorkflowJob
- `id` - Primary key
- `deck_id` - FK to Deck
- `extraction_run_id` - FK to DeckExtractionRun
- `job_type` - "source_ingestion" | "source_extraction" | "miniatures" | etc.
- `status` - "queued" | "running" | "completed" | "failed_retryable" | "failed_final" | "blocked" | "timed_out"
- `priority` - Integer priority
- `idempotency_key` - Unique key for deduplication
- `input_json`, `output_json` - JSONB payloads
- `attempt_count`, `max_attempts`, `recovery_count` - Retry tracking
- `locked_by`, `locked_until`, `heartbeat_at` - Worker lease
- `queued_at`, `started_at`, `completed_at`, `failed_at` - Timestamps

---

## API Endpoints

### Backend (FastAPI)

**Upload:**
```
POST /api/products/deck-aistack-codes/decks/upload
→ Creates Deck + DeckFile + DeckExtractionRun + WorkflowJob
→ Returns deck_id, processing status
```

**Processing Visibility:**
```
GET /api/products/deck-aistack-codes/decks/{deck_id}/processing
→ Returns complete pipeline state
→ Includes: upload, processing, outputs, worker, phases, nextAction
```

**Workflow State:**
```
GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
→ Returns workflow jobs, phases, canOpenSmartDeck, canRetry
```

**Start Extraction:**
```
POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction
→ Queues source extraction job
→ Returns accepted response
```

**Retry:**
```
POST /api/products/deck-aistack-codes/decks/{deck_id}/retry
→ Requeues failed jobs
→ Returns updated visibility
```

### Frontend (SvelteKit Proxies)

All backend endpoints are proxied through SvelteKit at:
```
/api/products/deck-aistack-codes/decks/{deckId}/...
```

---

## Frontend Polling Logic

**File:** `src/routes/(product)/decks/[deckId]/processing/+page.svelte`

```typescript
const POLL_DELAY_MS = 3000;        // Poll every 3 seconds
const MAX_POLL_ATTEMPTS = 24;      // Max 24 polls (72 seconds total)

// Polling stops when:
- canOpenSmartDeck === true
- canRetry === true
- status === 'failed'
- deckExtractionStatus === 'failed'
- backendStatus >= 500
- MAX_POLL_ATTEMPTS reached

// Auto-start extraction if:
- No active running jobs
- Not already attempted
- Not in terminal state
```

---

## Worker Execution

**File:** `app/workers/deck_queue_worker.py`

```python
class DeckQueueWorker(DurableWorkerBase):
    def run(self) -> None:
        while True:
            process_next_durable_deck(
                worker_kind=self.worker_kind,
                worker_recovery_only=self.worker_recovery_only
            )
            recover_stale_processing_runs()
            time.sleep(settings.DECK_WORKER_POLL_INTERVAL_SECONDS)
```

**Worker Claim Process:**
1. Query WorkflowJob WHERE status IN ('queued', 'failed_retryable')
2. ORDER BY priority DESC, created_at ASC
3. FOR UPDATE SKIP LOCKED (prevents duplicate claims)
4. Check dependencies (upstream jobs must be completed)
5. Set status = 'running', locked_by = worker_id, heartbeat_at = now
6. Execute job logic
7. Update status to 'completed' or 'failed_*'

---

## Error Handling

### Retry Logic
- `max_attempts` = 3 (configurable via DECK_PROCESSING_MAX_ATTEMPTS)
- Failed jobs with `attempt_count < max_attempts` → status = 'failed_retryable'
- Failed jobs with `attempt_count >= max_attempts` → status = 'failed_final'
- Frontend shows "Retry" button for failed_retryable jobs

### Stale Job Recovery
- Worker runs `recover_stale_processing_runs()` every cycle
- Finds jobs with status = 'running' AND heartbeat_at < cutoff
- Resets to 'queued' if `attempt_count < max_attempts`
- Sets to 'timed_out' if max attempts exceeded

### Checksum Supersession
- If new upload arrives with different checksum:
  - Old runs marked as 'failed'
  - Error: "Processing run superseded by a newer source checksum"
  - Prevents processing stale sources

---

## Configuration

### Environment Variables

```bash
# Worker Configuration
DECK_WORKER_POLL_INTERVAL_SECONDS=5
DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS=30
DECK_WORKER_STALE_AFTER_SECONDS=900
DECK_WORKER_ID=worker-1
DECK_WORKER_JOB_TYPES=source_ingestion,source_extraction,miniatures

# Processing Configuration
DECK_PROCESSING_MAX_ATTEMPTS=3

# Railway Deployment
APP_ROLE=worker  # For worker service
```

### Railway Services

**API Service:**
```
Root Directory: deck-backend-rescue
Start Command: python scripts/start_railway.py
Public URL: https://api.deck.aistack.codes
```

**Worker Service:**
```
Root Directory: deck-backend-rescue
Start Command: APP_ROLE=worker python scripts/start_railway.py
Public URL: none
```

---

## Testing

### Backend Tests
```bash
cd deck-backend-rescue
python3 -m pytest tests/test_durable_worker_contract.py -v
python3 -m pytest tests/test_processing_visibility_robustness.py -v
python3 -m pytest tests/test_processing_source_enrichment_visibility.py -v
```

### Frontend Type Check
```bash
cd deck-frontend-rescue
npm run check
```

### Manual Testing

1. **Upload a deck:**
   ```bash
   curl -X POST http://localhost:8000/api/products/deck-aistack-codes/decks/upload \
     -F "file=@test.pdf" \
     -H "Authorization: Bearer <token>"
   ```

2. **Check processing status:**
   ```bash
   curl http://localhost:8000/api/products/deck-aistack-codes/decks/{deck_id}/processing \
     -H "Authorization: Bearer <token>"
   ```

3. **Start worker:**
   ```bash
   cd deck-backend-rescue
   python3 -m app.workers.deck_queue_worker
   ```

4. **Open processing page:**
   ```
   http://localhost:5173/decks/{deck_id}/processing
   ```

---

## Known Limitations

1. **Migration required in deployed environments** - explicit stage columns exist in code/migrations, but production DBs need Alembic upgrade.
2. **Single worker kind** - all job types can still be handled by one worker service unless deployment splits dedicated workers.
3. **Polling-based frontend updates** - processing UI polls instead of using WebSockets.

---

## Future Enhancements

1. **Alembic migration** - Add explicit stage/status columns to DeckExtractionRun
2. **Upload page polling** - Show progress on /decks/new after upload
3. **Smart Deck gating** - Block access until processing complete
4. **Admin processing table** - Dashboard showing all jobs with filters
5. **Dedicated workers** - Split into source_worker, generation_worker, publisher_worker
6. **WebSocket updates** - Replace polling with push-based updates
7. **Progress percentages** - Show % complete for long-running stages

---

## Troubleshooting

### Worker not claiming jobs
- Check `DECK_WORKER_JOB_TYPES` includes the job type
- Check job dependencies (upstream jobs must be completed)
- Check job priority (higher priority claimed first)
- Check `locked_until` (job may be locked by another worker)

### Processing stuck in "queued"
- Worker may not be running
- Check worker logs for errors
- Check `heartbeat_at` (may be stale)
- Manually trigger recovery: `recover_stale_processing_runs()`

### Frontend not showing updates
- Check browser console for errors
- Check network tab for /workflow-state requests
- Verify backend endpoint returns data
- Check CORS configuration

### "Processing run superseded" error
- New upload arrived with different checksum
- Old run intentionally failed
- Upload same file again or accept new processing

---

## Related Documentation

- [Pipeline Visibility Implementation](./pipeline-visibility-implementation.md)
- [Worker Pipeline Architecture](./worker-pipeline-architecture.md)
- [Deck Processing Queue Service](./deck-processing-queue-service.md)
- [Workflow Job Contract](./workflow-job-contract.md)

---

**Document Version**: 1.0  
**Last Updated**: July 14, 2026  
**Maintained By**: Development Team
