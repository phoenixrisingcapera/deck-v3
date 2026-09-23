# `app/workers/compile_final_deck_worker.py`

## Purpose

Dedicated worker bootstrap for compile-final jobs.

## Features Owned

- Worker kind selection
- Single-job-type worker configuration

## Exports / Entry Points

- module entrypoint via `main()`

## Variables / Constants Owned

- `WORKER_KIND=compile_final_deck`
- `DECK_WORKER_JOB_TYPES=compile_final_deck`

## Inputs

- Environment variables
- Shared deck queue worker runtime

## Outputs

- Process configured to claim only `compile_final_deck` jobs

## Upstream / Downstream Coupling

- Upstream: Railway process or local worker launch command
- Downstream: `deck_queue_worker.main`

## Audit Notes

- This file exists so compile-final can be deployed as its own worker without broadening another worker's job-type scope.
