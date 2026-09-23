# Railway pre-deploy recovery

Railway was still failing at `Deploy > Pre deploy command` even though the repository start command now owns migrations through `scripts/start_railway.py`.

## Current rule

Only one place should run migrations:

```bash
python scripts/start_railway.py
```

That script runs Alembic and runtime schema repair before starting the API.

## Pre-deploy command

The repository now points Railway pre-deploy to a no-op:

```bash
python scripts/railway_predeploy_noop.py
```

This prevents Railway from running a second migration path before startup.

## If Railway UI still has an old command

Open Railway:

```text
dddecks-backend -> Settings -> Deploy -> Pre-deploy command
```

Replace any old command such as:

```bash
alembic upgrade head
APP_ROLE=migration alembic upgrade head && APP_ROLE=migration python scripts/repair_production_schema.py
```

with:

```bash
python scripts/railway_predeploy_noop.py
```

or clear the field completely if Railway allows it.

## Why

Running migrations from both Railway pre-deploy and runtime startup causes duplicate schema work and can fail when columns or indexes already exist.
