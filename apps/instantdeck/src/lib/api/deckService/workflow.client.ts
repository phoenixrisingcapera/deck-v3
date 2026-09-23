import {
  ApiClientError,
  fetchApiJsonOrThrow,
  isApiAuthError,
  isApiBackendError,
  isApiNetworkError,
} from '$lib/api/apiError';
import { deckProductApiPath, deckWorkflowJobApiPath, deckWorkflowStateApiPath } from '$lib/contracts';
import type { DeckExport, DeckExportShare, DeckExportShareCreated } from '$lib/contracts/types';
import type { BrandProfile } from '$lib/types/deckService-brand';
import type { DesignVersion, SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
import { reconcileAuthoritativeProcessingStatus } from './processingPolling';

/*
  This file is the frontend translator for backend deck workflow state.

  The backend tells us truth for:
  - whether the source file is saved
  - slide extraction and previews
  - whether Smart Deck can open
  - worker failures and retry needs

  This file should normalize backend responses only.
*/

const BACKEND_UNAVAILABLE_STATUS_CODES = new Set([502, 503, 504]);
const DEFAULT_WORKFLOW_JOB_MAX_ATTEMPTS = 240;
const DEFAULT_WORKFLOW_JOB_POLL_DELAY_MS = 1000;
const WORKFLOW_JOB_STATUSES = new Set(['queued', 'running', 'completed', 'failed_retryable', 'failed_final', 'blocked', 'timed_out']);

async function createClassifiedHtmlDeckExport(
  deckId: string,
  designVersionId: string,
  exportType: 'final_deck' | 'provisional_html'
): Promise<DeckExport> {
  const response = await fetch(deckProductApiPath(`/decks/${deckId}/workflows/export`), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      type: exportType,
      exportType,
      format: 'html',
      designVersionId,
      idempotencyKey: crypto.randomUUID()
    })
  });
  const accepted = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof accepted?.detail?.message === 'string' ? accepted.detail.message : 'Could not start HTML export.');
  const jobId = typeof accepted?.jobId === 'string' ? accepted.jobId : '';
  if (!jobId) throw new Error('HTML export workflow did not return a job id.');
  const job = await waitForWorkflowJobCompletion(jobId, 'HTML export failed.');
  if (job.status !== 'completed') throw new Error(job.error?.message ?? 'HTML export failed to complete.');
  const exportsResponse = await fetch(`/api/decks/${deckId}/exports`);
  const exportsPayload = await exportsResponse.json().catch(() => null);
  if (!exportsResponse.ok) throw new Error('HTML export completed, but its download could not be loaded.');
  const records = Array.isArray(exportsPayload?.exports) ? exportsPayload.exports as DeckExport[] : [];
  const output = (job.output ?? {}) as Record<string, unknown>;
  const exportId = typeof output.exportId === 'string' ? output.exportId : null;
  const exact = records.find((item) => item.type === exportType && item.format === 'html' && item.designVersionId === designVersionId && (!exportId || item.id === exportId));
  if (!exact) throw new Error('HTML export completed without the requested design version artifact.');
  return exact;
}

export function createHtmlDeckExport(deckId: string, designVersionId: string): Promise<DeckExport> {
  return createClassifiedHtmlDeckExport(deckId, designVersionId, 'final_deck');
}

export function createProvisionalHtmlDeckExport(deckId: string, designVersionId: string): Promise<DeckExport> {
  return createClassifiedHtmlDeckExport(deckId, designVersionId, 'provisional_html');
}

export async function createInstantDeckShare(
  deckId: string,
  designVersionId: string,
  expiresInDays: number | null = null
): Promise<DeckExportShareCreated> {
  const deckExport = await createProvisionalHtmlDeckExport(deckId, designVersionId);
  if (deckExport.designVersionId !== designVersionId || deckExport.format !== 'html') {
    throw new Error('The share export does not match the displayed Instant Deck DesignVersion.');
  }
  const share = await fetchApiJsonOrThrow<DeckExportShareCreated>(
    `/api/decks/${deckId}/exports/${deckExport.id}/shares`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ expiresInDays })
    },
    'Could not create a share link for this Instant Deck.'
  );
  if (share.exportId !== deckExport.id || share.designVersionId !== designVersionId || share.status !== 'active') {
    throw new Error('The created share link is not bound to the displayed Instant Deck DesignVersion.');
  }
  return share;
}

export async function revokeInstantDeckShare(
  deckId: string,
  exportId: string,
  shareId: string
): Promise<DeckExportShare> {
  return fetchApiJsonOrThrow<DeckExportShare>(
    `/api/decks/${deckId}/exports/${exportId}/shares/${shareId}`,
    { method: 'DELETE' },
    'Could not revoke the Instant Deck share link.'
  );
}

export type DeckExtractionStatus = 'idle' | 'queued' | 'processing' | 'ready' | 'failed';
type DeckProcessingLifecycleStatus = 'idle' | 'queued' | 'processing' | 'ready' | 'failed' | 'unknown';
export type WorkflowJobType =
  | 'source_ingestion'
  | 'source_extraction'
  | 'miniatures'
  | 'brand_extraction'
  | 'smart_deck_context'
  | 'db_publisher'
  | 'llm_generation'
  | 'instant_deck_generation'
  | 'selected_slide_generation'
  | 'compile_final_deck'
  | 'schema_validation'
  | 'preview_render'
  | 'apply_version'
  | 'due_diligence'
  | 'deck_map_analysis'
  | 'market_research'
  | 'media_processing'
  | 'smart_edit'
  | 'export';

export type WorkflowJobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'status_unavailable'
  | 'failed_retryable'
  | 'failed_final'
  | 'blocked'
  | 'timed_out';

export interface WorkflowJobSummary {
  jobId: string;
  jobType: WorkflowJobType;
  status: WorkflowJobStatus;
  phase: string;
  attemptCount?: number | null;
  maxAttempts?: number | null;
  recoveryCount?: number | null;
  progress?: number | null;
  queuedAt?: string | null;
  startedAt?: string | null;
  heartbeatAt?: string | null;
  updatedAt?: string | null;
  lastRecoveredAt?: string | null;
  completedAt?: string | null;
  failedAt?: string | null;
  publishedPhase?: 'ai_vc_understanding' | 'ai_vc_research' | 'ai_vc_analysis' | 'narrative_reconstruction' | 'visual_direction' | 'visual_asset_planning' | 'smart_deck_ready' | 'preview_ready' | 'applied' | 'export_ready' | null;
  terminal?: boolean;
  terminalReason?: string | null;
  retryEligible?: boolean;
  error?: { code?: string; message?: string; recoverable?: boolean; nextAction?: WorkflowNextAction | null } | null;
  workflowId?: string | null;
  rootJobId?: string | null;
  generationJobId?: string | null;
  parentJobId?: string | null;
  dependencyJobIds?: string[];
  authoritative?: boolean;
}

export interface AuthoritativeInstantChain {
  workflowId: string;
  rootJobId: string;
  generationJobId: string;
  chainJobIds: string[];
  schemaValidationJobId?: string | null;
  previewRenderJobId?: string | null;
  publisherJobId?: string | null;
}

type WorkflowNextAction =
  | 'continue_upload'
  | 'view_processing'
  | 'apply_preview'
  | 'open_smart_deck'
  | 'configure_provider'
  | 'retry_job'
  | 'manual_review'
  | 'create_smart_deck';

const DEFAULT_AUTH_EXPIRED_MESSAGE = 'Your session expired. Sign in again to continue processing this deck.';

let deckProcessingAuthExpired = false;
let deckProcessingAuthExpiredMessage = DEFAULT_AUTH_EXPIRED_MESSAGE;
let deckProcessingAuthExpiredPath: string | undefined;

class DeckProcessingAuthExpiredError extends Error {
  status = 401;
  actionLabel = 'Sign in again';

  constructor(message = deckProcessingAuthExpiredMessage, readonly path?: string) {
    super(message || DEFAULT_AUTH_EXPIRED_MESSAGE);
    this.name = 'DeckProcessingAuthExpiredError';
  }
}

function rememberAuthExpired(error: unknown, path?: string): DeckProcessingAuthExpiredError | null {
  if (!isApiAuthError(error) && !(error instanceof DeckProcessingAuthExpiredError)) {
    return null;
  }

  deckProcessingAuthExpired = true;
  deckProcessingAuthExpiredMessage = error instanceof Error && error.message ? error.message : DEFAULT_AUTH_EXPIRED_MESSAGE;
  deckProcessingAuthExpiredPath = path;
  return new DeckProcessingAuthExpiredError(deckProcessingAuthExpiredMessage, deckProcessingAuthExpiredPath);
}

function assertDeckProcessingAuthAvailable() {
  if (deckProcessingAuthExpired) {
    throw new DeckProcessingAuthExpiredError(deckProcessingAuthExpiredMessage, deckProcessingAuthExpiredPath);
  }
}

function backendUnavailableDiagnostics(
  deckId: string,
  statusCode: number | null | undefined,
  message: string,
  path: string,
  payload?: unknown
): SmartDeckProcessingStatusWithDiagnostics {
  const normalizedPayload = getRecord(payload);
  return reconcileAuthoritativeProcessingStatus({
    deckId,
    status: 'failed',
    nextAction: 'manual_review',
    sourceFileStatus: 'missing',
    sourceFileSaved: false,
    sourceSlideCount: 0,
    deckExtractionStatus: 'failed',
    sourceSlides: [],
    phases: [
      {
        key: 'processing_state_unavailable',
        label: 'Workflow state unavailable',
        status: 'failed',
        description: message,
        active: false,
        completed: false
      }
    ],
    stages: [
      {
        key: 'processing_state_unavailable',
        label: 'Workflow state unavailable',
        status: 'failed',
        description: message,
        active: false,
        completed: false
      }
    ],
    canOpenSmartDeck: false,
    canOpenInstantDeck: false,
    // Losing the workflow-state connection must not authorize a processing
    // mutation. The mounted loader offers a status read retry instead.
    canRetry: false,
    processingStage: 'failed',
    processingStageLabel: 'Workflow unavailable',
    message,
    errorMessage: message,
    blockingReason: 'backend_unavailable',
    missingArtifacts: [],
    failures: [],
    workerHeartbeat: null,
    latestConfirmation: null,
    updatedAt: undefined,
    backendStatus: statusCode ?? 0,
    backendStatusText: statusCode ? undefined : 'network',
    backendMessage: message,
    backendPath: path,
    backendPayload: normalizedPayload,
  });
}

export interface SourceEnrichmentStatus {
  source: string;
  llmStatus?: string;
  provider?: string;
  model?: string;
  message: string;
  badge: string;
}

export interface WorkflowSourceBlock {
  id?: string | null;
  blockIndex: number;
  rawText: string;
  normalizedText: string;
  blockType: string;
  sourceKind?: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkflowSourceAsset {
  id?: string | null;
  assetType: string;
  label?: string | null;
  mimeType?: string | null;
  assetUrl?: string | null;
  pageNumber?: number | null;
  width?: number | null;
  height?: number | null;
  metadata: Record<string, unknown>;
}

export interface WorkflowSourceSlide {
  id?: string | null;
  slideIndex: number;
  title: string;
  role: string;
  rawText: string;
  sourcePageNumber?: number | null;
  thumbnailPath?: string | null;
  thumbnailUrl?: string | null;
  previewImageUrl?: string | null;
  previewUrl?: string | null;
  thumbnailMimeType?: string | null;
  widthPoints?: number | null;
  heightPoints?: number | null;
  metadata: Record<string, unknown>;
  blocks: WorkflowSourceBlock[];
  assets: WorkflowSourceAsset[];
}

export interface ProcessingPhase {
  key: string;
  label: string;
  description?: string;
  status: 'pending' | 'active' | 'completed' | 'failed' | 'blocked' | string;
  active?: boolean;
  completed?: boolean;
  count?: number | null;
}

const FAILED_WORKFLOW_JOB_STATUSES = new Set(['failed_retryable', 'failed_final', 'timed_out']);

function normalizeProcessingPhases(phases: ProcessingPhase[]): ProcessingPhase[] {
  return phases.map((phase) => {
    const jobStatus = firstString(phase.status)?.toLowerCase();
    if (jobStatus === 'blocked') {
      return { ...phase, status: 'blocked', active: false, completed: false };
    }
    if (jobStatus && FAILED_WORKFLOW_JOB_STATUSES.has(jobStatus)) {
      return { ...phase, status: 'failed', active: false, completed: false };
    }
    return phase;
  });
}

export type WorkflowFailure = Record<string, unknown>;

export interface FactualReviewFinding {
  generatedSlide: number;
  generatedClaim: string;
  sourcePage: number | null;
  sourceEvidence: string;
  discrepancy: string;
  correction: string | null;
  sourceAmbiguous: boolean;
}
export interface SmartDeckProcessingStatus {
  factualReview?: { status: string; canResumeSavedReview?: boolean; generationJobId?: string; evidencePolicy?: string; referenceWarnings?: unknown[]; findings: FactualReviewFinding[]; draftText: { slide: number; text: string }[] } | null;
  deckId: string;
  publicResearch?: {
    status: string;
    message: string;
    verifiedClaimCount: number;
    planningStatus: string;
    sources: Array<{
      url: string;
      publisher: string;
      topic: string;
      publicationDate?: string | null;
      retrievalDate?: string | null;
    }>;
    limitations: string[];
  } | null;
  aiVcStrategy?: { status: string; architectureSource?: string | null; recoveryUsed: boolean } | null;
  workflowId?: string;
  authoritativeInstantChain?: AuthoritativeInstantChain | null;
  authoritativeInstantChainActive?: boolean;
  status: DeckProcessingLifecycleStatus;
  brandProfile?: BrandProfile | null;
  nextAction?: WorkflowNextAction;
  activeStage?: string | null;
  blockingReason?: string | null;
  updatedAt?: string | null;
  processingStage?: string | null;
  processingStageLabel?: string | null;
  sourceFileStatus?: string;
  sourceFileSaved: boolean;
  sourceSlideCount?: number;
  sourceEnrichment?: SourceEnrichmentStatus | null;
  sourceSlides?: WorkflowSourceSlide[];
  deckExtractionStatus: DeckExtractionStatus;
  latestConfirmation?: Record<string, unknown> | null;
  message?: string;
  errorMessage?: string;
  phases: ProcessingPhase[];
  stages: ProcessingPhase[];
  canOpenSmartDeck: boolean;
  canOpenInstantDeck: boolean;
  canGenerate?: boolean;
  canRetry: boolean;
  degradedMode?: boolean;
  missingArtifacts?: string[];
  failures?: WorkflowFailure[];
  workerHeartbeat?: Record<string, unknown> | null;
  activeJob?: WorkflowJobSummary | null;
  failedJob?: WorkflowJobSummary | null;
  latestJobs?: WorkflowJobSummary[];
}

export interface SmartDeckProcessingBackendDiagnostics {
  backendStatus?: number;
  backendStatusText?: string;
  backendMessage?: string;
  backendPath?: string;
  backendPayload?: Record<string, unknown> | null;
  requestId?: string | null;
  ticketId?: string | null;
}

export interface SmartDeckProcessingStatusWithDiagnostics
  extends SmartDeckProcessingStatus,
    SmartDeckProcessingBackendDiagnostics {}

function getRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
}

function hasCanonicalWorkflowDiagnostics(payload: unknown): boolean {
  const record = getRecord(payload);
  return typeof record.backendStatus === 'number' || record.blockingReason === 'backend_unavailable';
}

function assertStringField(record: Record<string, unknown>, field: string, missing: string[]) {
  if (typeof record[field] !== 'string' || !record[field].trim()) missing.push(field);
}

function assertObjectField(record: Record<string, unknown>, field: string, missing: string[]) {
  if (!record[field] || typeof record[field] !== 'object' || Array.isArray(record[field])) missing.push(field);
}

function assertDeckWorkflowStateContract(payload: unknown, deckId: string, path: string): asserts payload is Record<string, unknown> {
  const record = getRecord(payload);
  const missing: string[] = [];
  assertStringField(record, 'deckId', missing);
  assertStringField(record, 'workflowId', missing);
  assertStringField(record, 'phase', missing);
  assertStringField(record, 'status', missing);
  assertStringField(record, 'lifecycleStatus', missing);
  assertStringField(record, 'nextAction', missing);
  assertObjectField(record, 'source', missing);
  assertObjectField(record, 'smartDeck', missing);
  assertObjectField(record, 'provider', missing);
  assertObjectField(record, 'brand', missing);
  assertObjectField(record, 'links', missing);

  const source = getRecord(record.source);
  const smartDeck = getRecord(record.smartDeck);
  const links = getRecord(record.links);
  if (typeof source.fileSaved !== 'boolean') missing.push('source.fileSaved');
  if (typeof source.slideCount !== 'number') missing.push('source.slideCount');
  if (typeof smartDeck.ready !== 'boolean') missing.push('smartDeck.ready');
  if (typeof smartDeck.sourceSlideCount !== 'number') missing.push('smartDeck.sourceSlideCount');
  if (typeof links.processingUrl !== 'string') missing.push('links.processingUrl');
  if (typeof links.smartDeckUrl !== 'string') missing.push('links.smartDeckUrl');
  if (typeof record.deckId === 'string' && record.deckId !== deckId) missing.push('deckId');
  if (typeof record.status === 'string' && !WORKFLOW_JOB_STATUSES.has(record.status)) missing.push('status');

  if (missing.length > 0) {
    throw new ApiClientError({
      status: 409,
      kind: 'api_contract',
      requestId: null,
      payload: record,
      path,
      message: `Workflow-state API contract mismatch. Invalid or missing fields: ${missing.join(', ')}.`
    });
  }
}

function nullableRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function normalizeAuthoritativeInstantChain(value: unknown): AuthoritativeInstantChain | null {
  const record = nullableRecord(value);
  if (!record) return null;
  const workflowId = firstString(record.workflowId);
  const rootJobId = firstString(record.rootJobId);
  const generationJobId = firstString(record.generationJobId);
  const chainJobIds = Array.isArray(record.chainJobIds)
    ? record.chainJobIds.filter((id): id is string => typeof id === 'string' && id.trim().length > 0).map((id) => id.trim())
    : [];
  if (!workflowId || !rootJobId || !generationJobId || chainJobIds.length === 0) return null;
  return {
    workflowId,
    rootJobId,
    generationJobId,
    chainJobIds,
    schemaValidationJobId: firstString(record.schemaValidationJobId) ?? null,
    previewRenderJobId: firstString(record.previewRenderJobId) ?? null,
    publisherJobId: firstString(record.publisherJobId) ?? null
  };
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return undefined;
}

function firstBoolean(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'boolean') return value;
  }
  return undefined;
}

function firstNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return undefined;
}

function extractPayloadMessage(payload: unknown, fallbackMessage: string): string {
  const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  const detail = record && typeof record.detail === 'object' && record.detail !== null ? (record.detail as Record<string, unknown>) : null;
  const candidates = [
    record?.message,
    record?.error,
    record?.title,
    record?.detail,
    record?.errorMessage,
    record?.error_message,
    detail?.message,
    detail?.error,
    detail?.reason
  ];

  const direct = candidates.find((value): value is string => typeof value === 'string' && value.trim().length > 0);
  if (direct) return direct.trim();
  return fallbackMessage;
}

function normalizeLifecycleStatus(value: unknown): DeckProcessingLifecycleStatus {
  const normalized = firstString(value)?.toLowerCase();
  if (!normalized) return 'unknown';
  if (['queued', 'accepted', 'starting', 'waiting', 'ingestion_started', 'processing_started'].includes(normalized)) {
    return 'queued';
  }
  if (['processing', 'extracting', 'parsed', 'extracting_blocks', 'structuring', 'classifying_blocks', 'analysing', 'adapting'].includes(normalized)) {
    return 'processing';
  }
  if (['ready', 'complete', 'completed', 'finished'].includes(normalized)) {
    return 'ready';
  }
  if (['failed', 'failed_retryable', 'failed_final', 'blocked', 'timed_out', 'error', 'dead_letter'].includes(normalized)) {
    return 'failed';
  }
  return 'unknown';
}

function hasBackendFailure(record: Record<string, unknown>, status: DeckProcessingLifecycleStatus): boolean {
  return (
    status === 'failed' ||
    firstBoolean(record.degradedMode) === true ||
    firstString(record.deckExtractionStatus) === 'failed'
  );
}

function isSavedLike(value: unknown) {
  return value === true || value === 'saved' || value === 'ready' || value === 'uploaded' || value === 'available';
}

function resolveSourceFilePresence(record: Record<string, unknown>): boolean | undefined {
  return firstBoolean(record.hasSourceFile, record.has_source_file, record.sourceFileSaved, record.source_file_saved);
}

function resolveSourceFileStatus(record: Record<string, unknown>): string {
  const explicitStatus = firstString(record.sourceFileStatus, record.source_file_status);
  const hasSourceFile = resolveSourceFilePresence(record);
  if (hasSourceFile === false) return 'missing';
  if (explicitStatus) return explicitStatus;
  return isSavedLike(record.sourceFileSaved) ? 'saved' : 'missing';
}

function parseTimestamp(value: unknown): number | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function getWorkflowStatusAgeMinutes(status: SmartDeckProcessingStatus | null | undefined): number | null {
  const timestamp = parseTimestamp(status?.updatedAt);
  if (timestamp === null) return null;
  return Math.max(0, Math.round((Date.now() - timestamp) / 60000));
}

export function isWorkflowStatusStalled(status: SmartDeckProcessingStatus | null | undefined, thresholdMinutes = 12): boolean {
  if (!status) return false;
  if (!['processing', 'queued'].includes(status.status)) return false;
  if (status.degradedMode) return false;
  if (status.nextAction === 'manual_review') return false;
  const ageMinutes = getWorkflowStatusAgeMinutes(status);
  return ageMinutes !== null && ageMinutes >= thresholdMinutes;
}

export function getWorkflowActivePhaseLabel(status: SmartDeckProcessingStatus | null | undefined): string | null {
  if (!status) return null;
  if (status.activeStage) {
    const explicit = status.stages.find((phase) => phase.key === status.activeStage);
    if (explicit) {
      return explicit.label || explicit.key || null;
    }
  }
  const activePhase = status.phases.find((phase) => phase.active || phase.status === 'active');
  if (!activePhase) return null;
  return activePhase.label || activePhase.key || null;
}

export function normalizeSmartDeckProcessingStatus(payload: unknown, deckId: string): SmartDeckProcessingStatusWithDiagnostics {
  const record = getRecord(payload);
  const source = getRecord(record.source);
  const brand = getRecord(record.brand);
  const smartDeck = getRecord(record.smartDeck);
  const smartDeckRecord = smartDeck;
  const nextAction = firstString(record.nextAction) as WorkflowNextAction | undefined;
  const activeStage = firstString(record.activeStage, record.processingStage, record.phase);
  const status = normalizeLifecycleStatus(firstString(record.lifecycleStatus, record.status, record.state));
  const sourceFileStatus = resolveSourceFileStatus(record);
  const sourceFileSaved = sourceFileStatus !== 'missing';
  const sourceEnrichment = (source.sourceEnrichment ?? null) as SourceEnrichmentStatus | null;
  const sourceSlides = Array.isArray(source.slides)
    ? (source.slides as WorkflowSourceSlide[])
    : [];
  const sourceSlideCount = firstNumber(record.sourceSlideCount, source.sourceSlideCount, source.slideCount) ?? sourceSlides.length;
  const brandProfile = brand.profile && typeof brand.profile === 'object' ? (brand.profile as BrandProfile) : null;
  const phases = normalizeProcessingPhases(Array.isArray(record.phases) ? (record.phases as ProcessingPhase[]) : []);
  const stages = normalizeProcessingPhases(Array.isArray(record.stages) ? (record.stages as ProcessingPhase[]) : phases);
  const failures = Array.isArray(record.failures) ? (record.failures as WorkflowFailure[]) : [];
  const latestJobs = Array.isArray(record.latestJobs)
    ? record.latestJobs.filter((value): value is WorkflowJobSummary => Boolean(value) && typeof value === 'object' && !Array.isArray(value))
    : [];
  const missingArtifacts = Array.isArray(record.missingArtifacts)
    ? record.missingArtifacts.filter((value): value is string => typeof value === 'string' && value.trim().length > 0).map((value) => value.trim())
    : [];
  const canOpenSmartDeck = record.canOpenSmartDeck === true;
  const canOpenInstantDeck = record.canOpenInstantDeck === true;
  // DISABLED: Readiness was inferred from nested aliases, lifecycle status,
  // source counts, and frontend failure heuristics. workflow-state owns it.
  // const explicitCanOpen = firstBoolean(record.canOpenSmartDeck, smartDeck.canOpenSmartDeck, smartDeck.ready);
  // const canOpenSmartDeck = (explicitCanOpen ?? (nextAction === 'open_smart_deck' || status === 'ready')) && sourceSlideCount > 0 && !hasBackendFailure(record, status);

  const backendStatus = firstNumber(record.backendStatus);
  const backendStatusText = firstString(record.backendStatusText);
  const backendMessage = firstString(record.backendMessage, record.message, record.errorMessage, record.error);
  const backendPath = firstString(record.backendPath);
  const backendPayload = nullableRecord(record.backendPayload);
  const detail = getRecord(record.detail);
  const requestId = firstString(record.requestId, record.request_id, detail.requestId, detail.request_id, backendPayload?.requestId, backendPayload?.request_id) ?? null;
  const ticketId = firstString(record.ticketId, record.ticket_id, detail.ticketId, detail.ticket_id, backendPayload?.ticketId, backendPayload?.ticket_id) ?? null;

  return {
    deckId: firstString(record.deckId) ?? deckId,
    workflowId: firstString(record.workflowId),
    authoritativeInstantChain: normalizeAuthoritativeInstantChain(record.authoritativeInstantChain),
    factualReview: record.factualReview && typeof record.factualReview === 'object'
      ? {
          status: firstString(getRecord(record.factualReview).status) ?? 'needs_review',
          canResumeSavedReview: getRecord(record.factualReview).canResumeSavedReview === true,
          generationJobId: firstString(getRecord(record.factualReview).generationJobId),
          evidencePolicy: firstString(getRecord(record.factualReview).evidencePolicy),
          referenceWarnings: Array.isArray(getRecord(record.factualReview).referenceWarnings) ? getRecord(record.factualReview).referenceWarnings as unknown[] : [],
          findings: Array.isArray(getRecord(record.factualReview).findings)
            ? (getRecord(record.factualReview).findings as FactualReviewFinding[]) : [],
          draftText: Array.isArray(getRecord(record.factualReview).draftText)
            ? (getRecord(record.factualReview).draftText as unknown[]).flatMap((entry) => {
                const item = getRecord(entry);
                return typeof item.slide === 'number' && Number.isInteger(item.slide) && item.slide > 0 && typeof item.text === 'string'
                  ? [{ slide: item.slide, text: item.text.slice(0, 4000) }] : [];
              }).slice(0, 512) : []
        } : null,
    publicResearch: record.publicResearch && typeof record.publicResearch === 'object'
      ? {
          status: String(getRecord(record.publicResearch).status || 'unavailable'),
          message: String(getRecord(record.publicResearch).message || 'Market research was unavailable.'),
          verifiedClaimCount: typeof getRecord(record.publicResearch).verifiedClaimCount === 'number'
            ? getRecord(record.publicResearch).verifiedClaimCount as number : 0,
          planningStatus: String(getRecord(record.publicResearch).planningStatus || 'unavailable'),
          sources: Array.isArray(getRecord(record.publicResearch).sources)
            ? (getRecord(record.publicResearch).sources as unknown[]).flatMap((entry) => {
                const source = getRecord(entry);
                const url = firstString(source.url);
                if (!url?.startsWith('https://')) return [];
                return [{
                  url,
                  publisher: firstString(source.publisher) ?? 'Public source',
                  topic: firstString(source.topic) ?? 'market_context',
                  publicationDate: firstString(source.publicationDate) ?? null,
                  retrievalDate: firstString(source.retrievalDate) ?? null
                }];
              }).slice(0, 24) : [],
          limitations: Array.isArray(getRecord(record.publicResearch).limitations)
            ? (getRecord(record.publicResearch).limitations as unknown[])
                .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
                .map((value) => value.slice(0, 500)).slice(0, 12) : []
        }
      : null,
    aiVcStrategy: record.aiVcStrategy && typeof record.aiVcStrategy === 'object'
      ? {
          status: String(getRecord(record.aiVcStrategy).status || 'failed'),
          architectureSource: firstString(getRecord(record.aiVcStrategy).architectureSource) ?? null,
          recoveryUsed: getRecord(record.aiVcStrategy).recoveryUsed === true
        }
      : null,
    status,
    brandProfile,
    nextAction,
    activeStage,
    blockingReason: firstString(record.blockingReason, record.blocking_reason) ?? null,
    updatedAt: firstString(record.updatedAt, record.updated_at, record.updatedAtIso, record.updated_at_iso),
    processingStage: activeStage,
    processingStageLabel: firstString(record.processingStageLabel, record.processing_stage_label, record.stageLabel, record.stage_label),
    sourceFileStatus,
    sourceFileSaved,
    sourceSlideCount,
    sourceEnrichment,
    sourceSlides,
    deckExtractionStatus: (firstString(record.deckExtractionStatus) ?? 'idle') as DeckExtractionStatus,
    latestConfirmation: nullableRecord(record.latestConfirmation ?? record.latest_confirmation),
    message: firstString(record.message, record.nextStepMessage),
    errorMessage: firstString(record.errorMessage, record.error),
    phases,
    stages,
    canOpenSmartDeck,
    canOpenInstantDeck,
    canGenerate: firstBoolean(record.canGenerate) ?? undefined,
    canRetry: firstBoolean(record.canRetry, record.retryAllowed) ?? false,
    degradedMode: firstBoolean(record.degradedMode) ?? false,
    missingArtifacts,
    failures,
    workerHeartbeat: nullableRecord(record.workerHeartbeat),
    activeJob: nullableRecord(record.activeJob) as WorkflowJobSummary | null,
    failedJob: nullableRecord(record.failedJob) as WorkflowJobSummary | null,
    latestJobs,
    backendStatus,
    backendStatusText,
    backendMessage,
    backendPath,
    backendPayload,
    requestId,
    ticketId,
  };
}

async function getDeckWorkflowState(deckId: string): Promise<unknown> {
  assertDeckProcessingAuthAvailable();
  const path = deckWorkflowStateApiPath(deckId);
  const fallbackMessage = 'Could not load deck workflow state.';
  try {
    return await fetchApiJsonOrThrow<unknown>(path, { method: 'GET' }, fallbackMessage);
  } catch (error) {
    const authError = rememberAuthExpired(error, path);
    if (authError) {
      throw authError;
    }
    if (isApiBackendError(error) && BACKEND_UNAVAILABLE_STATUS_CODES.has(error.status)) {
      return backendUnavailableDiagnostics(
        deckId,
        error.status,
        extractPayloadMessage(error.payload, `${fallbackMessage} Backend returned HTTP ${error.status}`),
        path,
        error.payload
      );
    }
    if (isApiNetworkError(error)) {
      return backendUnavailableDiagnostics(
        deckId,
        error.status,
        `${fallbackMessage} ${typeof error.message === 'string' ? error.message : 'backend unavailable.'}`,
        path,
        error.payload
      );
    }
    throw error;
  }
}

async function getWorkflowJob(jobId: string, signal?: AbortSignal): Promise<{
  jobId: string;
  deckId?: string;
  jobType?: WorkflowJobType;
  status: WorkflowJobStatus;
  heartbeatAt?: string | null;
  startedAt?: string | null;
  phase?: string | null;
  error?: { message: string; code?: string; recoverable?: boolean; nextAction?: string; requestId?: string; failureTicketId?: string } | null;
  output?: Record<string, unknown> | null;
  artifacts?: Array<Record<string, unknown>> | null;
}> {
  assertDeckProcessingAuthAvailable();
  const path = deckWorkflowJobApiPath(jobId);
  try {
    return await fetchApiJsonOrThrow<{
      jobId: string;
      deckId?: string;
      jobType?: WorkflowJobType;
      status: WorkflowJobStatus;
      heartbeatAt?: string | null;
      startedAt?: string | null;
      phase?: string | null;
      error?: { message: string; code?: string; recoverable?: boolean; nextAction?: string; requestId?: string; failureTicketId?: string } | null;
      output?: Record<string, unknown> | null;
      artifacts?: Array<Record<string, unknown>> | null;
    }>(
      path,
      { method: 'GET', signal },
      'Could not load workflow job.'
    );
  } catch (error) {
    const authError = rememberAuthExpired(error, path);
    if (authError) {
      throw authError;
    }
    const status = typeof (error as { status?: number }).status === 'number' ? (error as { status?: number }).status : undefined;
    const message =
      typeof (error as { message?: unknown }).message === 'string'
        ? (error as { message?: string }).message
        : 'Workflow job status was not available.';
    if (status === 502 || status === 503 || status === 504 || status === 0) {
      return {
        jobId,
        status: 'status_unavailable',
        error: { message: `Workflow job backend unavailable: ${message}` },
      };
    }
    throw error;
  }
}

export function normalizeSmartDeckReadiness(payload: unknown, deckId: string): SmartDeckProcessingStatusWithDiagnostics {
  const record = getRecord(payload);
  const smartDeck = getRecord(record.smartDeck);
  const status = normalizeLifecycleStatus(firstString(record.lifecycleStatus, record.status, record.state));
  const nextAction = firstString(record.nextAction) as WorkflowNextAction | undefined;
  const source = getRecord(record.source);
  const sourceSlides = Array.isArray(source.slides) ? (source.slides as WorkflowSourceSlide[]) : [];
  const sourceSlideCount = firstNumber(record.sourceSlideCount, source.sourceSlideCount, source.slideCount) ?? sourceSlides.length;
  const canOpenSmartDeck = record.canOpenSmartDeck === true;
  // DISABLED: Frontend source-count and failure checks duplicated the backend
  // workflow-state read model and could override its authoritative boolean.
  // const explicitCanOpen = firstBoolean(record.canOpenSmartDeck, smartDeck.canOpenSmartDeck, smartDeck.ready);
  // const canOpenSmartDeck = explicitCanOpen === true && sourceSlideCount > 0 && !hasBackendFailure(record, status);
  const ready = canOpenSmartDeck;
  const legacyBlockingReason = firstString(record.blockingReason);

  return {
    ...normalizeSmartDeckProcessingStatus(payload, deckId),
    status: ready ? 'ready' : status,
    nextAction,
    blockingReason: firstString(legacyBlockingReason, record.blocking_reason) ?? null,
    canOpenSmartDeck,
    canRetry: firstBoolean(record.canRetry, record.retryAllowed) ?? false,
    sourceSlideCount
  };
}

export async function getSmartDeckReadinessState(deckId: string): Promise<SmartDeckProcessingStatusWithDiagnostics> {
  assertDeckProcessingAuthAvailable();
  const path = deckWorkflowStateApiPath(deckId);
  const fallbackMessage = 'Could not load Smart Deck readiness state.';
  try {
    const payload = await fetchApiJsonOrThrow<unknown>(path, { method: 'GET' }, fallbackMessage);
    assertDeckWorkflowStateContract(payload, deckId, path);
    return normalizeSmartDeckReadiness(payload, deckId);
  } catch (error) {
    const authError = rememberAuthExpired(error, path);
    if (authError) {
      throw authError;
    }
    if (isApiBackendError(error) && BACKEND_UNAVAILABLE_STATUS_CODES.has(error.status)) {
      return backendUnavailableDiagnostics(
        deckId,
        error.status,
        extractPayloadMessage(error.payload, `${fallbackMessage} Backend returned HTTP ${error.status}`),
        path,
        error.payload
      );
    }
    if (isApiNetworkError(error)) {
      return backendUnavailableDiagnostics(
        deckId,
        error.status,
        `${fallbackMessage} ${typeof error.message === 'string' ? error.message : 'backend unavailable.'}`,
        path,
        error.payload
      );
    }
    throw error;
  }
}

export interface WorkflowJobCompletionResult {
  jobId: string;
  deckId?: string;
  jobType?: WorkflowJobType;
  status: WorkflowJobStatus;
  error?: { message: string; code?: string; recoverable?: boolean; nextAction?: string; requestId?: string; failureTicketId?: string } | null;
  errorMessage?: string | null;
  output?: Record<string, unknown> | null;
  artifacts?: Array<Record<string, unknown>> | null;
  designVersion?: DesignVersion | null;
  workspace?: SmartDeckWorkspacePayload | null;
}

export class WorkflowJobTerminalError extends Error {
  constructor(
    message: string,
    readonly details: NonNullable<WorkflowJobCompletionResult['error']>
  ) {
    super(message);
    this.name = 'WorkflowJobTerminalError';
  }
}

export class WorkflowJobPollingIncompleteError extends Error {
  readonly nonMutating = true;

  constructor(readonly jobId: string) {
    super(`Workflow job ${jobId} is still processing or temporarily unavailable. Check status again without starting another command.`);
    this.name = 'WorkflowJobPollingIncompleteError';
  }
}

function delayMs(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException('Polling was cancelled.', 'AbortError'));
      return;
    }
    const timeout = setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, ms);
    const abort = () => {
      clearTimeout(timeout);
      reject(signal?.reason ?? new DOMException('Polling was cancelled.', 'AbortError'));
    };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export async function waitForWorkflowJobCompletion(
  jobId: string,
  failureMessage: string,
  maxAttempts = DEFAULT_WORKFLOW_JOB_MAX_ATTEMPTS,
  pollDelayMs = DEFAULT_WORKFLOW_JOB_POLL_DELAY_MS,
  onProgress?: (job: { status: WorkflowJobStatus; phase?: string | null; output?: Record<string, unknown> | null }) => void,
  signal?: AbortSignal
): Promise<WorkflowJobCompletionResult> {
  let attempt = 0;
  while (attempt < maxAttempts) {
    signal?.throwIfAborted();
    const job = await getWorkflowJob(jobId, signal);
    const status = String(job.status ?? '');
    onProgress?.({ status: job.status, phase: job.phase, output: job.output });
    if (status === 'completed') {
      return job;
    }
    if (status === 'status_unavailable') {
      await delayMs(pollDelayMs, signal);
      attempt += 1;
      continue;
    }
    if (status === 'failed_retryable' || status === 'failed_final' || status === 'blocked' || status === 'timed_out') {
      const details = job.error ?? { message: failureMessage };
      throw new WorkflowJobTerminalError(details.message || failureMessage, details);
    }
    // Backend workflow state owns stale-worker recovery. The browser must not
    // turn an old heartbeat into permission for a duplicate generation POST.
    attempt += 1;
    await delayMs(pollDelayMs, signal);
  }
  throw new WorkflowJobPollingIncompleteError(jobId);
}

export async function getDeckWorkflowStatus(deckId: string): Promise<SmartDeckProcessingStatusWithDiagnostics> {
  const payload = await getDeckWorkflowState(deckId);
  if (!hasCanonicalWorkflowDiagnostics(payload)) {
    assertDeckWorkflowStateContract(payload, deckId, deckWorkflowStateApiPath(deckId));
  }
  return normalizeSmartDeckProcessingStatus(payload, deckId);
}

export interface DeckProcessingVisibility {
  deckId: string;
  status?: string;
  nextAction?: string;
  processing?: { status?: string; stage?: string } | null;
  upload?: { sourceSaved?: boolean } | null;
  deckStatus?: string;
}

export async function getDeckProcessingVisibility(deckId: string): Promise<DeckProcessingVisibility | null> {
  assertDeckProcessingAuthAvailable();
  const path = `/api/products/deck-aistack-codes/decks/${deckId}/processing`;
  try {
    return await fetchApiJsonOrThrow<DeckProcessingVisibility>(path, { method: 'GET' }, 'Could not load processing status.');
  } catch {
    return null;
  }
}

export function isProcessingRecoverable(state: DeckProcessingVisibility | null): boolean {
  if (!state) return false;
  const processingStatus = state.processing?.status;
  return Boolean(
    state.upload?.sourceSaved ||
    processingStatus === 'queued' ||
    processingStatus === 'running' ||
    processingStatus === 'processing' ||
    state.nextAction === 'open_smart_deck' ||
    processingStatus === 'completed' ||
    processingStatus === 'ready' ||
    state.deckStatus === 'ready'
  );
}
