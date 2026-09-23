import type { DeckGraph } from '$types/domain';
import {
  applyDesignVersion,
  createElementVariationJob,
  discardDesignVersion,
  getGeneratedSlideCode,
  getSmartDeckWorkspace,
  patchSmartDeckPreferences,
  startSmartDeckGenerationWorkflow,
  updateSmartDeckSelection,
  waitForWorkflowJobCompletion,
  type DesignVersion,
  type GeneratedSlidePreviewStatus,
  type GeneratedSlideSchemaStatus,
  type HtmlCompiledSlideRenderIdentity,
  type SmartDeckGenerationInput,
  type SmartDeckWorkspacePayload
} from '$lib/api/smartDeckWorkspace';
import type { SmartDeckUserGenerationResult, SmartDeckUserViewModel } from './smartDeckUserTypes';
import { buildSmartDeckDesignContext } from '$lib/components/instant-deck/designFallback';
// DISABLED: createUserSmartDeckSlide uses the mounted local proxy, so importing
// deckProductApiPath here would bypass the intended browser-facing boundary.
// import { deckProductApiPath } from '$lib/contracts';
import { fetchApiJsonOrThrow } from '$lib/api/apiError';
import type { CreateDeckSlideRequest } from '$lib/contracts';
import { generatedSlideHasSourceLineage, resolveGeneratedSlideForSource } from './generatedSlideIdentity.js';

export function toHtmlCompiledSlideRenderIdentity(
  deckId: string,
  version: DesignVersion | null,
  generatedSlide: DesignVersion['generatedSlides'][number] | null | undefined
): HtmlCompiledSlideRenderIdentity | null {
  const artifact = version?.htmlArtifact;
  if (
    !version ||
    version.renderMode !== 'html_compiled.v1' ||
    !artifact?.id ||
    !artifact.sha256 ||
    !generatedSlide ||
    generatedSlide.renderMode !== 'html_compiled.v1' ||
    !generatedSlide.sectionId
  ) return null;

  return {
    deckId,
    designVersionId: version.id,
    htmlArtifactId: artifact.id,
    artifactSha256: artifact.sha256,
    generatedSlideId: generatedSlide.id,
    sectionId: generatedSlide.sectionId,
    sectionSha256: generatedSlide.sectionSha256 ?? null,
    compilationHash: generatedSlide.compilationHash ?? null,
    renderMode: 'html_compiled.v1',
    renderProofStatus: generatedSlide.renderProofStatus ?? version.renderProofStatus ?? 'pending'
  };
}

export function toInstantDeckGeneratedSlideRail(
  version: DesignVersion | null,
  sourceSlides: SmartDeckWorkspacePayload['sourceSlides']
): SmartDeckUserViewModel['slides'] {
  if (!version) return [];

  return version.generatedSlides.map((generatedSlide, index) => {
    const sourceSlide = sourceSlides.find((slide) => slide.id === generatedSlide.sourceSlideId) ?? null;
    const number = generatedSlide.slideNumber ?? sourceSlide?.slideNumber ?? index + 1;
    const title = generatedSlide.title?.trim() || sourceSlide?.title?.trim() || `Slide ${String(number).padStart(2, '0')}`;
    const generatedPreviewUrl = version.renderMode === 'html_compiled.v1' || generatedSlide.renderMode === 'html_compiled.v1'
      ? null
      : firstSafePreviewUrl(
      generatedSlide.previewImageUrl,
      generatedSlide.preview_image_url,
      generatedSlide.previewUrl,
      generatedSlide.preview_url,
      generatedSlide.thumbnailUrl,
      generatedSlide.thumbnail_url
    );
    const htmlSlide = toHtmlCompiledSlideRenderIdentity(version.deckId, version, generatedSlide);

    return {
      id: generatedSlide.id,
      number,
      title,
      thumbnailUrl: generatedPreviewUrl,
      previewUrl: generatedPreviewUrl,
      // The Instant Deck rail represents generated artifacts. Keeping this
      // null prevents the shared navigator from substituting source media.
      sourceThumbnailUrl: null,
      sourceSlideId: generatedSlide.sourceSlideId ?? null,
      generatedSlideId: generatedSlide.id,
      previewStatus: generatedSlide.previewStatus ?? (generatedPreviewUrl ? 'ready' : 'pending'),
      schemaStatus: generatedSlide.schemaStatus ?? 'ready',
      sourceText: sourceSlide?.extractedText ?? '',
      generatedTitle: generatedSlide.title ?? null,
      hasGeneratedVersion: true,
      renderMode: generatedSlide.renderMode ?? 'scene_graph.v1',
      sectionId: generatedSlide.sectionId ?? null,
      sourceSlideIds: generatedSlide.sourceSlideIds ?? (generatedSlide.sourceSlideId ? [generatedSlide.sourceSlideId] : []),
      renderProofStatus: generatedSlide.renderProofStatus ?? 'pending',
      designVersionId: version.id,
      htmlArtifactId: version.htmlArtifact?.id ?? null,
      htmlSlide,
      persistedElements: (generatedSlide.elements ?? []).map((element) => ({
        id: element.id,
        elementKey: element.elementKey,
        elementType: element.elementType,
        zIndex: element.zIndex,
        x: element.x,
        y: element.y,
        width: element.width,
        height: element.height,
        locked: element.locked,
        visible: element.visible,
        content: element.content ?? null
      }))
    };
  });
}

export function versionContainsSourceSlide(version: DesignVersion | null | undefined, sourceSlideId: string | null) {
  if (!version || !sourceSlideId) return false;
  return version.generatedSlides.some((slide) => generatedSlideHasSourceLineage(slide, sourceSlideId));
}

export function resolveSmartDeckVersionId(options: {
  workspace: SmartDeckWorkspacePayload | null;
  requestedVersionId?: string | null;
  selectedSlideId?: string | null;
  generatedOnly?: boolean;
}) {
  const { workspace, requestedVersionId = null, selectedSlideId = null, generatedOnly = false } = options;
  if (!workspace) return null;

  const instantGenerationJobIds = new Set(
    workspace.generationJobs
      .filter((job) => job.generationMode === 'instant_deck')
      .map((job) => job.id)
  );
  const isAllowedVersion = (version: DesignVersion) => !generatedOnly || Boolean(version.generationJobId && instantGenerationJobIds.has(version.generationJobId));
  const containsSelectedSlide = (version: DesignVersion) => !selectedSlideId || versionContainsSourceSlide(version, selectedSlideId);
  const findById = (versionId: string | null | undefined, requireSelectedSlide = true) => {
    if (!versionId) return null;
    return workspace.designVersions.find((version) => (
      version.id === versionId &&
      isAllowedVersion(version) &&
      (!requireSelectedSlide || containsSelectedSlide(version))
    ))?.id ?? null;
  };

  return (
    findById(requestedVersionId) ??
    findById(workspace.resolvedDesignVersionId) ??
    findById(workspace.candidateDesignVersionId) ??
    findById(workspace.savedDesignVersionId) ??
    findById(workspace.activeDesignVersionId) ??
    findById(workspace.preferences.activeDesignVersionId) ??
    workspace.designVersions.find((version) => isAllowedVersion(version) && containsSelectedSlide(version) && version.isActive)?.id ??
    workspace.designVersions.find((version) => isAllowedVersion(version) && containsSelectedSlide(version))?.id ??
    findById(workspace.resolvedDesignVersionId, false) ??
    findById(workspace.candidateDesignVersionId, false) ??
    findById(workspace.savedDesignVersionId, false) ??
    findById(workspace.activeDesignVersionId, false) ??
    findById(workspace.preferences.activeDesignVersionId, false) ??
    workspace.designVersions.find((version) => isAllowedVersion(version) && version.isActive)?.id ??
    workspace.designVersions.find(isAllowedVersion)?.id ??
    null
  );
}

function versionLabel(index: number, version: DesignVersion, workspace: SmartDeckWorkspacePayload | null) {
  if (version.id === workspace?.savedDesignVersionId && workspace.savedDeckVersionNumber) {
    return `Version ${workspace.savedDeckVersionNumber}`;
  }
  if (version.isActive) return 'Current';
  return `Version ${index + 1}`;
}

function firstSafePreviewUrl(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function elementContentPreview(content: Record<string, unknown> | null | undefined) {
  if (!content) return '';
  const text = typeof content.text === 'string'
    ? content.text
    : typeof content.label === 'string'
      ? content.label
      : typeof content.title === 'string'
        ? content.title
        : typeof content.value === 'string'
          ? content.value
          : '';
  return text.trim().slice(0, 160);
}

function semanticElementLabel(elementType: string) {
  const normalized = elementType.trim().toLowerCase();
  if (['title', 'heading', 'headline'].includes(normalized)) return 'Title / heading';
  if (['body', 'paragraph', 'text'].includes(normalized)) return 'Paragraph / body text';
  if (['name', 'person_name', 'company_name'].includes(normalized)) return 'Person or company name';
  if (['metric', 'number', 'stat'].includes(normalized)) return 'Metric or numeric proof';
  if (['chart', 'chart_placeholder'].includes(normalized)) return 'Chart or chart data';
  if (['image', 'media', 'logo'].includes(normalized)) return 'Image / media';
  if (['shape', 'container', 'panel'].includes(normalized)) return 'Shape or visual container';
  return 'Other text block';
}

function targetCapabilities(elementType: string) {
  const normalized = elementType.trim().toLowerCase();
  const designSupported = ['title', 'heading', 'headline', 'body', 'paragraph', 'text', 'shape', 'container', 'panel', 'image', 'media', 'logo', 'chart', 'chart_placeholder', 'metric', 'number', 'stat'].includes(normalized);
  return {
    smartEdit: true,
    design: designSupported
  };
}

export function toSmartDeckUserViewModel(options: {
  workspace: SmartDeckWorkspacePayload | null;
  graph: DeckGraph;
  selectedSlideId?: string | null;
  selectedVersionId?: string | null;
  selectedGeneratedSlideId?: string | null;
  selectedElementId?: string | null;
  generatedOnly?: boolean;
}): SmartDeckUserViewModel {
  const { workspace, graph, selectedSlideId = null, selectedVersionId = null, selectedGeneratedSlideId = null, selectedElementId = null, generatedOnly = false } = options;
  const instantGenerationJobIds = new Set(
    workspace?.generationJobs
      .filter((job) => job.generationMode === 'instant_deck')
      .map((job) => job.id) ?? []
  );
  const isAllowedVersion = (version: DesignVersion) => !generatedOnly || Boolean(version.generationJobId && instantGenerationJobIds.has(version.generationJobId));
  const currentVersionId = resolveSmartDeckVersionId({ workspace, selectedSlideId, generatedOnly });
  const activeVersionId = resolveSmartDeckVersionId({ workspace, requestedVersionId: selectedVersionId, selectedSlideId, generatedOnly });
  const currentVersion = workspace?.designVersions.find((version) => version.id === currentVersionId) ?? null;
  const activeVersion = workspace?.designVersions.find((version) => version.id === activeVersionId) ?? currentVersion;

  const sourceSlides = workspace?.sourceSlides ?? [];
  const graphSlides = graph.slides ?? [];
  const slides = (sourceSlides.length > 0 ? sourceSlides : graphSlides).map((slide, index) => {
    const sourceSlideId = 'slideNumber' in slide ? slide.id : slide.id;
    const number = 'slideNumber' in slide ? (slide.slideNumber ?? index + 1) : slide.slideNumber ?? slide.slideIndex + 1;
    const title = slide.title?.trim() || `Slide ${String(number).padStart(2, '0')}`;
    const sourcePreviewUrl = firstSafePreviewUrl(
      'previewImageUrl' in slide ? slide.previewImageUrl : null,
      'preview_image_url' in slide ? slide.preview_image_url : null,
      'previewUrl' in slide ? slide.previewUrl : null,
      'preview_url' in slide ? slide.preview_url : null,
      'thumbnailUrl' in slide ? slide.thumbnailUrl : null,
      'thumbnail_url' in slide ? slide.thumbnail_url : null
    );
    const sourceThumbnailUrl = firstSafePreviewUrl(
      'thumbnailUrl' in slide ? slide.thumbnailUrl : null,
      'thumbnail_url' in slide ? slide.thumbnail_url : null,
      sourcePreviewUrl
    );
    const generatedSlide = resolveGeneratedSlideForSource(
      activeVersion?.generatedSlides ?? [],
      sourceSlideId,
      sourceSlideId === selectedSlideId ? selectedGeneratedSlideId : null
    );
    const generatedPreviewUrl = firstSafePreviewUrl(
      generatedSlide?.previewImageUrl,
      generatedSlide?.preview_image_url,
      generatedSlide?.previewUrl,
      generatedSlide?.preview_url,
      generatedSlide?.thumbnailUrl,
      generatedSlide?.thumbnail_url
    );
    const htmlSlide = toHtmlCompiledSlideRenderIdentity(options.graph.deck.id, activeVersion ?? null, generatedSlide);

    const previewStatus: GeneratedSlidePreviewStatus | 'source_only' = generatedSlide
      ? generatedSlide.previewStatus ?? (generatedPreviewUrl ? 'ready' : 'pending')
      : 'source_only';
    const schemaStatus: GeneratedSlideSchemaStatus | 'source_only' = generatedSlide
      ? generatedSlide.schemaStatus ?? 'ready'
      : 'source_only';

    return {
      id: sourceSlideId,
      number,
      title,
      // Generated visual truth must not silently degrade into source media.
      // Source media is kept separately for an explicitly labelled source-only state.
      thumbnailUrl: generatedSlide ? generatedPreviewUrl : sourceThumbnailUrl,
      previewUrl: generatedSlide ? generatedPreviewUrl : sourcePreviewUrl,
      sourceThumbnailUrl,
      sourceSlideId,
      generatedSlideId: generatedSlide?.id ?? null,
      previewStatus,
      schemaStatus,
      sourceText: 'extractedText' in slide ? slide.extractedText ?? '' : slide.rawText ?? '',
      generatedTitle: generatedSlide?.title ?? null,
      hasGeneratedVersion: Boolean(generatedSlide),
      renderMode: generatedSlide?.renderMode ?? 'scene_graph.v1',
      sectionId: generatedSlide?.sectionId ?? null,
      sourceSlideIds: generatedSlide?.sourceSlideIds ?? (generatedSlide?.sourceSlideId ? [generatedSlide.sourceSlideId] : []),
      renderProofStatus: generatedSlide?.renderProofStatus ?? 'pending',
      designVersionId: generatedSlide?.designVersionId ?? activeVersion?.id ?? null,
      htmlArtifactId: activeVersion?.htmlArtifact?.id ?? null,
      htmlSlide,
      // Contract boundary: render-schema element IDs are presentation keys;
      // variation routes require the persisted GeneratedSlideElement database ID.
      persistedElements: (generatedSlide?.elements ?? []).map((element) => ({
        id: element.id,
        elementKey: element.elementKey,
        elementType: element.elementType,
        zIndex: element.zIndex,
        x: element.x,
        y: element.y,
        width: element.width,
        height: element.height,
        locked: element.locked,
        visible: element.visible,
        content: element.content ?? null
      }))
    };
  }).filter((slide) => !generatedOnly || slide.hasGeneratedVersion);

  const selected =
    slides.find((slide) => slide.id === selectedSlideId) ??
    slides.find((slide) => slide.id === workspace?.preferences.activeSourceSlideId) ??
    slides[0] ??
    null;

  const generatedVersions =
    workspace?.designVersions.filter(isAllowedVersion).map((version, index) => ({
      id: version.id,
      label: versionLabel(index, version, workspace ?? null),
      name: version.name,
      status: version.status,
      isActive: version.isActive,
      createdAt: version.createdAt,
      slideCount: version.generatedSlides.length,
      designVersion: version
    })) ?? [];

  const deckMapContext = {
    slides: slides.map((slide) => {
      const sourceSlide = sourceSlides.find((candidate) => candidate.id === slide.id);
      return {
        slideId: slide.id,
        slideNumber: slide.number,
        title: slide.title,
        role: sourceSlide?.layoutHints && typeof sourceSlide.layoutHints === 'object' && 'role' in sourceSlide.layoutHints
          ? String(sourceSlide.layoutHints.role ?? '') || null
          : null,
        extractedText: slide.sourceText,
        thumbnailUrl: slide.thumbnailUrl,
        previewImageUrl: slide.previewUrl,
        hasGeneratedVersion: slide.hasGeneratedVersion,
        generatedSlideId: slide.generatedSlideId,
        persistedElements: (activeVersion?.generatedSlides.find((candidate) => candidate.sourceSlideId === slide.id)?.elements ?? []).map((element) => ({
          id: element.id,
          elementKey: element.elementKey,
          elementType: element.elementType,
          semanticLabel: semanticElementLabel(element.elementType),
          locked: element.locked,
          visible: element.visible,
          targetCapabilities: targetCapabilities(element.elementType),
          isSelected: element.id === selectedElementId || element.elementKey === selectedElementId,
          rawType: element.elementType,
          exactContent: typeof element.content?.text === 'string'
            ? element.content.text
            : typeof element.content?.label === 'string'
              ? element.content.label
              : typeof element.content?.title === 'string'
                ? element.content.title
                : '',
          generatedSlideId: slide.generatedSlideId,
          slideId: slide.id,
          x: element.x,
          y: element.y,
          width: element.width,
          height: element.height,
          zIndex: element.zIndex,
          contentPreview: elementContentPreview(element.content ?? null)
        }))
      };
    }),
    readyForLlm: slides.some((slide) => Boolean(slide.sourceText.trim()))
  };

  return {
    deckId: workspace?.deck.id ?? graph.deck.id,
    deckName: workspace?.deck.title ?? graph.deck.title,
    audience: workspace?.preferences.audience ?? workspace?.deck.audience ?? graph.deck.audience ?? null,
    purpose: workspace?.deck.purpose ?? graph.deck.purpose ?? null,
    slides,
    selectedSlide: selected,
    generatedVersions,
    selectedVersion: generatedVersions.find((version) => version.id === activeVersion?.id) ?? generatedVersions[0] ?? null,
    workspaceStatus: workspace?.generatedWorkspaceStatus ?? null,
    coverageComplete: workspace?.coverageComplete ?? false,
    deckMapContext
  };
}

export async function generateSmartDeckVersion(
  deckId: string,
  input: SmartDeckGenerationInput,
  polling?: { maxAttempts?: number; signal?: AbortSignal }
): Promise<SmartDeckUserGenerationResult> {
  const response = await startSmartDeckGenerationWorkflow(deckId, {
    ...input,
    designContext: input.designContext ?? buildSmartDeckDesignContext({ graph: null }),
    idempotencyKey: input.idempotencyKey ?? `smart-deck:${deckId}:${Date.now()}:${Math.random().toString(36).slice(2)}`
  });
  const finalRun = await waitForWorkflowJobCompletion(
    response.jobId,
    'Smart Deck generation failed.',
    polling?.maxAttempts,
    undefined,
    undefined,
    polling?.signal
  );

  if (finalRun.status !== 'completed') {
    throw new Error(finalRun.errorMessage ?? 'Could not generate a new version. Try again.');
  }

  const workspace = finalRun.workspace ?? (await getSmartDeckWorkspace(deckId));
  const designVersion = input.generationMode === 'instant_deck'
    ? workspace.designVersions.find((version) =>
        version.generationJobId === response.jobId &&
        (!finalRun.designVersion?.id || version.id === finalRun.designVersion.id)
      ) ?? null
    : workspace.designVersions.find((version) => version.id === (finalRun.designVersion?.id ?? resolveSmartDeckVersionId({
        workspace,
        selectedSlideId: input.activeSourceSlideId ?? input.selectedSourceSlideIds[0] ?? null,
        generatedOnly: false
      }))) ?? null;

  return { generationJobId: response.jobId, workspace, designVersion };
}

export async function refreshUserSmartDeckWorkspace(deckId: string, signal?: AbortSignal) {
  return getSmartDeckWorkspace(deckId, signal);
}

export async function retryFailedSmartDeckSlides(deckId: string, priorGenerationJobId: string) {
  return fetchApiJsonOrThrow<{ jobId: string; status: string }>(
    `/api/products/deck-aistack-codes/decks/${deckId}/workflows/retry-failed-slides`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        priorGenerationJobId,
        idempotencyKey: `mounted-retry:${priorGenerationJobId}`
      })
    },
    'Failed slides could not be retried.'
  );
}

export async function createUserSmartDeckSlide(deckId: string, input: CreateDeckSlideRequest) {
  return fetchApiJsonOrThrow<{ deckId: string; slide: { id: string } }>(
    `/api/decks/${deckId}/slides`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input)
    },
    'Slide could not be created.'
  );
}

export async function loadUserGeneratedSlideCode(deckId: string, generatedSlideId: string) {
  return getGeneratedSlideCode(deckId, generatedSlideId);
}

export async function updateUserGeneratedSlideTypography(
  deckId: string,
  generatedSlideId: string,
  input: { headingFont: string; bodyFont: string }
) {
  return fetchApiJsonOrThrow<{
    generatedSlide: { designTokens?: Record<string, string> | null };
  }>(`/api/decks/${deckId}/generated-slides/${generatedSlideId}/design-tokens`, {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input)
  }, 'Slide typography could not be saved.');
}

export async function generateUserElementVariation(
  deckId: string,
  generatedSlideId: string,
  elementId: string,
  instruction: string,
  target?: {
    baseDesignVersionId: string;
    sourceSlideId: string;
    renderElementKey: string;
    renderElementType: string;
  }
) {
  return createElementVariationJob(deckId, generatedSlideId, elementId, {
    instruction,
    variationCount: 1,
    ...target
  });
}

export async function persistUserSmartDeckSelection(
  deckId: string,
  input: {
    activeSourceSlideId?: string | null;
    activeDesignVersionId?: string | null;
    activeGeneratedSlideId?: string | null;
    selectedElementId?: string | null;
    selectedSourceSlideIds?: string[];
  }
) {
  return updateSmartDeckSelection(deckId, {
    activeSourceSlideId: input.activeSourceSlideId,
    activeDesignVersionId: input.activeDesignVersionId,
    activeGeneratedSlideId: input.activeGeneratedSlideId,
    selectedElementId: input.selectedElementId,
    selectedSourceSlideIds: input.selectedSourceSlideIds
  });

  // DISABLED: Selection previously issued a second preferences PATCH.
  // The session-state command now persists the complete selection atomically.
  // await patchSmartDeckPreferences(deckId, input);
}

export async function persistUserSmartDeckPreferences(
  deckId: string,
  input: Partial<SmartDeckWorkspacePayload['preferences']>
) {
  return patchSmartDeckPreferences(deckId, input);
}

export async function applyUserSmartDeckVersion(deckId: string, versionId: string) {
  return applyDesignVersion(deckId, versionId);
}

export async function discardUserSmartDeckVersion(deckId: string, versionId: string) {
  return discardDesignVersion(deckId, versionId);
}

export async function analyzeDeckMap(deckId: string): Promise<{
  runId: string;
  deckId: string;
  status: string;
  analysis: DeckMapAnalysis | null;
  cached: boolean;
}> {
  const { deckProductApiPath } = await import('$lib/contracts');
  const { fetchApiJsonOrThrow } = await import('$lib/api/apiError');
  const receipt = await fetchApiJsonOrThrow<{ jobId: string; jobType: 'deck_map_analysis'; status: string }>(deckProductApiPath(`/decks/${deckId}/deck-map/analyze`), {
    method: 'POST',
  }, 'Deck map analysis failed.');
  if (!receipt.jobId || receipt.jobType !== 'deck_map_analysis') {
    throw new Error('Deck map analysis did not return a valid workflow receipt.');
  }
  const completed = await waitForWorkflowJobCompletion(receipt.jobId, 'Deck map analysis failed.');
  const output = completed.output;
  if (!output || !output.analysis) {
    throw new Error('Deck map analysis completed without a persisted result.');
  }
  return output as {
    runId: string;
    deckId: string;
    status: string;
    analysis: DeckMapAnalysis;
    cached: boolean;
  };
}

export async function generateMarketResearch(deckId: string): Promise<{
  runId: string;
  deckId: string;
  status: string;
  research: MarketResearchData | null;
  cached: boolean;
}> {
  const { deckProductApiPath } = await import('$lib/contracts');
  const { fetchApiJsonOrThrow } = await import('$lib/api/apiError');
  const receipt = await fetchApiJsonOrThrow<{ jobId: string; jobType: 'market_research'; status: string }>(deckProductApiPath(`/decks/${deckId}/market-research`), {
    method: 'POST',
  }, 'Market research failed.');
  if (!receipt.jobId || receipt.jobType !== 'market_research') {
    throw new Error('Market research did not return a valid workflow receipt.');
  }
  const completed = await waitForWorkflowJobCompletion(receipt.jobId, 'Market research failed.');
  const output = completed.output;
  if (!output || !output.research) {
    throw new Error('Market research completed without a persisted result.');
  }
  return output as {
    runId: string;
    deckId: string;
    status: string;
    research: MarketResearchData;
    cached: boolean;
  };
}

export interface DeckMapAnalysis {
  company: {
    name: string | null;
    stage: string | null;
    industry: string | null;
    businessModel: string | null;
    foundingTeam: string | null;
    headquarters: string | null;
  };
  narrative: {
    arcType: string;
    flowAssessment: string;
    strengthAreas: string[];
    weakAreas: string[];
    recommendedRestructuring: string | null;
  };
  slides: Array<{
    slideId: string;
    title: string;
    role: string;
    purposeAssessment: string;
    narrativeContribution: string;
    strength: string;
    improvementSuggestion: string | null;
  }>;
  evidence: {
    overallStrength: string;
    quantitativeClaims: number;
    qualitativeClaims: number;
    dataSourcesCited: number;
    strongAreas: string[];
    weakAreas: string[];
  };
  gaps: Array<{
    area: string;
    importance: string;
    suggestion: string;
  }>;
  qualityScore: {
    overall: number;
    narrativeFlow: number;
    evidenceQuality: number;
    investorReadiness: number;
    visualStructure: number;
  };
  system?: {
    provider?: string;
    model?: string | null;
    promptPackage?: { name?: string; version?: string };
    vectorRetrieval?: { status?: string; message?: string | null; chunkCount?: number };
    vectorSync?: { status?: string; message?: string | null; chunkCount?: number };
  };
}

export interface MarketResearchData {
  sources?: Array<{
    id: string;
    title: string;
    url?: string | null;
    provider?: string | null;
    publishedDate?: string | null;
  }>;
  citationStatus?: 'cited' | 'partial' | 'no_sources' | string;
  company: {
    name: string | null;
    description: string | null;
    foundedYear: number | null;
    headquarters: string | null;
    businessModel: string | null;
    fundingStage: string | null;
    totalRaised: string | null;
    teamSize: string | null;
    keyFinding: string | null;
    citationIds?: string[];
    keyFindingCitationIds?: string[];
  };
  marketSizing: {
    tam: string | null;
    sam: string | null;
    som: string | null;
    growthRate: string | null;
    sourceConfidence: string;
    note: string | null;
    citationIds?: string[];
  };
  competitors: Array<{
    name: string;
    category: string;
    threats: string | null;
    weaknesses: string | null;
    differentiation: string | null;
    citationIds?: string[];
  }>;
  industryTrends: string | null;
  industryTrendCitationIds?: string[];
  investmentThesis: {
    summary: string;
    strengths: string[];
    weaknesses: string[];
    differentiators: string[];
    citationIds?: string[];
  };
  risks: Array<{
    risk: string;
    severity: string;
    mitigation: string | null;
    citationIds?: string[];
  }>;
  vcAssessment: {
    score: number;
    stageFit: string;
    strengths: string[];
    concerns: string[];
    diligenceQuestions: string[];
    citationIds?: string[];
  };
  system?: {
    provider?: string;
    model?: string | null;
    promptPackage?: { name?: string; version?: string };
    vectorRetrieval?: { status?: string; message?: string | null; chunkCount?: number };
    vectorSync?: { status?: string; message?: string | null; chunkCount?: number };
  };
}
