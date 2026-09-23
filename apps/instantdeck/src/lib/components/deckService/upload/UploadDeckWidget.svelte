<!-- Purpose: uploads/continues deck flow UI container with uploaded deck list and helper state banner support. -->
<script lang="ts">
  import SaveConfirmationBanner from '$lib/components/deckService/feedback/SaveConfirmationBanner.svelte';
  import UploadedDocumentRow from './UploadedDocumentRow.svelte';
  import UploadedDecksList from './UploadedDecksList.svelte';
  import type { ApiErrorBannerModel } from '$lib/api/apiError';
  import type { UploadDeckWidgetViewModel, UploadedDocumentViewModel } from './upload-deck.types';
  import type { UploadedDeckListItem } from './uploaded-decks-list.types';

  interface Props {
    eyebrow?: string;
    accept: string;
    deckDragActive: boolean;
    viewModel: UploadDeckWidgetViewModel;
    uploadedDecks?: UploadedDeckListItem[];
    uploadedDecksLoading?: boolean;
    uploadedDecksError?: string | null;
    uploadedDecksErrorBanner?: ApiErrorBannerModel | null;
    selectedDeckId?: string | null;
    onDeckSelection: (event: Event) => void | Promise<void>;
    onDeckDragEnter: (event: DragEvent) => void;
    onDeckDragLeave: (event: DragEvent) => void;
    onDeckDrop: (event: DragEvent) => void | Promise<void>;
    onSelectDeck?: (deck: UploadedDeckListItem) => void;
    onRetryDeck?: (deckId: string) => void;
    onRemoveDeck?: (deckId: string) => void;
    onPrimaryAction?: () => void;
  }

  let {
    eyebrow = 'Upload',
    accept,
    deckDragActive,
    viewModel,
    uploadedDecks = [],
    uploadedDecksLoading = false,
    uploadedDecksError = null,
    uploadedDecksErrorBanner = null,
    selectedDeckId = null,
    onDeckSelection,
    onDeckDragEnter,
    onDeckDragLeave,
    onDeckDrop,
    onSelectDeck,
    onRetryDeck,
    onRemoveDeck,
    onPrimaryAction
  }: Props = $props();
</script>

<section class="upload-deck-widget panel">
  <div class="upload-deck-widget__header">
    <div class="eyebrow">{eyebrow}</div>
    <h3>{viewModel.title}</h3>
    <p>{viewModel.supportCopy}</p>
  </div>

  <label
    class="upload-deck-widget__dropzone"
    class:upload-deck-widget__dropzone--active={deckDragActive || viewModel.state === 'drag_active'}
    ondragenter={onDeckDragEnter}
    ondragover={onDeckDragEnter}
    ondragleave={onDeckDragLeave}
    ondrop={onDeckDrop}
  >
    <input type="file" accept={accept} onchange={onDeckSelection} />

    <div class="upload-deck-widget__drop-icon" aria-hidden="true">
      <svg viewBox="0 0 64 64" role="presentation">
        <path
          d="M20 50h23.5c7.5 0 13.5-5.8 13.5-13 0-6.7-5.1-12.3-11.7-12.9A16 16 0 0 0 16.2 20a12 12 0 0 0-1.2 24H20"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
        />
        <path d="M32 19v24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="3" />
        <path d="m24 27 8-8 8 8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="3" />
      </svg>
    </div>

    <strong>{viewModel.instruction}</strong>
    <div class="upload-deck-widget__browse-line">
      <span>or</span>
      <span class="upload-deck-widget__browse-link">{viewModel.browseLabel}</span>
    </div>
    <small>{viewModel.acceptedFormatsLabel}</small>
  </label>

  {#if viewModel.showUploadedDocument && viewModel.uploadedDocument}
    <div class="upload-deck-widget__uploaded-stage">
      <UploadedDocumentRow document={viewModel.uploadedDocument} />

      {#if viewModel.primaryActionLabel}
        <button
          type="button"
          class="upload-deck-widget__secondary-action upload-deck-widget__primary-create"
          onclick={onPrimaryAction}
          disabled={!viewModel.primaryActionEnabled}
        >
          {viewModel.primaryActionLabel}
        </button>
      {/if}
    </div>
  {/if}

  {#if viewModel.confirmation}
    <SaveConfirmationBanner
      title={viewModel.confirmation.title}
      message={viewModel.confirmation.message}
      tone={viewModel.confirmation.tone}
      actionLabel={viewModel.confirmation.actionLabel}
      actionHref={viewModel.confirmation.actionHref}
      compact={true}
    />
  {/if}

  {#if uploadedDecksLoading || uploadedDecks.length > 0 || uploadedDecksError || uploadedDecksErrorBanner}
    <UploadedDecksList
      decks={uploadedDecks}
      isLoading={uploadedDecksLoading}
      error={uploadedDecksError}
      errorBanner={uploadedDecksErrorBanner}
      {selectedDeckId}
      onSelectDeck={onSelectDeck}
      onRetryDeck={onRetryDeck}
      onRemoveDeck={onRemoveDeck}
      emptyTitle="No other workspace decks."
      emptyMessage="Uploaded decks from this workspace will appear here."
    />
  {/if}

  <div class="upload-deck-widget__helper-row">
    <p>
      {viewModel.helperLabel}
      {#if viewModel.helperHrefLabel}
        <a href={viewModel.helperHref}>{viewModel.helperHrefLabel}</a>
      {/if}
    </p>
  </div>
</section>

<style>
  .upload-deck-widget,
  .upload-deck-widget__header,
  .upload-deck-widget__uploaded-stage {
    display: grid;
    gap: 0.9rem;
  }

  .upload-deck-widget {
    padding: 1.05rem 1.15rem 1.15rem;
  }

  .upload-deck-widget__header {
    gap: 0.35rem;
  }

  .eyebrow,
  .upload-deck-widget__browse-link,
  .upload-deck-widget__helper-row a {
    color: #2f82ff;
  }

  .eyebrow {
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .upload-deck-widget__header h3,
  .upload-deck-widget__header p,
  .upload-deck-widget__helper-row p {
    margin: 0;
  }

  .upload-deck-widget__header h3 {
    font-size: clamp(1.25rem, 1.9vw, 1.9rem);
    line-height: 1.1;
    letter-spacing: -0.04em;
  }

  .upload-deck-widget__header p,
  .upload-deck-widget__helper-row p {
    color: rgba(200, 211, 234, 0.78);
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .upload-deck-widget__dropzone {
    position: relative;
    display: grid;
    gap: 0.45rem;
    justify-items: center;
    padding: 1.75rem 1rem 1.05rem;
    border-radius: 13px;
    border: 1px dashed var(--border, rgba(56, 106, 235, 0.55));
    background: var(--bg-subtle, rgba(10, 18, 37, 0.48));
    text-align: center;
    transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
  }

  .upload-deck-widget__dropzone--active {
    border-color: var(--accent, #4f86ff);
    background: var(--accent-soft, rgba(64, 112, 233, 0.16));
    transform: translateY(-1px);
  }

  .upload-deck-widget__dropzone input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .upload-deck-widget__drop-icon {
    width: 2.9rem;
    height: 2.9rem;
    color: #4580ff;
  }

  .upload-deck-widget__drop-icon svg {
    width: 100%;
    height: 100%;
  }

  .upload-deck-widget__dropzone strong {
    color: rgba(240, 245, 255, 0.96);
    font-size: 0.98rem;
    line-height: 1.35;
  }

  .upload-deck-widget__browse-line {
    display: inline-flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.25rem;
    color: rgba(181, 194, 224, 0.78);
    font-size: 0.94rem;
  }

  .upload-deck-widget__dropzone small {
    color: rgba(156, 169, 203, 0.75);
    font-size: 0.78rem;
  }

  .upload-deck-widget__secondary-action {
    border: 1px solid var(--border);
    border-radius: var(--radius, 8px);
    background: var(--surface, #09142e);
    color: var(--text, rgba(230, 238, 255, 0.92));
    padding: 0.68rem 0.95rem;
    font-weight: 600;
    cursor: pointer;
  }

  .upload-deck-widget__primary-create {
    justify-self: stretch;
    border-color: var(--accent, #4f86ff);
    background: var(--accent, #4f86ff);
    color: #fff;
  }

  .upload-deck-widget__secondary-action:disabled {
    cursor: not-allowed;
    opacity: 0.58;
  }

  .upload-deck-widget__helper-row a {
    color: var(--accent, #4f86ff);
    font-weight: 600;
    text-decoration: none;
  }
</style>
