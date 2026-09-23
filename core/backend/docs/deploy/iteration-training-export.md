# Iteration Training Export

## Purpose

Exports archived or review-complete iteration snapshots from the product database into a separate training database.

## Required Environment Variables

- `TRAINING_EXPORT_ENABLED=true`
- `TRAINING_DATABASE_URL=<separate training database url>`
- `TRAINING_EXPORT_BATCH_SIZE=50`

## Workspace Policy Gate

Snapshots only export when the workspace has:

- `allow_model_training = true`
- `model_training_policy != disabled`

## Manual Run

```bash
python scripts/export_iteration_training_snapshots.py
```

## Railway Service Role

Use `railway.training-export.toml` for a dedicated export service.

Recommended service behavior:

1. Run as a separate Railway service.
2. Trigger on a schedule or cron.
3. Keep `restartPolicyType = NEVER` for one-shot export execution.

## Export States

- `pending`: snapshot is queued for export
- `blocked`: workspace policy disallows training export
- `exported`: snapshot has been written to the training database

## Admin Endpoints

- `GET /api/admin/training/iteration-snapshots`
- `POST /api/admin/training/export-pending`
- `PATCH /api/admin/workspaces/{workspace_id}/training-policy`
