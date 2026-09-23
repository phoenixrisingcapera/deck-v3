# `app/workers/generation_runtime.py`

## Purpose

Worker runtime handlers for generation-adjacent workflow jobs.

## Features Owned

- LLM generation completion
- Schema validation completion
- Preview render completion
- Apply-version completion
- Compile-final completion

## Exports / Entry Points

- `handle_llm_generation`
- `handle_schema_validation`
- `handle_preview_render`
- `handle_apply_version`
- `handle_compile_final_deck`

## Variables / Constants Owned

- No major file-local configuration constants in the audited section

## Inputs

- Claimed `WorkflowJob`
- Worker id
- Job payload and dependency outputs

## Outputs

- Completed workflow job status
- Job `output_payload` consumed later by frontend or publisher stages

## Upstream / Downstream Coupling

- Upstream: `job_handlers.py`
- Downstream: `set_workflow_job_status`, `prepare_full_deck`, design-version services

## Audit Notes

- `handle_compile_final_deck` reuses the existing synchronous compiler instead of duplicating compile logic.
- The critical contract here is writing `compiledDeckId` and `finalDeckId` into `job.output`.
