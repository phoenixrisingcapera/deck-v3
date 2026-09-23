<!-- Purpose: composes brand input, extracted profile preview, signals, and action controls. -->
<script lang="ts">
  import BrandCardActions from './BrandCardActions.svelte';
  import BrandExtractionStatus from './BrandExtractionStatus.svelte';
  import BrandSignalChips from './BrandSignalChips.svelte';
  import BrandStatusBadge from './BrandStatusBadge.svelte';
  import LogoDropzone from './LogoDropzone.svelte';
  import SmartColourSwatch from './SmartColourSwatch.svelte';
  import TypographyPreview from './TypographyPreview.svelte';
  import type { BrandProfile, BrandStatus } from '$lib/types/deckService-brand';
  import { hasBrandSignals } from '$lib/types/deckService-brand';

  let {
    companyUrl = '',
    logoFile = null,
    logoPreviewUrl = '',
    logoDragActive = false,
    acceptedLogoTypes,
    brandStatus = 'idle',
    brandError = '',
    brandProfile = null,
    brandApproved = false,
    deckUploadComplete = false,
    hasBrandSourceInput = false,
    canExtractBrand = false,
    canContinue = false,
    modeLabel = 'slide_miniatures',
    formatFileSize,
    onCompanyUrlChange,
    onLogoDragEnter,
    onLogoDragLeave,
    onLogoDrop,
    onLogoFileChange,
    onExtract,
    onReview,
    onContinue
  }: {
    companyUrl?: string;
    logoFile?: File | null;
    logoPreviewUrl?: string;
    logoDragActive?: boolean;
    acceptedLogoTypes: string;
    brandStatus?: BrandStatus;
    brandError?: string;
    brandProfile?: BrandProfile | null;
    brandApproved?: boolean;
    deckUploadComplete?: boolean;
    hasBrandSourceInput?: boolean;
    canExtractBrand?: boolean;
    canContinue?: boolean;
    modeLabel?: string;
    formatFileSize: (size: number) => string;
    onCompanyUrlChange: (value: string) => void;
    onLogoDragEnter: (event: DragEvent) => void;
    onLogoDragLeave: (event: DragEvent) => void;
    onLogoDrop: (event: DragEvent) => void | Promise<void>;
    onLogoFileChange: (file: File | null) => void | Promise<void>;
    onExtract: () => void | Promise<void>;
    onReview: () => void;
    onContinue: () => void | Promise<void>;
  } = $props();

  const ready = $derived(Boolean(brandProfile && hasBrandSignals(brandProfile)) || brandStatus === 'ready');
  const cardState = $derived.by(() => {
    if (brandStatus === 'failed') return 'failed';
    if (ready) return 'ready';
    if (brandStatus === 'extracting') return 'extracting';
    return 'waiting';
  });

  const helperCopy = $derived.by(() => {
    if (cardState === 'ready') return 'Brand signals are persisted and ready to use in the first Smart Deck version.';
    if (cardState === 'extracting') return 'We are detecting brand signals while your deck continues processing.';
    if (modeLabel === 'slide_miniatures') return 'Upload your deck, then add a website or logo while processing continues.';
    return 'This card can create a persisted first version before a deck file exists.';
  });

  const microCopy = $derived.by(() => {
    if (deckUploadComplete) return 'Website, logo, and deck signals map into the same persisted brand profile contract.';
    if (hasBrandSourceInput) return 'URL and logo inputs create a source-backed first version and persist deterministic brand matches.';
    return 'Upload a deck, enter a company URL, or load a logo to create the first version.';
  });
</script>

<section class={`brand-profile-card brand-profile-card--${cardState}`} data-component-tag="brand-profile-card" aria-label="Brand profile card">
  <div class="brand-profile-card__header">
    <div>
      <div class="eyebrow">Brand</div>
      <h3>Brand profile</h3>
      <p>{helperCopy}</p>
    </div>
    <BrandStatusBadge status={brandStatus} {ready} />
  </div>

  <label class="brand-profile-card__field">
    <span>Company website</span>
    <input value={companyUrl} type="url" placeholder="https://company.com" autocomplete="url" oninput={(event) => onCompanyUrlChange((event.currentTarget as HTMLInputElement).value)} />
  </label>

  <div class="brand-profile-card__logo">
    <span>Logo optional</span>
    <LogoDropzone file={logoFile} previewUrl={logoPreviewUrl} dragActive={logoDragActive} accept={acceptedLogoTypes} {formatFileSize} onDragEnter={onLogoDragEnter} onDragLeave={onLogoDragLeave} onDrop={onLogoDrop} onFileChange={onLogoFileChange} />
  </div>

  <SmartColourSwatch brandProfile={brandProfile} status={brandStatus} />
  <TypographyPreview brandProfile={brandProfile} status={brandStatus} />
  <BrandSignalChips brandProfile={brandProfile} status={brandStatus} hasWebsiteInput={companyUrl.trim().length > 0} hasLogoInput={Boolean(logoFile || logoPreviewUrl)} hasDeckInput={deckUploadComplete} />

  {#if brandError || brandStatus === 'failed' || brandStatus === 'extracting'}
    <div class="brand-profile-card__status">
      <BrandExtractionStatus status={brandStatus} error={brandError} />
    </div>
  {/if}

  <p class="brand-profile-card__microcopy">{microCopy}</p>

  <BrandCardActions status={brandStatus} canExtract={canExtractBrand} canContinue={canContinue || brandApproved} {deckUploadComplete} onExtract={onExtract} onReview={onReview} onContinue={onContinue} />
</section>

<style>
  .brand-profile-card {
    display: grid;
    gap: 0.9rem;
    border: 1px solid var(--brand-card-border);
    border-radius: 16px;
    background: var(--brand-card-surface);
    padding: 1.05rem;
    box-shadow: var(--shadow-card);
  }

  .brand-profile-card__header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.85rem;
    align-items: start;
  }

  .brand-profile-card__header h3,
  .brand-profile-card__header p,
  .brand-profile-card__microcopy {
    margin: 0;
  }

  .brand-profile-card__header h3 {
    color: var(--brand-card-text);
  }

  .brand-profile-card__header p,
  .brand-profile-card__microcopy {
    color: var(--brand-card-text-muted);
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .brand-profile-card__field,
  .brand-profile-card__logo {
    display: grid;
    gap: 0.4rem;
  }

  .brand-profile-card__field span,
  .brand-profile-card__logo > span {
    color: var(--brand-card-text-muted);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .brand-profile-card__field input {
    width: 100%;
    border-radius: 14px;
    border: 1px solid var(--line-strong);
    padding: 0.8rem 0.9rem;
    background: var(--surface-input);
    color: var(--brand-card-text);
  }

  .brand-profile-card__field input:focus {
    outline: 2px solid color-mix(in srgb, var(--brand-card-accent) 42%, transparent);
    outline-offset: 2px;
  }

  .brand-profile-card__status {
    border: 1px solid var(--brand-card-border);
    border-radius: 12px;
    background: var(--brand-card-muted-surface);
    padding: 0.85rem;
  }

  .brand-profile-card--ready {
    border-color: color-mix(in srgb, var(--success) 32%, var(--brand-card-border));
  }

  .brand-profile-card--extracting {
    border-color: color-mix(in srgb, var(--brand-card-accent) 36%, var(--brand-card-border));
  }

  .brand-profile-card--failed {
    border-color: color-mix(in srgb, var(--danger) 36%, var(--brand-card-border));
  }

  @media (max-width: 720px) {
    .brand-profile-card__header {
      grid-template-columns: 1fr;
    }
  }
</style>
