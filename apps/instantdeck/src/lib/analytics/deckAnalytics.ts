type DeckAnalyticsPayload = {
  eventName: string;
  surface?: string;
  entityType?: string;
  entityId?: string;
  metadata?: Record<string, unknown>;
};

const SESSION_STORAGE_KEY = 'deck_aistack_analytics_session_id';

function getSessionId(): string {
  if (typeof sessionStorage === 'undefined') return 'server-session-unavailable';
  const existing = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const generated = `sess_${crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)}`;
  sessionStorage.setItem(SESSION_STORAGE_KEY, generated);
  return generated;
}

export async function trackDeckEvent(deckId: string, payload: DeckAnalyticsPayload): Promise<void> {
  try {
    // Product developer-tools events are persisted by the core database module.
    // Keep this non-blocking so telemetry cannot interrupt a user workflow.
    // DISABLED: No child `/developer-tools/events` SvelteKit route is mounted.
    // await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/developer-tools/events`, {
    // The mounted parent proxy forwards POST requests to the backend events endpoint.
    await fetch(`/api/products/deck-aistack-codes/decks/${deckId}/developer-tools`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        eventName: payload.eventName,
        surface: payload.surface ?? 'unknown',
        entityType: payload.entityType,
        entityId: payload.entityId,
        sessionId: getSessionId(),
        metadata: payload.metadata ?? {}
      })
    });
  } catch {
    // Analytics must never block the product workflow.
  }
}
