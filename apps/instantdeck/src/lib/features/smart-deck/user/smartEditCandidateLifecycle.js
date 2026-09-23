// @ts-check

/**
 * Keep Smart Edit navigation pinned to the exact persisted visual identity.
 * Existing panel/origin context is preserved while stale candidate identities
 * are replaced atomically.
 *
 * @param {URL} currentUrl
 * @param {string} deckId
 * @param {{ designVersionId: string; generatedSlideId: string; sourceSlideId: string }} identity
 */
export function buildCanonicalSmartEditUrl(currentUrl, deckId, identity) {
  const params = new URLSearchParams(currentUrl.searchParams);
  params.set('slide', identity.sourceSlideId);
  params.set('designVersionId', identity.designVersionId);
  params.set('generatedSlideId', identity.generatedSlideId);
  return `/decks/${encodeURIComponent(deckId)}/smart-edit?${params.toString()}`;
}
/** @param {string|null} origin @param {string} deckId @param {{designVersionId:string,generatedSlideId:string,sourceSlideId:string}|null} identity */
export function buildSmartEditOriginReturnUrl(origin, deckId, identity) {
  const encodedDeckId = encodeURIComponent(deckId);
  if (origin === 'smart-deck') return `/decks/${encodedDeckId}/smart-deck`;
  if (origin === 'due-diligence') return `/decks/${encodedDeckId}/due-diligence`;
  if (origin !== 'instant-deck' || !identity) return null;
  const params = new URLSearchParams({ slide: identity.sourceSlideId, designVersionId: identity.designVersionId, generatedSlideId: identity.generatedSlideId });
  return `/decks/${encodedDeckId}/instant-deck?${params.toString()}`;
}

/**
 * Resolve source-slide navigation against one exact persisted design version.
 * A generated slide ID from the previous source slide is retained only when it
 * still belongs to the newly selected source slide; otherwise the matching
 * generated slide in that version replaces it atomically.
 *
 * @param {{
 *   designVersions: Array<{ id: string; generatedSlides: Array<{ id: string; sourceSlideId?: string | null; sourceSlideIds?: string[]; renderMode?: 'scene_graph.v1' | 'html_compiled.v1' }> }>;
 *   selectedDesignVersionId: string | null;
 *   selectedSourceSlideId: string | null;
 *   selectedGeneratedSlideId: string | null;
 * }} input
 * @returns {{ designVersionId: string; generatedSlideId: string; sourceSlideId: string } | null}
 */
export function resolveSmartEditSlideIdentity(input) {
  if (!input.selectedDesignVersionId || !input.selectedSourceSlideId) return null;
  const selectedSourceSlideId = input.selectedSourceSlideId;
  const version = input.designVersions.find(({ id }) => id === input.selectedDesignVersionId);
  if (!version) return null;
  /** @param {{ sourceSlideId?: string | null; sourceSlideIds?: string[] }} slide */
  const hasLineage = (slide) => slide.sourceSlideId === selectedSourceSlideId || (slide.sourceSlideIds ?? []).includes(selectedSourceSlideId);
  const requested = input.selectedGeneratedSlideId
    ? version.generatedSlides.find(({ id }) => id === input.selectedGeneratedSlideId) ?? null
    : null;
  // Compiled section identity owns HTML selection. Its singular source ID may
  // be null and its many-to-many lineage is navigation context, not ownership.
  const exactRequested = requested && (requested.renderMode === 'html_compiled.v1' || hasLineage(requested))
    ? requested
    : null;
  const lineageMatches = version.generatedSlides.filter(hasLineage);
  const generatedSlide = exactRequested ?? (lineageMatches.length === 1 ? lineageMatches[0] : null);
  if (!generatedSlide) return null;
  return {
    designVersionId: version.id,
    generatedSlideId: generatedSlide.id,
    sourceSlideId: selectedSourceSlideId
  };
}

/**
 * @typedef {{ fingerprint: string; key: string } | null} ManualEditRetryIdentity
 */

/**
 * Reuse one key for an unchanged request. Callers clear this state only after
 * success, a user edit, or an explicit cancel/reset.
 *
 * @param {ManualEditRetryIdentity} current
 * @param {string} fingerprint
 * @param {() => string} createKey
 * @returns {{ identity: Exclude<ManualEditRetryIdentity, null>; key: string }}
 */
export function resolveManualEditRetryIdentity(current, fingerprint, createKey) {
  if (current?.fingerprint === fingerprint) return { identity: current, key: current.key };
  const identity = { fingerprint, key: createKey() };
  return { identity, key: identity.key };
}
