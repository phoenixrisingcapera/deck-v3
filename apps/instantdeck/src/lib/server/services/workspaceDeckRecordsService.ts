import { inferDeckFileType, type WorkspaceDeckRecord } from '$lib/components/deckService/upload/uploaded-decks-list.types';
import type { DeckFileType } from '$lib/contracts/types';

export function normalizeWorkspaceDeckRecord(payload: Record<string, unknown>): WorkspaceDeckRecord {
  const workflowPayload = payload.workflow && typeof payload.workflow === 'object'
    ? (payload.workflow as Record<string, unknown>)
    : null;
  const originalFilename = String(
    payload.originalFilename ??
      payload.original_filename ??
      payload.filename ??
      payload.title ??
      payload.displayName ??
      'Uploaded deck'
  );

  const mimeType = String(payload.mimeType ?? payload.mime_type ?? 'application/octet-stream');
  const filePayload = payload.file && typeof payload.file === 'object' ? (payload.file as { size?: unknown }) : null;
  const fileType: DeckFileType =
    typeof payload.fileType === 'string' && payload.fileType
      ? (payload.fileType as DeckFileType)
      : inferDeckFileType(originalFilename);

  return {
    id: String(payload.id ?? ''),
    workspaceId: String(payload.workspaceId ?? payload.workspace_id ?? 'ws_default'),
    displayName: String(payload.displayName ?? payload.display_name ?? payload.title ?? originalFilename),
    originalFilename,
    fileType,
    mimeType,
    fileSizeBytes:
      typeof payload.fileSizeBytes === 'number'
        ? payload.fileSizeBytes
        : typeof payload.file_size_bytes === 'number'
          ? payload.file_size_bytes
          : typeof filePayload?.size === 'number'
            ? filePayload.size
            : null,
    status: String(payload.status ?? 'uploaded'),
    thumbnailUrl:
      typeof payload.thumbnailUrl === 'string'
        ? payload.thumbnailUrl
        : typeof payload.thumbnail_url === 'string'
          ? payload.thumbnail_url
          : null,
    hasSourceFile:
      typeof payload.hasSourceFile === 'boolean'
        ? payload.hasSourceFile
        : typeof payload.has_source_file === 'boolean'
          ? payload.has_source_file
          : typeof workflowPayload?.hasSourceFile === 'boolean'
            ? workflowPayload.hasSourceFile
            : typeof workflowPayload?.has_source_file === 'boolean'
              ? workflowPayload.has_source_file
              : null,
    workflowId:
      typeof payload.workflowId === 'string'
        ? payload.workflowId
        : typeof payload.workflow_id === 'string'
          ? payload.workflow_id
          : typeof workflowPayload?.id === 'string'
            ? workflowPayload.id
            : typeof workflowPayload?.workflowId === 'string'
              ? workflowPayload.workflowId
              : typeof workflowPayload?.workflow_id === 'string'
                ? workflowPayload.workflow_id
                : null,
    workflowStatus:
      typeof payload.workflowStatus === 'string'
        ? payload.workflowStatus
        : typeof payload.workflow_status === 'string'
          ? payload.workflow_status
          : typeof workflowPayload?.status === 'string'
            ? workflowPayload.status
            : typeof workflowPayload?.workflowStatus === 'string'
              ? workflowPayload.workflowStatus
              : typeof workflowPayload?.workflow_status === 'string'
                ? workflowPayload.workflow_status
                : typeof workflowPayload?.lifecycleStatus === 'string'
                  ? workflowPayload.lifecycleStatus
                  : null,
    workflowUpdatedAt:
      typeof payload.workflowUpdatedAt === 'string'
        ? payload.workflowUpdatedAt
        : typeof payload.workflow_updated_at === 'string'
          ? payload.workflow_updated_at
          : typeof payload.progressUpdatedAt === 'string'
            ? payload.progressUpdatedAt
            : typeof payload.progress_updated_at === 'string'
              ? payload.progress_updated_at
              : typeof workflowPayload?.updatedAt === 'string'
                ? workflowPayload.updatedAt
                : typeof workflowPayload?.updated_at === 'string'
                  ? workflowPayload.updated_at
                  : typeof workflowPayload?.heartbeatAt === 'string'
                    ? workflowPayload.heartbeatAt
                    : typeof workflowPayload?.heartbeat_at === 'string'
                      ? workflowPayload.heartbeat_at
                      : null,
    activeStage:
      typeof payload.activeStage === 'string'
        ? payload.activeStage
        : typeof payload.active_stage === 'string'
          ? payload.active_stage
          : typeof workflowPayload?.activeStage === 'string'
            ? workflowPayload.activeStage
            : typeof workflowPayload?.active_stage === 'string'
              ? workflowPayload.active_stage
              : typeof workflowPayload?.processingStage === 'string'
                ? workflowPayload.processingStage
                : typeof workflowPayload?.processing_stage === 'string'
                  ? workflowPayload.processing_stage
                  : null,
    createdAt: String(payload.createdAt ?? payload.created_at ?? new Date().toISOString()),
    updatedAt: String(payload.updatedAt ?? payload.updated_at ?? new Date().toISOString())
  };
}
