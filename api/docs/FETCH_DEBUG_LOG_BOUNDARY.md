# Fetch debug log boundary

The browser may show `Fetch finished loading` and `Fetch failed loading` messages when DevTools verbose logging is enabled. Those messages are browser/client diagnostics and should not be implemented in backend runtime code.

## Backend rule

Backend services should use structured Python logging, request IDs, and failure tickets. Backend code must not add browser-style fetch instrumentation such as:

- `window.fetch`
- `console.log`
- `console.debug`
- `Fetch finished loading`
- `Fetch failed loading`

## Frontend boundary

If frontend app-level fetch diagnostics are needed, they must be gated by the frontend helper and disabled in production unless explicitly enabled.

## Verification

Run:

```bash
python scripts/verify_fetch_debug_log_boundary.py
python -m pytest tests/test_fetch_debug_log_boundary.py -q
```
