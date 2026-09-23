# Railway service split

This document defines the explicit Railway service split for the current
pipeline architecture. The goal is to avoid one coarse worker and keep the
backend jobs isolated by responsibility.

## Repos

- Backend: `deck-backend-rescue`
- Frontend: `deck-frontend-rescue`

## Frontend service

| Service name | Repo | Start command | Notes |
|---|---|---|---|
| `deck-frontend-web` | `deck-frontend-rescue` | `npm start` | SvelteKit app. Reads backend workflow-state only. |

## Backend API service

| Service name | Repo | Start command | Role | Notes |
|---|---|---|---|---|
| `deck-backend-api` | `deck-backend-rescue` | `python scripts/start_railway.py` | `api` | Serves FastAPI routes and canonical workflow endpoints. |

## Backend worker services

Use one Railway service per durable worker role. All of them can reuse the same
repository and the same worker bootstrap, but each service must set its own
`APP_ROLE`.

| Service name | Repo | Start command | `APP_ROLE` | Job types owned |
|---|---|---|---|---|
| `worker-source-ingestion` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-source-ingestion` | `source_ingestion` |
| `worker-source-extraction` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-source-extraction` | `source_extraction` |
| `worker-miniatures` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-miniatures` | `miniatures` |
| `worker-brand-extraction` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-brand-extraction` | `brand_extraction` |
| `worker-smart-deck-context` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-smart-deck-context` | `smart_deck_context` |
| `worker-db-publisher` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-db-publisher` | `db_publisher` |
| `worker-llm-generation` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-llm-generation` | `llm_generation` |
| `worker-schema-validation` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-schema-validation` | `schema_validation` |
| `worker-preview-render` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-preview-render` | `preview_render` |
| `worker-apply-version` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-apply-version` | `apply_version` |
| `worker-export` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-export` | `export` |
| `worker-stale-job-rescuer` | `deck-backend-rescue` | `python scripts/start_railway.py` | `worker-stale-job-rescuer` | recovery only |

## Shared backend environment

Set these on the backend API and all worker services:

- `DATABASE_URL`
- storage credentials and bucket config
- auth/session config
- any provider keys needed by the specific worker group
- `RUN_MIGRATIONS_ON_STARTUP=true` only on the API service, unless you
  explicitly want worker-side migrations

## Recommended create order

1. Backend API
2. Frontend web
3. `worker-source-ingestion`
4. `worker-source-extraction`
5. `worker-miniatures`
6. `worker-brand-extraction`
7. `worker-smart-deck-context`
8. `worker-db-publisher`
9. `worker-llm-generation`
10. `worker-schema-validation`
11. `worker-preview-render`
12. `worker-apply-version`
13. `worker-export`
14. `worker-stale-job-rescuer`

## Notes

- The backend worker bootstrap already maps `APP_ROLE` to the correct durable
  job type.
- The frontend should not run extraction or generation locally.
- Smart Deck becomes available only when the backend reports the canonical
  workflow state as ready.
- This split is intentional: each worker service should own one job family so
  failures, retries, and scaling are isolated.

## Live Railway state

Implemented on the production Railway project `lovely-ambition` in the
production environment.

- `deck-backend-api` is the production API service from
  `phoenixrisingcapera/deck-Aistack-backend-new` on the consolidated `main`
  branch with `APP_ROLE=api`.
- `deck-frontend-web` is the production frontend service from
  `phoenixrisingcapera/deck-Aistack-front-new` on the consolidated `main`
  branch.
- `deck.aistack.codes` is attached to `deck-frontend-web` and verified.
- `api.deck.aistack.codes` is attached to `deck-backend-api` and verified.
- The backend worker services are separate Railway services from the same
  backend repo, with `APP_ROLE` and `WORKER_KIND` set per service to the job
  family listed above.
