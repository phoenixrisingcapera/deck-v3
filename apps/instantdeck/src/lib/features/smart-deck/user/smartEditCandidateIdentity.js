// @ts-check

/** @typedef {'manual' | 'persisted'} ReconstructedCandidateKind */

/**
 * Resolve only the backend's explicit pending candidate for one source slide.
 * This prevents the active base editor from accepting local changes that the
 * backend must reject while another review candidate occupies the deck slot.
 *
 * @param {{
 *   deckId: string;
 *   sourceSlideId: string | null;
 *   workspace: null | {
 *     candidateDesignVersionId?: string | null;
 *     designVersions: Array<{
 *       id: string;
 *       deckId?: string;
 *       deck_id?: string;
 *       isActive?: boolean;
 *       generatedSlides: Array<{ id: string; deckId?: string; sourceSlideId?: string | null }>;
 *     }>;
 *   };
 * }} input
 * @returns {{ designVersionId: string; generatedSlideId: string; sourceSlideId: string } | null}
 */
export function resolvePendingSmartEditCandidate(input) {
  const { deckId, sourceSlideId, workspace } = input;
  const candidateVersionId = workspace?.candidateDesignVersionId ?? null;
  if (!workspace || !candidateVersionId || !sourceSlideId) return null;
  const versions = workspace.designVersions.filter((version) =>
    version.id === candidateVersionId &&
    !version.isActive &&
    (!version.deckId || version.deckId === deckId) &&
    (!version.deck_id || version.deck_id === deckId)
  );
  if (versions.length !== 1) return null;
  const slides = versions[0].generatedSlides.filter((slide) =>
    slide.sourceSlideId === sourceSlideId && (!slide.deckId || slide.deckId === deckId)
  );
  if (slides.length !== 1) return null;
  return { designVersionId: candidateVersionId, generatedSlideId: slides[0].id, sourceSlideId };
}

/**
 * Reconstruct review identity only from the backend's explicit candidate pointer
 * and an exact deck/version/source-slide match. Names and summaries are not
 * identity signals because users and generators can supply them.
 *
 * @param {{
 *   deckId: string;
 *   selectedVersionId: string | null;
 *   selectedSlideId: string | null;
 *   workspace: null | {
 *     candidateDesignVersionId?: string | null;
 *     designVersions: Array<{
 *       id: string;
 *       deckId?: string;
 *       deck_id?: string;
 *       isActive?: boolean;
 *       generatedSlides: Array<{ id: string; deckId?: string; sourceSlideId?: string | null }>;
 *     }>;
 *   };
 *   selectedGeneratedSlideId?: string | null;
 *   codeMetadata?: Record<string, unknown> | null;
 * }} input
 * @returns {{ deckId: string; slideId: string; generatedSlideId: string; elementId: null; versionId: string; kind: ReconstructedCandidateKind } | null}
 */
export function reconstructSmartEditCandidateIdentity(input) {
  const { deckId, workspace, selectedVersionId, selectedSlideId, selectedGeneratedSlideId = null, codeMetadata = null } = input;
  if (!workspace) return null;
  const candidateVersionId = workspace.candidateDesignVersionId ?? null;
  if (!candidateVersionId || candidateVersionId !== selectedVersionId || !selectedSlideId || !selectedGeneratedSlideId) return null;

  const versions = workspace.designVersions.filter((version) => version.id === candidateVersionId);
  if (versions.length !== 1) return null;
  const version = versions[0];
  if (version.isActive || (version.deckId && version.deckId !== deckId) || (version.deck_id && version.deck_id !== deckId)) return null;

  const matchingSlides = version.generatedSlides.filter((slide) =>
    slide.sourceSlideId === selectedSlideId &&
    slide.id === selectedGeneratedSlideId &&
    (!slide.deckId || slide.deckId === deckId)
  );
  if (matchingSlides.length !== 1) return null;

  const manualMetadataMatches = codeMetadata?.source === 'manual_layout_edit' &&
    codeMetadata?.lifecycle === 'candidate' &&
    typeof codeMetadata?.manualEditJobId === 'string' &&
    typeof codeMetadata?.baseDesignVersionId === 'string' &&
    typeof codeMetadata?.baseGeneratedSlideId === 'string';
  return {
    deckId,
    slideId: selectedSlideId,
    generatedSlideId: matchingSlides[0].id,
    elementId: null,
    versionId: candidateVersionId,
    kind: /** @type {ReconstructedCandidateKind} */ (manualMetadataMatches ? 'manual' : 'persisted')
  };
}

/**
 * Validate a completed manual edit against both its request snapshot and the
 * current navigation before any refreshed workspace or candidate is mounted.
 *
 * @param {{
 *   requestIdentity: { deckId: string; sourceSlideId: string; generatedSlideId: string; baseDesignVersionId: string };
 *   currentIdentity: { deckId: string; sourceSlideId: string | null; generatedSlideId: string | null; baseDesignVersionId: string | null };
 *   manualEditJob: { baseDesignVersionId: string; baseGeneratedSlideId: string; sourceSlideId: string; candidateDesignVersionId: string; candidateGeneratedSlideId: string };
 *   workspace: {
 *     deck: { id: string };
 *     candidateDesignVersionId?: string | null;
 *     savedDesignVersionId?: string | null;
 *     resolvedDesignVersionId?: string | null;
 *     activeDesignVersionId?: string | null;
 *     workspace: { activeDesignVersionId?: string | null };
 *     designVersions: Array<{ id: string; isActive: boolean; generatedSlides: Array<{ id: string; sourceSlideId?: string | null }> }>;
 *   };
 * }} input
 */
export function validateManualEditCandidateCompletion(input) {
  const { requestIdentity: request, currentIdentity: current, manualEditJob: job, workspace } = input;
  const navigationMatches = current.deckId === request.deckId &&
    current.sourceSlideId === request.sourceSlideId &&
    current.generatedSlideId === request.generatedSlideId &&
    current.baseDesignVersionId === request.baseDesignVersionId;
  const responseMatches = job.baseDesignVersionId === request.baseDesignVersionId &&
    job.baseGeneratedSlideId === request.generatedSlideId &&
    job.sourceSlideId === request.sourceSlideId;
  if (!navigationMatches || !responseMatches || workspace.deck.id !== request.deckId) {
    throw new Error('Manual layout save completed after the deck, slide, generated slide, or base version changed. Re-open the current active version before editing.');
  }

  const baseVersions = workspace.designVersions.filter((version) =>
    version.id === request.baseDesignVersionId &&
    version.isActive &&
    version.generatedSlides.filter((slide) => slide.sourceSlideId === request.sourceSlideId).length === 1 &&
    version.generatedSlides.some((slide) => slide.id === request.generatedSlideId && slide.sourceSlideId === request.sourceSlideId)
  );
  const candidateVersions = workspace.designVersions.filter((version) =>
    version.id === job.candidateDesignVersionId &&
    !version.isActive &&
    version.generatedSlides.filter((slide) => slide.sourceSlideId === request.sourceSlideId).length === 1 &&
    version.generatedSlides.some((slide) => slide.id === job.candidateGeneratedSlideId && slide.sourceSlideId === request.sourceSlideId)
  );
  const savedBaseMatches = workspace.savedDesignVersionId === request.baseDesignVersionId;
  const uniqueActiveBaseMatches = workspace.designVersions.filter((version) => version.isActive).length === 1 && baseVersions.length === 1;
  const activeBasePointers = [
    workspace.activeDesignVersionId,
    workspace.workspace.activeDesignVersionId,
    workspace.resolvedDesignVersionId
  ].filter((versionId) => typeof versionId === 'string');
  const activeBasePointersMatch = activeBasePointers.length > 0 && activeBasePointers.every((versionId) => versionId === request.baseDesignVersionId);
  if (
    (!savedBaseMatches && !uniqueActiveBaseMatches) ||
    workspace.candidateDesignVersionId !== job.candidateDesignVersionId ||
    !activeBasePointersMatch ||
    baseVersions.length !== 1 ||
    candidateVersions.length !== 1
  ) {
    throw new Error('Manual layout save returned an ambiguous or stale candidate identity. Refresh the active version before editing again.');
  }

  return {
    candidateDesignVersionId: job.candidateDesignVersionId,
    candidateGeneratedSlideId: job.candidateGeneratedSlideId
  };
}
