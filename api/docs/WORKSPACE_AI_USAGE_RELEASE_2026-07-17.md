# Workspace AI Usage Release

## Summary

This release adds an authenticated workspace AI usage summary and mounts it in
the product Utilities bar. It reports application-tracked token and generation
usage without presenting the application safety budget as Alibaba account
quota.

## Canonical Wiring

- Mounted UI: frontend `src/lib/components/UtilitiesBar.svelte`
- Frontend proxy: `GET /api/settings/workspace/ai-provider/usage`
- Backend route: `GET /api/settings/workspace/ai-provider/usage`
- Backend service: `get_workspace_ai_usage_summary()`
- Telemetry source: workspace- and user-scoped `AgentTelemetryEvent` rows
- Request quota source: user-scoped `AiUsageBucket` daily generation window

The endpoint requires the existing authenticated session and resolves only a
workspace owned by the current user. Provider account quota remains explicitly
`not_exposed`; the UI labels tracked values as partial application telemetry.

## Published Commits

- Backend: `4810c17` (`feat: workspace AI usage summary with concurrency-safe token tracking`)
- Frontend: `d1430b4` (`feat: workspace AI usage UI panel with authenticated proxy`)
- Frontend deployed revision containing the UI commit: `4dad264`

## Verification

- Backend focused suite: 16 tests passed.
- Backend `compileall` and `git diff --check` passed.
- Frontend workspace-provider and Utilities placement contracts passed.
- Frontend Svelte check passed.
- Frontend production build passed.
- Railway frontend deployment for `4dad264` succeeded.
- Production frontend health returned HTTP 200.

## Deployment And Rollback

Railway deploys the backend API/workers and frontend from their canonical
GitHub `main` branches. Rollback should redeploy the prior successful revision;
no migration or destructive data operation is required for this additive
endpoint and UI panel.

## Remaining Risks

- Usage coverage is intentionally partial because only instrumented provider
  calls contribute token counts.
- Alibaba account quota is not exposed by the current provider API and must not
  be inferred from the application safety budget.
- Authenticated browser confirmation is required to inspect workspace-specific
  production values; public requests must remain unauthorized.
