# Railway Full Test Runner

`deck-full-test-runner` is an isolated Railway service using the backend image
with `APP_ROLE=full-test`. It does not receive database URLs and never runs
migrations directly.

On every deployment it:

1. runs the backend contract matrix inside Railway;
2. checks deployed frontend/backend health;
3. authenticates with an isolated tester account;
4. uploads a generated four-slide PDF;
5. waits for durable source processing and verifies a miniature;
6. runs real Qwen Smart Deck generation and validates render-schema JSON;
7. generates, reloads, accepts, and verifies Smart Edit persistence;
8. runs Due Diligence and verifies reloadable history.

For terminal release evidence that must not call a paid provider, set:

```env
RAILWAY_FULL_TEST_NON_PROVIDER_ONLY=true
RAILWAY_FULL_TEST_REMOTE_ENABLED=false
```

That mode runs the isolated local contract matrix, including workspace
credential isolation and production fail-closed readiness checks, and records
the deployed product smoke as intentionally blocked. It never authenticates,
uploads, generates, edits, or invokes a provider.

The redacted result is exposed at:

```text
/api/full-test-report
```

Required service variables:

```env
APP_ENV=production
APP_ROLE=full-test
RAILWAY_FULL_TEST_REMOTE_ENABLED=true
DECK_AISTACK_SMOKE_BASE_URL=https://api.example.com
DECK_AISTACK_SMOKE_FRONTEND_URL=https://example.com
DECK_TESTER_EMAIL=isolated-test-user@example.com
DECK_TESTER_PASSWORD=<secret>
```

Do not attach `DATABASE_URL` or `AI_DATABASE_URL` to this service. Product data
is accessed only through authenticated APIs and is confined to the tester's
workspace.
