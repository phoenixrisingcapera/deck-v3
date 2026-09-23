<!-- Purpose: renders one uploaded deck item with status, stale-processing hint, and retry/remove actions. -->
<script lang="ts">
  import DeckFileIcon from './DeckFileIcon.svelte';
  import DeckStatusBadge from './DeckStatusBadge.svelte';
  import { hasActiveWorkflowStatus, type UploadedDeckListItem } from './uploaded-decks-list.types';

  type Props = {
    deck: UploadedDeckListItem;
    selected?: boolean;
    showActions?: boolean;
    onSelectDeck?: (deck: UploadedDeckListItem) => void;
    onRemoveDeck?: (deckId: string) => void;
    onRetryDeck?: (deckId: string) => void;
  };

  let { deck, selected = false, showActions = true, onSelectDeck, onRemoveDeck, onRetryDeck }: Props = $props();
  const metadata = $derived([deck.fileSizeLabel, deck.uploadedAtLabel].filter(Boolean).join(' · '));
  const workflowProgressTimestamp = $derived.by(() => {
    const value = deck.workflowUpdatedAt;
    if (typeof value !== 'string' || !value.trim()) return null;
    const timestamp = new Date(value).getTime();
    return Number.isFinite(timestamp) ? timestamp : null;
  });
  const hasActiveWorkflow = $derived(Boolean(deck.workflowId && hasActiveWorkflowStatus(deck.workflowStatus)));
  const staleProcessing = $derived(
    Boolean(
      deck.status === 'processing' &&
        hasActiveWorkflow &&
        workflowProgressTimestamp !== null &&
        Date.now() - workflowProgressTimestamp >= 12 * 60 * 1000
    )
  );
  const isProcessing = $derived(deck.status === 'processing');
  const staleCopy = $derived(
    staleProcessing
      ? 'No new backend progress has been reported recently. Retry processing or open the processing view to inspect the workflow-state.'
      : ''
  );

  // Select this deck row and bubble selection up to parent.
  function activate() {
    onSelectDeck?.(deck);
  }

  // Ensure Enter/Space activates row consistently for keyboard users.
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activate();
    }
  }
</script>

<div class="uploaded-deck-row" class:uploaded-deck-row--selected={selected}>
  {#if onSelectDeck}
    <button type="button" class="uploaded-deck-row__button" aria-pressed={selected} onclick={activate} onkeydown={handleKeydown}>
      <div class="uploaded-deck-row__lead">
        <DeckFileIcon fileType={deck.fileType} thumbnailUrl={deck.thumbnailUrl} />
        <div class="uploaded-deck-row__copy">
          <strong>{deck.name}</strong>
          <span>{metadata || 'Uploaded deck'}</span>
        </div>
      </div>
      <DeckStatusBadge status={selected ? 'selected' : deck.status} />
    </button>
  {:else}
    <div class="uploaded-deck-row__static">
      <div class="uploaded-deck-row__lead">
        <DeckFileIcon fileType={deck.fileType} thumbnailUrl={deck.thumbnailUrl} />
        <div class="uploaded-deck-row__copy">
          <strong>{deck.name}</strong>
          <span>{metadata || 'Uploaded deck'}</span>
        </div>
      </div>
      <DeckStatusBadge status={selected ? 'selected' : deck.status} />
    </div>
  {/if}

  {#if staleProcessing}
    <div class="uploaded-deck-row__stale">
      <strong>Processing looks stuck</strong>
      <p>{staleCopy}</p>
    </div>
  {/if}

  {#if showActions && (selected || staleProcessing) && (onRetryDeck || onRemoveDeck)}
    <div class="uploaded-deck-row__actions">
      {#if (deck.status === 'failed' || staleProcessing) && onRetryDeck}
        <button type="button" onclick={() => onRetryDeck?.(deck.id)}>Retry</button>
      {/if}
      {#if selected && onRemoveDeck}
        {#if isProcessing}
          <button type="button" disabled title="Remove is locked while processing">Remove locked</button>
        {:else}
          <button type="button" onclick={() => onRemoveDeck?.(deck.id)}>Remove</button>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .uploaded-deck-row {
    border: 1px solid rgba(81, 107, 165, 0.32);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(19, 31, 62, 0.96), rgba(14, 24, 49, 0.96));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }

  .uploaded-deck-row--selected {
    border-color: rgba(90, 167, 255, 0.46);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05), 0 0 0 1px rgba(84, 168, 255, 0.18);
  }

  .uploaded-deck-row__button,
  .uploaded-deck-row__static {
    width: 100%;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
  }

  .uploaded-deck-row__button {
    cursor: pointer;
  }

  .uploaded-deck-row__lead {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .uploaded-deck-row__copy {
    min-width: 0;
    display: grid;
    gap: 0.16rem;
  }

  .uploaded-deck-row__copy strong {
    color: rgba(243, 246, 255, 0.97);
    font-size: 0.96rem;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .uploaded-deck-row__copy span {
    color: rgba(188, 201, 231, 0.74);
    font-size: 0.82rem;
    line-height: 1.25;
  }

  .uploaded-deck-row__stale {
    margin: 0 1rem 0.9rem;
    padding: 0.75rem 0.85rem;
    border: 1px solid rgba(255, 204, 102, 0.24);
    border-radius: 12px;
    background: rgba(255, 204, 102, 0.08);
    display: grid;
    gap: 0.25rem;
  }

  .uploaded-deck-row__stale strong {
    color: #ffd98a;
    font-size: 0.82rem;
  }

  .uploaded-deck-row__stale p {
    margin: 0;
    color: rgba(228, 236, 255, 0.82);
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .uploaded-deck-row__actions {
    padding: 0 1rem 0.9rem;
    display: flex;
    justify-content: flex-end;
    gap: 0.55rem;
  }

  .uploaded-deck-row__actions button {
    border-radius: 999px;
    border: 1px solid rgba(95, 115, 168, 0.42);
    background: rgba(255, 255, 255, 0.03);
    color: rgba(232, 238, 255, 0.88);
    padding: 0.4rem 0.72rem;
    font: inherit;
    cursor: pointer;
  }

  .uploaded-deck-row__actions button:disabled {
    cursor: not-allowed;
    opacity: 0.58;
  }

  @media (max-width: 720px) {
    .uploaded-deck-row__button,
    .uploaded-deck-row__static {
      align-items: start;
      flex-direction: column;
    }
  }
</style>
