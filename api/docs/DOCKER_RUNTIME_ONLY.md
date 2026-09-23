# Docker runtime-only environment policy

Railway should inject application configuration when the container starts, not while the image is being built.

## What changed

This repository now has an explicit `Dockerfile`.

The Dockerfile only sets non-application Python/container defaults:

- `PYTHONDONTWRITEBYTECODE`
- `PYTHONUNBUFFERED`
- `PIP_NO_CACHE_DIR`

Application configuration remains in Railway runtime variables.

## Why

Nixpacks generated a Dockerfile that declared many Railway service variables as build-time arguments and image environment values. Docker warned about that because application configuration should not be baked into the image.

## Runtime start command

Railway should start the backend with:

```bash
python scripts/start_railway.py
```

## Verification

Run:

```bash
python scripts/verify_docker_runtime_only.py
```

The script fails if the Dockerfile starts using `ARG` or unexpected `ENV` keys.
