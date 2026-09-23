# Codex Prompt: Review Matrix and Surface Reviews

Goal: Implement the variants × slides × surfaces review matrix.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Route:

```txt
/decks/[deckId]/review-matrix
```

Surfaces:

- scroll
- play
- print
- thumbnail
- editor

Rules:

- Scroll-UI and Play-UI are coordinated implementations, not the same implementation rendered twice.
- A variant with zero content cannot be marked Ready.
- Use explicit surface actions: Open Scroll, Open Play, Open Print, Open Editor.

Components:

- DeckReviewMatrix
- VariantFilterChips
- SurfaceRollupPill
- SurfaceStatusCell
- VariantReadinessBadge
- SurfaceLauncherRow
- EmptyVariantState
