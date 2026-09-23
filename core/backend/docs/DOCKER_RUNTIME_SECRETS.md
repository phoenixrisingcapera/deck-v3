# Docker runtime secrets

This backend should receive production secrets from Railway at container runtime, not during image build.

## Problem fixed

Railway/Nixpacks can generate a Dockerfile that declares service variables as build `ARG` and `ENV` values. Docker then warns that sensitive values are being used in build-time instructions.

The backend now includes an explicit `Dockerfile` that does not declare application secrets as build args or image env values.

## Runtime rule

The image build should install dependencies and compile static knowledge artifacts only.

Runtime values such as auth signing secrets, AI provider keys, database URLs, and bucket credentials must be injected by Railway when the container starts.

## Start command

Both Railway config files now use:

```bash
python scripts/start_railway.py
```

This keeps startup behaviour consistent across Railway config readers.

## Do not add to Dockerfile

Do not add application secrets to the Dockerfile via `ARG` or `ENV`.

Only non-secret Python/container defaults should live in the Dockerfile, such as:

- `PYTHONDONTWRITEBYTECODE`
- `PYTHONUNBUFFERED`
- `PIP_NO_CACHE_DIR`
