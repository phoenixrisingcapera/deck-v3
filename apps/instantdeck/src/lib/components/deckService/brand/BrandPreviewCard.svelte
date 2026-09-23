<!-- Purpose: presents finalized brand profile details, palette, and sample source metadata. -->
<script lang="ts">
  import PaletteChips from './PaletteChips.svelte';
  import type { BrandProfile } from '$lib/types/deckService-brand';
  import {
    buildBrandPalette,
    getBrandConfidenceLabel,
    getBrandPaletteSourceLabel,
    getBrandPaletteSource,
    getBrandSummary,
    getBrandFieldStatusLabel,
    isFallbackPalette
  } from '$lib/types/deckService-brand';

  let {
    brandProfile,
    approved = false
  }: {
    brandProfile: BrandProfile;
    approved?: boolean;
  } = $props();

  const palette = $derived(buildBrandPalette(brandProfile));
  const confidencePercent = $derived(Math.round((brandProfile.confidenceScore ?? 0) * 100));
  const confidenceLabel = $derived(getBrandConfidenceLabel(brandProfile));
  const summary = $derived(getBrandSummary(brandProfile));
  const warnings = $derived(brandProfile.warnings ?? []);
  const paletteSource = $derived(getBrandPaletteSource(brandProfile));
  const paletteSourceLabel = $derived(getBrandPaletteSourceLabel(brandProfile));
  const fallbackPalette = $derived(isFallbackPalette(brandProfile));
  const sampledUrls = $derived(
    brandProfile.rawEvidence?.sampledUrls ??
      (brandProfile.rawEvidence?.paletteEvidence && Array.isArray(brandProfile.rawEvidence.paletteEvidence.sampledUrls)
        ? (brandProfile.rawEvidence.paletteEvidence.sampledUrls as string[])
        : [])
  );
  const fontLabel = $derived(
    brandProfile.fonts?.map((font) => font.family).join(', ') ?? brandProfile.fontCandidates?.join(', ') ?? 'Inter, Manrope'
  );
  const logoFallbackLetter = $derived((brandProfile.companyName?.trim()?.[0] ?? 'B').toUpperCase());
  let logoLoadFailed = $state(false);

  $effect(() => {
    brandProfile.logoUrl;
    logoLoadFailed = false;
  });

  // Map raw source mode keys to user-facing extraction source labels.
  function sourceModeLabel(value?: string | null) {
    if (!value) return '';
    if (value === 'manual_url') return 'Website-derived';
    if (value === 'logo_and_url') return 'Website + logo';
    if (value === 'logo_upload') return 'Logo-derived';
    if (value === 'context_seed') return 'Context default';
    if (value === 'manual') return 'Manual';
    return value.replaceAll('_', ' ');
  }

  // Build a concise explanation of palette provenance from raw source enum tokens.
  function paletteSourceNote(source: string) {
    if (source.includes('url_live_asset')) return 'Sampled from a live website asset such as a logo, icon, or manifest image.';
    if (source.includes('url_live_colors')) return 'Sampled from website CSS and inline colour values.';
    if (source.includes('logo_live_asset')) return 'Sampled directly from the uploaded logo or brand asset.';
    if (source.includes('logo_seed_fallback')) return 'The logo could not be sampled, so deterministic logo-byte fallback colours were used.';
    if (source.includes('deck_visual')) return 'Sampled from deck thumbnails, renders, and slide assets.';
    if (source.includes('fallback_deck_seed')) return 'No visual assets were available, so deterministic deck-seed swatches were used.';
    if (source.includes('context_seed')) return 'Context defaults were used until stronger brand signals arrive.';
    return '';
  }
</script>

<section class="brand-preview" class:brand-preview--fallback={fallbackPalette}>
  <div class="brand-preview__header">
    <div>
      <div class="eyebrow">Brand preview (extracted)</div>
      <h4>Brand profile ready</h4>
      <p class="summary">{summary}</p>
    </div>
    <div class="meta-stack">
      <span class="confidence-pill">{confidenceLabel}</span>
      <span class:fallback={fallbackPalette} class:approved class="source-pill">{paletteSourceLabel}</span>
      {#if brandProfile.sourceMode ?? brandProfile.source}
        <span class:approved class="source-pill source-pill--muted">{sourceModeLabel(brandProfile.sourceMode ?? brandProfile.source)}</span>
      {/if}
    </div>
  </div>

  {#if paletteSourceNote(paletteSource)}
    <p class={`brand-preview__note${fallbackPalette ? ' brand-preview__note--fallback' : ''}`}>
      {paletteSourceNote(paletteSource)}
    </p>
  {/if}

  <div class="brand-swatch-strip" aria-label="Extracted brand colour swatches">
    {#each palette as swatch}
      <article style={`--swatch:${swatch.value}`}>
        <span aria-hidden="true"></span>
        <div>
          <strong>{swatch.label}</strong>
          <code>{swatch.value}</code>
          <small>{swatch.evidenceField ? getBrandFieldStatusLabel(brandProfile, swatch.evidenceField) : 'Evidence unavailable'}</small>
        </div>
      </article>
    {/each}
  </div>

  <div class="brand-preview__body">
    <div class="brand-mark">
      {#if brandProfile.logoUrl && !logoLoadFailed}
        <img
          src={brandProfile.logoUrl}
          alt="Detected brand logo"
          loading="lazy"
          decoding="async"
          onerror={() => {
            logoLoadFailed = true;
          }}
        />
      {:else}
        <span>{logoFallbackLetter}</span>
      {/if}
    </div>

    <div class="brand-signals">
      <div>
        <span>Primary colors</span>
        <PaletteChips {palette} />
      </div>

      <div class="brand-facts">
        <article>
          <span>Typography</span>
          <strong>{fontLabel}</strong>
          <small>{getBrandFieldStatusLabel(brandProfile, 'fontCandidates')}</small>
        </article>
        <article>
          <span>Visual style</span>
          <strong>{brandProfile.visualStyle ?? 'Modern, technical, confident'}</strong>
        </article>
        <article>
          <span>Confidence score</span>
          <strong>{confidencePercent}%</strong>
        </article>
      </div>

      {#if fallbackPalette}
        <div class="brand-notes brand-notes--fallback" aria-label="Brand palette fallback notice">
          <strong>Palette source</strong>
          <p>
            These swatches are a safe default until Deck AIStack can replace them with stronger live URL, logo, or deck-derived
            colours.
          </p>
        </div>
      {/if}

      {#if sampledUrls.length > 0}
        <div class="brand-notes" aria-label="Sampled brand sources">
          <strong>Sampled sources</strong>
          <ul>
            {#each sampledUrls.slice(0, 3) as sampledUrl}
              <li>{sampledUrl}</li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if warnings.length > 0}
        <div class="brand-notes" aria-label="Brand extraction warnings">
          <strong>Notes</strong>
          <ul>
            {#each warnings as warning}
              <li>{warning}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .brand-preview {
    display: grid;
    gap: 0.95rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1rem;
    background: rgba(255, 255, 255, 0.02);
  }

  .brand-preview--fallback {
    border-color: rgba(255, 204, 102, 0.22);
  }

  .brand-preview__header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.75rem;
    align-items: start;
  }

  .summary,
  .brand-signals > div > span,
  .brand-facts article span,
  .brand-notes p {
    color: var(--muted);
    font-size: 0.84rem;
  }

  .summary,
  .brand-notes p {
    margin: 0.35rem 0 0;
  }

  .brand-preview__note {
    margin: 0;
    color: rgba(191, 207, 234, 0.88);
    font-size: 0.83rem;
    line-height: 1.45;
  }

  .brand-preview__note--fallback {
    color: #ffd98a;
  }

  .meta-stack {
    display: grid;
    gap: 0.55rem;
    justify-items: end;
  }

  .confidence-pill,
  .source-pill {
    border-radius: 999px;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.85rem;
    text-transform: capitalize;
  }

  .source-pill.approved {
    border-color: rgba(104, 221, 130, 0.35);
    color: #8ce698;
  }

  .source-pill.fallback {
    border-color: rgba(255, 204, 102, 0.42);
    color: #ffd98a;
  }

  .source-pill--muted {
    opacity: 0.82;
  }

  .brand-swatch-strip {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.55rem;
  }

  .brand-swatch-strip article {
    min-width: 0;
    border: 1px solid rgba(120, 145, 255, 0.18);
    border-radius: 12px;
    background: rgba(8, 15, 31, 0.52);
    overflow: hidden;
  }

  .brand-swatch-strip article > span {
    display: block;
    height: 2.35rem;
    background: var(--swatch);
  }

  .brand-swatch-strip article div {
    display: grid;
    gap: 0.15rem;
    padding: 0.48rem 0.55rem;
  }

  .brand-swatch-strip strong {
    color: rgba(240, 245, 255, 0.96);
    font-size: 0.72rem;
  }

  .brand-swatch-strip code {
    color: rgba(188, 201, 231, 0.8);
    font-size: 0.68rem;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .brand-swatch-strip small,
  .brand-facts small {
    color: #94a3b8;
    font-size: 0.68rem;
  }

  .brand-preview__body {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1rem;
    align-items: start;
  }

  .brand-mark {
    width: 4.5rem;
    height: 4.5rem;
    border-radius: 12px;
    display: grid;
    place-items: center;
    background: linear-gradient(160deg, rgba(34, 53, 109, 0.95), rgba(17, 26, 50, 0.95));
    border: 1px solid rgba(121, 145, 255, 0.18);
  }

  .brand-mark span {
    font-size: 2rem;
    font-weight: 700;
    color: #9ae37d;
  }

  .brand-mark img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: 12px;
    padding: 0.6rem;
  }

  .brand-signals {
    display: grid;
    gap: 0.9rem;
  }

  .brand-facts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    border-top: 1px solid var(--line);
    padding-top: 0.85rem;
  }

  .brand-facts article {
    display: grid;
    gap: 0.3rem;
  }

  .brand-notes {
    display: grid;
    gap: 0.45rem;
    border-top: 1px solid var(--line);
    padding-top: 0.75rem;
  }

  .brand-notes--fallback {
    border-top-color: rgba(255, 204, 102, 0.25);
  }

  .brand-notes strong {
    font-size: 0.82rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .brand-notes ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--text);
    font-size: 0.88rem;
    display: grid;
    gap: 0.25rem;
  }

  @media (max-width: 960px) {
    .brand-preview__header,
    .brand-preview__body,
    .brand-facts,
    .brand-swatch-strip {
      grid-template-columns: 1fr;
    }

    .meta-stack {
      justify-items: start;
    }
  }
</style>
