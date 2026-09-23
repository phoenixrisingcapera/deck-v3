# Selected-Slide Iteration Generation

## Deleted Architecture

**PySpark / Spark / distributed parallelization is removed.**

### Why

PySpark was the wrong tool for DeckAiStack:

- **Wrong abstraction**: The app is not doing large distributed dataframe computation.
- **Unnecessary infrastructure**: Requires Java runtime, SparkSession per job (~15s overhead), and a separate Docker image (`Dockerfile.pyspark`).
- **Rate-limit bottleneck**: The actual constraint is LLM provider rate limits, schema validation, and review UX — not CPU or data throughput.
- **Deployment complexity**: Adding PySpark to the worker fleet increases build time, image size, and operational surface.
- **Confuses source pipeline with generation pipeline**: The source pipeline (ingestion → extraction → context) is deterministic and runs once per upload. Generation is user-initiated, per-selection, and iterative. They should not share the same runtime model.

### Removed

| Item | Reason |
|---|---|
| `Dockerfile.pyspark` | PySpark worker image, unused |
| `requirements-pyspark.txt` | PySpark dependency pinning |
| `SparkSession`, `spark-submit` | Spark runtime code |
| `llm_parallelization` naming | Misleading name implying distributed compute |
| `_spark_session()`, `_execute_pyspark()` | Dead PySpark execution paths |
| `llm_parallelization_mode` config | Allowed `"pyspark"` as a valid mode |

---

## Preserved Architecture

### Selected-Slide Iteration Generation

The product **still requires** concurrent processing when a user selects multiple slides.

### Correct flow

```txt
Upload deck
→ source ingestion
→ source extraction
→ miniatures
→ brand extraction
→ smart_deck_context
→ db_publisher
→ smart_deck_ready
→ selected-slide generation
→ schema validation
→ preview/review batch
→ user accept/reject
→ apply version
→ export
```

### Hard rule

**No LLM generation may start before `SmartDeckContext` exists.**

### How it works

1. **SmartDeckContext first**: The source pipeline must complete and publish `smart_deck_ready` before any generation is allowed.
2. **Parent GenerationRun**: When a user selects slides and issues a prompt, the backend creates a parent generation run.
3. **One SlideGenerationJob per selected slide**: Each selected slide gets its own child job.
4. **Bounded concurrency**: Jobs run in rounds controlled by `MAX_CONCURRENT_SLIDE_GENERATIONS` (default: 3).
5. **Per-slide validation**: Each slide validates independently.
6. **Partial success**: If 8 of 10 slides succeed, the 8 successful proposals are preserved. The 2 failed slides can be retried.
7. **Reviewable iteration**: All proposals are grouped into a reviewable iteration/version set. Nothing applies silently.
8. **No silent overwrite**: The original deck is never modified without explicit user acceptance.

### Iteration examples

**User selects 4 slides:**
```txt
→ 4 child jobs
→ all run in parallel (within concurrency limit)
→ grouped into one review batch
```

**User selects 10 slides (MAX_CONCURRENT_SLIDE_GENERATIONS=3):**
```txt
Round 1: slides 1, 2, 3
Round 2: slides 4, 5, 6
Round 3: slides 7, 8, 9
Round 4: slide 10
→ successful slides preserved
→ failed slides can be retried independently
```

### Future contract

```txt
GenerationRun
- id
- deck_id
- mode: smart_deck | smart_edit | due_diligence
- prompt
- selected_slide_ids
- status: queued | running | partial | completed | failed
- total_slides
- completed_slides
- failed_slides
- created_by
- created_at

SlideGenerationJob
- id
- generation_run_id
- deck_id
- source_slide_id
- status: queued | running | completed | failed
- input_context_json
- output_render_schema_json
- warnings_json
- assumptions_json
- source_fact_ids
- confidence
- error_message

SlideVersion
- id
- deck_id
- source_slide_id
- generation_run_id
- render_schema_json
- status: proposed | accepted | rejected | failed

DesignVersion / ReviewBatch
- id
- deck_id
- generation_run_id
- label
- status: proposed | partially_accepted | accepted | rejected
```

### Configuration

| Setting | Default | Description |
|---|---|---|
| `MAX_CONCURRENT_SLIDE_GENERATIONS` | 3 | Maximum slides processed in one round |
| `MAX_SELECTED_SLIDES_PER_BATCH` | 10 | Maximum slides per iteration request |
| `ALLOW_PARTIAL_BATCH_SUCCESS` | true | Whether failed slides fail the whole batch |
| `MAX_REPAIR_ATTEMPTS_PER_SLIDE` | 1 | Maximum retry attempts per failed slide |

### Naming

Do not use:

- `parallelization`
- `pyspark`
- `spark batch`
- `distributed generation`

Use:

- `selected-slide iteration generation`
- `bounded slide concurrency`
- `GenerationRun`
- `SlideGenerationJob`
- `DesignVersion`
- `ReviewBatch`
