# Codex Prompt: Editor Runtime Integration

Goal: Connect `/decks/[deckId]/editor` to the shared persistent-field and block-mapping architecture.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


The editor must let a user:

1. Select a slide.
2. Select a block.
3. Inspect block content/style/position.
4. See persistent field binding, if present.
5. Navigate to Smart Edit, Deck Map, and Rebuild.

Create or update:

- `data/mockDeckEditor.ts`
- `lib/types/dididecks.ts`
- `lib/api/dididecks.ts`
- `components/editor/DeckEditorShell.tsx`
- `components/editor/SlideCanvas.tsx`
- `components/editor/BlockInspector.tsx`
- `components/editor/AiCommandPanel.tsx`
- `components/editor/EditorToolbar.tsx`

Required workflow links for field-bound blocks:

```txt
/decks/[deckId]/smart-edit?field={fieldKey}&slide={slideId}&block={blockId}
/decks/[deckId]/map?field={fieldKey}
/decks/[deckId]/rebuild?field={fieldKey}
```

Do not implement real backend mutation logic in this pass.
