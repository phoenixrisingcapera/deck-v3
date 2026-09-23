<script lang="ts">
  import { goto } from '$app/navigation';
  import type { ApiErrorBannerModel } from '$lib/api/apiError';
  import type { DeckExtractionStatus } from '$lib/api/deckService/workflow.client';
  import UploadDeckWidget from '$lib/components/deckService/upload/UploadDeckWidget.svelte';
  import {
    buildUploadDeckWidgetViewModel,
    type DeckUploadStatus
  } from '$lib/components/deckService/upload/upload-deck.types';
  import type { UploadedDeckListItem } from '$lib/components/deckService/upload/uploaded-decks-list.types';
  import type { SaveConfirmationBannerModel } from '$lib/contracts/types';

  /*
    UploadDeck is intentionally a UI boundary component.

    It does not upload files itself and it does not decide Smart Deck readiness.
    Parent route handlers own upload/retry/remove backend calls, while this
    component turns validated upload state into a single handoff action.
  */

  type Props = {
    eyebrow?: string;
    accept: string;
    deckId?: string;
    deckFile: File | null;
    deckDragActive: boolean;
    deckUploadStatus: DeckUploadStatus;
    deckExtractionStatus: DeckExtractionStatus;
    uploadError: string;
    saveConfirmation?: SaveConfirmationBannerModel | null;
    canContinueAfterUpload: boolean;
    buttonLabel?: string;
    maxFileLabel?: string;
    workspaceDecks?: UploadedDeckListItem[];
    workspaceDecksLoading?: boolean;
    workspaceDecksError?: string | null;
    workspaceDecksErrorBanner?: ApiErrorBannerModel | null;
    onDeckSelection: (event: Event) => void | Promise<void>;
    onDeckDragEnter: (event: DragEvent) => void;
    onDeckDragLeave: (event: DragEvent) => void;
    onDeckDrop: (event: DragEvent) => void | Promise<void>;
    onSelectDeck?: (deck: UploadedDeckListItem) => void;
    onRetryDeck?: (deckId: string) => void | Promise<void>;
    onRemoveDeck?: (deckId: string) => void | Promise<void>;
    onContinue: () => void;
    formatFileSize: (size: number) => string;
  };

  let {
    eyebrow = 'Upload',
    accept,
    deckId = '',
    deckFile,
    deckDragActive,
    deckUploadStatus,
    deckExtractionStatus,
    uploadError,
    saveConfirmation = null,
    canContinueAfterUpload,
    buttonLabel = 'Continue',
    maxFileLabel = 'PDF, PPT, PPTX • Max 200MB',
    workspaceDecks = [],
    workspaceDecksLoading = false,
    workspaceDecksError = null,
    workspaceDecksErrorBanner = null,
    onDeckSelection,
    onDeckDragEnter,
    onDeckDragLeave,
    onDeckDrop,
    onSelectDeck,
    onRetryDeck,
    onRemoveDeck,
    onContinue,
    formatFileSize
  }: Props = $props();

  let continuingToProcessing = $state(false);

  const viewModel = $derived(
    buildUploadDeckWidgetViewModel({
      deckFile,
      deckDragActive,
      deckUploadStatus,
      deckExtractionStatus,
      uploadError,
      saveConfirmation,
      canContinueAfterUpload,
      buttonLabel,
      maxFileLabel,
      formatFileSize
    })
  );

  const canHandoffToProcessing = $derived(
    Boolean(deckId && canContinueAfterUpload && deckUploadStatus === 'saved' && !continuingToProcessing)
  );

  async function continueToSmartDeck() {
    if (continuingToProcessing) return;

    if (!deckId) {
      // Brand-first or alternate parent flows may still provide an onContinue
      // fallback, but no backend processing route can be opened without deckId.
      onContinue();
      return;
    }

    if (!canContinueAfterUpload || deckUploadStatus !== 'saved') {
      return;
    }

    continuingToProcessing = true;

    // Readiness is backend-owned. The upload surface only hands off to the
    // processing page, which polls workflow-state before opening Smart Deck.
    try {
      await goto(`/decks/${deckId}/processing`);
    } finally {
      continuingToProcessing = false;
    }
  }

</script>

<UploadDeckWidget
  {eyebrow}
  {accept}
  {deckDragActive}
  viewModel={{
    ...viewModel,
    primaryActionEnabled: canHandoffToProcessing
  }}
  uploadedDecks={deckId ? workspaceDecks.filter((deck) => deck.id !== deckId) : workspaceDecks}
  uploadedDecksLoading={workspaceDecksLoading}
  uploadedDecksError={workspaceDecksError}
  uploadedDecksErrorBanner={workspaceDecksErrorBanner}
  selectedDeckId={deckId || null}
  {onDeckSelection}
  {onDeckDragEnter}
  {onDeckDragLeave}
  {onDeckDrop}
  {onSelectDeck}
  {onRetryDeck}
  {onRemoveDeck}
  onPrimaryAction={continueToSmartDeck}
/>
