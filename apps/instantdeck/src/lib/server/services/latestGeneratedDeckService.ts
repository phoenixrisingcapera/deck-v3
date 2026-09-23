import { error, type Cookies } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
import type { LatestGeneratedDeckCardModel } from '$lib/api/finalDeck';

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asStringOrNull(value: unknown): string | null | undefined {
  if (value == null) return value as null;
  return typeof value === 'string' ? value : undefined;
}

function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function toLatestGeneratedDeckCardModel(
  payload: unknown
): LatestGeneratedDeckCardModel | null {
  if (payload == null) return null;
  if (!isObject(payload)) {
    throw error(502, 'Latest generated deck payload shape is invalid.');
  }

  const deckId = payload.deckId;
  const title = payload.title;
  const status = payload.status;
  const latestBatchId = payload.latestBatchId;
  const createdAt = payload.createdAt;
  const finalizedAt = payload.finalizedAt;
  const openHref = payload.openHref;

  if (
    typeof deckId !== 'string' ||
    typeof title !== 'string' ||
    typeof status !== 'string' ||
    typeof latestBatchId !== 'string' ||
    typeof createdAt !== 'string' ||
    typeof finalizedAt !== 'string' ||
    typeof openHref !== 'string'
  ) {
    throw error(502, 'Latest generated deck payload is missing required fields.');
  }

  return {
    deckId,
    compiledDeckId: asStringOrNull(payload.compiledDeckId),
    title,
    status: status as LatestGeneratedDeckCardModel['status'],
    sourceFileName: asStringOrNull(payload.sourceFileName),
    latestBatchId,
    createdAt,
    finalizedAt,
    slideCount: asNumberOrUndefined(payload.slideCount),
    openHref,
    batchHref: asStringOrNull(payload.batchHref) ?? undefined
  };
}

export async function loadLatestGeneratedDeck(
  fetcher: typeof globalThis.fetch,
  cookies: Cookies
): Promise<LatestGeneratedDeckCardModel | null> {
  const backendUrl = requireBackendUrl();
  const response = await fetcher(`${backendUrl}/api/decks/generated/latest`, {
    headers: requireBackendAuthHeaders(cookies)
  }).catch(() => null);

  if (!response) {
    throw error(503, 'Could not load latest generated deck from the backend.');
  }
  if (!response.ok) {
    throw error(response.status, 'Could not load latest generated deck from the backend.');
  }

  const payload = await response.json().catch(() => null);
  if (!isObject(payload) || !('latestGeneratedDeck' in payload)) {
    throw error(502, 'Latest generated deck payload is invalid JSON or shape.');
  }
  return toLatestGeneratedDeckCardModel(payload.latestGeneratedDeck);
}
