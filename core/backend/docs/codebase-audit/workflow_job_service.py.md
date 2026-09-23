# `app/services/workflow_job_service.py`

## Purpose

Low-level durable workflow job model helper for job creation, status transitions, dependency management, and phase mapping.

## Features Owned

- Workflow job type constants
- Workflow status constants
- Phase mapping by job type and status
- Job creation and reuse
- Durable event append

## Exports / Entry Points

- `JOB_TYPE_*` constants
- `workflow_job_phase`
- `workflow_job_progress`
- `ensure_workflow_job`

## Variables / Constants Owned

- `JOB_TYPE_COMPILE_FINAL_DECK`
- `CLAIMABLE_JOB_STATUSES`
- `TERMINAL_JOB_STATUSES`
- `PUBLISHABLE_WORKFLOW_PHASES`

## Inputs

- Deck model
- Requested job type
- Input payload
- Existing job status

## Outputs

- Durable `WorkflowJob` rows
- Workflow phase tokens such as `compile_final_running` and `compiled_deck_ready`
- Workflow events

## Upstream / Downstream Coupling

- Upstream: orchestration services and workers
- Downstream: `workflow_jobs` table and worker claim logic

## Audit Notes

- If a new job type is missing here, the rest of the worker pipeline can appear wired but still mis-report phases or fail contract checks.
