const DIDIDECKS_API_PREFIX = "/api/products/dididecks";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${DIDIDECKS_API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`DidiDecks API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const dididecksApi = {
  listDecks: () => request("/decks"),
  getDeck: (deckId: string) => request(`/decks/${deckId}`),
  getDeckEditorView: (deckId: string) => request(`/decks/${deckId}/editor-view`),
  getDeckMap: (deckId: string) => request(`/decks/${deckId}/map`),
  getEditableFields: (deckId: string) => request(`/decks/${deckId}/editable-fields`),
  getFieldDetail: (deckId: string, fieldKey: string) => request(`/decks/${deckId}/fields/${encodeURIComponent(fieldKey)}`),
  previewChanges: (deckId: string, payload: unknown) => request(`/decks/${deckId}/changes/preview`, { method: "POST", body: JSON.stringify(payload) }),
  applyChanges: (deckId: string, payload: unknown) => request(`/decks/${deckId}/changes/apply`, { method: "POST", body: JSON.stringify(payload) }),
  updateBlock: (blockId: string, payload: unknown) => request(`/blocks/${blockId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  runAiCommand: (payload: unknown) => request(`/ai-commands`, { method: "POST", body: JSON.stringify(payload) }),
};
