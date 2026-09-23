# How to use this pack with Codex

Use one prompt at a time. Do not ask Codex to implement the entire product at once.

Recommended order:

1. `prompts/09_codex_github_readiness.md`
2. `prompts/05_codex_guardrail_verifier.md`
3. `prompts/03_codex_editor_runtime_integration.md`
4. `prompts/04_codex_backend_boundary.md`
5. `prompts/08_codex_review_matrix.md`
6. `prompts/06_codex_access_sharing.md`
7. `prompts/07_codex_data_assets.md`

Each Codex pass should end with:

```txt
npm run typecheck
npm run build
npm run lint, if available
```

For backend work, each pass should end with the backend test command that exists in that repo.

Do not accept answers that only say pages exist. Require build/typecheck status and architecture drift findings.
