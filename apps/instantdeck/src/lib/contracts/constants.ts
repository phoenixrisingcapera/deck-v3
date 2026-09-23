// `deck-aistack-codes` is the product namespace for the live deck user
// experience. This slug is not just routing metadata: it is the contract anchor
// for the product that users interact with, so features wired through it are
// expected to be complete end-to-end, not placeholder or half-connected flows.
const DEFAULT_DECK_PRODUCT_SLUG: string = 'deck-aistack-codes';

export function readDeckProductSlug(): string {
  const value = import.meta.env.PUBLIC_DECK_PRODUCT_SLUG;
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return DEFAULT_DECK_PRODUCT_SLUG;
}

export const DECK_PRODUCT_SLUG: string = readDeckProductSlug();
// Route and API helpers derived from this slug should always represent the
// canonical user product surface for deck.aistack.codes behavior.
export const DECK_PRODUCT_ROUTE_PREFIX: string = `/products/${DECK_PRODUCT_SLUG}`;
export const DECK_PRODUCT_API_PREFIX: string = `/api/products/${DECK_PRODUCT_SLUG}`;

export function normalizeProductPath(path: string): string {
  if (!path) {
    return '';
  }

  const normalized = path.trim();
  if (!normalized) {
    return '';
  }

  return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

export function deckProductRoutePath(path = ''): string {
  return `${DECK_PRODUCT_ROUTE_PREFIX}${normalizeProductPath(path)}`;
}

export function deckProductApiPath(path = ''): string {
  return `${DECK_PRODUCT_API_PREFIX}${normalizeProductPath(path)}`;
}

export function deckWorkflowStateApiPath(deckId: string): string {
  return deckProductApiPath(`/decks/${deckId}/workflow-state`);
}

export function deckWorkflowJobApiPath(jobId: string): string {
  // Workflow jobs are a shared backend surface, so polling stays on the global
  // `/api/workflow-jobs/{jobId}` route even when deck actions are product-scoped.
  return `/api/workflow-jobs/${jobId}`;
}
