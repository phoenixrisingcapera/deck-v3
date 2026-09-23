# Instant Deck recovery frontend release

Frontend publication remains required for the mounted Instant Deck recovery fixes.

- Route entry and revisit remain read-only; generation starts only from explicit **Regenerate**.
- Workflow polling keeps the shared bounded default. Instant Deck explicitly follows accepted work persistently, treats 502/503/504 status outages as reconnectable, and cancels polling on unmount.
- Generation jobs are canonical active-work status. Workspace flags are used only as a conservative lag hint.
- Uncertain status retains one generation intent key and exposes **Check status**, preventing a second command while backend authority is unresolved.
- Upload navigation is outside this release slice.

Required gates: workflow-client contract, Instant Deck contract, `npm run check` with zero errors, production build, and `git diff --check`.
