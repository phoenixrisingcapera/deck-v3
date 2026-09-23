import type { DesignBatchPreview } from '@deck-aistack-codes/shared';
import { deckProductApiPath } from '$lib/contracts';
import type {
  SmartDeckDeckType,
  SmartDeckGenerationTopicRequest,
  SmartDeckSubject,
  SmartDeckSubjectDetection
} from '$lib/types/smart-deck-subjects';
import { fetchApiJsonOrThrow } from '$lib/api/apiError';
import { waitForWorkflowJobCompletion } from '$lib/api/deckService/workflow.client';
import type { SmartDeckDesignContext } from '$lib/components/instant-deck/designFallback';

export { waitForWorkflowJobCompletion };

export type SmartDeckGenerationStatus = 'idle' | 'running' | 'ready' | 'failed';

export type SmartDeckSaveStatus = 'idle' | 'saving' | 'saved' | 'failed';
type GeneratedSlideValidationStatus = 'valid' | 'warning' | 'invalid' | 'unknown';
export type GeneratedSlidePreviewStatus = 'pending' | 'ready' | 'failed';
export type GeneratedSlideSchemaStatus = 'ready' | 'unavailable';
export type GeneratedWorkspaceStatus =
  | 'no_version'
  | 'queued'
  | 'running'
  | 'incomplete'
  | 'preview_pending'
  | 'preview_failed'
  | 'schema_unavailable'
  | 'candidate_ready'
  | 'saved_ready';

interface RenderSchemaElement {
  id: string;
  type: 'text' | 'shape' | 'image' | 'chart_placeholder';
  text?: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex?: number | null;
  fontSize?: number | null;
  fontWeight?: string | null;
  colorToken?: string | null;
  fillToken?: string | null;
  assetUrl?: string | null;
  analyticsKey?: string | null;
}

interface RenderSchemaBackgroundLayer {
  id: string;
  type: 'shape' | 'image';
  shape?: 'rectangle' | 'circle' | 'line' | null;
  role?: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex?: number;
  style?: {
    fill?: string | null;
    opacity?: number | null;
    radius?: number | null;
  } | null;
  assetUrl?: string | null;
}

export interface RenderSchema {
  schemaVersion: 'smart-deck-render-schema.v1';
  width: number;
  height: number;
  background: {
    type: 'token' | 'color' | 'gradient' | 'image' | 'layered';
    value?: string | null;
    fill?: string | null;
    layers?: RenderSchemaBackgroundLayer[];
  };
  brandTokensUsed?: string[];
  analytics?: {
    slidePurpose?: string | null;
    designRationale?: string | null;
    deckVariantId?: string | null;
    deckVariantLabel?: string | null;
    deckVariantRationale?: string | null;
    slideArchetypeId?: string | null;
    slideArchetypeLabel?: string | null;
    narrativeRole?: string | null;
    speakerNotes?: string | null;
    audience?: string | null;
    sourceFactIds?: string[];
    sourceFactsUsed?: string[];
    assumptions?: string[];
    missingInputs?: string[];
    qualityWarnings?: string[];
    confidence?: number | null;
    trackedEvents?: string[];
  };
  exportMetadata?: {
    exportReady?: boolean;
    renderer?: 'smart_deck_scene_graph';
    supportedFormats?: string[];
  };
  elements: RenderSchemaElement[];
}

interface GeneratedSlideElementVersion {
  id: string;
  elementId: string;
  generatedSlideId: string;
  designVersionId: string;
  versionNumber: number;
  source: string;
  status: string;
  style?: Record<string, unknown> | null;
  content?: Record<string, unknown> | null;
  changeSummary?: string | null;
  createdAt: string;
}

interface GeneratedSlideElement {
  id: string;
  generatedSlideId: string;
  deckId: string;
  designVersionId: string;
  sourceSlideId?: string | null;
  elementKey: string;
  elementType: string;
  parentElementId?: string | null;
  zIndex: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  locked: boolean;
  visible: boolean;
  style?: Record<string, unknown> | null;
  content?: Record<string, unknown> | null;
  versions: GeneratedSlideElementVersion[];
  createdAt: string;
  updatedAt: string;
}

export interface SmartDeckSourceSlide {
  id: string;
  deckId: string;
  slideNumber: number;
  title: string;
  extractedText: string;
  thumbnailUrl?: string | null;
  thumbnail_url?: string | null;
  previewImageUrl?: string | null;
  preview_image_url?: string | null;
  previewUrl?: string | null;
  preview_url?: string | null;
  layoutHints?: Record<string, unknown>;
  blocks?: unknown[];
}

interface SmartDeckWorkspaceState {
  id: string;
  deckId: string;
  userId?: string | null;
  activeDesignVersionId?: string | null;
  activeSourceSlideId?: string | null;
  activeGeneratedSlideId?: string | null;
  selectedElementId?: string | null;
  status: 'ready' | 'generating' | 'reviewing' | 'failed' | string;
  createdAt: string;
  updatedAt: string;
}

interface SmartDeckPreferences {
  id: string;
  workspaceId: string;
  deckId: string;
  selectedSourceSlideIds: string[];
  activeSourceSlideId?: string | null;
  activeDesignVersionId?: string | null;
  activeGeneratedSlideId?: string | null;
  selectedElementId?: string | null;
  audience?: string | null;
  deckType?: SmartDeckDeckType | null;
  preferredModel?: string | null;
  selectedSubject?: SmartDeckSubject | null;
  selectedActionId?: string | null;
  zoomLevel: number;
  canvasFitMode: 'fit' | 'fill' | 'actual_size';
  rightPanelOpen: boolean;
  slideRailOpen: boolean;
  updatedAt: string;
}

export interface SmartDeckChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
  selectedSourceSlideIds?: string[];
  generationBatchId?: string | null;
  metadata?: Record<string, unknown> | null;
}

interface BackendGeneratedSlide {
  id: string;
  deckId: string;
  designVersionId: string;
  generationJobId?: string | null;
  sourceSlideId?: string | null;
  slideNumber: number;
  title: string;
  status: string;
  renderSchema: Record<string, unknown> | null;
  renderMode?: 'scene_graph.v1' | 'html_compiled.v1';
  sectionId?: string | null;
  sectionSha256?: string | null;
  compilationHash?: string | null;
  sourceSlideIds?: string[];
  renderProofStatus?: 'pending' | 'ready' | 'failed';
  designRationale?: string | null;
  speakerNotes?: string | null;
  sourceFactIds?: string[];
  sourceFactsUsed?: string[];
  assumptions?: string[];
  missingInputs?: string[];
  qualityWarnings?: string[];
  confidence?: number | null;
  qualityFlags?: string[];
  variantId?: string | null;
  variantLabel?: string | null;
  variantRationale?: string | null;
  archetypeId?: string | null;
  archetypeLabel?: string | null;
  narrativeRole?: string | null;
  designTokens?: Record<string, string> | null;
  previewImageUrl?: string | null;
  previewStatus?: GeneratedSlidePreviewStatus;
  schemaStatus?: GeneratedSlideSchemaStatus;
  preview_image_url?: string | null;
  previewUrl?: string | null;
  preview_url?: string | null;
  thumbnailUrl?: string | null;
  thumbnail_url?: string | null;
  validationStatus: GeneratedSlideValidationStatus | string;
  elements?: GeneratedSlideElement[];
  createdAt: string;
  updatedAt: string;
}

export interface DesignVersion {
  id: string;
  version_id?: string;
  deckId: string;
  deck_id?: string;
  generationJobId?: string | null;
  name: string;
  status: string;
  isActive: boolean;
  summary?: string | null;
  artifactType?: 'render_schema.v1' | 'full_html_deck.v1';
  renderMode?: 'scene_graph.v1' | 'html_compiled.v1';
  htmlArtifact?: {
    id: string;
    sha256: string;
    slideCount: number;
    parserVersion?: string | null;
    compilerVersion?: string | null;
    sanitizerPolicyVersion?: string | null;
    rendererVersion: string;
  } | null;
  renderProofStatus?: 'pending' | 'ready' | 'failed' | null;
  sourceSlideIds?: string[];
  source_slide_ids?: string[];
  selectedElementIds?: string[];
  selected_element_ids?: string[];
  promptTask?: string | null;
  prompt_task?: string | null;
  audience?: string | null;
  deckType?: string | null;
  deck_type?: string | null;
  model?: string | null;
  validationStatus?: string | null;
  validation_status?: string | null;
  previewAssetUrl?: string | null;
  preview_asset_url?: string | null;
  previewAssetKey?: string | null;
  preview_asset_key?: string | null;
  errorMessage?: string | null;
  error_message?: string | null;
  generatedSlides: BackendGeneratedSlide[];
  createdAt: string;
  updatedAt: string;
}

export interface SmartDeckWorkspacePayload {
  deck: {
    id: string;
    workspaceId?: string | null;
    title: string;
    status: string;
    audience?: string | null;
    purpose?: string | null;
    summary?: string | null;
  };
  workspace: SmartDeckWorkspaceState;
  preferences: SmartDeckPreferences;
  messages: SmartDeckChatMessage[];
  designTokens: Array<Record<string, unknown>>;
  sourceSlides: SmartDeckSourceSlide[];
  generationJobs: Array<{
    id: string;
    deckId: string;
    status: string;
    prompt: string;
    selectedSourceSlideIds: string[];
    failedSlideIds?: string[];
    coverageComplete?: boolean | null;
    generationMode?: 'standard' | 'instant_deck';
    createdAt: string;
  }>;
  designVersions: DesignVersion[];
  savedDeckVersionId?: string | null;
  savedDeckVersionNumber?: number | null;
  savedDesignVersionId?: string | null;
  candidateDesignVersionId?: string | null;
  resolvedDesignVersionId?: string | null;
  generatedWorkspaceStatus?: GeneratedWorkspaceStatus;
  requestedSourceSlideIds?: string[];
  generatedSourceSlideIds?: string[];
  missingSourceSlideIds?: string[];
  coverageComplete?: boolean;
  activeDesignVersionId?: string | null;
  activeSourceSlideId?: string | null;
  activeGeneratedSlideId?: string | null;
  generatedSlides: BackendGeneratedSlide[];
  investmentCritique?: {
    status: 'ready';
    advisory: true;
    internalProductOnly: true;
    publicationBlocking: false;
    strengths: string[];
    concerns: string[];
    missingProof: string[];
    investorObjections: string[];
    recommendedChanges: string[];
    severity: {
      advisory: string[];
      important: string[];
      criticalForFundraising: string[];
    };
    nextAction: string;
  } | null;
  visualIntelligence?: {
    status: 'ready';
    schemaVersion: 'visual-intelligence.v1';
    internalProductOnly: true;
    publicationBlocking: false;
    visualDirection: {
      design_thesis?: string;
      concept?: string;
      brand_character?: string[];
      typography_direction?: string;
      color_strategy?: string;
      imagery_strategy?: string;
      data_visualization_direction?: string;
      diagram_language?: string;
      density?: string;
      whitespace_strategy?: string;
      avoid?: string[];
    };
    slideVisualBriefs: Array<Record<string, unknown>>;
    chartSpecCount: number;
    diagramSpecCount: number;
    visionReviewStatus: 'not_requested' | 'pending' | 'completed';
  } | null;
  visionReview?: {
    status: 'ready';
    schema_version: 'vision-review.v1';
    internalProductOnly: true;
    publicationBlocking: false;
    rendered_artifact_ids: string[];
    findings: Array<{
      slide_id?: string | null;
      issue: string;
      severity: 'advisory' | 'important' | 'critical_for_visual_quality';
      dimension: string;
    }>;
    strengths: string[];
  } | null;
  sourceSummary?: {
    status: 'verified' | 'no_verified_sources';
    internalProductOnly: true;
    exportedWithDeck: false;
    sources: Array<{
      evidenceId: string;
      topic?: string | null;
      publisher?: string | null;
      url: string;
      publicationDate?: string | null;
      retrievalDate?: string | null;
      summary?: string | null;
    }>;
  };
  knowledgeMetadata?: Record<string, unknown> | null;
  runtimeContext?: Record<string, unknown> | null;
  runtimeCapabilities?: {
    schemaVersion?: string;
    knowledgeMetadata?: Record<string, unknown>;
    productBoundary?: Record<string, unknown>;
    llmTasks?: Array<{
      key: string;
      inputs: string[];
      outputs: string[];
    }>;
    guardrailGroups?: Array<{
      group: string;
      rules: string[];
    }>;
    llmExtensions?: string[];
    schemas?: string[];
    prompts?: string[];
    enabledSmartDeckCapabilities?: string[];
    instructions?: string[];
    instantDeck?: {
      generationMode?: 'instant_deck';
      defaultPrompt?: string | null;
      knowledgePack?: Record<string, unknown> | null;
      promptPackage?: { name?: string; version?: string; sections?: string[] } | null;
      agentOrchestration?: {
        agentKey?: string;
        execution?: string;
        commandRoute?: string;
        workflowJobType?: string | null;
        jobChain?: string[];
        workerServices?: string[];
        providerUseCase?: string;
        requiredInputFields?: string[];
      } | null;
      referenceRegistry?: Record<string, unknown> | null;
      embeddingSeedSources?: Record<string, unknown> | null;
    } | null;
  } | null;
}

export interface SmartDeckGenerationInput {
  prompt: string;
  selectedSourceSlideIds: string[];
  idempotencyKey?: string;
  activeSourceSlideId?: string | null;
  selectedElementId?: string | null;
  deckType?: SmartDeckDeckType;
  audience?: string | null;
  preferredModel?: string | null;
  selectedSubject?: SmartDeckSubject | null;
  detectedSubjects?: SmartDeckSubjectDetection[];
  actionId?: string | null;
  actionPrompt?: string | null;
  userPrompt?: string | null;
  latestBatchId?: string | null;
  designContext?: SmartDeckDesignContext;
  provenance?: SmartDeckGenerationProvenance;
  generationMode?: 'standard' | 'instant_deck';
  outputContract?: 'render_schema.v1' | 'full_html_deck.v1';
  baseDesignVersionId?: string | null;
}

export interface InstantHtmlCapability {
  artifactId: string;
  artifactSha256: string;
  designVersionId: string;
  artifactEncryptionKeyVersion: string;
  generatedSlideId: string;
  sectionId: string;
  scope: 'section' | 'full_deck';
  renderMode: 'html_compiled.v1';
  renderProofStatus: 'ready';
  renderUrl: string;
  expiresAt: string;
}

export interface HtmlCompiledSlideRenderIdentity {
  deckId: string;
  designVersionId: string;
  htmlArtifactId: string;
  artifactSha256: string;
  generatedSlideId: string;
  sectionId: string;
  sectionSha256: string | null;
  compilationHash: string | null;
  renderMode: 'html_compiled.v1';
  renderProofStatus: 'pending' | 'ready' | 'failed';
}

const instantHtmlCapabilityCache = new Map<string, { request: Promise<InstantHtmlCapability>; expiresAt: number }>();

// The workspace artifact identity does not expose a trusted expected key
// version. The client can therefore require capability presence only; backend
// redemption remains authoritative for key-version equality and validity.
function hasArtifactEncryptionKeyVersion(capability: InstantHtmlCapability) {
  return typeof capability.artifactEncryptionKeyVersion === 'string'
    && Boolean(capability.artifactEncryptionKeyVersion.trim());
}

export async function mintInstantHtmlCapability(deckId: string, artifactId: string, generatedSlideId: string, scope: 'section' | 'full_deck' = 'section') {
  return requestJson<InstantHtmlCapability>(
    deckProductApiPath(`/decks/${deckId}/html-artifacts/${artifactId}/slides/${generatedSlideId}/capability?scope=${scope}`),
    { method: 'POST' }
  );
}

export async function mintInstantHtmlFullDeckCapability(slide: HtmlCompiledSlideRenderIdentity) {
  const capability = await mintInstantHtmlCapability(slide.deckId, slide.htmlArtifactId, slide.generatedSlideId, 'full_deck');
  if (
    capability.scope !== 'full_deck'
    || capability.designVersionId !== slide.designVersionId
    || capability.artifactId !== slide.htmlArtifactId
    || capability.artifactSha256 !== slide.artifactSha256
    || capability.generatedSlideId !== slide.generatedSlideId
    || capability.renderMode !== 'html_compiled.v1'
    || capability.renderProofStatus !== 'ready'
    || !hasArtifactEncryptionKeyVersion(capability)
  ) {
    throw new Error('Compiled full-deck capability identity did not match.');
  }
  const expiresAt = Date.parse(capability.expiresAt);
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now() + 5_000) {
    throw new Error('Compiled full-deck capability is expired or missing a valid expiry.');
  }
  return capability;
}

export function getCachedInstantHtmlCapability(slide: HtmlCompiledSlideRenderIdentity) {
  const key = [slide.deckId, slide.designVersionId, slide.htmlArtifactId, slide.artifactSha256, slide.generatedSlideId, slide.sectionId, slide.sectionSha256, slide.compilationHash].join(':');
  const cached = instantHtmlCapabilityCache.get(key);
  if (cached && cached.expiresAt > Date.now() + 30_000) return cached.request;
  if (cached) instantHtmlCapabilityCache.delete(key);

  const request = mintInstantHtmlCapability(slide.deckId, slide.htmlArtifactId, slide.generatedSlideId, 'section')
    .then((capability) => {
      if (
        capability.artifactId !== slide.htmlArtifactId ||
        capability.artifactSha256 !== slide.artifactSha256 ||
        capability.designVersionId !== slide.designVersionId ||
        capability.scope !== 'section' ||
        capability.generatedSlideId !== slide.generatedSlideId ||
        capability.sectionId !== slide.sectionId ||
        capability.renderMode !== 'html_compiled.v1' ||
        capability.renderProofStatus !== 'ready' ||
        !hasArtifactEncryptionKeyVersion(capability)
      ) {
        throw new Error('Compiled slide capability identity did not match.');
      }
      const expiresAt = Date.parse(capability.expiresAt);
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now() + 5_000) {
        throw new Error('Compiled slide capability is expired or missing a valid expiry.');
      }
      instantHtmlCapabilityCache.set(key, {
        request: Promise.resolve(capability),
        expiresAt
      });
      return capability;
    })
    .catch((error) => {
      instantHtmlCapabilityCache.delete(key);
      throw error;
    });
  instantHtmlCapabilityCache.set(key, { request, expiresAt: Number.POSITIVE_INFINITY });
  return request;
}

export interface SmartDeckGenerationProvenance {
  mode: 'due_diligence_full_deck';
  audience: string;
  audienceArtifactId?: string | null;
  diligenceArtifactIds: string[];
}

export type SlideRedesignTaskContext = 'standard' | 'background_vision';

export interface SlideRedesignVisionExecution {
  status: string;
  executed: boolean;
}

export interface SlideRedesignRun {
  runId: string;
  deckId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  scope: 'selected_slides' | 'current_slide' | 'selected_element';
  selectedSlideIds: string[];
  designVersionId: string | null;
  design_version_id?: string | null;
  workspace: SmartDeckWorkspacePayload | null;
  visionExecution: SlideRedesignVisionExecution;
  visionEvidence?: { status: 'pending' | 'ready' | 'unavailable' | 'unsupported_provider' | 'failed'; executed: boolean; taskContext: 'background_vision'; provider?: string | null; model?: string | null; context?: { imageCount?: number; slideId?: string | null } } | null;
}

export async function createSlideRedesignRun(input: {
  deckId: string;
  currentSlideId?: string;
  slideId?: string;
  generatedSlideId?: string;
  baseDesignVersionId?: string;
  instruction: string;
  audience?: string | null;
  taskContext?: 'slide_content' | 'background_vision' | 'standard';
  targetKind?: 'slide' | 'background' | 'element';
  scope?: string;
  selectedSlideIds?: string[];
}): Promise<SlideRedesignRun> {
  const slideId = input.slideId ?? input.currentSlideId;
  if (!slideId) throw new Error('createSlideRedesignRun requires slideId or currentSlideId.');
  return requestJson('/api/assistant/slide-redesign-runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      deckId: input.deckId,
      scope: input.scope ?? 'current_slide',
      currentSlideId: slideId,
      selectedSlideIds: input.selectedSlideIds ?? [slideId],
      generatedSlideId: input.generatedSlideId,
      baseDesignVersionId: input.baseDesignVersionId,
      instruction: input.instruction,
      audience: input.audience ?? null,
      taskContext: input.taskContext ?? 'standard',
      targetKind: input.targetKind
    })
  });
}

export async function getSlideRedesignRun(runId: string): Promise<SlideRedesignRun> {
  return requestJson(`/api/assistant/slide-redesign-runs/${encodeURIComponent(runId)}`);
}

export async function waitForSlideRedesignRun(runId: string, deckId?: string, slideId?: string): Promise<SlideRedesignRun> {
  for (let poll = 0; poll < 300; poll += 1) {
    const run = await getSlideRedesignRun(runId);
    if (deckId && slideId && (run.deckId !== deckId || !run.selectedSlideIds.includes(slideId))) {
      throw new Error('Slide redesign identity no longer matches the selected slide.');
    }
    if (run.status === 'completed') return run;
    if (run.status === 'failed') throw new Error('Slide redesign failed.');
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  throw new Error('Slide redesign timed out.');
}

interface SmartDeckGenerationResponse {
  jobId: string;
  jobType: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase?: string;
  workflowStateUrl?: string;
  jobUrl?: string;
}

type RawSmartDeckGenerationResponse = {
  jobId?: string;
  runId?: string;
  run_id?: string;
  generationJob?: {
    id?: string;
  } | null;
  jobType?: string;
  job_type?: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase?: string;
  workflowStateUrl?: string;
  workflow_state_url?: string;
  jobUrl?: string;
  job_url?: string;
};

export interface SmartDeckGenerationWorkflowResult {
  jobId: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'failed_retryable' | 'failed_final' | 'blocked' | 'timed_out';
  error?: { message: string } | null;
  errorMessage?: string | null;
  artifacts?: Array<Record<string, unknown>> | null;
  designVersion?: DesignVersion | null;
  workspace?: SmartDeckWorkspacePayload | null;
}

interface ElementVariationJob {
  id: string;
  deckId: string;
  workspaceId: string;
  generatedSlideId: string;
  elementId: string;
  baseElementVersionId?: string | null;
  instruction: string;
  variationCount: number;
  status: string;
  outputElementVersionId?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface GeneratedSlideCode {
  generatedSlideId: string;
  schemaJson: RenderSchema;
  renderSchema: RenderSchema;
  designTokens?: Record<string, string> | null;
  codeMetadata?: Record<string, unknown> | null;
  validationStatus: GeneratedSlideValidationStatus;
  validationMessages: string[];
}

export type ManualEditOperation =
  | { operation: 'move'; persistedElementId: string; elementKey: string; x: number; y: number }
  | { operation: 'resize'; persistedElementId: string; elementKey: string; width: number; height: number };

export interface ManualEditJobResponse {
  manualEditJob: {
    id: string;
    status: 'completed';
    baseDesignVersionId: string;
    baseGeneratedSlideId: string;
    sourceSlideId: string;
    candidateDesignVersionId: string;
    candidateGeneratedSlideId: string;
    idempotencyKey: string;
    operationCount: number;
    createdAt: string;
  };
  candidateDesignVersion: DesignVersion;
  generatedSlide: DesignVersion['generatedSlides'][number];
  renderSchema: RenderSchema;
}

export interface SmartDeckAssistantRunResponse {
  runId: string;
  deckId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  intentType?: string;
  scope?: string;
  outputType?: string;
  inputContext?: Record<string, unknown>;
  insight?: {
    title: string;
    summary: string;
    content: Record<string, unknown>;
    confidence: 'low' | 'medium' | 'high';
    assumptions: string[];
    missingEvidence: string[];
    suggestedSlideUpdate?: string | null;
    recommendedAction: 'save_insight' | 'add_to_slide' | 'create_version' | 'none';
  } | null;
  assistantMessage?: SmartDeckChatMessage | null;
  savedArtifactId?: string | null;
}

export async function getSmartDeckWorkspace(deckId: string, signal?: AbortSignal): Promise<SmartDeckWorkspacePayload> {
  return requestJson<SmartDeckWorkspacePayload>(`/api/decks/${deckId}/smart-deck`, { signal });
}

export async function createSmartDeckAssistantRun(input: {
  deckId: string;
  instruction: string;
  currentSlideId?: string | null;
  audience?: string | null;
}): Promise<SmartDeckAssistantRunResponse> {
  return requestJson<SmartDeckAssistantRunResponse>('/api/assistant/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      deckId: input.deckId,
      intentType: input.currentSlideId ? 'slide_critique' : 'narrative_flow',
      scope: input.currentSlideId ? 'current_slide' : 'whole_deck',
      currentSlideId: input.currentSlideId ?? null,
      selectedSlideIds: input.currentSlideId ? [input.currentSlideId] : [],
      instruction: input.instruction,
      audience: input.audience ?? null
    })
  });
}

function normalizeSlideRedesignRun(raw: Record<string, unknown>): SlideRedesignRun {
  const generationJob = raw.generationJob && typeof raw.generationJob === 'object'
    ? raw.generationJob as Record<string, unknown>
    : null;
  const output = raw.output && typeof raw.output === 'object' ? raw.output as Record<string, unknown> : null;
  const visionValue = raw.visionExecution ?? raw.vision_execution ?? output?.visionExecution ?? output?.vision_execution;
  const visionExecution = visionValue && typeof visionValue === 'object'
    ? visionValue as Record<string, unknown>
    : null;
  return {
    runId: String(raw.runId ?? raw.run_id ?? generationJob?.id ?? ''),
    deckId: String(raw.deckId ?? raw.deck_id ?? generationJob?.deckId ?? ''),
    status: String(raw.status ?? generationJob?.status ?? 'queued') as SlideRedesignRun['status'],
    scope: String(raw.scope ?? 'selected_slides') as SlideRedesignRun['scope'],
    selectedSlideIds: Array.isArray(raw.selectedSlideIds)
      ? raw.selectedSlideIds.map(String)
      : Array.isArray(raw.selected_slide_ids) ? raw.selected_slide_ids.map(String) : [],
    designVersionId: typeof raw.designVersionId === 'string'
      ? raw.designVersionId
      : typeof raw.design_version_id === 'string' ? raw.design_version_id : null,
    workspace: raw.workspace && typeof raw.workspace === 'object' ? raw.workspace as SmartDeckWorkspacePayload : null,
    visionExecution: {
      status: typeof visionExecution?.status === 'string' ? visionExecution.status : 'not_proven',
      executed: visionExecution?.executed === true
    }
  };
}

export async function getGeneratedSlideCode(deckId: string, generatedSlideId: string): Promise<GeneratedSlideCode> {
  const payload = await requestJson<{
    codeVersion: {
      generatedSlideId: string;
      renderSchema: RenderSchema;
      status: GeneratedSlideValidationStatus;
      validationErrors?: Array<Record<string, unknown>>;
      codeJson?: Record<string, unknown> | null;
    };
    generatedSlide: {
      designTokens?: Record<string, string> | null;
    };
  }>(`/api/decks/${deckId}/generated-slides/${generatedSlideId}/code`);

  return {
    generatedSlideId: payload.codeVersion.generatedSlideId,
    schemaJson: payload.codeVersion.renderSchema,
    renderSchema: payload.codeVersion.renderSchema,
    designTokens: payload.generatedSlide.designTokens ?? null,
    codeMetadata: payload.codeVersion.codeJson ?? null,
    validationStatus: payload.codeVersion.status,
    validationMessages: payload.codeVersion.validationErrors?.map((item) => JSON.stringify(item)) ?? ['render schema is valid']
  };
}

export async function createGeneratedSlideManualEditJob(input: {
  deckId: string;
  generatedSlideId: string;
  baseDesignVersionId: string;
  sourceSlideId: string;
  idempotencyKey: string;
  operations: ManualEditOperation[];
}): Promise<ManualEditJobResponse> {
  return requestJson<ManualEditJobResponse>(
    `/api/decks/${input.deckId}/generated-slides/${input.generatedSlideId}/manual-edit-jobs`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        baseDesignVersionId: input.baseDesignVersionId,
        sourceSlideId: input.sourceSlideId,
        idempotencyKey: input.idempotencyKey,
        operations: input.operations
      })
    }
  );
}

export async function startSmartDeckGenerationWorkflow(
  deckId: string,
  input: SmartDeckGenerationInput
): Promise<SmartDeckGenerationResponse> {
  const payload = await requestJson<RawSmartDeckGenerationResponse>(deckProductApiPath(`/decks/${deckId}/workflows/smart-deck-generation`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });

  const jobId = payload.jobId ?? payload.runId ?? payload.run_id ?? payload.generationJob?.id ?? '';
  if (!jobId) {
    throw new Error('Smart Deck generation started without a workflow job id.');
  }

  return {
    jobId,
    jobType: payload.jobType ?? payload.job_type ?? 'smart_deck_generation',
    status: payload.status,
    phase: payload.phase,
    workflowStateUrl: payload.workflowStateUrl ?? payload.workflow_state_url,
    jobUrl: payload.jobUrl ?? payload.job_url
  };
}

export async function createElementVariationJob(
  deckId: string,
  generatedSlideId: string,
  elementId: string,
  input: {
    instruction: string;
    variationCount?: number;
    baseDesignVersionId?: string;
    sourceSlideId?: string;
    renderElementKey?: string;
    renderElementType?: string;
  }
): Promise<{
  variationJob: {
    id: string;
    generatedSlideId: string;
  };
  element: {
    id: string;
  };
  generatedSlide?: {
    id: string;
  } | null;
  designVersion?: DesignVersion | null;
  workspace?: SmartDeckWorkspacePayload | null;
}> {
  return requestJson(`/api/decks/${deckId}/generated-slides/${generatedSlideId}/elements/${elementId}/variation-jobs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });
}

export async function applyDesignVersion(
  deckId: string,
  versionId: string
): Promise<{ versionId: string; status: 'saved' }> {
  const payload = await requestJson<{ jobId?: string }>(deckProductApiPath(`/decks/${deckId}/workflows/apply-design-version`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      designVersionId: versionId,
      idempotencyKey: `apply-design-version:${deckId}:${versionId}:${Date.now()}`
    })
  });
  if (!payload.jobId) {
    throw new Error('Design version apply did not return a workflow job id.');
  }
  await waitForWorkflowJobCompletion(payload.jobId, 'Design version apply failed.');
  return {
    versionId,
    status: 'saved'
  };
}

export async function discardDesignVersion(deckId: string, versionId: string): Promise<DesignVersion[]> {
  const payload = await requestJson<{ designVersions: DesignVersion[] }>(
    `/api/decks/${deckId}/design-versions/${versionId}/discard`,
    { method: 'POST' }
  );
  return payload.designVersions;
}

export async function restoreDesignVersion(deckId: string, versionId: string): Promise<DesignVersion[]> {
  const payload = await requestJson<{ designVersions: DesignVersion[] }>(
    `/api/decks/${deckId}/design-versions/${versionId}/restore`,
    { method: 'POST' }
  );
  return payload.designVersions;
}

export async function updateSmartDeckSelection(
  deckId: string,
  input: {
    activeSourceSlideId?: string | null;
    activeDesignVersionId?: string | null;
    activeGeneratedSlideId?: string | null;
    selectedElementId?: string | null;
    selectedSourceSlideIds?: string[];
  }
): Promise<SmartDeckWorkspacePayload['preferences']> {
  return requestJson(`/api/decks/${deckId}/smart-deck/session-state`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });
}

export async function patchSmartDeckPreferences(
  deckId: string,
  input: Partial<SmartDeckWorkspacePayload['preferences']>
): Promise<SmartDeckWorkspacePayload['preferences']> {
  return requestJson(`/api/decks/${deckId}/smart-deck/preferences`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  return fetchApiJsonOrThrow<T>(path, init, `${init.method || 'GET'} ${path} failed`);
}
