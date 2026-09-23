FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        clamav \
        clamav-freshclam \
        libreoffice \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# The API fails closed when ClamAV cannot scan. Bake a real signature database
# into the immutable image so customer uploads are scanned instead of rejected
# because the slim base image contains only the scanner binary.
RUN freshclam --stdout \
    && find /var/lib/clamav -maxdepth 1 -type f \( -name '*.cvd' -o -name '*.cld' \) -size +0c -print -quit | grep -q . \
    && clamscan --version

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1
RUN pip install -r requirements.txt
RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

# Railway service settings can override railway.toml and still run
# `alembic upgrade head` as a pre-deploy command. Suppress that CLI call on
# Railway only; runtime migrations still run via `python -m alembic` from
# scripts/start_railway.py.
RUN if [ -x /usr/local/bin/alembic ]; then mv /usr/local/bin/alembic /usr/local/bin/alembic.real; fi \
    && printf '%s\n' \
        '#!/bin/sh' \
        'if [ "$1" = "upgrade" ] && [ "$2" = "head" ] && { [ -n "${RAILWAY_ENVIRONMENT:-}" ] || [ -n "${RAILWAY_ENVIRONMENT_ID:-}" ] || [ -n "${RAILWAY_SERVICE_NAME:-}" ] || [ -n "${RAILWAY_PROJECT_ID:-}" ]; }; then' \
        '  echo "Railway pre-deploy alembic CLI suppressed; migrations run from scripts/start_railway.py."' \
        '  exit 0' \
        'fi' \
        'exec python -m alembic "$@"' \
        > /usr/local/bin/alembic \
    && chmod +x /usr/local/bin/alembic

COPY . ./

RUN groupadd --system deckapp && useradd --system --gid deckapp --home-dir /app deckapp \
    && chown -R deckapp:deckapp /app

RUN python llm_knowledge/deck_archetype_knowledge/scripts/compile_deck_archetypes.py \
    --src llm_knowledge/deck_archetype_knowledge/source_md \
    --out llm_knowledge/deck_archetype_knowledge/compiled_json

# Refresh after source COPY so each source release checks current signatures,
# instead of reusing the dependency layer's older signature database.
RUN freshclam --stdout && clamscan --version

USER deckapp

# Bake the release identity into the image; runtime environment labels alone
# cannot prove which source was built by a CLI upload.
ARG DECK_BUILD_COMMIT=development
RUN printf '%s\n' "$DECK_BUILD_COMMIT" > /app/BUILD_REVISION

CMD ["python", "scripts/start_railway.py"]
