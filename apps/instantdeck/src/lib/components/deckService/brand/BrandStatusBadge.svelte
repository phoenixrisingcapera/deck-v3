<!-- Purpose: maps brand extraction status to compact status badge copy and tone. -->
<script lang="ts">
  import type { BrandStatus } from '$lib/types/deckService-brand';

  let {
    status = 'idle',
    ready = false
  }: {
    status?: BrandStatus;
    ready?: boolean;
  } = $props();

  const label = $derived.by(() => {
    if (ready || status === 'ready') return 'Ready';
    if (status === 'extracting') return 'Extracting';
    if (status === 'failed') return 'Needs review';
    return 'Waiting';
  });

  const badgeTone = $derived.by(() => {
    if (ready || status === 'ready') return 'ready';
    if (status === 'extracting') return 'extracting';
    if (status === 'failed') return 'failed';
    return 'waiting';
  });
</script>

<span class={`brand-status-badge brand-status-badge--${badgeTone}`} data-component-tag="brand-status-badge">
  <span class="brand-status-badge__dot" aria-hidden="true"></span>
  {label}
</span>

<style>
  .brand-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    width: fit-content;
    border-radius: 999px;
    border: 1px solid var(--brand-card-border);
    background: var(--brand-card-muted-surface);
    color: var(--brand-card-text-muted);
    padding: 0.35rem 0.58rem;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .brand-status-badge__dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    background: currentColor;
  }

  .brand-status-badge--ready {
    border-color: color-mix(in srgb, var(--success) 48%, var(--brand-card-border));
    background: color-mix(in srgb, var(--success) 12%, var(--brand-card-muted-surface));
    color: var(--success);
  }

  .brand-status-badge--extracting {
    border-color: color-mix(in srgb, var(--brand-card-accent) 48%, var(--brand-card-border));
    background: color-mix(in srgb, var(--brand-card-accent) 12%, var(--brand-card-muted-surface));
    color: var(--brand-card-accent);
  }

  .brand-status-badge--failed {
    border-color: color-mix(in srgb, var(--danger) 48%, var(--brand-card-border));
    background: color-mix(in srgb, var(--danger) 12%, var(--brand-card-muted-surface));
    color: var(--danger);
  }

  .brand-status-badge--extracting .brand-status-badge__dot {
    animation: brand-status-pulse 900ms ease-in-out infinite;
  }

  @keyframes brand-status-pulse {
    50% {
      opacity: 0.28;
      transform: scale(0.72);
    }
  }
</style>
