<!-- Purpose: shows brand intelligence phase and previews either persisted card or placeholder. -->
  <script lang="ts">
  import BrandPreviewCard from './BrandPreviewCard.svelte';
  import SmartColourSwatchPlaceholder from './SmartColourSwatchPlaceholder.svelte';
  import type { DeckExtractionStatus } from '$lib/api/deckService/workflow.client';
  import type { BrandProfile, BrandStatus } from '$lib/types/deckService-brand';
  import type { BrandIntelligencePhase } from '$lib/types/brand-intelligence';
  import { hasBrandSignals } from '$lib/types/deckService-brand';

  let {
    brandProfile = null,
    brandApproved = false,
    brandStatus = 'idle',
    deckExtractionStatus = 'idle',
    companyUrl = '',
    logoFile = null,
    brandGuidelinesFile = null
  }: {
    brandProfile?: BrandProfile | null;
    brandApproved?: boolean;
    brandStatus?: BrandStatus;
    deckExtractionStatus?: DeckExtractionStatus;
    companyUrl?: string;
    logoFile?: File | null;
    brandGuidelinesFile?: File | null;
  } = $props();

  const hasWebsiteInput = $derived(companyUrl.trim().length > 0);
  const hasLogoInput = $derived(Boolean(logoFile));
  const hasGuidelinesInput = $derived(Boolean(brandGuidelinesFile));
  const phase = $derived.by<BrandIntelligencePhase>(() => {
    if (Boolean((brandProfile && hasBrandSignals(brandProfile)) || brandStatus === 'ready')) return 'brand_ready';
    if (brandStatus === 'failed') return 'failed';
    if (brandStatus === 'extracting' && hasWebsiteInput) return 'sampling_url';
    if (brandStatus === 'extracting' && hasLogoInput) return 'reading_logo';
    if (deckExtractionStatus === 'processing' || deckExtractionStatus === 'queued') return 'reading_deck';
    if (hasWebsiteInput || hasLogoInput || hasGuidelinesInput) return 'needs_user_input';
    return 'waiting';
  });

  const panelSummary = $derived.by(() => {
    if (phase === 'brand_ready') return 'Existing persisted brand profile and swatches are ready for review.';
    if (phase === 'reading_deck') return 'Deck AIStack is reading your deck visuals while extraction runs.';
    if (phase === 'sampling_url') return 'Website and intake signals are being merged into a stronger brand profile.';
    if (phase === 'reading_logo') return 'Logo colours are being sampled before the first persisted brand profile is final.';
    if (phase === 'needs_user_input') return 'Starter swatches are visible while you add more brand evidence.';
    if (phase === 'failed') return 'The fallback swatch shell stays visible so the modal does not degrade into an empty state.';
    return 'Open extraction to see smart swatches appear before the full brand profile is persisted.';
  });
</script>

<section class="smart-brand-step-panel" data-component-tag="smart-brand-step-panel" aria-label="Step 2 brand intelligence panel">
  <div class="smart-brand-step-panel__head">
    <div>
      <div class="eyebrow">Step 2</div>
      <h4>Brand intelligence</h4>
      <p>{panelSummary}</p>
    </div>
    <span>{Boolean((brandProfile && hasBrandSignals(brandProfile)) || brandStatus === 'ready') ? 'Ready' : phase.replaceAll('_', ' ')}</span>
  </div>

  {#if brandProfile && hasBrandSignals(brandProfile)}
    <BrandPreviewCard {brandProfile} approved={brandApproved} />
  {:else}
    <SmartColourSwatchPlaceholder {phase} {hasWebsiteInput} {hasLogoInput} hasGuidelinesInput={hasGuidelinesInput} />
  {/if}
</section>

<style>
  .smart-brand-step-panel {
    display: grid;
    gap: 0.9rem;
  }

  .smart-brand-step-panel__head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: start;
  }

  .smart-brand-step-panel__head h4,
  .smart-brand-step-panel__head p {
    margin: 0;
  }

  .smart-brand-step-panel__head h4 {
    color: var(--ink);
  }

  .smart-brand-step-panel__head p,
  .smart-brand-step-panel__head span {
    color: var(--muted);
    font-size: 0.84rem;
  }

  .smart-brand-step-panel__head span {
    border-radius: 999px;
    border: 1px solid var(--line);
    padding: 0.4rem 0.68rem;
    text-transform: capitalize;
    background: rgba(255, 255, 255, 0.03);
  }
</style>
