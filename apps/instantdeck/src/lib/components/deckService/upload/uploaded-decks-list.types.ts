/** Purpose: maps backend deck status payloads to uploaded deck list models and helper conversion functions. */
import type { Deck } from '$types/domain';
import type { DeckFileType } from '$lib/contracts/types';

export type UploadedDeckListStatus = 'uploaded' | 'processing' | 'failed' | 'selected';

export interface WorkspaceDeckRecord {
  id: string;
  workspaceId: string;
  displayName: string;
  originalFilename: string;
  fileType: DeckFileType;
  mimeType: string;
  fileSizeBytes: number | null;
  status: string;
  thumbnailUrl?: string | null;
  hasSourceFile?: boolean | null;
  workflowId?: string | null;
  workflowStatus?: string | null;
  workflowUpdatedAt?: string | null;
  activeStage?: string | null;
  createdAt: string;
  updatedAt: string;
}

interface UploadedDeck {
  id: string;
  name: string;
  fileType: DeckFileType;
  fileSizeBytes?: number | null;
  fileSizeLabel?: string | null;
  uploadedAt?: string | null;
  uploadedAtLabel?: string | null;
  status: UploadedDeckListStatus;
  thumbnailUrl?: string | null;
  hasSourceFile?: boolean | null;
  workflowId?: string | null;
  workflowStatus?: string | null;
  workflowUpdatedAt?: string | null;
  activeStage?: string | null;
}

export interface UploadedDeckListItem extends UploadedDeck {
  fileKindLabel?: string;
}

const ACTIVE_WORKFLOW_STATUSES = new Set(['queued', 'accepted', 'starting', 'processing', 'running']);

export function hasActiveWorkflowStatus(status: string | null | undefined): boolean {
  const normalized = status?.trim().toLowerCase() ?? '';
  return ACTIVE_WORKFLOW_STATUSES.has(normalized);
}

// Convert backend workflow status text into normalized list status used by deck row UI.
export function mapDeckStatusToListStatus(
  status: string,
  options: { hasActiveWorkflow?: boolean } = {}
): UploadedDeckListStatus {
  // Normalize backend workflow status values into UI list status tokens.
  const normalized = status.trim().toLowerCase();
  if (normalized === 'failed' || normalized === 'error' || normalized === 'dead_letter') return 'failed';
  if (normalized === 'selected') return 'selected';
  if (normalized === 'uploaded') {
    return options.hasActiveWorkflow ? 'processing' : 'uploaded';
  }
  if (
    normalized === 'queued' ||
    normalized === 'parsing' ||
    normalized === 'structuring' ||
    normalized === 'extracting_blocks' ||
    normalized === 'classifying_blocks' ||
    normalized === 'analysing' ||
    normalized === 'adapting' ||
    normalized === 'processing' ||
    normalized === 'running'
  ) {
    return 'processing';
  }

  return 'uploaded';
}

// Map a persisted Deck model into an uploaded-list row shape.
export function mapDeckToUploadedDeck(
  deck: Deck,
  options: {
    formatFileSize: (size: number) => string;
    formatRelativeUploadDate: (value: string | null | undefined) => string | null;
  }
): UploadedDeckListItem {
  const fileName = deck.file?.filename || `${deck.title}.deck`;

  return {
    id: deck.id,
    name: fileName,
    fileType: inferDeckFileType(fileName),
    fileSizeBytes: typeof deck.file?.size === 'number' ? deck.file.size : null,
    fileKindLabel: inferDeckFileKindLabel(fileName),
    fileSizeLabel: typeof deck.file?.size === 'number' ? options.formatFileSize(deck.file.size) : null,
    uploadedAt: deck.file?.uploadedAt ?? deck.updatedAt,
    uploadedAtLabel: options.formatRelativeUploadDate(deck.file?.uploadedAt ?? deck.updatedAt),
    status: mapDeckStatusToListStatus(deck.status)
  };
}

// Map workspace deck records (worker payload) into list-item DTO for upload UX.
export function mapWorkspaceDeckRecordToListItem(
  deck: WorkspaceDeckRecord,
  options: {
    formatDeckFileSize: (size: number | null | undefined) => string | null;
    formatDeckUploadDate: (value: string | null | undefined) => string | null;
    selectedDeckId?: string | null;
  }
): UploadedDeckListItem {
  const fileName = deck.originalFilename || deck.displayName || `${deck.id}.deck`;
  const hasActiveWorkflow = Boolean(deck.workflowId && hasActiveWorkflowStatus(deck.workflowStatus));
  const status = options.selectedDeckId && options.selectedDeckId === deck.id
    ? 'selected'
    : mapDeckStatusToListStatus(deck.status, { hasActiveWorkflow });

  return {
    id: deck.id,
    name: fileName,
    fileType: deck.fileType || inferDeckFileType(fileName),
    fileSizeBytes: deck.fileSizeBytes,
    fileKindLabel: inferDeckFileKindLabel(fileName),
    fileSizeLabel: options.formatDeckFileSize(deck.fileSizeBytes),
    uploadedAt: deck.updatedAt,
    uploadedAtLabel: options.formatDeckUploadDate(deck.updatedAt),
    status,
    thumbnailUrl: deck.thumbnailUrl ?? null,
    hasSourceFile: deck.hasSourceFile ?? null,
    workflowId: deck.workflowId ?? null,
    workflowStatus: deck.workflowStatus ?? null,
    workflowUpdatedAt: deck.workflowUpdatedAt ?? null,
    activeStage: deck.activeStage ?? null
  };
}

// Map filename extensions to deck file type constants for iconing and labels.
export function inferDeckFileType(name: string): DeckFileType {
  // Map filename extensions to deck file type constants for iconing and labels.
  const extension = name.split('.').pop()?.toLowerCase();
  if (extension === 'ppt') return 'ppt';
  if (extension === 'pptx') return 'pptx';
  if (extension === 'pdf') return 'pdf';
  if (extension === 'key') return 'key';
  return 'other';
}

// Convert deck file type into compact badge text in the list.
export function inferDeckFileKindLabel(name: string): string {
  // Convert deck file type into compact badge text in the list.
  const fileType = inferDeckFileType(name);
  if (fileType === 'ppt' || fileType === 'pptx') return 'PPT';
  if (fileType === 'pdf') return 'PDF';
  if (fileType === 'key') return 'KEY';
  return 'FILE';
}
