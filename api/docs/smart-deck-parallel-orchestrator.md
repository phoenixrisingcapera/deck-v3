# Smart Deck parallel orchestrator boundary

## Problem

The Smart Deck workflow currently has too much work coupled to request/response and UI state. The frontend should display persisted workspace state and submit commands. It should not coordinate expensive work.

The backend also has route-level background threads for generation jobs. This is acceptable for a prototype, but it is not a production orchestration model because jobs can be lost on process restart, DB writes can race, and the UI cannot reliably know which stage is blocked.

## Required production boundary

Use an explicit orchestration service with durable jobs and stage-level status.

```txt
Upload accepted
  -> deck_intake_job
  -> slide_extraction_job per slide
  -> source_fact_job per slide/block
  -> research_agent_job per topic/deck
  -> content_agent_job per slide or selected-slide group
  -> slide_render_job per generated slide
  -> artifact_persist_job per render/code/thumbnail artifact
  -> workspace_publish_job
  -> frontend reads published workspace snapshot
```

## Parallel work units

| Work unit | Parallelism key | Owner | Output |
| --- | --- | --- | --- |
| Slide extraction | `deck_id + slide_number` | extraction worker | source slide, blocks, preview image |
| Research agent | `deck_id + research_topic` | research worker | research artifact and cited findings |
| Content agent | `deck_id + source_slide_id` or selected group | LLM worker | slide claims, rewrite plan, source fact IDs |
| Slide render production | `deck_id + generated_slide_id` | render worker | render schema, generated elements, code version |
| Artifact persistence | `artifact_id` | artifact worker | bucket key, signed URL metadata |
| DB publish | `deck_id + workspace_version` | orchestrator | atomic workspace state visible to frontend |

## PySpark boundary

Use PySpark only for batch-style or distributed data processing:

- large-deck text/block extraction normalization
- embedding preparation at scale
- clustering across many decks
- nightly analytics over artifacts, facts, and traces
- offline evaluation and regression promotion

Do not use PySpark for frontend work or live transactional DB writes. Live DB writes should stay in the API/worker service with SQLAlchemy transactions, idempotency keys, and row-level job status. Spark can write analytical tables or staging outputs, but the orchestrator should publish to the product database.

## LLM service boundary

Create a dedicated LLM worker/orchestrator service rather than running generation inside the frontend route.

Required tables or equivalent models:

- `deck_workflow_runs`
- `deck_workflow_jobs`
- `deck_workflow_job_dependencies`
- `deck_workflow_artifacts`
- `deck_workspace_snapshots`

Each job must have:

- `id`
- `deck_id`
- `job_type`
- `status`: queued, running, completed, failed, dead_letter
- `idempotency_key`
- `input_json`
- `output_json`
- `error_json`
- `attempt_count`
- `created_at`, `started_at`, `completed_at`

## Frontend contract

The frontend should only call:

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflow-command`
- `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`
- `GET /api/decks/{deck_id}/smart-deck`
- `GET /api/decks/{deck_id}/generated-slides/{generated_slide_id}/code`

The frontend content viewer must render from persisted `renderSchema` or source slide preview URLs only. If `activeGeneratedSlideId` is missing but a current or preview design version has generated slides, the frontend must deterministically select the first renderable slide rather than showing an empty viewer.

## Release rule

The product is not release-ready until one uploaded deck can move through:

```txt
Upload -> Extract -> Persist source slides -> Generate research/content -> Generate render schemas -> Publish workspace -> Viewer displays slide -> Save iteration
```

without frontend polling loops starting backend work and without route-level background threads being the only job runner.
