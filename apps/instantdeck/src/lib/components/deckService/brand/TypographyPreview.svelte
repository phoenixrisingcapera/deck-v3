<!-- Purpose: shows inferred typography signals and fallback shimmer when extraction is pending. -->
<script lang="ts">
  import type { BrandProfile, BrandStatus } from '$lib/types/deckService-brand';

  let {
    brandProfile = null,
    status = 'idle'
  }: {
    brandProfile?: BrandProfile | null;
    status?: BrandStatus;
  } = $props();

  const fonts = $derived.by(() => {
    const fromFonts = brandProfile?.fonts?.map((font) => font.family).filter(Boolean) ?? [];
    const fromCandidates = brandProfile?.fontCandidates?.filter(Boolean) ?? [];
    return Array.from(new Set(fromFonts.concat(fromCandidates))).slice(0, 2);
  });

  const loading = $derived(status === 'extracting' && fonts.length === 0);
</script>

<section class="typography-preview" data-component-tag="typography-preview" aria-label="Typography preview">
  <strong>Typography</strong>

  {#if fonts.length > 0}
    <div class="typography-preview__grid">
      {#each fonts as font, index}
        <article>
          <span aria-hidden="true">Ag</span>
          <div>
            <strong>{font}</strong>
            <small>{index === 0 ? 'Primary' : 'Secondary'}</small>
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <div class:typography-preview__grid--loading={loading} class="typography-preview__grid" aria-hidden="true">
      <article><span>Ag</span><i></i><i></i></article>
      <article><span>Ag</span><i></i><i></i></article>
    </div>
  {/if}
</section>

<style>
  .typography-preview {
    display: grid;
    gap: 0.65rem;
  }

  .typography-preview > strong {
    color: var(--brand-card-text);
    font-size: 0.88rem;
  }

  .typography-preview__grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .typography-preview article {
    min-width: 0;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 0.6rem;
    border: 1px solid var(--brand-card-border);
    border-radius: 12px;
    background: var(--brand-card-muted-surface);
    padding: 0.65rem;
  }

  .typography-preview article > span {
    color: var(--brand-card-text);
    font-size: 1.35rem;
    line-height: 1;
  }

  .typography-preview article div {
    display: grid;
    gap: 0.12rem;
  }

  .typography-preview article strong {
    color: var(--brand-card-text);
    font-size: 0.84rem;
  }

  .typography-preview article small {
    color: var(--brand-card-text-muted);
    font-size: 0.76rem;
  }

  .typography-preview article i {
    display: block;
    min-height: 0.55rem;
    border-radius: 999px;
    background: var(--brand-card-border);
  }

  .typography-preview__grid--loading article {
    animation: typography-loading 1100ms ease-in-out infinite;
  }

  @keyframes typography-loading {
    50% {
      opacity: 0.58;
    }
  }

  @media (max-width: 720px) {
    .typography-preview__grid {
      grid-template-columns: 1fr;
    }
  }
</style>
