// @ts-check

/** @param {{sourceSlideId?: string|null, sourceSlideIds?: string[]} } slide @param {string} sourceSlideId */
export function generatedSlideHasSourceLineage(slide, sourceSlideId) {
  return slide.sourceSlideId === sourceSlideId || (slide.sourceSlideIds ?? []).includes(sourceSlideId);
}

/**
 * Source lineage is not ownership. Only return a source-to-generated mapping
 * when the requested generated ID makes it exact, or lineage has one match.
 * @template {{id:string,sourceSlideId?:string|null,sourceSlideIds?:string[]}} T
 * @param {T[]} generatedSlides
 * @param {string|null} sourceSlideId
 * @param {string|null|undefined} requestedGeneratedSlideId
 * @returns {T|null}
 */
export function resolveGeneratedSlideForSource(generatedSlides, sourceSlideId, requestedGeneratedSlideId) {
  if (requestedGeneratedSlideId) {
    const requested = generatedSlides.find((slide) => slide.id === requestedGeneratedSlideId) ?? null;
    if (!requested) return null;
    if (!sourceSlideId || generatedSlideHasSourceLineage(requested, sourceSlideId)) return requested;
    return null;
  }
  if (!sourceSlideId) return null;
  const matches = generatedSlides.filter((slide) => generatedSlideHasSourceLineage(slide, sourceSlideId));
  return matches.length === 1 ? matches[0] : null;
}

/**
 * Persisted generated ownership wins during degraded recovery. It may have no
 * single source slide because compiled sections support many-to-many lineage.
 * @template {{id:string,sourceSlideId?:string|null,sourceSlideIds?:string[]}} T
 * @param {T[]} generatedSlides
 * @param {string|null|undefined} persistedGeneratedSlideId
 * @returns {{generatedSlide:T|null, sourceSlideId:string|null}}
 */
export function resolvePersistedGeneratedSelection(generatedSlides, persistedGeneratedSlideId) {
  const generatedSlide = persistedGeneratedSlideId
    ? generatedSlides.find((slide) => slide.id === persistedGeneratedSlideId) ?? null
    : null;
  return { generatedSlide, sourceSlideId: generatedSlide?.sourceSlideId ?? null };
}

/**
 * Recover the exact persisted version/generated selection as one atomic state.
 * This prevents degraded SSR defaults from pinning recovery to an unrelated
 * source slide before the canonical workspace arrives.
 * @template {{id:string,generatedSlides:Array<{id:string,sourceSlideId?:string|null,sourceSlideIds?:string[]}>}} V
 * @param {V[]} designVersions
 * @param {string|null|undefined} persistedVersionId
 * @param {string|null|undefined} persistedGeneratedSlideId
 * @param {string[]} validSourceSlideIds
 * @param {string|null|undefined} persistedSourceSlideId
 */
export function resolveRecoveredWorkspaceSelection(designVersions, persistedVersionId, persistedGeneratedSlideId, validSourceSlideIds, persistedSourceSlideId = null) {
  const version = persistedVersionId
    ? designVersions.find(({ id }) => id === persistedVersionId) ?? null
    : null;
  if (!version) return { versionId: null, generatedSlideId: null, sourceSlideId: null };
  const exact = resolveExactGeneratedHandoff(version.generatedSlides, persistedGeneratedSlideId, persistedSourceSlideId, validSourceSlideIds);
  return {
    versionId: version.id,
    generatedSlideId: exact.generatedSlide?.id ?? null,
    sourceSlideId: exact.sourceSlideId
  };
}

/** @param {{slideId:string,generatedSlideId:string,versionId:string}} snapshot @param {{slideId:string|null,generatedSlideId:string|null,versionId:string|null}} current */
export function generationIdentityStillCurrent(snapshot, current) {
  return snapshot.slideId === current.slideId &&
    snapshot.generatedSlideId === current.generatedSlideId &&
    snapshot.versionId === current.versionId;
}

/** @param {{id:string,createdAt?:string}} left @param {{id:string,createdAt?:string}} right */
function compareNewestPersistedIdentity(left, right) {
  const leftTime = Date.parse(left.createdAt ?? '');
  const rightTime = Date.parse(right.createdAt ?? '');
  if (Number.isFinite(leftTime) && Number.isFinite(rightTime) && leftTime !== rightTime) return rightTime - leftTime;
  if (Number.isFinite(leftTime) !== Number.isFinite(rightTime)) return Number.isFinite(rightTime) ? 1 : -1;
  return right.id.localeCompare(left.id);
}

/**
 * Select the authoritative completed intent before resolving its linked read
 * model. Never fall back to an older linked version while the newest job's
 * version is still becoming visible.
 * @param {Array<{id:string,status:string,generationMode?:string,selectedSourceSlideIds:string[],createdAt?:string}>} jobs
 * @param {Array<{id:string,generationJobId?:string|null,createdAt?:string}>} versions
 * @param {string[]} sourceSlideIds
 */
export function resolveLatestCompletedInstantGeneration(jobs, versions, sourceSlideIds) {
  const job = jobs
    .filter((candidate) => candidate.status === 'completed' &&
      candidate.generationMode === 'instant_deck' &&
      sameOrderedSourceSlideIds(candidate.selectedSourceSlideIds, sourceSlideIds))
    .sort(compareNewestPersistedIdentity)[0] ?? null;
  if (!job) return null;
  const version = versions
    .filter((candidate) => candidate.generationJobId === job.id)
    .sort(compareNewestPersistedIdentity)[0] ?? null;
  return { jobId: job.id, versionId: version?.id ?? null };
}

/**
 * @param {Array<{id:string,status:string,generationMode?:string,selectedSourceSlideIds:string[],createdAt?:string}>} jobs
 * @param {Array<{id:string,generationJobId?:string|null,createdAt?:string}>} versions
 * @param {string[]} sourceSlideIds
 */
export function resolveCompletedInstantGenerationVersionId(jobs, versions, sourceSlideIds) {
  return resolveLatestCompletedInstantGeneration(jobs, versions, sourceSlideIds)?.versionId ?? null;
}

/**
 * Bounded read-model reconciliation for an already completed generation. This
 * function has no generation callback by design: unresolved completion can
 * only issue cancelable workspace reads.
 * @template {{generationJobs:Array<{id:string,status:string,generationMode?:string,selectedSourceSlideIds:string[],createdAt?:string}>,designVersions:Array<{id:string,generationJobId?:string|null,createdAt?:string}>}} W
 * @param {{
 *   initialWorkspace: W,
 *   sourceSlideIds: string[],
 *   knownCompletedJobs?: W['generationJobs'],
 *   exactCompletedJobId?: string|null,
 *   refreshWorkspace: (signal?: AbortSignal) => Promise<W>,
 *   waitForRefresh: (signal?: AbortSignal) => Promise<void>,
 *   signal?: AbortSignal,
 *   maxRefreshAttempts?: number
 * }} options
 */
export async function reconcileCompletedInstantGenerationReadModel({
  initialWorkspace,
  sourceSlideIds,
  knownCompletedJobs = [],
  exactCompletedJobId = null,
  refreshWorkspace,
  waitForRefresh,
  signal,
  maxRefreshAttempts = 5
}) {
  let currentWorkspace = initialWorkspace;
  const knownById = new Map(knownCompletedJobs.map((job) => [job.id, job]));
  const resolveCurrent = () => {
    if (exactCompletedJobId) {
      const version = currentWorkspace.designVersions
        .filter((candidate) => candidate.generationJobId === exactCompletedJobId)
        .sort(compareNewestPersistedIdentity)[0] ?? null;
      return { jobId: exactCompletedJobId, versionId: version?.id ?? null };
    }
    const currentById = new Map(currentWorkspace.generationJobs.map((job) => [job.id, job]));
    for (const [jobId, job] of knownById) currentById.set(jobId, job);
    return resolveLatestCompletedInstantGeneration([...currentById.values()], currentWorkspace.designVersions, sourceSlideIds);
  };
  let resolution = resolveCurrent();
  if (!resolution) return { status: 'none', workspace: currentWorkspace, resolution: null };
  if (resolution.versionId) return { status: 'resolved', workspace: currentWorkspace, resolution };

  for (let attempt = 0; attempt < maxRefreshAttempts; attempt += 1) {
    signal?.throwIfAborted();
    await waitForRefresh(signal);
    signal?.throwIfAborted();
    currentWorkspace = await refreshWorkspace(signal);
    resolution = resolveCurrent();
    if (resolution?.versionId) return { status: 'resolved', workspace: currentWorkspace, resolution };
  }
  return { status: 'unresolved', workspace: currentWorkspace, resolution };
}

/** @param {string[]} actual @param {string[]} expected */
export function sameOrderedSourceSlideIds(actual, expected) {
  return actual.length === expected.length && actual.every((slideId, index) => slideId === expected[index]);
}

/**
 * @template {{id:string,sourceSlideId?:string|null,sourceSlideIds?:string[]}} T
 * @param {T[]} generatedSlides
 * @param {string|null|undefined} requestedGeneratedSlideId
 * @param {string|null|undefined} requestedSourceSlideId
 * @param {string[]} validSourceSlideIds
 * @returns {{generatedSlide:T|null, sourceSlideId:string|null}}
 */
export function resolveExactGeneratedHandoff(generatedSlides, requestedGeneratedSlideId, requestedSourceSlideId, validSourceSlideIds) {
  const generatedSlide = requestedGeneratedSlideId
    ? generatedSlides.find((slide) => slide.id === requestedGeneratedSlideId) ?? null
    : null;
  if (!generatedSlide) return { generatedSlide: null, sourceSlideId: null };
  const valid = new Set(validSourceSlideIds);
  const anchors = [...new Set([generatedSlide.sourceSlideId, ...(generatedSlide.sourceSlideIds ?? [])].filter((sourceId) => typeof sourceId === 'string'))]
    .filter((sourceId) => valid.has(sourceId));
  return {
    generatedSlide,
    sourceSlideId: requestedSourceSlideId && anchors.includes(requestedSourceSlideId) ? requestedSourceSlideId : anchors[0] ?? null
  };
}

/**
 * Monotonic guard for async generated-code reads. Identity checks alone cannot
 * reject two requests for the same generated slide that resolve out of order.
 */
export function createGeneratedCodeRequestGuard() {
  let latestSequence = 0;
  return {
    begin() {
      const requestSequence = ++latestSequence;
      return () => requestSequence === latestSequence;
    },
    invalidate() {
      latestSequence += 1;
    }
  };
}

/**
 * Serialize selection writes and allow only the latest submitted intent to
 * update mounted state. Older in-flight responses remain harmless.
 */
export function createLatestSelectionPersistence() {
  let latestIntent = 0;
  let tail = Promise.resolve();
  return {
    /** @template T @param {() => Promise<T>} persist */
    submit(persist) {
      const intent = ++latestIntent;
      const result = tail.then(async () => {
        if (intent !== latestIntent) return { status: 'superseded', response: null, error: null };
        try {
          const response = await persist();
          return intent === latestIntent
            ? { status: 'applied', response, error: null }
            : { status: 'superseded', response: null, error: null };
        } catch (error) {
          return intent === latestIntent
            ? { status: 'failed', response: null, error }
            : { status: 'superseded', response: null, error: null };
        }
      });
      tail = result.then(() => undefined);
      return result;
    }
  };
}

/** @param {Record<string, unknown>} response @param {Record<string, unknown>} expected */
export function selectionResponseMatches(response, expected) {
  return Object.entries(expected).every(([key, value]) => {
    if (value === undefined) return true;
    if (Array.isArray(value)) {
      const actual = response[key];
      return Array.isArray(actual)
        && actual.length === value.length
        && value.every((entry, index) => actual[index] === entry);
    }
    return response[key] === value;
  });
}

/**
 * Merge only persisted selection fields into the live workspace. The caller
 * supplies the exact response identity, so an in-flight callback cannot revive
 * a stale captured workspace or apply a version absent from the current deck.
 * @param {Record<string, any>|null|undefined} currentWorkspace
 * @param {{deckId:string,designVersionId?:string|null}} expected
 * @param {Record<string, unknown>} selection
 */
export function mergeSelectionIntoLiveWorkspace(currentWorkspace, expected, selection) {
  if (!currentWorkspace || currentWorkspace.deck?.id !== expected.deckId) return null;
  /** @type {Array<{id:string}>} */
  const designVersions = currentWorkspace.designVersions ?? [];
  if (
    expected.designVersionId != null
    && !designVersions.some((version) => version.id === expected.designVersionId)
  ) return null;

  const scalarFields = ['activeDesignVersionId', 'activeSourceSlideId', 'activeGeneratedSlideId', 'selectedElementId'];
  /** @type {Record<string, unknown>} */
  const rootSelection = {};
  /** @type {Record<string, unknown>} */
  const stateSelection = {};
  /** @type {Record<string, unknown>} */
  const preferenceSelection = {};
  for (const field of scalarFields) {
    if (!(field in selection)) continue;
    preferenceSelection[field] = selection[field];
    if (field === 'selectedElementId') stateSelection[field] = selection[field];
    else {
      rootSelection[field] = selection[field];
      stateSelection[field] = selection[field];
    }
  }
  if (Array.isArray(selection.selectedSourceSlideIds)) {
    preferenceSelection.selectedSourceSlideIds = [...selection.selectedSourceSlideIds];
  }
  return {
    ...currentWorkspace,
    ...rootSelection,
    workspace: { ...currentWorkspace.workspace, ...stateSelection },
    preferences: { ...currentWorkspace.preferences, ...preferenceSelection }
  };
}

/** @param {string[]} left @param {string[]} right */
function sameSourceSet(left, right) {
  return left.length === right.length && left.every((sourceId) => right.includes(sourceId));
}

/**
 * Build truthful completion copy from one exact version. Coverage belongs to
 * its completed generation job; workspace fallback is accepted only when its
 * resolved version and requested lineage are explicitly bound to this version.
 * @param {{id:string,generationJobId?:string|null,renderProofStatus?:string|null,generatedSlides:Array<{sourceSlideId?:string|null,sourceSlideIds?:string[]}>}} version
 * @param {Array<{id:string,status:string,generationMode?:string,selectedSourceSlideIds:string[],coverageComplete?:boolean|null}>} jobs
 * @param {{resolvedDesignVersionId?:string|null,requestedSourceSlideIds?:string[],coverageComplete?:boolean}|null|undefined} workspace
 */
export function describeInstantVersionCompletion(version, jobs, workspace) {
  const lineage = [...new Set(version.generatedSlides.flatMap((slide) => [slide.sourceSlideId, ...(slide.sourceSlideIds ?? [])]).filter((sourceId) => typeof sourceId === 'string'))];
  const exactJob = version.generationJobId
    ? jobs.find((job) => job.id === version.generationJobId && job.status === 'completed') ?? null
    : null;
  let coverage = 'unknown';
  if (exactJob?.generationMode === 'instant_deck' && exactJob.coverageComplete === false) {
    coverage = 'partial';
  } else if (
    exactJob?.generationMode === 'instant_deck'
    && exactJob.coverageComplete === true
    && sameSourceSet(exactJob.selectedSourceSlideIds, lineage)
  ) {
    coverage = 'complete';
  } else if (
    !exactJob
    && workspace?.resolvedDesignVersionId === version.id
    && sameSourceSet(workspace.requestedSourceSlideIds ?? [], lineage)
    && typeof workspace.coverageComplete === 'boolean'
  ) {
    coverage = workspace.coverageComplete ? 'complete' : 'partial';
  }
  const proof = ['ready', 'pending', 'failed'].includes(String(version.renderProofStatus))
    ? String(version.renderProofStatus)
    : 'unknown';
  const count = version.generatedSlides.length;
  const sections = `${count} generated section${count === 1 ? '' : 's'}`;
  const coverageCopy = coverage === 'complete'
    ? 'complete source coverage is confirmed.'
    : coverage === 'partial'
      ? 'source coverage is partial.'
      : 'source coverage is not yet confirmed.';
  const message = proof === 'ready'
    ? `Version ready with ${sections}; ${coverageCopy}`
    : proof === 'pending'
      ? `Version created with ${sections}; generated preview pending secure render proof; ${coverageCopy}`
      : proof === 'failed'
        ? `Version created with ${sections}; generated preview failed secure render proof; ${coverageCopy}`
        : `Version created with ${sections}; generated preview status is not yet confirmed; ${coverageCopy}`;
  return { proof, coverage, message };
}
