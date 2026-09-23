# Railway Smart Deck Generation Worker Contract

## Goal

Ensure `llm_generation`, `schema_validation`, `preview_render`, and `db_publisher` jobs are actually claimed in Railway instead of sitting queued.

## Preferred deployment

Use dedicated worker service names:

- `worker-llm-generation`
- `worker-schema-validation`
- `worker-preview-render`
- `worker-db-publisher`

This keeps each worker on a single durable job type.

## Legacy generic worker fallback

If Railway still uses one of these service names:

- `deck-processing-worker`
- `deck-processing-worker-service`

then the runtime now supports only two valid modes:

1. Recovery-only rescuer
2. Explicit Smart Deck generation pipeline fallback

### Recovery-only mode

- inferred worker kind: `stale_job_rescuer`
- only for stale-job recovery
- does not claim normal queued generation jobs

### Explicit generation pipeline fallback

Set:

- `DECK_ENABLE_GENERIC_GENERATION_PIPELINE_WORKER=true`

The runtime will then claim:

- `llm_generation`
- `schema_validation`
- `preview_render`
- `db_publisher`

and will auto-set the equivalent multi-job worker contract.

## Fail-fast rule

If a generic Railway worker name is used outside recovery mode without the explicit fallback flag, the worker now raises a runtime error instead of silently stranding queued jobs.

## User-testing implication

For Smart Deck user testing to work, at least one deployed worker path must claim the generation pipeline job types above.
