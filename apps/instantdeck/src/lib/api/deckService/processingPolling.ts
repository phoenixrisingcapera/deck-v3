import type {
  SmartDeckProcessingStatusWithDiagnostics,
  WorkflowJobSummary
} from './workflow.client';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'accepted', 'starting', 'processing']);
const DIRECT_FAILURE_STATUSES = new Set(['failed', 'failed_retryable', 'failed_final', 'timed_out']);
const BLOCKED_JOB_STATUSES = new Set(['blocked']);
const INSTANT_JOB_TYPES = new Set(['instant_deck_generation', 'schema_validation', 'preview_render', 'db_publisher']);
const STAGE_TYPES = ['instant_deck_generation', 'schema_validation', 'preview_render', 'db_publisher'];
const RETRY_PREVIOUS_IDENTITY = Symbol('processing-retry-previous-identity');

type RetryPendingStatus = SmartDeckProcessingStatusWithDiagnostics & {
  [RETRY_PREVIOUS_IDENTITY]?: string;
};

export function isProcessingAuthFailure(error: unknown): boolean {
  const status = error && typeof error === 'object' && typeof (error as { status?: unknown }).status === 'number'
    ? (error as { status: number }).status
    : null;
  if (status === 401 || status === 403) return true;
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /authentication|required|sign.?in|session.*expired|missing.*token|invalid.*token|revoked/i.test(message);
}

export function createProcessingResponseError(
  response: { status: number },
  payload: unknown,
  fallbackMessage: string
): Error & { status: number } {
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : null;
  const errorRecord = record?.error && typeof record.error === 'object' && !Array.isArray(record.error)
    ? record.error as Record<string, unknown>
    : null;
  const detailRecord = record?.detail && typeof record.detail === 'object' && !Array.isArray(record.detail)
    ? record.detail as Record<string, unknown>
    : null;
  const message = [errorRecord?.message, record?.message, record?.detail, detailRecord?.message]
    .find((value): value is string => typeof value === 'string' && value.trim().length > 0)?.trim() || fallbackMessage;
  const error = new Error(message) as Error & { status: number };
  error.status = response.status;
  return error;
}

export function isBackendUnavailableDiagnostic(
  status: SmartDeckProcessingStatusWithDiagnostics | null
): boolean {
  return Boolean(
    status?.blockingReason === 'backend_unavailable' ||
      (typeof status?.backendStatus === 'number' && status.backendStatus >= 500)
  );
}

function jobStatus(job: WorkflowJobSummary | null | undefined): string {
  return String(job?.status ?? '').toLowerCase();
}

function uniqueJobs(status: SmartDeckProcessingStatusWithDiagnostics): WorkflowJobSummary[] {
  const jobs = [status.activeJob, status.failedJob, ...(status.latestJobs ?? [])];
  const byId = new Map<string, WorkflowJobSummary>();
  for (const job of jobs) if (job?.jobId) byId.set(job.jobId, job);
  return [...byId.values()];
}

function canonicalInstantChain(status: SmartDeckProcessingStatusWithDiagnostics): WorkflowJobSummary[] | null {
  const chain = status.authoritativeInstantChain;
  if (!chain || !status.workflowId || chain.workflowId !== status.workflowId) return null;
  if (chain.rootJobId !== chain.generationJobId || !chain.chainJobIds.includes(chain.generationJobId)) return null;

  const jobsById = new Map(uniqueJobs(status).map((job) => [job.jobId, job]));
  const chainJobs = chain.chainJobIds.map((id) => jobsById.get(id));
  if (chainJobs.some((job) => !job)) return null;
  const jobs = chainJobs as WorkflowJobSummary[];
  if (jobs.some((job) => !INSTANT_JOB_TYPES.has(job.jobType) || (job.workflowId && job.workflowId !== chain.workflowId))) return null;

  const generation = jobsById.get(chain.generationJobId);
  if (!generation || generation.jobType !== 'instant_deck_generation') return null;
  const declaredStages = [
    ['schema_validation', chain.schemaValidationJobId],
    ['preview_render', chain.previewRenderJobId],
    ['db_publisher', chain.publisherJobId]
  ] as const;
  let priorId = generation.jobId;
  for (const [expectedType, id] of declaredStages) {
    if (!id) continue;
    const job = jobsById.get(id);
    if (!job || job.jobType !== expectedType || !chain.chainJobIds.includes(id)) return null;
    if (job.generationJobId && job.generationJobId !== generation.jobId) return null;
    if (job.rootJobId && job.rootJobId !== generation.jobId) return null;
    if (job.parentJobId && job.parentJobId !== priorId) return null;
    if (job.dependencyJobIds?.length && !job.dependencyJobIds.includes(priorId)) return null;
    priorId = id;
  }
  return jobs.sort((left, right) => STAGE_TYPES.indexOf(left.jobType) - STAGE_TYPES.indexOf(right.jobType));
}

function jobErrorMessage(job: WorkflowJobSummary | null): string | undefined {
  for (const value of [job?.error?.message, job?.terminalReason]) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return undefined;
}

export function reconcileAuthoritativeProcessingStatus(
  status: SmartDeckProcessingStatusWithDiagnostics
): SmartDeckProcessingStatusWithDiagnostics {
  if (isBackendUnavailableDiagnostic(status)) return status;
  const jobs = canonicalInstantChain(status);
  if (!jobs) return status;
  const failure = jobs.find((job) => DIRECT_FAILURE_STATUSES.has(jobStatus(job))) ??
    jobs.find((job) => BLOCKED_JOB_STATUSES.has(jobStatus(job))) ?? null;
  const active = failure ? null : jobs.find((job) => ACTIVE_JOB_STATUSES.has(jobStatus(job))) ?? null;

  if (active) {
    return {
      ...status,
      authoritativeInstantChainActive: true,
      status: 'processing',
      nextAction: 'view_processing',
      activeStage: active.phase || active.jobType,
      canOpenInstantDeck: false,
      canRetry: false,
      message: undefined,
      errorMessage: undefined
    };
  }
  if (!failure) return { ...status, authoritativeInstantChainActive: false };

  const retryable = jobStatus(failure) === 'failed_retryable' || failure.retryEligible === true;
  const message = jobErrorMessage(failure);
  return {
    ...status,
    authoritativeInstantChainActive: false,
    status: 'failed',
    nextAction: retryable ? 'retry_job' : 'manual_review',
    activeStage: failure.phase || failure.jobType,
    canOpenInstantDeck: false,
    canRetry: retryable,
    message: message ?? status.message,
    errorMessage: message ?? status.errorMessage
  };
}

function snapshotIdentity(status: SmartDeckProcessingStatusWithDiagnostics): string {
  const summarize = (job: WorkflowJobSummary | null | undefined) => job ? {
    jobId: job.jobId,
    status: job.status,
    attemptCount: job.attemptCount ?? null,
    recoveryCount: job.recoveryCount ?? null,
    progress: job.progress ?? null
  } : null;
  return JSON.stringify({
    status: status.status,
    deckExtractionStatus: status.deckExtractionStatus,
    nextAction: status.nextAction ?? null,
    canOpenSmartDeck: status.canOpenSmartDeck,
    canOpenInstantDeck: status.canOpenInstantDeck,
    canRetry: status.canRetry,
    chain: status.authoritativeInstantChain ?? null,
    activeJob: summarize(status.activeJob),
    failedJob: summarize(status.failedJob),
    jobs: uniqueJobs(status).sort((left, right) => left.jobId.localeCompare(right.jobId)).map(summarize)
  });
}

function rootCounters(status: SmartDeckProcessingStatusWithDiagnostics): [number, number] {
  const rootId = status.authoritativeInstantChain?.generationJobId;
  const root = rootId ? uniqueJobs(status).find((job) => job.jobId === rootId) : null;
  return [Number(root?.attemptCount ?? 0), Number(root?.recoveryCount ?? 0)];
}

function hasNewerCounters(previous: SmartDeckProcessingStatusWithDiagnostics, incoming: SmartDeckProcessingStatusWithDiagnostics): boolean {
  const [previousAttempt, previousRecovery] = rootCounters(previous);
  const [incomingAttempt, incomingRecovery] = rootCounters(incoming);
  return incomingAttempt > previousAttempt || incomingRecovery > previousRecovery;
}

function terminalInstant(status: SmartDeckProcessingStatusWithDiagnostics): boolean {
  return status.canOpenInstantDeck || (!status.authoritativeInstantChainActive &&
    (status.status === 'failed' || status.nextAction === 'manual_review' || status.nextAction === 'retry_job'));
}

export function mergeProcessingSnapshot(
  previous: SmartDeckProcessingStatusWithDiagnostics | null,
  incoming: SmartDeckProcessingStatusWithDiagnostics
): SmartDeckProcessingStatusWithDiagnostics {
  if (!previous) return incoming;
  const retryIdentity = (previous as RetryPendingStatus)[RETRY_PREVIOUS_IDENTITY];
  if (isBackendUnavailableDiagnostic(incoming)) {
    const preserved = {
      ...previous,
      blockingReason: 'backend_unavailable',
      backendStatus: incoming.backendStatus,
      backendStatusText: incoming.backendStatusText,
      backendMessage: incoming.backendMessage ?? incoming.errorMessage ?? incoming.message,
      backendPath: incoming.backendPath,
      backendPayload: incoming.backendPayload,
      requestId: incoming.requestId,
      ticketId: incoming.ticketId
    };
    if (retryIdentity) {
      Object.defineProperty(preserved, RETRY_PREVIOUS_IDENTITY, {
        value: retryIdentity,
        enumerable: false
      });
    }
    return preserved;
  }

  if (retryIdentity && snapshotIdentity(incoming) === retryIdentity) return previous;

  const previousRoot = previous.authoritativeInstantChain?.generationJobId;
  const incomingRoot = incoming.authoritativeInstantChain?.generationJobId;
  if (previousRoot && incomingRoot && previousRoot !== incomingRoot) return incoming;
  if (previousRoot && !incomingRoot) return previous;
  if (previousRoot === incomingRoot && terminalInstant(previous)) {
    if (hasNewerCounters(previous, incoming)) return incoming;
    if (incoming.authoritativeInstantChainActive || terminalInstant(incoming)) return previous;
  }
  return incoming;
}

export function beginProcessingRetry(
  previous: SmartDeckProcessingStatusWithDiagnostics
): SmartDeckProcessingStatusWithDiagnostics {
  const next = {
    ...previous,
    status: 'processing' as const,
    deckExtractionStatus: 'processing' as const,
    nextAction: 'view_processing' as const,
    blockingReason: null,
    canRetry: false,
    message: undefined,
    errorMessage: undefined,
    activeJob: null,
    failedJob: null,
    latestJobs: []
  } as RetryPendingStatus;
  Object.defineProperty(next, RETRY_PREVIOUS_IDENTITY, {
    value: snapshotIdentity(previous),
    enumerable: false
  });
  return next;
}

function hasActiveProcessingJob(status: SmartDeckProcessingStatusWithDiagnostics, instantMode: boolean): boolean {
  if (!instantMode) return uniqueJobs(status).some((job) => ACTIVE_JOB_STATUSES.has(jobStatus(job)));
  if (status.authoritativeInstantChainActive === true) return true;
  if (status.authoritativeInstantChain) return false;
  return Boolean(status.activeJob && INSTANT_JOB_TYPES.has(status.activeJob.jobType) && ACTIVE_JOB_STATUSES.has(jobStatus(status.activeJob)));
}

export function isTerminalProcessingOutcome(
  status: SmartDeckProcessingStatusWithDiagnostics | null,
  context: { instantMode: boolean }
): boolean {
  if (!status || isBackendUnavailableDiagnostic(status)) return false;
  if (hasActiveProcessingJob(status, context.instantMode)) return false;
  const canOpenDeck = context.instantMode ? status.canOpenInstantDeck : status.canOpenSmartDeck;
  if (canOpenDeck || status.canRetry) return true;
  if (status.nextAction === 'retry_job' || status.nextAction === 'manual_review') return true;
  if (status.nextAction === 'open_smart_deck' && status.canOpenSmartDeck) return true;
  if (status.status === 'failed' || status.deckExtractionStatus === 'failed') return true;
  return status.status === 'ready' && !hasActiveProcessingJob(status, context.instantMode);
}

export function shouldContinueProcessingPoll(
  status: SmartDeckProcessingStatusWithDiagnostics | null,
  context: { authExpired: boolean; instantMode: boolean }
): boolean {
  if (context.authExpired) return false;
  if (!status || isBackendUnavailableDiagnostic(status)) return true;
  return !isTerminalProcessingOutcome(status, context);
}
