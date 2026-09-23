# Smart Deck Text Tool Completion

The canonical Smart Deck workspace mounts `SmartDeckTextPanel` from its existing rail. The panel updates the active generated slide through the authenticated generated-slide design-token proxy and replaces the mounted canvas token state with the persisted response.

The frontend owns presentation, active-slide selection, proxy authentication, save feedback, and immediate renderer refresh. The backend owns deck authorization, input validation, generated-slide and `DesignToken` persistence, and security audit recording.

Full cross-repository wiring and verification are documented in workspace-root `SMART_DECK_TEXT_TOOL_COMPLETION.md`.
