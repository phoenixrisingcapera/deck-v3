import type { Cookies } from '@sveltejs/kit';
import { error } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
import type { CompiledDeckModel } from '$lib/api/finalDeck';

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function asOptionalString(value: unknown): string | null | undefined {
  if (value == null) return null;
  return typeof value === 'string' ? value : undefined;
}

function toCompiledDeckModel(payload: unknown): CompiledDeckModel {
  if (!isObject(payload)) {
    throw error(502, 'Compiled deck payload is invalid.');
  }

  const slidesRaw = isObject(payload.slides) ? payload.slides : undefined;
  const slideIndexIsValid = (value: unknown): value is number =>
    typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value);
  const asChoice = (value: unknown): string => (typeof value === 'string' ? value : 'original');

  if (
    typeof payload.deckId !== 'string' ||
    typeof payload.batchId !== 'string' ||
    typeof payload.compiledDeckId !== 'string' ||
    typeof payload.status !== 'string' ||
    typeof payload.title !== 'string' ||
    typeof payload.finalizedAt !== 'string' ||
    !isObject(payload.manifest)
  ) {
    throw error(502, 'Compiled deck payload is missing required fields.');
  }

  const rawSlides = Array.isArray(payload.slides) ? payload.slides : [];
  const slides = rawSlides.map((slide, index) => {
    if (!isObject(slide)) {
      throw error(502, `Compiled deck payload has invalid slide entry at index ${index}.`);
    }

    if (typeof slide.title !== 'string' || !slideIndexIsValid(slide.slideIndex)) {
      throw error(502, `Compiled deck slide payload is invalid at index ${index}.`);
    }

    return {
      sourceSlideId: asOptionalString(slide.sourceSlideId),
      generatedSlideCandidateId: asOptionalString(slide.generatedSlideCandidateId),
      slideIndex: slide.slideIndex,
      choice: asChoice(slide.choice),
      title: slide.title,
      manifest: isObject(slide.manifest) ? (slide.manifest as Record<string, unknown>) : {}
    };
  });

  return {
    deckId: payload.deckId,
    batchId: payload.batchId,
    compiledDeckId: payload.compiledDeckId,
    status: asString(payload.status) as CompiledDeckModel['status'],
    title: payload.title,
    slideCount: asNumber(payload.slideCount),
    finalizedAt: payload.finalizedAt,
    manifest: payload.manifest as Record<string, unknown>,
    slides
  };
}

export async function loadCompiledDeck(
  fetcher: typeof globalThis.fetch,
  cookies: Cookies,
  deckId: string,
  compiledDeckId: string
): Promise<CompiledDeckModel | null> {
  const backendUrl = requireBackendUrl();
  const response = await fetcher(`${backendUrl}/api/decks/${deckId}/compiled-decks/${compiledDeckId}`, {
    headers: requireBackendAuthHeaders(cookies)
  }).catch(() => null);

  if (!response) {
    throw error(503, 'Compiled deck lookup failed.');
  }
  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    throw error(response.status, 'Compiled deck lookup failed.');
  }

  const payload = await response.json().catch(() => null);
  if (!isObject(payload) || !('compiledDeck' in payload)) {
    throw error(502, 'Compiled deck payload is invalid JSON or shape.');
  }
  if (!payload.compiledDeck) {
    return null;
  }
  return toCompiledDeckModel(payload.compiledDeck);
}

export async function loadFinalDeckForIteration(
  fetcher: typeof globalThis.fetch,
  cookies: Cookies,
  deckId: string,
  iterationId: string
): Promise<CompiledDeckModel | null> {
  const backendUrl = requireBackendUrl();
  const response = await fetcher(`${backendUrl}/api/decks/${deckId}/iterations/${iterationId}/final-deck`, {
    headers: requireBackendAuthHeaders(cookies)
  }).catch(() => null);

  if (!response) {
    throw error(503, 'Final deck lookup failed.');
  }
  if (!response.ok) {
    throw error(response.status, 'Final deck lookup failed.');
  }

  const payload = await response.json().catch(() => null);
  if (!isObject(payload) || !('compiledDeck' in payload)) {
    throw error(502, 'Final deck payload is invalid JSON or shape.');
  }
  if (!payload.compiledDeck) {
    return null;
  }
  return toCompiledDeckModel(payload.compiledDeck);
}
