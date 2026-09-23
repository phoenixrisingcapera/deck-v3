# Background worker compatibility wrapper

## Purpose

Legacy queue/run entrypoints still exist for compatibility, but they should no longer execute source processing inline.

The durable worker fleet owns execution through `workflow_jobs`. The legacy background wrapper now only delegates to the compatibility projection helper and closes its session.

## Behaviour

When `process_queued_deck_run_in_background(run_id)` runs now, it:

- opens a DB session;
- calls `process_queued_deck_run(db, run_id)` to refresh the compatibility run view from the durable workflow graph;
- does not claim a workflow job;
- does not force any workflow job to `running`;
- does not execute extraction/generation inline;
- closes the DB session.

## Why this matters

This removes the last coarse background path that could behave like a second worker/orchestrator. Durable execution stays with the dedicated workflow workers and stale-job rescuer.

## Verification

Added:

```bash
python -m pytest tests/test_deck_processing_background_failure.py -q
```

Recommended with this slice:

```bash
python -m compileall -q app scripts
python -m pytest tests/test_deck_processing_background_failure.py -q
```
