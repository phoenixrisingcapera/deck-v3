<script lang="ts">
  import type { BrandProfile, BrandSourceLabel, BrandStatus } from '$lib/types/deckService-brand';
  import { buildBrandSourceLabels } from '$lib/types/deckService-brand';

  let {
    brandProfile = null,
    status = 'idle',
    hasWebsiteInput = false,
    hasLogoInput = false,
    hasDeckInput = false,
    hasBrandGuidelinesInput = false
  }: {
    brandProfile?: BrandProfile | null;
    status?: BrandStatus;
    hasWebsiteInput?: boolean;
    hasLogoInput?: boolean;
    hasDeckInput?: boolean;
    hasBrandGuidelinesInput?: boolean;
  } = $props();

  const labels = $derived<BrandSourceLabel[]>(
    buildBrandSourceLabels(brandProfile, {
      hasWebsiteInput,
      hasLogoInput,
      hasDeckInput,
      hasBrandGuidelinesInput
    })
  );
  const hasAvailableLabel = $derived(labels.some((label) => label.status === 'available' || label.status === 'fallback'));
  const pending = $derived(status === 'idle' || (!hasAvailableLabel && status !== 'extracting'));
  const extracting = $derived(status === 'extracting');
</script>

<section class="brand-source-labels" data-component-tag="brand-source-labels" aria-label="Brand source labels">
  <div class="brand-source-labels__header">
    {#if pending}
      <strong>Source labels pending</strong>
    {:else if extracting}
      <strong>Source labels extracting</strong>
    {:else}
      <strong>Source labels</strong>
    {/if}
    <span>{labels.length} sources</span>
  </div>
  <div class="brand-source-labels__grid">
    {#each labels as label}
      <span class={`brand-source-label brand-source-label--${label.status}`} title={label.detail ?? label.label}>{label.label}</span>
    {/each}
  </div>
</section>

<style>
  .brand-source-labels {
    display: grid;
    gap: 0.5rem;
    border: 1px solid var(--brand-card-border);
    border-radius: 12px;
    background: var(--brand-card-muted-surface);
    padding: 0.7rem;
  }

  .brand-source-labels__header {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
  }

  .brand-source-labels__header strong {
    color: var(--brand-card-text);
    font-size: 0.84rem;
  }

  .brand-source-labels__header span {
    color: var(--brand-card-text-muted);
    font-size: 0.72rem;
    font-weight: 700;
  }

  .brand-source-labels__grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .brand-source-label {
    border: 1px solid var(--brand-card-border);
    border-radius: 999px;
    background: var(--surface-input);
    color: var(--brand-card-text-muted);
    padding: 0.38rem 0.58rem;
    font-size: 0.76rem;
    font-weight: 800;
  }

  .brand-source-label--available,
  .brand-source-label--fallback {
    border-color: color-mix(in srgb, var(--brand-card-accent) 42%, var(--brand-card-border));
    color: var(--brand-card-text);
  }

  .brand-source-label--missing,
  .brand-source-label--pending {
    opacity: 0.72;
  }
</style>
