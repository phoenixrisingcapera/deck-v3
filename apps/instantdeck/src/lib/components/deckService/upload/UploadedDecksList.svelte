<!-- Purpose: renders uploaded deck list with loading, error, empty, and interaction states. -->
<script lang="ts">
  import EmptyDecksState from './EmptyDecksState.svelte';
  import UploadedDeckRow from './UploadedDeckRow.svelte';
  import UploadedDecksSkeleton from './UploadedDecksSkeleton.svelte';
  import type { ApiErrorBannerModel } from '$lib/api/apiError';
  import type { UploadedDeckListItem } from './uploaded-decks-list.types';

  type Props = {
    decks: UploadedDeckListItem[];
    selectedDeckId?: string | null;
    isLoading?: boolean;
    error?: string | null;
    errorBanner?: ApiErrorBannerModel | null;
    onSelectDeck?: (deck: UploadedDeckListItem) => void;
    onRemoveDeck?: (deckId: string) => void;
    onRetryDeck?: (deckId: string) => void;
    showHeader?: boolean;
    showActions?: boolean;
    maxHeight?: number;
    className?: string;
    emptyTitle?: string;
    emptyMessage?: string;
  };

  let {
    decks,
    selectedDeckId = null,
    isLoading = false,
    error = null,
    errorBanner = null,
    onSelectDeck,
    onRemoveDeck,
    onRetryDeck,
    showHeader = true,
    showActions = true,
    maxHeight = 260,
    className = '',
    emptyTitle = 'No decks uploaded yet.',
    emptyMessage = 'Upload a PDF or PowerPoint file to get started.'
  }: Props = $props();

  const errorTitle = $derived(errorBanner?.title ?? 'Could not load uploaded decks.');
  const errorMessage = $derived(errorBanner?.message ?? error);
</script>

<section class={`uploaded-decks-list ${className}`.trim()}>
  {#if showHeader}
    <div class="uploaded-decks-list__header">
      <div>
        <strong>Uploaded decks</strong>
        <span>{decks.length} {decks.length === 1 ? 'deck' : 'decks'}</span>
      </div>
    </div>
  {/if}

  {#if isLoading}
    <UploadedDecksSkeleton />
  {:else if errorMessage}
    <div class="uploaded-decks-list__state uploaded-decks-list__state--error">
      <strong>{errorTitle}</strong>
      <p>{errorMessage}</p>
      {#if errorBanner?.actionHref && errorBanner?.actionLabel}
        <a href={errorBanner.actionHref}>{errorBanner.actionLabel}</a>
      {/if}
    </div>
  {:else if decks.length === 0}
    <EmptyDecksState title={emptyTitle} message={emptyMessage} />
  {:else}
    <div class="uploaded-decks-list__scroll" style={`max-height:${maxHeight}px`}>
      {#each decks as deck}
        <UploadedDeckRow
          deck={deck}
          selected={selectedDeckId === deck.id || deck.status === 'selected'}
          {showActions}
          {onSelectDeck}
          {onRemoveDeck}
          {onRetryDeck}
        />
      {/each}
    </div>
  {/if}
</section>

<style>
  .uploaded-decks-list {
    display: grid;
    gap: 0.72rem;
  }

  .uploaded-decks-list__header div {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.8rem;
  }

  .uploaded-decks-list__header strong,
  .uploaded-decks-list__state strong {
    margin: 0;
    color: rgba(243, 246, 255, 0.97);
  }

  .uploaded-decks-list__header strong {
    font-size: 0.9rem;
  }

  .uploaded-decks-list__header span,
  .uploaded-decks-list__state p {
    color: rgba(188, 201, 231, 0.78);
    font-size: 0.78rem;
  }

  .uploaded-decks-list__state {
    border: 1px solid rgba(255, 157, 162, 0.42);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(27, 20, 31, 0.94), rgba(36, 17, 26, 0.96));
    padding: 0.95rem 1rem;
    display: grid;
    gap: 0.25rem;
  }

  .uploaded-decks-list__state p {
    margin: 0;
    line-height: 1.45;
  }

  .uploaded-decks-list__state a {
    justify-self: start;
    margin-top: 0.25rem;
    color: #8cc7ff;
    font-size: 0.78rem;
    font-weight: 700;
  }

  .uploaded-decks-list__scroll {
    overflow-y: auto;
    display: grid;
    gap: 0.7rem;
    padding-right: 0.18rem;
  }
</style>
