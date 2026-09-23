# Smart Deck Brand Tool Completion

The canonical `/decks/[deckId]/smart-deck` Brand rail reuses `BrandPreviewCard` and `BrandSelectorEditor`. It loads and saves the deck-scoped brand profile through the authenticated product proxy, displays whether persisted brand signals are active, and starts the existing reviewable generation workflow for the selected slide.

The backend maps the persisted profile into renderer-safe color and typography tokens. Generated slides, design-token rows, generation artifacts, retrieval context, and element variations use the same resolved token set. The mounted renderer consumes `brand.headingFont` and `brand.bodyFont` in addition to the existing color tokens.

Canonical contracts and verification commands are documented in the workspace-root `SMART_DECK_BRAND_TOOL_COMPLETION.md`.
