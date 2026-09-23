import { error, redirect } from '@sveltejs/kit';
import { BACKEND_URL } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';
import { createDependencyStatus, createDeveloperToolsPayload } from '$lib/developer-tools/payload';
import { canMountInstantDeckRecovery } from '$lib/server/instantDeckRecovery';
import type {
  DeckShellProperties,
  DeckWorkspaceModel,
  DeckWorkspacePreferences,
  DesignBatchDetail,
  DesignBatchPreview,
  SaveConfirmation
} from '@deck-aistack-codes/shared';
import type { SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
import type { DeckGraph } from '$types/domain';
import { getDeckWorkspaceModel } from '$server/services/generatedWorkspaceService';
import { getDeckWorkspacePreferences } from '$server/services/shellWorkspaceService';
import { loadDeckGraph } from '$server/services/deckService';
import { getDesignBatchById, listLatestDesignBatches } from '$server/services/designBatchService';

const EMPTY_AI_PROVIDER_SUMMARY = {
  provider: null,
  preferredModel: null,
  apiKeyLast4: null,
  isConfigured: false,
  configuredAt: null,
  skippedAt: null
};

const PROCESSING_STATUSES = new Set([
  // Backend states that mean the source file is saved but Smart Deck should not
  // mount yet. The processing page should keep polling workflow-state instead.
  'accepted',
  'queued',
  'running',
  'uploaded',
  'starting',
  'processing',
  'parsing',
  'structuring',
  'extracting_blocks',
  'classifying_blocks',
  'analysing',
  'adapting'
]);
const FAILED_STATUSES = new Set(['failed', 'error', 'dead_letter', 'failed_retryable', 'failed_final', 'blocked', 'timed_out']);
// Source-file status aliases that are safe to show as saved even when later AI
// processing is degraded or needs retry.
const SAVED_SOURCE_STATUSES = new Set(['saved', 'ready', 'uploaded', 'available']);
const HARD_ACCESS_FAILURE_STATUSES = new Set([401, 403, 404]);
const SMART_DECK_FETCH_TIMEOUT_MS = 20_000;

type DegradedIssue = {
  key: string;
  label: string;
  message: string;
  status?: number;
  requestId?: string | null;
  ticketId?: string | null;
};

type SmartDeckWorkspaceStatus = {
  status: 'ready' | 'degraded';
  backendStatus: number;
  message: string | null;
  actionHref?: string;
  actionLabel?: string;
  issues?: DegradedIssue[];
};

type WorkspaceReadiness = 'smart_deck' | 'instant_deck';

type SmartDeckDebug = {
  processingNextAction: string | null;
  canOpenSmartDeck: boolean;
  generatedSlideCount: number;
  sourceSlideCount: number;
  activeDesignVersionId: string | null;
  activeGeneratedSlideId: string | null;
  renderSchemaElementCount: number;
  hasRenderableSchema: boolean;
  hasSourceSlides: boolean;
  workspaceStatus: string | null;
};

function getRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function getArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Record<string, unknown>[] : [];
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return null;
}

function instantDeckKnowledgeMetadata(workspace: unknown): { name: string | null; version: string | null } {
  const runtime = getRecord(getRecord(workspace).runtimeCapabilities);
  const instantDeck = getRecord(runtime.instantDeck);
  const knowledgePack = getRecord(instantDeck.knowledgePack);
  const workspaceKnowledge = getRecord(getRecord(workspace).knowledgeMetadata);
  return {
    name: firstString(knowledgePack.name, workspaceKnowledge.name),
    version: firstString(knowledgePack.version, workspaceKnowledge.version)
  };
}

function isSavedSourceStatus(value: unknown): boolean {
  return value === true || (typeof value === 'string' && SAVED_SOURCE_STATUSES.has(value));
}

function processingNextAction(payload: unknown): string | null {
  // Workflow-state has had several response shapes. Read all known locations so
  // the UI keeps working while backend contracts converge.
  const record = getRecord(payload);
  const processing = getRecord(record.processing);
  const smartDeck = getRecord(record.smartDeck);
  const value =
    record.nextAction ??
    record.next_action ??
    processing.nextAction ??
    processing.next_action ??
    smartDeck.processingNextAction ??
    smartDeck.nextAction;
  return typeof value === 'string' ? value : null;
}

function processingStatus(payload: unknown): string | null {
  const record = getRecord(payload);
  const processing = getRecord(record.processing);
  const deck = getRecord(record.deck);
  return firstString(
    processing.status,
    processing.state,
    record.status,
    record.state,
    record.deckStatus,
    record.deck_status,
    deck.status,
    deck.state
  );
}

function processingMessage(payload: unknown): string | null {
  const record = getRecord(payload);
  const processing = getRecord(record.processing);
  const detail = getRecord(record.detail);
  return firstString(
    record.message,
    record.nextStepMessage,
    record.next_step_message,
    record.errorMessage,
    record.error_message,
    record.error,
    detail.message,
    detail.error,
    processing.message,
    processing.errorMessage,
    processing.error_message,
    processing.error
  );
}

function sourceFileIsSaved(payload: unknown): boolean {
  // This checks only source persistence, not generated workspace readiness. It
  // lets the UI reassure users that their upload is not lost after worker errors.
  const record = getRecord(payload);
  const processing = getRecord(record.processing);
  const upload = getRecord(record.upload);
  const deck = getRecord(record.deck);
  const source = getRecord(record.source);

  return [
    source.fileSaved,
    upload.sourceSaved,
    upload.source_saved,
    upload.sourceFileSaved,
    upload.source_file_saved,
    record.sourceSaved,
    record.source_saved,
    record.sourceFileSaved,
    record.source_file_saved,
    record.sourceFileStatus,
    record.source_file_status,
    record.uploadStatus,
    record.upload_status,
    processing.sourceSaved,
    processing.source_saved,
    processing.sourceFileSaved,
    processing.source_file_saved,
    processing.sourceFileStatus,
    processing.source_file_status,
    deck.sourceFileStatus,
    deck.source_file_status,
    deck.uploadStatus,
    deck.upload_status
  ].some(isSavedSourceStatus);
}

function smartDeckNeedsManualReview(payload: unknown): boolean {
  const record = getRecord(payload);
  const processing = getRecord(record.processing);
  const status = processingStatus(payload);
  return (
    processing.requiresManualReview === true ||
    processing.requires_manual_review === true ||
    status === 'dead_letter' ||
    record.nextAction === 'manual_review' ||
    record.next_action === 'manual_review'
  );
}

function processingSmartDeckDebug(payload: unknown): Record<string, unknown> {
  const record = getRecord(payload);
  return getRecord(record.smartDeck);
}

function smartDeckIsReady(payload: unknown): boolean {
  // Single canonical frontend gate: only backend canOpenSmartDeck=true should
  // allow the public Smart Deck workspace to mount.
  const record = getRecord(payload);
  return record.canOpenSmartDeck === true;
}

function requiredWorkspaceIsReady(payload: unknown, requiredReadiness: WorkspaceReadiness): boolean {
  const record = getRecord(payload);
  return requiredReadiness === 'instant_deck'
    ? record.canOpenInstantDeck === true
    : smartDeckIsReady(payload);
}

function requiredWorkspaceCanMount(payload: unknown, requiredReadiness: WorkspaceReadiness): boolean {
  // A terminal Instant generation may leave the source-backed Smart Deck
  // workspace healthy but no generated HTML version. Mount the dedicated
  // Instant surface in that one state so its Regenerate action can create a
  // fresh idempotent whole-deck operation. Never treat it as a ready result.
  return canMountInstantDeckRecovery({
    requiredReadiness,
    requiredWorkspaceReady: requiredWorkspaceIsReady(payload, requiredReadiness),
    sourceWorkspaceReady: smartDeckIsReady(payload)
  });
}

function smartDeckIsProcessing(payload: unknown): boolean {
  const status = processingStatus(payload);
  return Boolean(status && PROCESSING_STATUSES.has(status));
}

function smartDeckFailed(payload: unknown): boolean {
  const status = processingStatus(payload);
  return Boolean(status && FAILED_STATUSES.has(status));
}

function getPayloadMessage(payload: unknown, fallback: string): string {
  const record = getRecord(payload);
  const detail = getRecord(record.detail);
  return (
    firstString(
      record.message,
      record.error,
      record.reason,
      detail.message,
      detail.error,
      detail.reason,
      typeof record.detail === 'string' ? record.detail : null
    ) ?? fallback
  );
}

function getPayloadRequestId(response: Response | null, payload: unknown): string | null {
  const record = getRecord(payload);
  const detail = getRecord(record.detail);
  return firstString(record.requestId, record.request_id, detail.requestId, detail.request_id, response?.headers.get('x-request-id'));
}

function getPayloadTicketId(payload: unknown): string | null {
  const record = getRecord(payload);
  const detail = getRecord(record.detail);
  return firstString(record.ticketId, record.ticket_id, detail.ticketId, detail.ticket_id);
}

function formatIssueMessage(message: string, issue: Pick<DegradedIssue, 'requestId' | 'ticketId'>): string {
  const suffix = [issue.requestId ? `request ${issue.requestId}` : null, issue.ticketId ? `ticket ${issue.ticketId}` : null]
    .filter(Boolean)
    .join(', ');
  return suffix ? `${message} (${suffix})` : message;
}

async function buildIssue(
  key: string,
  label: string,
  response: Response | null,
  fallback: string
): Promise<DegradedIssue> {
  const payload = await response?.json().catch(() => null);
  const issue = {
    key,
    label,
    message: getPayloadMessage(payload, fallback),
    status: response?.status,
    requestId: getPayloadRequestId(response, payload),
    ticketId: getPayloadTicketId(payload)
  } satisfies DegradedIssue;

  return {
    ...issue,
    message: formatIssueMessage(issue.message, issue)
  };
}

function issueForKey(issues: DegradedIssue[], key: string) {
  return issues.find((issue) => issue.key === key) ?? null;
}

async function readJsonOrNull(response: Response | null): Promise<unknown> {
  if (!response?.ok) return null;
  return response.json().catch(() => null);
}

async function fetchOrNull(fetcher: typeof fetch, path: string, init?: RequestInit): Promise<Response | null> {
  return fetcher(path, {
    ...init,
    signal: init?.signal ?? AbortSignal.timeout(SMART_DECK_FETCH_TIMEOUT_MS)
  }).catch(() => null);
}

type ProcessingVisibilityLoadResult = {
  payload: unknown;
  backendStatus: number | null;
};

async function loadProcessingVisibility(fetcher: typeof fetch, deckId: string): Promise<ProcessingVisibilityLoadResult> {
  // workflow-state is the first request on Smart Deck pages because it decides
  // whether to redirect to processing, show degraded mode, or load the workspace.
  const response = await fetchOrNull(fetcher, deckProductApiPath(`/decks/${deckId}/workflow-state`));
  if (!response) {
    return { payload: null, backendStatus: null };
  }
  return {
    payload: await readJsonOrNull(response),
    backendStatus: response.status
  };
}

async function loadDeckProperties(fetcher: typeof fetch, deckId: string): Promise<DeckShellProperties | null> {
  const response = await fetchOrNull(fetcher, `/api/decks/${deckId}/properties`);
  if (!response?.ok) return null;
  const payload = await response.json().catch(() => null);
  return payload && typeof payload === 'object' && 'properties' in payload ? (payload as { properties?: DeckShellProperties }).properties ?? null : null;
}

function shouldLoadSmartDeckWorkspace(processingVisibility: unknown): boolean {
  // Avoid hitting workspace endpoints for decks that workers have not marked as
  // openable. This prevents half-built generated slides from rendering as final.
  return processingVisibility !== null && smartDeckIsReady(processingVisibility);
}

function workspaceGeneratedSlides(workspace: unknown): Record<string, unknown>[] {
  const record = getRecord(workspace);
  const directSlides = getArray(record.generatedSlides ?? record.generated_slides);
  if (directSlides.length > 0) return directSlides;
  const designVersions = getArray(record.designVersions ?? record.design_versions);
  return designVersions.flatMap((version) => getArray(version.generatedSlides ?? version.generated_slides));
}

function workspaceSourceSlides(workspace: unknown): Record<string, unknown>[] {
  const record = getRecord(workspace);
  return getArray(record.sourceSlides ?? record.source_slides);
}

function workspaceHasSourceSlides(workspace: unknown): boolean {
  return workspaceSourceSlides(workspace).length > 0;
}

function workspaceHasRenderableSchema(workspace: unknown): boolean {
  const slides = workspaceGeneratedSlides(workspace);
  return slides.some((slide) => {
    const renderSchema = getRecord(slide.renderSchema ?? slide.render_schema_json);
    return Array.isArray(renderSchema.elements) && renderSchema.elements.length > 0;
  });
}

function workspaceCanMountSmartDeck(
  workspace: unknown,
  processingVisibility: unknown,
  requiredReadiness: WorkspaceReadiness
): boolean {
  // Both conditions are required: actual workspace payload and backend readiness.
  // Diagnostics may still receive fallbacks, but public users should not.
  const backendReady = processingVisibility !== null
    ? requiredWorkspaceCanMount(processingVisibility, requiredReadiness)
    : null;
  return Boolean(workspace && backendReady === true);
}

function publicSmartDeckStatus(
  deckId: string,
  status: SmartDeckWorkspaceStatus
): SmartDeckWorkspaceStatus {
  // Public Smart Deck keeps deck-scoped degraded issues visible so users and
  // developers can understand the current workspace failure from the product
  // page without leaving the canonical route.
  if (status.status === 'ready') return status;
  return {
    status: 'degraded',
    backendStatus: status.backendStatus,
    message: 'Smart Deck is still processing. The workspace will open when processing is complete.',
    actionHref: status.actionHref ?? `/decks/${deckId}/processing`,
    actionLabel: status.actionLabel ?? 'View processing',
    issues: status.issues
  };
}

function buildSmartDeckDebug(processingVisibility: unknown, workspace: unknown): SmartDeckDebug {
  const processingSmartDeck = processingSmartDeckDebug(processingVisibility);
  const workspaceRecord = getRecord(workspace);
  const slides = workspaceGeneratedSlides(workspace);
  const sourceSlides = workspaceSourceSlides(workspace);
  const activeGeneratedSlideId = firstString(
    processingSmartDeck.activeGeneratedSlideId,
    processingSmartDeck.active_generated_slide_id,
    workspaceRecord.activeGeneratedSlideId,
    workspaceRecord.active_generated_slide_id,
    getRecord(workspaceRecord.workspace).activeGeneratedSlideId,
    getRecord(workspaceRecord.preferences).activeGeneratedSlideId
  );
  const activeSlide = activeGeneratedSlideId ? slides.find((slide) => slide.id === activeGeneratedSlideId) : undefined;
  const renderSchema = getRecord(activeSlide?.renderSchema ?? activeSlide?.render_schema_json);
  const elementCountFromWorkspace = Array.isArray(renderSchema.elements) ? renderSchema.elements.length : 0;
  const generatedSlideCount = firstNumber(
    processingSmartDeck.generatedSlideCount,
    processingSmartDeck.generated_slide_count,
    slides.length
  ) ?? 0;
  const renderSchemaElementCount = firstNumber(
    processingSmartDeck.renderSchemaElementCount,
    processingSmartDeck.render_schema_element_count,
    elementCountFromWorkspace
  ) ?? 0;
  const hasRenderableSchema =
    processingSmartDeck.hasRenderableSchema === true ||
    workspaceHasRenderableSchema(workspace) ||
    (generatedSlideCount > 0 && renderSchemaElementCount > 0);
  const hasSourceSlides = workspaceHasSourceSlides(workspace);
  const backendReady = processingVisibility !== null ? smartDeckIsReady(processingVisibility) : null;

  return {
    processingNextAction: processingNextAction(processingVisibility),
    canOpenSmartDeck: backendReady === true,
    generatedSlideCount,
    sourceSlideCount: sourceSlides.length,
    activeDesignVersionId: firstString(
      processingSmartDeck.activeDesignVersionId,
      processingSmartDeck.active_design_version_id,
      workspaceRecord.activeDesignVersionId,
      workspaceRecord.active_design_version_id,
      getRecord(workspaceRecord.workspace).activeDesignVersionId
    ),
    activeGeneratedSlideId,
    renderSchemaElementCount,
    hasRenderableSchema,
    hasSourceSlides,
    workspaceStatus: firstString(processingSmartDeck.workspaceStatus, getRecord(workspaceRecord.workspace).status)
  };
}

function smartDeckReadOnlyStatus(
  deckId: string,
  processingVisibility: unknown,
  workspaceResponse: Response | null,
  issues: DegradedIssue[]
): SmartDeckWorkspaceStatus {
  // Convert backend workflow conditions into one user-facing state object. This
  // keeps route load logic separate from page copy and action button decisions.
  // This fallback is reached only after the required readiness/mount decision
  // failed, so an HTTP 200 or raw workspace must never promote it to ready.
  const message = processingMessage(processingVisibility);
  const actionHref = `/decks/${deckId}/processing`;

  if (smartDeckFailed(processingVisibility) && sourceFileIsSaved(processingVisibility)) {
    return {
      status: 'degraded',
      backendStatus: workspaceResponse?.status ?? 409,
      message:
        message ??
        'Your source file is saved, but Smart Deck processing did not finish. Use the processing screen to retry.',
      actionHref,
      actionLabel: 'Retry processing',
      issues
    };
  }

  if (smartDeckNeedsManualReview(processingVisibility)) {
    return {
      status: 'degraded',
      backendStatus: workspaceResponse?.status ?? 409,
      message: message ?? 'Smart Deck processing needs manual review before the workspace can open.',
      actionHref,
      actionLabel: 'Review processing',
      issues
    };
  }

  if (smartDeckIsProcessing(processingVisibility) || sourceFileIsSaved(processingVisibility)) {
    return {
      status: 'degraded',
      backendStatus: workspaceResponse?.status ?? 202,
      message: message ?? 'Smart Deck is still processing. The workspace will open when the backend marks it ready.',
      actionHref,
      actionLabel: 'View processing',
      issues
    };
  }

  return {
    status: 'degraded',
    backendStatus: workspaceResponse?.status ?? 503,
    message: message ?? 'Smart Deck workspace is not ready yet. Check the processing screen for the current state.',
    actionHref,
    actionLabel: 'View processing',
    issues
  };
}

async function loadPersistedSourceInspection(fetcher: typeof fetch, deckId: string, existingWorkflowState?: unknown): Promise<{
  structure: unknown;
  issues: DegradedIssue[];
}> {
  const issues: DegradedIssue[] = [];
  const workflowStateResponse = existingWorkflowState === undefined
    ? await fetchOrNull(fetcher, deckProductApiPath(`/decks/${deckId}/workflow-state`))
    : null;

  if (workflowStateResponse && !workflowStateResponse.ok) {
    issues.push(
      await buildIssue(
        'source-structure',
        'Source inspection',
        workflowStateResponse,
        'Could not load persisted source inspection.'
      )
    );
  }
  if (existingWorkflowState === undefined && !workflowStateResponse) {
    issues.push({ key: 'source-structure', label: 'Source inspection', message: 'Could not reach source structure data.' });
  }

  const workflowState = existingWorkflowState ?? (workflowStateResponse?.ok ? await workflowStateResponse.json().catch(() => null) : null);
  const sourceSlides = Array.isArray(workflowState?.source?.slides) ? workflowState.source.slides : [];

  return {
    structure: {
      slides: sourceSlides,
      sourceEnrichment: workflowState?.source?.sourceEnrichment ?? null
    },
    issues
  };
}

async function readBackendError(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null);
  return getPayloadMessage(payload, fallback);
}

function defaultWorkspacePreferences(deckId: string): DeckWorkspacePreferences {
  return {
    deckId,
    activeTool: 'deck_map',
    leftPanelOpen: true,
    selectedSlideId: null,
    lastBatchId: null,
    lastSlideVersionId: null,
    selectedElementType: null,
    selectedDataView: null,
    chatOpen: false,
    updatedAt: null
  };
}

function fallbackDeckGraph(deckId: string): DeckGraph {
  // Degraded-mode graph used when canonical deck graph is unreachable. It keeps
  // the page renderable without pretending real slide analysis is available.
  const now = new Date().toISOString();
  const slideId = `${deckId}_syncing_slide_1`;
  const blockId = `${deckId}_syncing_block_1`;

  return {
    deck: {
      id: deckId,
      workspaceId: '',
      title: 'Deck is syncing',
      audience: 'Investment Committee',
      purpose: 'Initial diligence review',
      status: 'uploaded',
      createdAt: now,
      updatedAt: now,
      summary: 'The deck metadata is temporarily unavailable while the source file and Smart Deck state sync.'
    },
    slides: [
      {
        id: slideId,
        deckId,
        slideIndex: 0,
        slideNumber: 1,
        title: 'Processing state',
        role: 'status',
        rawText: 'Smart Deck is not fully ready yet. Use the processing screen to retry or inspect the current backend state.',
        narrativeNotes: 'Fallback slide shown while Smart Deck data is degraded.',
        status: 'pending'
      }
    ],
    blocks: [
      {
        id: blockId,
        slideId,
        blockIndex: 0,
        rawText: 'Smart Deck is not fully ready yet. Use the processing screen to retry or inspect the current backend state.',
        normalizedText: 'smart deck processing fallback',
        blockType: 'body'
      }
    ],
    classifications: [],
    findings: [],
    suggestions: [],
    smartEditSuggestions: [],
    revisions: []
  };
}

function fallbackProperties(graph: DeckGraph): DeckShellProperties {
  return {
    deckId: graph.deck.id,
    companyName: null,
    companyWebsiteUrl: null,
    contactEmail: null,
    companyStage: null,
    founderName: null,
    teamSummary: null,
    brandSummary: null,
    visualDirection: null,
    audienceLabel: graph.deck.audience,
    primaryGoal: graph.deck.purpose,
    processingStatus: 'draft' as DeckShellProperties['processingStatus'],
    sourceFileName: graph.deck.originalFilename ?? null,
    brandReady: false,
    sourcesUsed: [],
    brandAssetLabels: [],
    updatedAt: null
  };
}

function fallbackWorkspaceModel(graph: DeckGraph): DeckWorkspaceModel {
  return {
    deck: {
      id: graph.deck.id,
      workspaceId: graph.deck.workspaceId,
      title: graph.deck.title,
      audience: graph.deck.audience,
      purpose: graph.deck.purpose,
      status: graph.deck.status as DeckWorkspaceModel['deck']['status'],
      summary: graph.deck.summary,
      createdAt: graph.deck.createdAt,
      updatedAt: graph.deck.updatedAt,
      generationStatus: 'idle',
      generationMode: 'openai',
      latestGenerationRunId: null
    },
    slides: graph.slides.map((slide) => ({
      id: slide.id,
      deckId: slide.deckId,
      slideNumber: slide.slideNumber ?? slide.slideIndex + 1,
      title: slide.title,
      rawText: slide.rawText,
      summary: null,
      slideRole: slide.role as DeckWorkspaceModel['slides'][number]['slideRole'],
      blocks: graph.blocks
        .filter((block) => block.slideId === slide.id)
        .map((block) => ({
          id: block.id,
          deckId: block.deckId,
          slideId: block.slideId,
          blockIndex: block.blockIndex,
          blockType: block.blockType as DeckWorkspaceModel['slides'][number]['blocks'][number]['blockType'],
          rawText: block.rawText,
          currentText: block.rawText,
          normalizedText: block.normalizedText,
          classification: null
        }))
    })),
    versions: [],
    feedback: []
  };
}

function isHardAccessFailure(response: Response | null): boolean {
  return Boolean(response && !response.ok && HARD_ACCESS_FAILURE_STATUSES.has(response.status));
}

export interface LoadSmartDeckPageOptions {
  requiredReadiness?: WorkspaceReadiness;
}

export type SmartDeckPageData = {
  graph: DeckGraph;
  workspaceLabel: string;
  currentDeckLabel: string;
  properties: DeckShellProperties | undefined;
  workspacePreferences: DeckWorkspacePreferences;
  workspaceModel: DeckWorkspaceModel;
  latestConfirmation: SaveConfirmation | null;
  latestBatches: DesignBatchPreview[];
  activeBatch: DesignBatchDetail | null;
  activeBatchError: string | null;
  smartDeckWorkspace: SmartDeckWorkspacePayload | null;
  smartDeckWorkspaceStatus: SmartDeckWorkspaceStatus;
  processingVisibility: unknown;
  smartDeckProcessingVisibility: unknown;
  smartDeckDebug: SmartDeckDebug | null;
  sourceInspection: {
    structure: unknown;
  };
  aiProviderSummary: unknown;
  previewDesignVersionId: string | null;
  selectedSlideId: string | null | undefined;
  selectedDesignVersionId: string | null;
  selectedGeneratedSlideId: string | null;
  instantDeckMode: boolean;
  developerToolsPayload: unknown;
};

export async function loadSmartDeckPage(
  params: { deckId: string },
  url: URL,
  fetchFn: typeof fetch,
  locals: App.Locals,
  options?: LoadSmartDeckPageOptions
): Promise<SmartDeckPageData> {
  // Central server-side loader for the customer Smart Deck workspace.
  // It intentionally gathers partial data, records degraded issues, and avoids
  // mounting the generated workspace until backend readiness allows it.
  const startedAt = Date.now();
  const requiredReadiness = options?.requiredReadiness ?? 'smart_deck';
  const instantDeckOnly = requiredReadiness === 'instant_deck';

  if (BACKEND_URL) {
    const issues: DegradedIssue[] = [];
    const processingVisibilityLoad = await loadProcessingVisibility(fetchFn, params.deckId);
    if (processingVisibilityLoad.backendStatus === 401 || processingVisibilityLoad.backendStatus === 403) {
      throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`);
    }
    const processingVisibility = getRecord(processingVisibilityLoad.payload);
    
    // Gate initial access: redirect to processing while a newly uploaded deck
    // has not reached Smart Deck readiness. During client invalidation, however,
    // a generation job can temporarily make canOpenSmartDeck false even though
    // the workspace is already mounted. Redirecting that background __data.json
    // request makes SvelteKit report a failed reload and blanks the active deck.
    const canOpenRequiredWorkspace = requiredWorkspaceCanMount(processingVisibility, requiredReadiness);
    const isClientDataReload = url.pathname.endsWith('/__data.json');
    if (!canOpenRequiredWorkspace && !isClientDataReload) {
      throw redirect(303, `/decks/${params.deckId}/processing${url.search}`);
    }
    
    const loadSmartDeckWorkspace = canOpenRequiredWorkspace || shouldLoadSmartDeckWorkspace(processingVisibility) || isClientDataReload;

    const [
      graphResponse,
      propertiesResponse,
      preferencesResponse,
      workspaceModelResponse,
      batchesResponse,
      smartDeckWorkspaceResponse,
      providerResponse
    ] = await Promise.all([
      // Load independent Smart Deck data in parallel. Each response is validated
      // below so one degraded panel does not blank the whole workspace.
      fetchOrNull(fetchFn, `/api/decks/${params.deckId}`),
      instantDeckOnly ? Promise.resolve(null) : fetchOrNull(fetchFn, `/api/decks/${params.deckId}/properties`),
      instantDeckOnly ? Promise.resolve(null) : fetchOrNull(fetchFn, `/api/decks/${params.deckId}/workspace`),
      instantDeckOnly ? Promise.resolve(null) : fetchOrNull(fetchFn, deckProductApiPath(`/decks/${params.deckId}/workspace`)),
      instantDeckOnly ? Promise.resolve(null) : fetchOrNull(fetchFn, `/api/decks/${params.deckId}/iterations?limit=3`),
      // The mounted Smart Deck workspace always enters through the frontend
      // `/api/decks/*` proxy, which then calls the backend product router.
      // This is the contract path to audit when cards seem disconnected.
      loadSmartDeckWorkspace ? fetchOrNull(fetchFn, `/api/decks/${params.deckId}/smart-deck`) : Promise.resolve(null),
      instantDeckOnly ? Promise.resolve(null) : fetchOrNull(fetchFn, '/api/settings/workspace/ai-provider')
    ]);

    if (isHardAccessFailure(graphResponse)) {
      throw error(graphResponse?.status ?? 404, graphResponse ? await readBackendError(graphResponse, 'Deck not found') : 'Deck not found');
    }

    if (graphResponse && !graphResponse.ok) {
      issues.push(await buildIssue('deck-graph', 'Deck graph', graphResponse, 'Could not load the canonical deck graph.'));
    }
    if (!graphResponse) {
      issues.push({ key: 'deck-graph', label: 'Deck graph', message: 'Could not reach the canonical deck graph.' });
    }

    if (!instantDeckOnly && propertiesResponse && !propertiesResponse.ok) {
      issues.push(await buildIssue('deck-properties', 'Deck properties', propertiesResponse, 'Could not load Smart Deck properties.'));
    }
    if (!instantDeckOnly && !propertiesResponse) {
      issues.push({ key: 'deck-properties', label: 'Deck properties', message: 'Could not reach Smart Deck properties.' });
    }

    if (!instantDeckOnly && preferencesResponse && !preferencesResponse.ok) {
      issues.push(await buildIssue('workspace-preferences', 'Workspace preferences', preferencesResponse, 'Could not load workspace preferences.'));
    }
    if (!instantDeckOnly && batchesResponse && !batchesResponse.ok) {
      issues.push(await buildIssue('design-batches', 'Iterations', batchesResponse, 'Could not load recent iterations.'));
    }
    if (!instantDeckOnly && !batchesResponse) {
      issues.push({ key: 'design-batches', label: 'Iterations', message: 'Could not reach recent iterations.' });
    }
    if (!instantDeckOnly && providerResponse && !providerResponse.ok) {
      issues.push(await buildIssue('ai-provider', 'AI provider', providerResponse, 'Could not load workspace AI provider settings.'));
    }
    if (!instantDeckOnly && !providerResponse) {
      issues.push({ key: 'ai-provider', label: 'AI provider', message: 'Could not reach workspace AI provider settings.' });
    }
    if (loadSmartDeckWorkspace && smartDeckWorkspaceResponse && !smartDeckWorkspaceResponse.ok) {
      issues.push(await buildIssue('smart-deck-workspace', 'Smart Deck workspace', smartDeckWorkspaceResponse, 'Smart Deck workspace is not ready yet.'));
    }
    if (loadSmartDeckWorkspace && !smartDeckWorkspaceResponse) {
      issues.push({ key: 'smart-deck-workspace', label: 'Smart Deck workspace', message: 'Could not reach the Smart Deck workspace.' });
    }

    const graph = graphResponse?.ok ? ((await graphResponse.json()) as DeckGraph) : fallbackDeckGraph(params.deckId);
    const propertiesPayload = propertiesResponse?.ok
      ? ((await propertiesResponse.json()) as { properties?: DeckShellProperties })
      : { properties: null };
    const preferencesPayload = preferencesResponse?.ok
      ? ((await preferencesResponse.json()) as { workspace?: DeckWorkspacePreferences })
      : { workspace: null };
    const workspaceModelPayload = workspaceModelResponse?.ok
      ? ((await workspaceModelResponse.json()) as {
          workspace?: DeckWorkspaceModel;
          latestConfirmation?: SaveConfirmation | null;
        })
      : { workspace: null, latestConfirmation: null };
    const batchesPayload = batchesResponse?.ok ? ((await batchesResponse.json()) as { batches?: DesignBatchPreview[] }) : { batches: [] };
    const rawSmartDeckWorkspace = smartDeckWorkspaceResponse?.ok ? ((await smartDeckWorkspaceResponse.json()) as unknown) : null;
    const canMountSmartDeckWorkspace = workspaceCanMountSmartDeck(
      rawSmartDeckWorkspace,
      processingVisibility,
      requiredReadiness
    );
    if (rawSmartDeckWorkspace && !canMountSmartDeckWorkspace) {
      issues.push({
        key: 'smart-deck-workspace-contract',
        label: 'Smart Deck workspace',
        message: 'Smart Deck workspace returned before backend readiness allowed the workspace to open.'
      });
    }
    const smartDeckWorkspaceResult = canMountSmartDeckWorkspace ? rawSmartDeckWorkspace : null;
    // From this point on, smartDeckWorkspaceResult is the only workspace payload
    // allowed to mount publicly. rawSmartDeckWorkspace may be present but unsafe.
    const providerPayload = providerResponse?.ok ? await providerResponse.json().catch(() => null) : null;
    const latestBatches = batchesPayload.batches ?? [];
    const activeBatchId = url.searchParams.get('batch') ?? latestBatches[0]?.id ?? null;
    const activeBatchResponse = activeBatchId
      ? await fetchOrNull(fetchFn, `/api/decks/${params.deckId}/iterations/${activeBatchId}`)
      : null;
    if (activeBatchId && activeBatchResponse && !activeBatchResponse.ok) {
      issues.push(await buildIssue('active-batch', 'Active iteration', activeBatchResponse, 'Active iteration could not be loaded.'));
    }
    if (activeBatchId && !activeBatchResponse) {
      issues.push({ key: 'active-batch', label: 'Active iteration', message: 'Could not reach the active iteration.' });
    }
    const activeBatchPayload = activeBatchResponse?.ok
      ? ((await activeBatchResponse.json()) as { batch?: DesignBatchDetail })
      : null;
    const activeBatchError = activeBatchId && !activeBatchResponse?.ok
      ? 'Active iteration lookup failed.'
      : null;
    const sourceInspection = await loadPersistedSourceInspection(fetchFn, params.deckId, processingVisibility);
    issues.push(...sourceInspection.issues);
    const workspacePreferences = preferencesPayload.workspace ?? defaultWorkspacePreferences(params.deckId);
    const properties = propertiesPayload.properties ?? fallbackProperties(graph);
    const workspaceModel = workspaceModelPayload.workspace ?? fallbackWorkspaceModel(graph);
    const smartDeckWorkspacePayload = smartDeckWorkspaceResult as SmartDeckWorkspacePayload | null;
    const workspaceStatus =
      workspaceCanMountSmartDeck(smartDeckWorkspacePayload, processingVisibility, requiredReadiness)
        ? {
            status: 'ready' as const,
            backendStatus: smartDeckWorkspaceResponse?.status ?? 200,
            message: null,
            issues
        }
        : smartDeckReadOnlyStatus(params.deckId, processingVisibility, smartDeckWorkspaceResponse, issues);
    const publicWorkspaceStatus = publicSmartDeckStatus(params.deckId, workspaceStatus);
    const smartDeckDebug = buildSmartDeckDebug(processingVisibility, smartDeckWorkspacePayload);
    const completedAt = Date.now();
    const processingRequestId = firstString(
      processingVisibility?.requestId,
      processingVisibility?.request_id,
      getRecord(processingVisibility?.detail).requestId,
      getRecord(processingVisibility?.detail).request_id
    );
    const processingTicketId = firstString(
      processingVisibility?.ticketId,
      processingVisibility?.ticket_id,
      getRecord(processingVisibility?.detail).ticketId,
      getRecord(processingVisibility?.detail).ticket_id
    );
    const instantDeckKnowledge = instantDeckKnowledgeMetadata(smartDeckWorkspacePayload);
    const developerToolsPayload = createDeveloperToolsPayload({
      route: {
        canonicalPath: `/decks/${params.deckId}/smart-deck`,
        routeStatus: publicWorkspaceStatus.status === 'ready' ? 'mounted_and_wired' : 'mounted_but_degraded',
        routeNotice: null
      },
      subject: {
        workspaceId: graph.deck.workspaceId,
        deckId: graph.deck.id,
        audience: graph.deck.audience,
        activeDeckId: graph.deck.id
      },
      load: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      correlation: {
        backendStatus: processingVisibilityLoad.backendStatus,
        requestId: processingRequestId,
        ticketId: processingTicketId,
        backendPath: deckProductApiPath(`/decks/${params.deckId}/workflow-state`),
        message: publicWorkspaceStatus.message
      },
      workflow: {
        status: processingStatus(processingVisibility),
        nextAction: smartDeckDebug?.processingNextAction ?? null,
        activeStage: firstString(processingVisibility?.activeStage, processingVisibility?.processingStage, processingVisibility?.active_stage),
        runId: null,
        jobId: null,
        canRetry: null,
        canOpenSmartDeck: smartDeckDebug?.canOpenSmartDeck ?? null
      },
      artifacts: {
        sourceFileStatus: null,
        sourceSlideCount: smartDeckDebug?.sourceSlideCount ?? null,
        generatedSlideCount: smartDeckDebug?.generatedSlideCount ?? null,
        latestExportId: null,
        latestExportType: null,
        activeDesignVersionId: smartDeckDebug?.activeDesignVersionId ?? null,
        activeGeneratedSlideId: smartDeckDebug?.activeGeneratedSlideId ?? null,
        knowledgePackageName: instantDeckKnowledge.name,
        knowledgePackageVersion: instantDeckKnowledge.version
      },
      degradation: {
        status: publicWorkspaceStatus.status,
        issues: publicWorkspaceStatus.issues?.map((issue) => ({
          key: issue.key,
          label: issue.label,
          status: issue.status ?? null,
          requestId: issue.requestId ?? null,
          ticketId: issue.ticketId ?? null,
          message: issue.message
        })) ?? [],
        actionHref: publicWorkspaceStatus.actionHref ?? null,
        actionLabel: publicWorkspaceStatus.actionLabel ?? null
      },
      dependencies: [
        createDependencyStatus('workflow-state', 'Workflow state', {
          status: processingVisibilityLoad.backendStatus,
          requestId: processingRequestId,
          ticketId: processingTicketId,
          backendPath: deckProductApiPath(`/decks/${params.deckId}/workflow-state`)
        }),
        createDependencyStatus('deck-graph', 'Deck graph', {
          status: graphResponse?.status ?? null,
          requestId: graphResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'deck-graph')?.ticketId ?? null,
          backendPath: `/api/decks/${params.deckId}`,
          message: issueForKey(issues, 'deck-graph')?.message ?? null
        }),
        createDependencyStatus('deck-properties', 'Deck properties', {
          status: propertiesResponse?.status ?? null,
          requestId: propertiesResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'deck-properties')?.ticketId ?? null,
          backendPath: `/api/decks/${params.deckId}/properties`,
          message: issueForKey(issues, 'deck-properties')?.message ?? null
        }),
        createDependencyStatus('workspace-preferences', 'Workspace preferences', {
          status: preferencesResponse?.status ?? null,
          requestId: preferencesResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'workspace-preferences')?.ticketId ?? null,
          backendPath: `/api/decks/${params.deckId}/workspace`,
          message: issueForKey(issues, 'workspace-preferences')?.message ?? null
        }),
        createDependencyStatus('iterations', 'Iterations', {
          status: batchesResponse?.status ?? null,
          requestId: batchesResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'design-batches')?.ticketId ?? null,
          backendPath: `/api/decks/${params.deckId}/iterations?limit=3`,
          message: issueForKey(issues, 'design-batches')?.message ?? null
        }),
        createDependencyStatus('smart-deck-workspace', 'Smart Deck workspace', {
          status: smartDeckWorkspaceResponse?.status ?? null,
          requestId: smartDeckWorkspaceResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'smart-deck-workspace')?.ticketId ?? null,
          backendPath: `/api/decks/${params.deckId}/smart-deck`,
          message: issueForKey(issues, 'smart-deck-workspace')?.message ?? null
        }),
        createDependencyStatus('ai-provider', 'AI provider', {
          status: providerResponse?.status ?? null,
          requestId: providerResponse?.headers.get('x-request-id') ?? null,
          ticketId: issueForKey(issues, 'ai-provider')?.ticketId ?? null,
          backendPath: '/api/settings/workspace/ai-provider',
          message: issueForKey(issues, 'ai-provider')?.message ?? null
        })
      ]
    });

    return {
      graph,
      workspaceLabel: graph.deck.workspaceId ? `Workspace ${graph.deck.workspaceId}` : 'Deck workspace',
      currentDeckLabel: graph.deck.title,
      properties,
      workspacePreferences,
      workspaceModel,
      latestConfirmation: workspaceModelPayload.latestConfirmation ?? null,
      latestBatches,
      activeBatch: activeBatchPayload?.batch ?? null,
      activeBatchError,
      smartDeckWorkspace: smartDeckWorkspacePayload,
      smartDeckWorkspaceStatus: publicWorkspaceStatus,
      processingVisibility,
      smartDeckProcessingVisibility: processingVisibility,
      smartDeckDebug,
      sourceInspection: {
        structure: sourceInspection.structure
      },
      aiProviderSummary: providerPayload?.summary ?? EMPTY_AI_PROVIDER_SUMMARY,
      previewDesignVersionId: url.searchParams.get('previewDesignVersionId'),
      selectedSlideId: url.searchParams.get('slide') ?? workspacePreferences.selectedSlideId ?? graph.slides[0]?.id,
      selectedDesignVersionId: url.searchParams.get('designVersionId'),
      selectedGeneratedSlideId: url.searchParams.get('generatedSlideId'),
      instantDeckMode: url.searchParams.get('instant') === '1',
      developerToolsPayload,
    };
  }

  const [graph, properties, workspacePreferences, workspaceModelResult, latestBatches, smartDeckWorkspace, providerResponse, workflowResponse] = await Promise.all([
    loadDeckGraph(params.deckId).catch(() => null),
    instantDeckOnly ? Promise.resolve(null) : loadDeckProperties(fetchFn, params.deckId),
    instantDeckOnly ? Promise.resolve(defaultWorkspacePreferences(params.deckId)) : getDeckWorkspacePreferences(params.deckId).catch(() => defaultWorkspacePreferences(params.deckId)),
    instantDeckOnly ? Promise.resolve(undefined) : getDeckWorkspaceModel(params.deckId).catch(() => undefined),
    instantDeckOnly ? Promise.resolve([]) : listLatestDesignBatches(params.deckId, 3).catch(() => []),
    fetchFn(`/api/decks/${params.deckId}/smart-deck`).then((response) => (response.ok ? response.json() : null)).catch(() => null),
    instantDeckOnly ? Promise.resolve(null) : fetchFn('/api/settings/workspace/ai-provider').catch(() => null),
    fetchFn(`/api/products/deck-aistack-codes/decks/${params.deckId}/workflow-state`).catch(() => null)
  ]);

  const localGraph = graph ?? fallbackDeckGraph(params.deckId);
  const activeBatchId = url.searchParams.get('batch') ?? latestBatches[0]?.id ?? null;
  const activeBatch = activeBatchId ? await getDesignBatchById(params.deckId, activeBatchId).catch(() => undefined) : undefined;
  const providerPayload = providerResponse?.ok ? await providerResponse.json().catch(() => null) : null;
  const workflowPayload = workflowResponse?.ok ? await workflowResponse.json().catch(() => null) : null;
  const sourceInspection = await loadPersistedSourceInspection(fetchFn, params.deckId);
  const instantDeckKnowledge = instantDeckKnowledgeMetadata(smartDeckWorkspace);
  const fallbackWorkspaceModelResult = workspaceModelResult ?? {
    workspace: fallbackWorkspaceModel(localGraph),
    latestConfirmation: null
  };
  const canMountSmartDeckWorkspace = workspaceCanMountSmartDeck(
    smartDeckWorkspace,
    workflowPayload,
    requiredReadiness
  );
  const smartDeckDebug = buildSmartDeckDebug(null, canMountSmartDeckWorkspace ? smartDeckWorkspace : null);
  const completedAt = Date.now();
  const fallbackMessage = canMountSmartDeckWorkspace
    ? null
    : 'We could not load your Smart Deck workspace right now. The source deck remains viewable in degraded mode.';

  return {
    graph: localGraph,
    workspaceLabel: localGraph.deck.workspaceId ? `Workspace ${localGraph.deck.workspaceId}` : 'Deck workspace',
    currentDeckLabel: localGraph.deck.title,
    properties: properties ?? fallbackProperties(localGraph),
    workspacePreferences,
    workspaceModel: fallbackWorkspaceModelResult.workspace,
    latestConfirmation: fallbackWorkspaceModelResult.latestConfirmation,
    latestBatches,
    activeBatch: activeBatch ?? null,
    activeBatchError: null,
    smartDeckWorkspace: canMountSmartDeckWorkspace ? smartDeckWorkspace : null,
    smartDeckWorkspaceStatus: canMountSmartDeckWorkspace
      ? { status: 'ready' as const, backendStatus: 200, message: null, issues: sourceInspection.issues }
      : {
          status: 'degraded' as const,
          backendStatus: 503,
          message: 'We could not load your Smart Deck workspace right now. The source deck remains viewable in degraded mode.',
          actionHref: `/decks/${params.deckId}/processing`,
          actionLabel: 'View processing',
          issues: sourceInspection.issues
      },
    processingVisibility: null,
    smartDeckProcessingVisibility: null,
    smartDeckDebug,
    sourceInspection: {
      structure: sourceInspection.structure
    },
    aiProviderSummary: providerPayload?.summary ?? EMPTY_AI_PROVIDER_SUMMARY,
    previewDesignVersionId: url.searchParams.get('previewDesignVersionId'),
    selectedSlideId: url.searchParams.get('slide') ?? workspacePreferences.selectedSlideId ?? localGraph.slides[0]?.id,
    selectedDesignVersionId: url.searchParams.get('designVersionId'),
    selectedGeneratedSlideId: url.searchParams.get('generatedSlideId'),
    instantDeckMode: url.searchParams.get('instant') === '1',
    developerToolsPayload: createDeveloperToolsPayload({
      route: {
        canonicalPath: `/decks/${params.deckId}/smart-deck`,
        routeStatus: smartDeckWorkspace ? 'mounted_and_wired' : 'mounted_but_degraded',
        routeNotice: null
      },
      subject: {
        workspaceId: localGraph.deck.workspaceId,
        deckId: localGraph.deck.id,
        audience: localGraph.deck.audience,
        activeDeckId: localGraph.deck.id
      },
      load: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      correlation: {
        backendStatus: smartDeckWorkspace ? 200 : 503,
        requestId: null,
        ticketId: null,
        backendPath: `/api/decks/${params.deckId}/smart-deck`,
        message: fallbackMessage
      },
      workflow: {
        status: smartDeckWorkspace ? 'ready' : 'degraded',
        nextAction: smartDeckDebug?.processingNextAction ?? null,
        activeStage: null,
        runId: null,
        jobId: null,
        canRetry: null,
        canOpenSmartDeck: canMountSmartDeckWorkspace
      },
      artifacts: {
        sourceFileStatus: null,
        sourceSlideCount: smartDeckDebug?.sourceSlideCount ?? null,
        generatedSlideCount: smartDeckDebug?.generatedSlideCount ?? null,
        latestExportId: null,
        latestExportType: null,
        activeDesignVersionId: smartDeckDebug?.activeDesignVersionId ?? null,
        activeGeneratedSlideId: smartDeckDebug?.activeGeneratedSlideId ?? null,
        knowledgePackageName: instantDeckKnowledge.name,
        knowledgePackageVersion: instantDeckKnowledge.version
      },
      degradation: {
        status: smartDeckWorkspace ? 'ready' : 'degraded',
        issues: sourceInspection.issues.map((issue) => ({
          key: issue.key,
          label: issue.label,
          status: issue.status ?? null,
          requestId: issue.requestId ?? null,
          ticketId: issue.ticketId ?? null,
          message: issue.message
        })),
        actionHref: smartDeckWorkspace ? null : `/decks/${params.deckId}/processing`,
        actionLabel: smartDeckWorkspace ? null : 'View processing'
      },
      dependencies: [
        createDependencyStatus('smart-deck-workspace', 'Smart Deck workspace', {
          status: smartDeckWorkspace ? 200 : 503,
          backendPath: `/api/decks/${params.deckId}/smart-deck`,
          message: fallbackMessage
        }),
        createDependencyStatus('ai-provider', 'AI provider', {
          status: providerResponse?.status ?? null,
          requestId: providerResponse?.headers.get('x-request-id') ?? null,
          backendPath: '/api/settings/workspace/ai-provider'
        })
      ]
    })
  };
}
