# Instant HTML render boundary

Instant HTML is disabled by default. When enabled, the renderer uses a dedicated HTTPS origin and a dedicated `preview_render` worker.

## One-use URL capability

The authenticated API mints a high-entropy capability with a maximum 30-second lifetime. The first credential-free iframe `GET` consumes and revokes it transactionally; replay is denied. Application request logs replace the capability path segment with `[REDACTED]`.

The initial URL path is necessarily visible to infrastructure that terminates HTTP before FastAPI, including Railway ingress. Application redaction cannot erase provider ingress history. Production ingress/access logging for `/api/instant-html-render/*` must therefore be disabled or path-redacted, and its retention restricted. The one-use, short lifetime limits the value of unavoidable path exposure.

## Secret separation

The renderer and preview worker must not receive provider keys, session/auth secrets, billing secrets, `WORKSPACE_AI_FERNET_KEY`, `AI_DATABASE_URL`, or any AI-database alias. They receive the core `DATABASE_URL`, artifact-storage credentials, and `INSTANT_HTML_RENDER_FERNET_KEY`; the purpose-specific render key encrypts sanitized render artifacts and cannot decrypt provider credentials or raw provider checkpoints. The process contract is rechecked immediately before Playwright starts.

Artifact lookup and decryption stay in the dedicated preview worker parent. The sanitized render document and bounded non-secret viewport options are then sent over stdin to an isolated-mode (`python -I`) child using a fixed script path, bounded request/response sizes, and a hard timeout. The child runs from `/tmp`, does not import application settings, and starts Playwright's Node driver and Chromium with an explicit environment containing only `HOME`, `PATH`, locale variables, `TMPDIR`, and `PLAYWRIGHT_BROWSERS_PATH`. Database URLs, storage credentials, render keys, provider/auth/session/billing secrets, and telemetry credentials are absent from the child environment. The document is never placed in command arguments or a persistent tempfile; stdout and stderr are incrementally read under separate hard ceilings and never logged, and timeout cleanup kills and boundedly reaps the child process group.

This is strict environment and IPC isolation **inside the secret-minimal dedicated preview-worker container**, not complete container, kernel, or OS isolation. The parent process in that container still requires the core database, artifact-storage credentials, and render key to fetch/decrypt the sanitized artifact. A malicious or compromised same-container dependency that escapes the child boundary could therefore target the parent process. Linux `no_new_privs` and conservative resource limits are defense-in-depth controls, not a sandbox guarantee. A later stronger boundary is a separate credential-free browser-renderer container that receives only sanitized documents through an authenticated internal transport; that deployment split is not claimed by the current implementation.

`INSTANT_HTML_RENDER_PARENT_ORIGIN` is a single HTTPS origin and is the only CSP `frame-ancestors` value. Storage endpoints must also be clean HTTPS origins and match a supported provider host suffix or `INSTANT_HTML_STORAGE_ALLOWED_HOSTS`. Renderer liveness is `/health/live`; Railway routes only after `/health/ready` verifies the core database migration head, render key/config, and read-only artifact-storage access.

## Unknown non-idempotent provider outcomes

Every transport-unknown POST outcome, including OpenAI, moves the operation to `manual_reconciliation_required`, holds its quota reservation, and blocks its workflow job. `X-Client-Request-Id` and OpenAI `x-request-id` are support-correlation evidence, not deduplication guarantees. A super-admin-only control-plane endpoint records one of three audited decisions: not processed (terminal release), processed with an attached encrypted raw checkpoint (requeue from checkpoint), or processed without an artifact (terminal release). The maintenance reconciler applies the no-artifact release policy after 24 hours so held operations cannot remain charged and nonterminal indefinitely.

Deterministic checkpoint recovery is governed separately by
`docs/instant_html_checkpoint_recovery_runbook.md`. Recovery replay and
publication fail closed unless the current provider binding, request-context
hash, compilation grounding, and committed design/artifact lineage all match.
Legacy context-only publishing recovery has no deploy-time enable switch and is
not available.
