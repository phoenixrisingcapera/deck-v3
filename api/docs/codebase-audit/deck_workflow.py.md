# `app/api/routes/deck_workflow.py`

## Purpose

Backend API surface for durable deck workflow commands and workflow state reads.

## Features Owned

- Workflow state read route
- Workflow command dispatch
- Source extraction queue route
- Smart Deck generation queue route
- Brand extraction route
- Export/apply queue routes
- Compile-final queue route

## Exports / Entry Points

- `deck_workflow_state`
- `deck_workflow_command`
- `start_source_extraction_workflow`
- `start_compile_final_workflow`

## Variables / Constants Owned

- `router`

## Inputs

- Authenticated `deck_id`
- Typed workflow payloads
- `PrepareFullDeckRequest`

## Outputs

- `WorkflowCommandAcceptedResponse`
- `DeckWorkflowStateResponse`
- HTTP error payloads for invalid or conflicting requests

## Upstream / Downstream Coupling

- Upstream: frontend workflow proxies and pages
- Downstream: `deck_workflow_service.py`, auth deps, rate limits, guardrails

## Audit Notes

- This file owns API shape, not worker logic.
- Compile-final became mergeable only after this route stopped relying on the synchronous shell endpoint.
