// @ts-check

/**
 * @typedef {{ id: string; generationJobId?: string | null; isActive?: boolean }} VersionIdentity
 * @typedef {{ id: string; generationMode?: string | null }} GenerationJobIdentity
 * @typedef {{
 *   designVersions: VersionIdentity[];
 *   generationJobs: GenerationJobIdentity[];
 *   resolvedDesignVersionId?: string | null;
 *   savedDesignVersionId?: string | null;
 *   candidateDesignVersionId?: string | null;
 *   activeDesignVersionId?: string | null;
 *   preferences: { activeDesignVersionId?: string | null };
 * }} WorkspaceVersionIdentity
 */

/**
 * @param {WorkspaceVersionIdentity} workspace
 * @param {VersionIdentity} version
 * @param {boolean} generatedOnly
 */
export function isAllowedCanonicalVersion(workspace, version, generatedOnly) {
  if (!generatedOnly) return true;
  if (
    version.id === workspace.resolvedDesignVersionId ||
    version.id === workspace.savedDesignVersionId ||
    version.id === workspace.candidateDesignVersionId
  ) {
    return true;
  }
  const instantJobIds = new Set(
    workspace.generationJobs.filter((job) => job.generationMode === 'instant_deck').map((job) => job.id)
  );
  return Boolean(version.generationJobId && instantJobIds.has(version.generationJobId));
}

/**
 * @param {WorkspaceVersionIdentity | null} workspace
 * @param {{ selectedVersionId?: string | null; generatedOnly?: boolean }} [options]
 */
export function resolveCanonicalDesignVersionId(workspace, options = {}) {
  if (!workspace) return null;
  const { selectedVersionId = null, generatedOnly = false } = options;
  const preferredIds = [
    selectedVersionId,
    workspace.resolvedDesignVersionId,
    workspace.savedDesignVersionId,
    workspace.candidateDesignVersionId,
    workspace.activeDesignVersionId,
    workspace.preferences.activeDesignVersionId
  ];
  /** @param {VersionIdentity} version */
  const eligible = (version) => isAllowedCanonicalVersion(workspace, version, generatedOnly);
  for (const versionId of preferredIds) {
    const version = workspace.designVersions.find((candidate) => candidate.id === versionId && eligible(candidate));
    if (version) return version.id;
  }
  return workspace.designVersions.find((version) => version.isActive && eligible(version))?.id ??
    workspace.designVersions.find(eligible)?.id ??
    null;
}

/**
 * @template {{ id: string }} T
 * @param {T[]} slides
 * @param {string | null} selectedSlideId
 * @param {string | null | undefined} preferredSlideId
 * @param {boolean} requireExactSelection
 * @returns {T | null}
 */
export function selectCanonicalSlide(slides, selectedSlideId, preferredSlideId, requireExactSelection) {
  const selected = selectedSlideId ? slides.find((slide) => slide.id === selectedSlideId) ?? null : null;
  if (selected || requireExactSelection) return selected;
  return slides.find((slide) => slide.id === preferredSlideId) ?? slides[0] ?? null;
}
