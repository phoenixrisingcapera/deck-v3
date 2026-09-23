# Product vs admin backend route boundaries

DeckAiStack separates user workflow routes from admin/control-plane routes at
registration time.

## Product route registration

Product route registration lives in:

```text
app/api/routes/product/__init__.py
```

These routers serve user-facing behavior:

- upload deck
- workflow-state / processing
- Smart Deck workspace
- generation and apply version
- exports
- product analytics
- workspace summary and AI provider settings

Product routes should not expose admin-only diagnostics or worker controls.

## Admin route registration

Admin route registration lives in:

```text
app/api/routes/admin/__init__.py
```

These routers serve control-plane behavior:

- failure tickets
- deployment readiness
- admin operations
- admin user management
- provider/knowledge diagnostics
- product analytics for operators

Admin routes must keep their super-admin route guards. The failure-ticket report
endpoint remains separately registered because it intentionally accepts reports
without the global resource-access dependency.

## Current boundary status

This first pass separates route registration without physically renaming every
route module. Existing imports such as `app.api.routes.products` remain stable
for tests and route-level unit coverage.

Known follow-up:

- Move product route modules into `app/api/routes/product/` once tests stop
  importing the old flat paths directly.
- Move admin route modules into `app/api/routes/admin/` after adding
  compatibility shims or updating direct imports.
- Add a contract test that fails if admin routes are registered through the
  product route list.
