<!-- Purpose: renders brand palette when ready and loading placeholders while extracting. -->
<script lang="ts">
  import type { BrandProfile, BrandStatus } from '$lib/types/deckService-brand';
  import { buildBrandPalette, hasBrandSignals } from '$lib/types/deckService-brand';

  let {
    brandProfile = null,
    status = 'idle'
  }: {
    brandProfile?: BrandProfile | null;
    status?: BrandStatus;
  } = $props();

  const ready = $derived(Boolean(brandProfile && hasBrandSignals(brandProfile)) || status === 'ready');
  const extracting = $derived(status === 'extracting');
  const palette = $derived(brandProfile ? buildBrandPalette(brandProfile).slice(0, 5) : []);
  const placeholders = Array.from({ length: 5 });
</script>

<section class="smart-colour-swatch" data-component-tag="smart-colour-swatch" aria-label="Smart colour swatch">
  <div class="smart-colour-swatch__head">
    <strong>Smart colour swatch</strong>
    <span>{ready ? 'Deterministic match' : extracting ? 'Scanning' : 'Waiting'}</span>
  </div>

  {#if ready && palette.length > 0}
    <div class="smart-colour-swatch__grid smart-colour-swatch__grid--ready">
      {#each palette as swatch}
        <article class="smart-colour-swatch__item" style={`--brand-swatch:${swatch.value}`}>
          <span class="smart-colour-swatch__colour" aria-hidden="true"></span>
          <div>
            <strong>{swatch.label}</strong>
            <code>{swatch.value}</code>
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <div class:smart-colour-swatch__grid--extracting={extracting} class="smart-colour-swatch__grid" aria-hidden="true">
      {#each placeholders as _, index}
        <span class="smart-colour-swatch__placeholder" style={`--placeholder-index:${index}`}></span>
      {/each}
    </div>
    <p>{extracting ? 'Detecting colours from website, logo, and deck signals.' : 'No colours detected yet. This card will stay visible while the deck processes.'}</p>
  {/if}
</section>

<style>
  .smart-colour-swatch {
    display: grid;
    gap: 0.65rem;
  }

  .smart-colour-swatch__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .smart-colour-swatch__head strong {
    color: var(--brand-card-text);
    font-size: 0.88rem;
  }

  .smart-colour-swatch__head span,
  .smart-colour-swatch p {
    color: var(--brand-card-text-muted);
    font-size: 0.8rem;
  }

  .smart-colour-swatch p {
    margin: 0;
  }

  .smart-colour-swatch__grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.55rem;
  }

  .smart-colour-swatch__placeholder,
  .smart-colour-swatch__item {
    min-width: 0;
    border-radius: 12px;
    border: 1px solid var(--brand-card-border);
    background: var(--brand-card-muted-surface);
    overflow: hidden;
  }

  .smart-colour-swatch__placeholder {
    min-height: 4.2rem;
  }

  .smart-colour-swatch__grid--extracting .smart-colour-swatch__placeholder {
    background:
      linear-gradient(110deg, transparent, color-mix(in srgb, var(--brand-card-accent) 18%, transparent), transparent),
      var(--brand-card-muted-surface);
    animation: smart-swatch-loading 1200ms ease-in-out infinite;
    animation-delay: calc(var(--placeholder-index) * 90ms);
  }

  .smart-colour-swatch__colour {
    display: block;
    min-height: 2.6rem;
    background: var(--brand-swatch);
  }

  .smart-colour-swatch__item div {
    display: grid;
    gap: 0.16rem;
    padding: 0.48rem 0.52rem;
  }

  .smart-colour-swatch__item strong,
  .smart-colour-swatch__item code {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .smart-colour-swatch__item strong {
    color: var(--brand-card-text);
    font-size: 0.72rem;
  }

  .smart-colour-swatch__item code {
    color: var(--brand-card-text-muted);
    font-size: 0.68rem;
  }

  @keyframes smart-swatch-loading {
    50% {
      opacity: 0.54;
    }
  }

  @media (max-width: 720px) {
    .smart-colour-swatch__grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
</style>
