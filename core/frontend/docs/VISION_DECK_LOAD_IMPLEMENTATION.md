# Vision Deck Load Frontend

The canonical upload path now navigates to `/decks/{deckId}/processing` as soon
as the backend returns a persisted ID. Cleanup and workspace refresh continue in
the background.

The processing route:

- polls canonical workflow state until a backend terminal state;
- updates on every successful response;
- renders source miniature URLs as they become available;
- opens Smart Deck only when `canOpenSmartDeck` is true.

Smart Edit uses the `suggestionId` created by the backend review workflow, and
Due Diligence retains run history and conversion fields during normalization.

```bash
npm run check
npm run build
npm run test:workflow-client-contract
npm run test:upload-contract
```

Production acceptance still requires an authenticated upload and reload test.
