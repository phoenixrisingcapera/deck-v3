# Smart Deck Text Tool Completion

The canonical Smart Deck API now supports ownership-checked typography updates for an active generated slide:

`PATCH /api/products/deck-aistack-codes/decks/{deck_id}/generated-slides/{generated_slide_id}/design-tokens`

The route validates bounded CSS-safe heading/body font stacks, updates generated-slide `design_tokens_json`, creates or updates generated-slide-scoped `DesignToken` rows, and records `smart_deck.typography_update` in the security audit.

Focused coverage verifies safe input, unsafe CSS rejection, mounted route uniqueness, and persistence behavior. Full cross-repository wiring is documented in workspace-root `SMART_DECK_TEXT_TOOL_COMPLETION.md`.
