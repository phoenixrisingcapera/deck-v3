<!-- Purpose: renders upload/deck processing state badge token. -->
<script lang="ts">
  import type { UploadedDeckListStatus } from './uploaded-decks-list.types';

  type Props = {
    status: UploadedDeckListStatus;
  };

  let { status }: Props = $props();
  const label = $derived(status === 'selected' ? 'Selected' : status === 'processing' ? 'Processing' : status === 'failed' ? 'Failed' : 'Uploaded');
</script>

<div class={`deck-status-badge deck-status-badge--${status}`}>
  <span class="deck-status-badge__icon" aria-hidden="true">
    {#if status === 'processing'}
      <span class="deck-status-badge__spinner"></span>
    {:else if status === 'failed'}
      !
    {:else}
      <svg viewBox="0 0 16 16" role="presentation">
        <path d="m4 8 2.2 2.2L12 4.8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" />
      </svg>
    {/if}
  </span>
  <span>{label}</span>
</div>

<style>
  .deck-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.45rem 0.78rem;
    border-radius: 999px;
    border: 1px solid rgba(96, 121, 176, 0.22);
    background: rgba(19, 29, 58, 0.8);
    color: rgba(224, 236, 255, 0.92);
    font-size: 0.8rem;
    white-space: nowrap;
  }

  .deck-status-badge--uploaded {
    border-color: rgba(86, 205, 125, 0.26);
    color: #64db8a;
  }

  .deck-status-badge--selected {
    border-color: rgba(84, 168, 255, 0.28);
    color: #73c5ff;
  }

  .deck-status-badge--failed {
    border-color: rgba(255, 117, 117, 0.26);
    color: #ff8f8f;
  }

  .deck-status-badge__icon {
    width: 16px;
    height: 16px;
    display: grid;
    place-items: center;
    font-weight: 700;
  }

  .deck-status-badge__icon svg {
    width: 16px;
    height: 16px;
  }

  .deck-status-badge__spinner {
    width: 13px;
    height: 13px;
    border-radius: 999px;
    border: 2px solid rgba(102, 166, 255, 0.22);
    border-top-color: currentColor;
    animation: deck-status-spin 0.9s linear infinite;
  }

  @keyframes deck-status-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
