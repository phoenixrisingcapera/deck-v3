# `app/services/deck_workflow_service.py`

## Purpose

Backend orchestration layer that turns workflow API requests into durable workflow jobs and exposes workflow state.

## Features Owned

- Workflow state assembly
- Source extraction queueing
- Smart Deck generation queueing
- Apply/export queueing
- Compile-final queueing
- Idempotency handling for workflow requests

## Exports / Entry Points

- `get_deck_workflow_state`
- `queue_source_extraction`
- `queue_smart_deck_generation`
- `queue_apply_design_version`
- `queue_export`
- `queue_compile_final_deck`

## Variables / Constants Owned

- `WORKFLOW_READY_PHASES`
- `SOURCE_PIPELINE_MAX_ATTEMPTS`

## Inputs

- ORM deck and batch lookups
- Typed workflow payloads
- Existing workflow jobs for idempotency reuse

## Outputs

- Accepted workflow job payloads
- Normalized workflow state structures
- Conflict or validation errors

## Upstream / Downstream Coupling

- Upstream: `deck_workflow.py`
- Downstream: `workflow_job_service.py`, DB models, generation/provider services

## Audit Notes

- `queue_compile_final_deck` is the bridge that turns final compilation into a durable worker-backed action.
- The idempotency key ties compile behavior to a concrete batch and compile inputs.
