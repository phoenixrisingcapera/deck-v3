# Smart Deck context-first pipeline

## Purpose

The backend must build a deterministic SmartDeckContext before any LLM generation is allowed.

The LLM is not the first step. The backend first converts the uploaded deck into typed evidence, slide previews, brand context, and a canonical SmartDeckContext. Only after that context is published as ready should Smart Deck generation run.

## Canonical MVP order

```txt
source_ingestion
-> source_extraction
-> miniatures
-> brand_extraction
-> smart_deck_context
-> db_publisher
```

## Product rule

```txt
Deck evidence + thumbnails + brand context
-> SmartDeckContext
-> smart_deck_ready
-> LLM generation
```

Do not publish `smart_deck_ready` before `brand_extraction` and `smart_deck_context` have completed.

## Why PySpark is not required yet

PySpark is an execution backend, not the product architecture.

For the MVP, the app needs reliable typed workflow state more than distributed compute. The durable worker queue can run the pipeline now. Later, the same worker contracts can be executed through PySpark or another parallel runtime if scale requires it.

## Worker responsibilities

### source_ingestion

Owns file intake provenance:

- deck id
- source file id
- checksum
- processing run id

### source_extraction

Owns deck evidence extraction:

- slides
- slide text
- source structure
- extracted layout or element payloads where available

### miniatures

Owns slide preview readiness:

- thumbnails
- preview URLs
- miniature status

### brand_extraction

Owns brand evidence:

- detected colors
- logo references
- font candidates
- visual constraints
- confidence/warnings

### smart_deck_context

Owns the canonical context object consumed by Smart Deck:

- deck metadata
- slides
- thumbnails
- extracted source facts
- brand profile
- deck map/context
- ready_for_llm flag

### db_publisher

Owns final publication of readiness states:

- `smart_deck_ready`
- later preview/apply/export phases

The publisher must remain the only stage that publishes final workflow readiness.

## LLM gate

Smart Deck generation should only be queued after workflow state reaches a ready phase such as `smart_deck_ready`, `preview_ready`, `applied`, or `export_ready`.

Generation must use SmartDeckContext as the canonical input. It should not read raw deck state directly or generate from partial extraction state.

## Super admin observability

Super admin views should show every workflow job status:

- queued
- running
- completed
- failed_retryable
- failed_final
- blocked
- timed_out

They should also show artifacts, failure messages, worker ownership, retry status, and the current workflow phase.

## Deployment verification

After deploy, verify the runtime sequence:

```bash
python - <<'PY'
from app.services.deck_processing import workflow_jobs
print(workflow_jobs.SOURCE_PIPELINE_JOB_SEQUENCE)
PY
```

Expected output:

```txt
['source_ingestion', 'source_extraction', 'miniatures', 'brand_extraction', 'smart_deck_context', 'db_publisher']
```

Then upload one deck and verify:

1. `source_extraction` completes.
2. `miniatures` completes.
3. `brand_extraction` completes.
4. `smart_deck_context` completes.
5. `db_publisher` publishes `smart_deck_ready`.
6. Smart Deck generation can then be queued.

## Non-goals for this PR

This PR does not introduce PySpark.
This PR does not replace the durable workflow job queue.
This PR does not implement market research, competitor research, founder research, or external enrichment workers.
