// @ts-check

/**
 * @typedef {{ id: string; slideIndex: number; slideNumber?: number }} GraphSlideIdentity
 * @typedef {{ id: string; slideNumber: number }} WorkspaceSourceSlideIdentity
 */

/** @param {GraphSlideIdentity} slide */
function normalizedGraphSlideNumber(slide) {
  const slideNumber = slide.slideNumber ?? slide.slideIndex + 1;
  return slideNumber === slide.slideIndex ? slide.slideIndex + 1 : slideNumber;
}

/**
 * @param {GraphSlideIdentity[]} graphSlides
 * @param {WorkspaceSourceSlideIdentity[]} sourceSlides
 * @param {string | null} graphSlideId
 */
export function resolveGeneratedSourceSlideId(graphSlides, sourceSlides, graphSlideId) {
  if (!graphSlideId) return null;
  if (sourceSlides.some((slide) => slide.id === graphSlideId)) return graphSlideId;
  const graphSlide = graphSlides.find((slide) => slide.id === graphSlideId);
  if (!graphSlide) return graphSlideId;
  const numberMatches = sourceSlides.filter((slide) => slide.slideNumber === normalizedGraphSlideNumber(graphSlide));
  return numberMatches.length === 1 ? numberMatches[0].id : graphSlideId;
}

/**
 * @param {GraphSlideIdentity[]} graphSlides
 * @param {WorkspaceSourceSlideIdentity[]} sourceSlides
 * @param {string | null} requestedSlideId
 */
export function resolveGraphSlideId(graphSlides, sourceSlides, requestedSlideId) {
  if (!requestedSlideId) return null;
  if (graphSlides.some((slide) => slide.id === requestedSlideId)) return requestedSlideId;
  const sourceSlide = sourceSlides.find((slide) => slide.id === requestedSlideId);
  if (!sourceSlide) return null;
  const numberMatches = graphSlides.filter((slide) => normalizedGraphSlideNumber(slide) === sourceSlide.slideNumber);
  return numberMatches.length === 1 ? numberMatches[0].id : null;
}
