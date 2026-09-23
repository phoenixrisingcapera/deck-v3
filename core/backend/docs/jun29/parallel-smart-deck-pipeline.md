# Parallel Smart Deck Pipeline

## Problem

The Smart Deck viewer and generation path should not depend on the browser doing heavy orchestration. The frontend should only send commands, display job state, and render persisted artifacts. The backend should own all heavy work and persist every state transition.

The parallelizable work units are:

1. Source slide production
2. Research agent runs
3. Content agent runs
4. Render/schema generation per slide
5. Database writes and artifact persistence

## Boundary rule

PySpark, if used, belongs in backend compute only. It must not run in Svelte, browser code, or frontend server routes.

The frontend contract should remain:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflow-command`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`
- `GET /api/decks/{deck_id}/smart-deck`
- `GET /api/decks/{deck_id}/generated-slides/{generated_slide_id}/code`

The frontend should poll or subscribe to state. It should not coordinate agents directly.

## Recommended service split

```text
Svelte UI
  -> Backend API command boundary
    -> Orchestrator DB job table
      -> Intake worker
      -> Slide production worker pool
      -> Research agent worker pool
      -> Content agent worker pool
      -> Render schema worker pool
      -> Artifact writer / DB writer
        -> Postgres + object storage
```

## Job model

Use a first-class pipeline job model rather than ad hoc background threads.

Recommended tables:

- `workflow_runs`
- `workflow_tasks`
- `workflow_task_dependencies`
- `workflow_artifacts`
- `agent_runs`
- `slide_generation_tasks`
- `db_write_batches`

Every task should have:

- `id`
- `workflow_run_id`
- `deck_id`
- `task_type`
- `status`: `queued | running | completed | failed | retrying | dead_letter`
- `input_json`
- `output_json`
- `artifact_keys_json`
- `error_message`
- `attempt_count`
- `started_at`
- `completed_at`
- `created_at`
- `updated_at`

## Parallel DAG

```text
upload_saved
  -> source_extract
    -> slide_tasks[slide_1..slide_n]
      -> research_agent_tasks[topic/slide]
      -> content_agent_tasks[slide]
      -> render_schema_tasks[slide]
    -> db_write_batch
    -> workspace_ready
```

Parallelizable units:

- Each slide can be processed independently after source extraction.
- Research can run per topic, per slide cluster, or per deck section.
- Content rewriting can run per slide once source facts are available.
- Render/schema creation can run per slide once content is available.
- DB writes should be batched and idempotent after each task emits deterministic task output.

## PySpark fit

PySpark is suitable only if the workload is large enough to justify distributed compute:

- Batch parsing many decks
- Extracting features from many slides
- Embedding large corpora
- Joining slide facts, research facts, and content facts at scale
- Recomputing analytics or quality scores over many artifacts

PySpark is not the first tool for single-user, low-latency interactive generation. For the MVP, a queue + worker pool is usually better:

- Celery/RQ/Arq/Dramatiq for job dispatch
- Postgres for job state
- Redis for queue state if needed
- Separate Railway worker services
- Optional Spark service later for bulk analytics and batch processing

## LLM service contract

The LLM service should expose provider-neutral tasks:

- `research.deck_context`
- `research.slide_facts`
- `content.slide_rewrite`
- `render.slide_schema`
- `critique.render_schema`
- `repair.render_schema`

Each task must receive immutable inputs and return JSON only. The writer persists validated results.

## DB write strategy

Do not write partial objects directly from every agent with uncontrolled shape. Use write batches:

1. Agent emits validated task output.
2. Orchestrator stores output as task artifact.
3. Writer builds a deterministic transaction.
4. Writer upserts generated slides, elements, code versions, design versions, and workspace state.
5. Writer marks `workspace_ready` only after renderable schemas exist.

## Viewer readiness contract

The content viewer should open only when at least one of these is true:

- Source slides exist and can be shown in degraded mode.
- A generated slide exists with `render_schema_json.elements.length > 0`.
- A generated slide code version exists with valid render schema.

Frontend should never show an empty canvas if source or renderable workspace data exists.

## Implementation stages

### PR 1: Viewer reliability

- Resolve active generated slide from current/preview design versions.
- Fallback to `generatedSlide.renderSchema` if `/code` lookup is slow or missing.
- Keep source slide preview visible in degraded mode.

### PR 2: Explicit workflow DAG

- Add `workflow_runs` and `workflow_tasks`.
- Replace route-level thread orchestration with task creation.
- Add workflow state endpoint exposing task progress.

### PR 3: Worker service split

- Create workers for source extraction, slide production, research, content, render schema, and writer.
- Make each worker idempotent.
- Move all long-running LLM calls out of API request lifecycle.

### PR 4: Parallel execution

- Process slide tasks concurrently with bounded worker concurrency.
- Process research and content tasks independently when dependencies are satisfied.
- Batch DB writes through writer tasks.

### PR 5: Optional PySpark backend compute

- Add Spark only for large batch transforms and analytics.
- Keep interactive generation on worker queues unless measured workload requires Spark.

## Non-goals

- Do not put PySpark in frontend routes.
- Do not make the browser orchestrate workers.
- Do not let LLM agents write directly to final tables without validation.
- Do not mark Smart Deck ready without source slides or renderable generated slides.
