# Railway deck workers

Deck processing runs as dedicated Railway roles from the same backend repo. In
production, identity comes from matching `APP_ROLE`, `WORKER_KIND`,
`DECK_WORKER_JOB_TYPES`, and the known `RAILWAY_SERVICE_NAME`. An explicit kind
cannot override a conflicting service identity.

## API service

Start command:

```bash
APP_ROLE=api python scripts/start_railway.py
```

Role:

```bash
APP_ROLE=api
```

The API accepts uploads and enqueues deck processing runs.

## Worker services

Create a second Railway service from the same repo and Dockerfile.

Start command:

```bash
APP_ROLE=worker python scripts/start_railway.py
```

Each worker must claim only its configured job types. Do not copy every API
variable into every worker.

`APP_ROLE=worker` is required in worker service configuration. As a fail-safe,
known worker `RAILWAY_SERVICE_NAME` values route to the worker when `APP_ROLE`
is absent. Unknown services retain the API default; conflicting known worker
roles fail startup.

### Provider capability matrix

| Role | OpenAI/provider variables | Storage |
|---|---|---|
| API | Allowed for exact provider preflight and explicit API AI work | Required |
| Instant generation (`instant_deck_generation`) | **Required**: `OPENAI_API_KEY`, audited `OPENAI_MODEL`, `DECK_LLM_PROVIDER=openai`, `DECK_GENERATION_MODE=openai` | Required |
| General generation / explicit AI workers | Required only for the provider-backed job types they execute | As required by artifacts |
| Composite source pipeline / dedicated Smart Deck context | Required only while `SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED=true` (the current default) | Required |
| Dedicated ingestion, extraction, brand, and miniature workers | Forbidden; these roles do not resolve provider credentials | Required as needed |
| Schema validation | Forbidden | Required only for artifact validation |
| Preview/render worker | Forbidden | Required |
| DB publisher | Forbidden | Required |
| Stale recovery/maintenance | Forbidden, including `WORKSPACE_AI_FERNET_KEY` | **Required external** S3 or Supabase configuration for cleanup/purge |
| Dedicated renderer | Forbidden | Required |

`full_html_deck.v1` builds its grounded request JSON in
`full_html_generation_service.build_grounded_context_pack`, serializes it in
`generate_full_html_deck`, and uses the inline `_system_prompt()`. There is no
external V2 prompt JSON file to mount. The bundled `prompt_recipe.json` supplies
the upload-first objective, while legacy prompt packages do not own this path.

### Safe production rollout

1. Keep the current release running and remove provider/provider-decryption
   variable names—including `WORKSPACE_AI_FERNET_KEY` and
   `WORKSPACE_AI_FERNET_KEY_VERSION`—from schema validation, DB publisher,
   preview, maintenance, and renderer roles. Inspect and mutate names only.
2. Before deploying this code, set `APP_ROLE=worker`, exact matching
   `WORKER_KIND`, and `DECK_WORKER_JOB_TYPES` on each queue worker. The source
   pipeline uses `APP_ROLE=worker-source-pipeline`, `WORKER_KIND=source_pipeline`,
   and the canonical six source-pipeline job names. The LLM worker lists every
   bounded command job it already owns; it does not own Instant generation or rendering.
   Set only `WORKER_KIND=stale_job_rescuer` plus
   `DECK_WORKER_RECOVERY_ONLY=true` on maintenance; recovery must not claim job types.
3. Configure maintenance with the same canonical external storage backend and
   complete, service-specific bucket-scoped credentials used only for
   checkpoint/artifact cleanup. Configure a custom
   endpoint for non-AWS S3-compatible storage and set
   `UPLOAD_STORAGE_S3_PROVIDER=compatible`; standard AWS S3 uses `aws` and may
   omit an endpoint. Do not attach a local volume as a substitute.
   Custom endpoint hosts must be provider-owned or explicitly listed in
   `INSTANT_HTML_STORAGE_ALLOWED_HOSTS`; endpoints must be clean HTTPS origins
   without credentials, paths, query strings, or fragments. Literal IPs must be
   globally routable; loopback, private, link-local, unspecified, multicast, and
   other non-global IPv4/IPv6 literals are rejected even if allowlisted.
   Hostnames are checked syntactically and by allowlist without DNS resolution;
   runtime network egress controls remain required.
4. Deploy the capability-policy release only after steps 1–3. Production defaults
   directly to enforcement. `WORKER_FORBIDDEN_SECRET_POLICY=audit` is health-only:
   it imports no database/provider runtime, never polls or claims, and always
   returns HTTP 503. It is not healthy staging. Clean variable names first, then
   use enforce. Do not use
   `ALLOW_UNSAFE_PRODUCTION_STARTUP` for the production rollout: worker health
   does not expose detailed errors, and capability/secret/storage violations are
   non-bypassable even when that legacy flag is present. Remove-first is the gate.
5. Confirm provider-free roles have no provider/decryption names, Instant generation keeps
   the OpenAI variables, maintenance storage readiness is green, and all public
   readiness endpoints return HTTP 200.

Never print or copy variable values while performing this rollout. Public health
returns only a coarse readiness status; use internal startup logs/telemetry for
sanitized diagnostics.

Useful variables:

```bash
DECK_WORKER_POLL_INTERVAL_SECONDS=10
DECK_WORKER_STALE_AFTER_SECONDS=900
DECK_WORKER_STALE_RECOVERY_LIMIT=10
DECK_PROCESSING_MAX_ATTEMPTS=3
```

Workers claim queued work only within their explicit capability. The dedicated
stale recovery role recovers stale jobs and performs bounded artifact cleanup.
