# Railway Service Trim - 2026-07-08

## Context

Production deployments were stuck behind Railway queue messages such as `Waiting for deployment slot`. The project also had duplicate web/API services and several nonessential worker services running or queued. The goal was to reduce compute/deployment pressure without deleting databases or persistent volumes.

## Scope

Project: `lovely-ambition`

Project ID: `5b6efec3-7cdb-48f4-a302-dc9fa95eca08`

Environment: `production`

Environment ID: `0b8c57af-c156-4524-ba1e-92c525561e37`

## Removed Services

These services had no persistent volumes and were removed from the production environment:

| Service | ID | Reason |
| --- | --- | --- |
| `dddecks-backend` | `183a425a-559b-498f-b789-aad7cc4bb9de` | Duplicate/legacy backend. Canonical backend is `deck-backend-api`. |
| `deck-Aistack-front-new` | `2da18c65-35ba-4004-8610-840a2309e787` | Duplicate frontend. Canonical public frontend is `deck-frontend-web`. |
| `training-export` | `7987ad0a-05fc-45fc-b720-e618a3a8cbcf` | Nonessential during launch/debug. |
| `worker-db-publisher` | `0ad2aaa8-1818-4f29-beb8-75af7d65de9c` | Nonessential during launch/debug. |
| `worker-exports-publisher` | `9e2c067d-60bc-486a-946e-60621c64601a` | Extra export worker; not required for upload/auth recovery. |
| `worker-generation-pipeline` | `ab35e70f-6501-400c-a179-753b73442cd5` | Extra generation worker; keep one source worker while stabilizing. |
| `worker-llm-generation` | `ac167ee5-1385-497c-ac3e-36255e9570c5` | Extra LLM worker; not required for upload/auth recovery. |
| `worker-stale-job-rescuer` | `7fdad7a7-4854-497d-bfc1-7dce2b307d0b` | Nonessential during launch/debug. |

## Retained Services

These services remain in production:

| Service | Purpose |
| --- | --- |
| `deck-backend-api` | Canonical backend API at `api.deck.aistack.codes`. |
| `deck-frontend-web` | Canonical public frontend at `deck.aistack.codes`. |
| `deck-primary-db` | Main app database. |
| `deck-user-db` | Auth/user database. |
| `deck-self-training-db` | Vector/training database, kept separate because pgvector work can slow app DB workloads. |
| `deck-billing-db` | Billing database. Can be consolidated later if needed, but was not touched. |
| `worker-source-pipeline` | Single retained worker for source/deck processing. |
| `deck-admin-console` | Admin console, retained for operational visibility. |
| `superadmin-aistack` | Superadmin surface, retained for operational visibility. |

## Deployment State After Trim

The service count is smaller, but Railway deployment slot backlog may still persist until the platform clears queued deployments. At the time of trim, `deck-backend-api` still showed queued deployments with `Waiting for deployment slot`.

## Important Production Fixes Waiting On Queue

The following fixes were committed and pushed before/around the trim and may still require Railway to promote queued deployments:

| Repo | Commit | Summary |
| --- | --- | --- |
| Backend | `8841c68` | Mirrors authenticated users into the app DB before deck upload persistence. |
| Frontend | `a317be4` | Guides existing users from sign-up to sign-in with the email prefilled. |

## Restore Notes

Removed services can be recreated from their repos/configs if needed, but they were intentionally not retained during launch stabilization. Prefer adding back only one worker at a time.

Recommended restore order if capacity improves:

1. Add or restore the specific worker needed for a proven bottleneck.
2. Verify deploy health and app behavior.
3. Avoid restoring duplicate public frontend/backend services unless there is a deliberate staging or migration reason.

## Target Lean Production Shape

Short-term target shape:

| Category | Services |
| --- | --- |
| Web | `deck-frontend-web`, `deck-backend-api` |
| Databases | `deck-primary-db`, `deck-user-db`, `deck-self-training-db`, optional `deck-billing-db` |
| Workers | `worker-source-pipeline` only while stabilizing |
| Admin | Keep only if needed for launch operations |

This keeps pgvector/training isolated from the app DB while reducing duplicate compute services and deployment pressure.
