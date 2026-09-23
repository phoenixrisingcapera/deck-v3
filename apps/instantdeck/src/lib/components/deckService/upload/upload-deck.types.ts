/** Purpose: types and view-model helpers for deck upload widget states and labels. */
import type { SaveConfirmationBannerModel } from '$lib/contracts/types';

export interface UploadedDocumentViewModel {
  name: string;
  sizeLabel: string;
  statusLabel: string;
  statusTone: 'success' | 'info' | 'warning' | 'danger';
  fileKindLabel: string;
}

export type DeckUploadStatus = 'idle' | 'uploading' | 'saved' | 'failed';

export type UploadDeckWidgetState =
  | 'idle'
  | 'drag_active'
  | 'selected'
  | 'uploading'
  | 'uploaded'
  | 'processing'
  | 'ready'
  | 'failed';

export interface UploadDeckWidgetViewModel {
  state: UploadDeckWidgetState;
  title: string;
  supportCopy: string;
  instruction: string;
  acceptedFormatsLabel: string;
  browseLabel: string;
  showUploadedDocument: boolean;
  uploadedDocument: UploadedDocumentViewModel | null;
  confirmation: SaveConfirmationBannerModel | null;
  helperLabel: string;
  helperHrefLabel: string;
  helperHref: string;
  primaryActionLabel: string | null;
  primaryActionEnabled: boolean;
}

// Build the full upload-widget UI model from transport + form state.
export function buildUploadDeckWidgetViewModel(input: {
  deckFile: File | null;
  deckDragActive: boolean;
  deckUploadStatus: DeckUploadStatus;
  deckExtractionStatus: 'idle' | 'queued' | 'processing' | 'ready' | 'failed';
  uploadError: string;
  saveConfirmation: SaveConfirmationBannerModel | null;
  canContinueAfterUpload: boolean;
  buttonLabel: string;
  maxFileLabel: string;
  formatFileSize: (size: number) => string;
}): UploadDeckWidgetViewModel {
  // Convert raw upload/extraction signals into a single list-row status token.
  function resolveWidgetState(localInput: {
    deckFile: File | null;
    deckDragActive: boolean;
    deckUploadStatus: DeckUploadStatus;
    deckExtractionStatus: 'idle' | 'queued' | 'processing' | 'ready' | 'failed';
    uploadError: string;
  }): UploadDeckWidgetState {
    if (localInput.deckUploadStatus === 'failed' || localInput.uploadError) return 'failed';
    if (localInput.deckDragActive && !localInput.deckFile) return 'drag_active';
    if (localInput.deckUploadStatus === 'uploading') return 'uploading';
    if (localInput.deckUploadStatus === 'saved' && localInput.deckExtractionStatus === 'ready') return 'ready';
    if (localInput.deckUploadStatus === 'saved' && localInput.deckExtractionStatus === 'processing') return 'processing';
    if (localInput.deckUploadStatus === 'saved' && localInput.deckExtractionStatus === 'queued') return 'uploaded';
    if (localInput.deckUploadStatus === 'saved' && localInput.deckExtractionStatus === 'failed') return 'uploaded';
    if (localInput.deckFile) return 'selected';
    return 'idle';
  }

  // Human label used for upload row status badges.
  function resolveRowStatusLabel(state: UploadDeckWidgetState): string {
    if (state === 'ready' || state === 'uploaded') return 'Uploaded';
    if (state === 'processing') return 'Processing';
    if (state === 'uploading' || state === 'selected') return 'Saving';
    if (state === 'failed') return 'Failed';
    return 'Selected';
  }

  // Pick visual tone bucket that matches row status semantics.
  function resolveRowStatusTone(state: UploadDeckWidgetState): UploadedDocumentViewModel['statusTone'] {
    if (state === 'failed') return 'danger';
    if (state === 'processing' || state === 'uploading' || state === 'selected') return 'info';
    return 'success';
  }

  // Translate file extension into compact type token shown in upload rows.
  function resolveFileKindLabel(fileName: string): string {
    const extension = fileName.split('.').pop()?.toUpperCase();
    if (extension === 'PPT' || extension === 'PPTX') return 'PPT';
    if (extension === 'PDF') return 'PDF';
    if (extension === 'KEY') return 'KEY';
    return 'FILE';
  }

  // Resolve the confirmation banner for failed/uploaded/processing states with explicit copy.
  function resolveConfirmation(
    state: UploadDeckWidgetState,
    confirmation: SaveConfirmationBannerModel | null,
    uploadError: string
  ): SaveConfirmationBannerModel | null {
    if (confirmation) return confirmation;
    if (state === 'failed') {
      return {
        title: 'Deck save failed',
        message: uploadError || 'Try the upload again or choose a different source file.',
        tone: 'danger'
      };
    }
    if (state === 'processing') {
      return {
        title: 'Deck uploaded',
        message: 'The backend worker pipeline will continue processing from workflow-state.',
        tone: 'info'
      };
    }
    if (state === 'uploaded') {
      return {
        title: 'Deck uploaded',
        message: 'Your deck is saved. The backend worker pipeline will continue from workflow-state.',
        tone: 'success'
      };
    }
    return null;
  }

  const state = resolveWidgetState(input);
  const uploadedDocument = input.deckFile
    ? {
        name: input.deckFile.name,
        sizeLabel: input.formatFileSize(input.deckFile.size),
        statusLabel: resolveRowStatusLabel(state),
        statusTone: resolveRowStatusTone(state),
        fileKindLabel: resolveFileKindLabel(input.deckFile.name)
      }
    : null;

  return {
    state,
    title: 'Drop your deck',
    supportCopy: 'PDF or PowerPoint. AI analysis starts automatically.',
    instruction: state === 'drag_active' ? 'Drop your file here' : 'Drag and drop your file here',
    acceptedFormatsLabel: input.maxFileLabel,
    browseLabel: 'browse files',
    showUploadedDocument: Boolean(uploadedDocument),
    uploadedDocument,
    confirmation: resolveConfirmation(state, input.saveConfirmation, input.uploadError),
    helperLabel: state === 'uploaded' ? 'Saved.' : '',
    helperHrefLabel: '',
    helperHref: '#',
    primaryActionLabel: input.canContinueAfterUpload ? input.buttonLabel : null,
    primaryActionEnabled: input.canContinueAfterUpload
  };
}
