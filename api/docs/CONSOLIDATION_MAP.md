# Consolidation Map

## Completed In This Pass

- Moved unused worker entrypoint stubs to `app/workers/legacy/`.
- Moved unused service re-export shims to `app/services/legacy/`.
- Moved unused extractor agents to `app/agents/legacy/`.
- Moved old slide-generation provider files to `app/services/generation/legacy/` and updated active imports.
- Added `app/core/utils.py` for shared utility functions:
  - `safe_read_json`
  - `read_json_payload`
  - `safe_filename`
  - `request_id`
- Removed eager service imports from `app/services/__init__.py` to avoid DB engine setup during unrelated package imports.
- Updated tests to import concrete service modules instead of package-level re-exports.

## Active Runtime Paths

- Worker runtime: `app/workers/entrypoints/`, `app/workers/dispatch/`, `app/workers/runtime/`.
- LLM strategy: `app/services/llm/qwen_strategy.py`, provider transports in `app/services/llm/`.
- Upload filename normalization: `app/core/utils.py::safe_filename`.
- Request ID extraction: `app/core/utils.py::request_id`.

## Intentionally Deferred

- Splitting `app/services/llm/generation_service.py` and `app/services/admin/operations.py` requires a dedicated refactor pass with broader tests.
- Full provider hierarchy unification is deferred because both `app/services/llm/` and `app/ai_orchestration/providers/` are active.
- DB-backed tests require local `psycopg` or a matching test DB environment.
