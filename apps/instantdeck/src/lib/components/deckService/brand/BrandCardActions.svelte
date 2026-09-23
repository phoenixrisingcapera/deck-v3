<!-- Purpose: actions for review, extract, and continue flows in the brand profile step. -->
<script lang="ts">
  import type { BrandStatus } from '$lib/types/deckService-brand';

  let {
    status = 'idle',
    canExtract = false,
    canContinue = false,
    deckUploadComplete = false,
    onExtract,
    onReview,
    onContinue
  }: {
    status?: BrandStatus;
    canExtract?: boolean;
    canContinue?: boolean;
    deckUploadComplete?: boolean;
    onExtract: () => void | Promise<void>;
    onReview: () => void;
    onContinue: () => void | Promise<void>;
  } = $props();

  const extractLabel = $derived.by(() => {
    if (status === 'extracting') return 'Extracting brand...';
    if (deckUploadComplete) return 'Extract brand';
    return 'Create first version';
  });
</script>

<div class="brand-card-actions" data-component-tag="brand-card-actions">
  <button class="button brand-card-actions__secondary" type="button" onclick={onReview} disabled={status === 'extracting'}>
    Review brand profile
  </button>
  <button class="button brand-card-actions__primary" type="button" onclick={onExtract} disabled={!canExtract}>
    {extractLabel}
  </button>
  <button class="brand-card-actions__menu" type="button" disabled={!canContinue} onclick={onContinue}>
    Use brand
  </button>
</div>

<style>
  .brand-card-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr) auto;
    gap: 0.55rem;
    align-items: stretch;
    border-top: 1px solid var(--brand-card-border);
    padding-top: 0.8rem;
  }

  .brand-card-actions :global(.button),
  .brand-card-actions__menu {
    min-height: 2.7rem;
    border-radius: 12px;
    justify-content: center;
  }

  .brand-card-actions__secondary {
    background: var(--brand-card-muted-surface);
    color: var(--brand-card-text);
    border: 1px solid var(--brand-card-border);
  }

  .brand-card-actions__primary {
    background: var(--brand-card-accent);
    color: var(--button-primary-ink);
    border: 1px solid var(--brand-card-accent);
  }

  .brand-card-actions__menu {
    border: 1px solid var(--brand-card-border);
    background: var(--brand-card-muted-surface);
    color: var(--brand-card-text);
    padding: 0 0.75rem;
    font-weight: 700;
    cursor: pointer;
  }

  .brand-card-actions__menu:disabled,
  .brand-card-actions :global(.button:disabled) {
    cursor: not-allowed;
    opacity: 0.55;
  }

  @media (max-width: 820px) {
    .brand-card-actions {
      grid-template-columns: 1fr;
    }
  }
</style>
