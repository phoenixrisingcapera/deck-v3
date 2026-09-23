# PR Consolidation Ledger

## Absorbed In Current Main

- #69: Workspace AI provider summary/revoke now degrades when no workspace exists; save creates a workspace when needed.
- #89/#70: Admin processing health now returns richer workflow diagnostics through the active `processing_status_service` path.
- #85: Artifact namespace helper and verifier added as a foundation for product-scoped bucket keys.
- #72: Brand profile payload now exposes normalized `sourceLabels` from raw brand evidence.
- #81, #66, #63, #30, #17: Already represented in current production code paths.

## Not Directly Merged

- #92, #91, #25: Substantive VC/RAG/prompt-engine work, but large enough to require a dedicated schema/migration pass.
- #85 follow-up: write sites still need to adopt `artifact_namespace_service` before flat artifact keys are fully eliminated.
- #74: SVG logo upload support remains for a focused brand upload pass.
- #67: Due diligence route contract should be added with current route registration, not the stale PR layout.
- #64: Superseded by workspace-provider service hardening.
- #83/#84: Docs-only architecture notes retained as PR references, not merged into runtime.

## Rule Used

No open PR was cleanly mergeable. Code was absorbed only where it could be adapted to the current consolidated runtime paths without reintroducing stale route groups or duplicate service layers.
