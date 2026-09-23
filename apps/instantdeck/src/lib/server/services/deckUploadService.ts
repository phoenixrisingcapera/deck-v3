import { error } from '@sveltejs/kit';
import { createUploadRequestId } from '$lib/api/uploadRequestIdentity';
import { BACKEND_URL } from '$server/backendApi';
import { BACKEND_URL_ENV_NAME } from '$server/backendUrl';

export const SUPPORTED_DECK_EXTENSIONS = ['.pdf', '.ppt', '.pptx'] as const;
export const SUPPORTED_DECK_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'
]);
export const SUPPORTED_LOGO_EXTENSIONS = ['.gif', '.jpg', '.jpeg', '.png', '.webp'] as const;
export const SUPPORTED_LOGO_MIME_TYPES = new Set(['image/gif', 'image/jpeg', 'image/png', 'image/webp']);
export const SUPPORTED_BRAND_GUIDE_EXTENSIONS = ['.doc', '.docx', '.md', '.pdf', '.txt'] as const;
export const SUPPORTED_BRAND_GUIDE_MIME_TYPES = new Set([
  'application/msword',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/markdown',
  'text/plain'
]);

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

export function isSupportedDeckUpload(file: File) {
  const lowerCaseName = file.name.toLowerCase();
  return SUPPORTED_DECK_MIME_TYPES.has(file.type) || SUPPORTED_DECK_EXTENSIONS.some((extension) => lowerCaseName.endsWith(extension));
}

export function isSupportedUpload(file: File, extensions: readonly string[], mimeTypes: Set<string>) {
  const lowerCaseName = file.name.toLowerCase();
  return mimeTypes.has(file.type) || extensions.some((extension) => lowerCaseName.endsWith(extension));
}

export function firstString(form: FormData, ...keys: string[]) {
  for (const key of keys) {
    const value = form.get(key);
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }

  return '';
}

export function stringList(form: FormData, ...keys: string[]) {
  return keys.flatMap((key) => form.getAll(key)).filter((value): value is string => typeof value === 'string' && value.trim().length > 0);
}

export function firstFile(form: FormData, ...keys: string[]) {
  for (const key of keys) {
    const value = form.get(key);
    if (value instanceof File && value.size > 0) {
      return value;
    }
  }

  return null;
}

export function firstPayloadValue(payload: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }

  return undefined;
}

export function textOrNull(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

export function detailRecord(payload: unknown): Record<string, unknown> | null {
  const record = asRecord(payload);
  if (!record) return null;
  return asRecord(record.detail) ?? record;
}

export function responseHeaders(requestId?: string | null) {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (requestId) {
    headers['x-request-id'] = requestId;
  }
  return headers;
}

export function uploadContext(file: File, failureCategory: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    failureCategory,
    backendUrlConfigured: Boolean(BACKEND_URL),
    fileExtension: file.name.split('.').pop()?.toLowerCase() ?? '',
    mimeType: file.type || 'application/octet-stream',
    size: file.size,
    ...extra
  };
}

export function normalizeUploadFailure(
  payload: unknown,
  status: number,
  fallbackMessage: string,
  responseRequestId?: string | null
): Record<string, unknown> {
  const detail = detailRecord(payload);
  const safeDetail = detail ?? {};
  const requestId =
    textOrNull(firstPayloadValue(safeDetail, 'requestId', 'request_id')) ??
    textOrNull(responseRequestId) ??
    null;
  const failureCategory =
    textOrNull(firstPayloadValue(safeDetail, 'failureCategory', 'failure_category')) ??
    'backend_upload_response_error';

  return {
    ok: false,
    // Never relay arbitrary backend/provider exception text through the public
    // proxy. Category and neutral correlation IDs are sufficient for support.
    message: fallbackMessage,
    status,
    requestId,
    failureCategory,
    ticketId: firstPayloadValue(safeDetail, 'ticketId', 'ticket_id') ?? null,
    errorName: null,
    recoverable: firstPayloadValue(safeDetail, 'recoverable') === true,
    uploadReadiness: null,
    missingRequiredChecks: null,
    warningChecks: null,
    acceptedVariableGroups: null,
    detail: null
  };
}

export function normalizeUpload(payload: Record<string, unknown>) {
  return {
    deckId: payload.deckId ?? payload.deck_id,
    deckStatus: firstPayloadValue(payload, 'deckStatus', 'deck_status', 'status') ?? null,
    deckExtractionStatus: String(
      firstPayloadValue(payload, 'deck_extraction_status', 'deckExtractionStatus', 'state', 'status') ?? 'uploaded'
    ),
    sourcePersistenceState: firstPayloadValue(payload, 'sourcePersistenceState', 'source_persistence_state', 'sourceFileStatus', 'source_file_status') ?? null,
    queueState: firstPayloadValue(payload, 'queueState', 'queue_state', 'workflowState', 'workflow_state') ?? null,
    queueError: textOrNull(firstPayloadValue(payload, 'queueError', 'queue_error')),
    queueFailureTicketId: textOrNull(firstPayloadValue(payload, 'queueFailureTicketId', 'queue_failure_ticket_id')),
    requestId: firstPayloadValue(payload, 'requestId', 'request_id') ?? null,
    failureTicketId: firstPayloadValue(payload, 'failureTicketId', 'failure_ticket_id', 'ticketId', 'ticket_id') ?? null,
    uploadReadiness: firstPayloadValue(payload, 'uploadReadiness', 'upload_readiness') ?? null,
    storageWarning: firstPayloadValue(payload, 'storageWarning', 'storage_warning') ?? null,
    nextAction: firstPayloadValue(payload, 'nextAction', 'next_action') ?? null,
    processingStatusUrl: firstPayloadValue(payload, 'processingStatusUrl', 'processing_status_url') ?? null,
    smartDeckUrl: firstPayloadValue(payload, 'smartDeckUrl', 'smart_deck_url') ?? null,
    preferredWorkspace: firstPayloadValue(payload, 'preferredWorkspace', 'preferred_workspace') ?? null,
    preferredWorkspaceUrl: firstPayloadValue(payload, 'preferredWorkspaceUrl', 'preferred_workspace_url') ?? null,
    processing: firstPayloadValue(payload, 'processing') ?? null,
    confirmation: payload.confirmation ?? null
  };
}

export function requireBackend() {
  const backendUrl = (BACKEND_URL ?? '').trim().replace(/\/$/, '');
  if (!backendUrl) {
    throw error(503, `Backend URL is required for persisted deck uploads. Set ${BACKEND_URL_ENV_NAME}.`);
  }
  return backendUrl;
}

export function resolveRequestId(
  request: Request,
  options: { ensureUploadRequestId?: boolean } = {}
): string | null {
  const requestId = request.headers.get('x-request-id')?.trim();
  if (requestId) {
    return requestId;
  }
  if (options.ensureUploadRequestId) {
    return createUploadRequestId();
  }
  return null;
}

export function withRequestId(request: Request, headers: HeadersInit = {}, requestId: string | null = null) {
  const effectiveRequestId = requestId ?? request.headers.get('x-request-id')?.trim() ?? null;
  if (!effectiveRequestId) {
    return headers;
  }

  return {
    ...headers,
    'x-request-id': effectiveRequestId
  };
}
