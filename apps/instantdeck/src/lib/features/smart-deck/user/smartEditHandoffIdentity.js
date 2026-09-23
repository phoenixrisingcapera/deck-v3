// @ts-check
import { resolveGeneratedSlideForSource } from './generatedSlideIdentity.js';

/** @param {{designVersions:Array<{id:string,generatedSlides:Array<{id:string,sourceSlideId?:string|null,sourceSlideIds?:string[]}>}>,selectedVersionId:string|null,sourceSlideId:string|null,requestedGeneratedSlideId?:string|null}} input */
export function resolveExactSmartEditHandoffIdentity(input) {
  if (!input.selectedVersionId || !input.sourceSlideId) return null;
  const version = input.designVersions.find(({ id }) => id === input.selectedVersionId);
  if (!version) return null;
  const generatedSlide = resolveGeneratedSlideForSource(
    version.generatedSlides,
    input.sourceSlideId,
    input.requestedGeneratedSlideId
  );
  if (!generatedSlide) return null;
  return { designVersionId: version.id, generatedSlideId: generatedSlide.id, sourceSlideId: input.sourceSlideId };
}

/** @param {string} deckId @param {{designVersionId:string,generatedSlideId:string,sourceSlideId:string}} identity @param {{panel?:string,origin?:'smart-deck'|'instant-deck'}} [options] */
export function buildSmartEditHandoffUrl(deckId, identity, options = {}) {
  const params = new URLSearchParams();
  if (options.panel) params.set('panel', options.panel);
  params.set('origin', options.origin ?? 'smart-deck');
  params.set('slide', identity.sourceSlideId);
  params.set('designVersionId', identity.designVersionId);
  params.set('generatedSlideId', identity.generatedSlideId);
  return `/decks/${encodeURIComponent(deckId)}/smart-edit?${params.toString()}`;
}
