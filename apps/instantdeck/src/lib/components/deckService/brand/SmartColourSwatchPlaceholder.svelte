<!-- Purpose: placeholder visual while brand swatch extraction is pending or waiting on evidence. -->
<script lang="ts">
  import type { BrandIntelligencePhase } from '$lib/types/brand-intelligence';

  let {
    phase = 'waiting',
    hasWebsiteInput = false,
    hasLogoInput = false,
    hasGuidelinesInput = false
  }: {
    phase?: BrandIntelligencePhase;
    hasWebsiteInput?: boolean;
    hasLogoInput?: boolean;
    hasGuidelinesInput?: boolean;
  } = $props();

  const title = $derived.by(() => {
    if (phase === 'reading_deck') return 'Reading your deck visuals...';
    if (phase === 'sampling_url') return 'Learning brand from website...';
    if (phase === 'reading_logo') return 'Learning brand from logo...';
    if (phase === 'failed') return 'Preparing intelligent swatches...';
    if (phase === 'needs_user_input') return 'Starter swatches generated from intake context.';
    return 'Smart colour swatch will appear here';
  });

  const body = $derived.by(() => {
    if (phase === 'reading_deck') return 'Deck AIStack is sampling slide colours while extraction continues in the background.';
    if (phase === 'sampling_url') return 'Website colour hints will be merged into the brand profile when available.';
    if (phase === 'reading_logo') return 'Logo colours are being sampled to strengthen the first brand profile.';
    if (phase === 'failed') return 'Fallback swatches stay visible so the review flow does not go blank.';
    if (phase === 'needs_user_input') return 'Add your website or logo to improve palette accuracy before the Smart Deck opens.';
    return 'Open extraction to see intelligent swatches replace these placeholders as signals arrive.';
  });

  const detectedSources = $derived.by(() => {
    return [
      { label: 'Source deck colours', active: phase === 'reading_deck' || phase === 'brand_ready' || phase === 'needs_user_input' },
      { label: 'Logo colours', active: hasLogoInput || phase === 'reading_logo' || phase === 'brand_ready' },
      { label: 'Website colours', active: hasWebsiteInput || phase === 'sampling_url' || phase === 'brand_ready' },
      { label: 'Guidelines context', active: hasGuidelinesInput }
    ];
  });

  const placeholderSwatches = [
    { label: 'Primary', tone: 'var(--accent)' },
    { label: 'Secondary', tone: 'var(--surface-strong)' },
    { label: 'Accent', tone: 'color-mix(in srgb, var(--accent) 60%, white)' },
    { label: 'Background', tone: 'var(--surface-soft)' },
    { label: 'Text', tone: 'var(--ink)' }
  ];
</script>

<section class={`swatch-placeholder swatch-placeholder--${phase}`} aria-label="Smart colour swatch placeholder">
  <div class="swatch-placeholder__head">
    <div>
      <div class="eyebrow">Smart colour swatch</div>
      <strong>{title}</strong>
    </div>
    <span>{phase.replaceAll('_', ' ')}</span>
  </div>

  <div class="swatch-placeholder__grid" aria-hidden="true">
    {#each placeholderSwatches as swatch, index}
      <article style={`--placeholder-tone:${swatch.tone}; --delay:${index * 100}ms;`}>
        <span></span>
        <div>
          <strong>{swatch.label}</strong>
          <small>Preparing intelligent swatch</small>
        </div>
      </article>
    {/each}
  </div>

  <p>{body}</p>

  <div class="swatch-placeholder__signals">
    <strong>Detected so far</strong>
    <ul>
      {#each detectedSources as source}
        <li class:active={source.active}>{source.label}</li>
      {/each}
    </ul>
  </div>

  <div class="swatch-placeholder__footer">
    Optional: add a website, logo, or guidelines to improve the brand profile.
  </div>
</section>

<style>
  .swatch-placeholder {
    display: grid;
    gap: 0.9rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1rem;
    background: rgba(255, 255, 255, 0.02);
  }

  .swatch-placeholder__head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: start;
  }

  .swatch-placeholder__head strong {
    display: block;
    margin-top: 0.2rem;
    color: var(--ink);
  }

  .swatch-placeholder__head span,
  .swatch-placeholder p,
  .swatch-placeholder__footer,
  .swatch-placeholder__signals li {
    color: var(--muted);
    font-size: 0.84rem;
  }

  .swatch-placeholder p,
  .swatch-placeholder__footer {
    margin: 0;
  }

  .swatch-placeholder__grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.55rem;
  }

  .swatch-placeholder__grid article {
    min-width: 0;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(120, 145, 255, 0.18);
    background: rgba(8, 15, 31, 0.52);
    animation: placeholder-breathe 1400ms ease-in-out infinite;
    animation-delay: var(--delay);
  }

  .swatch-placeholder__grid span {
    display: block;
    min-height: 2.4rem;
    background:
      linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.18), transparent),
      linear-gradient(180deg, color-mix(in srgb, var(--placeholder-tone) 82%, black), var(--placeholder-tone));
    background-size: 200% 100%, 100% 100%;
    animation: placeholder-sheen 1800ms ease-in-out infinite;
  }

  .swatch-placeholder__grid div {
    display: grid;
    gap: 0.15rem;
    padding: 0.48rem 0.55rem;
  }

  .swatch-placeholder__grid strong {
    color: rgba(240, 245, 255, 0.96);
    font-size: 0.72rem;
  }

  .swatch-placeholder__grid small {
    color: rgba(188, 201, 231, 0.8);
    font-size: 0.68rem;
  }

  .swatch-placeholder__signals {
    display: grid;
    gap: 0.55rem;
  }

  .swatch-placeholder__signals strong {
    color: var(--ink);
    font-size: 0.86rem;
  }

  .swatch-placeholder__signals ul {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.28rem;
  }

  .swatch-placeholder__signals li.active {
    color: #8cc5ff;
  }

  .swatch-placeholder--failed {
    border-color: rgba(255, 146, 146, 0.24);
  }

  .swatch-placeholder--needs_user_input {
    border-color: rgba(255, 204, 102, 0.24);
  }

  @keyframes placeholder-breathe {
    50% {
      transform: translateY(-1px);
      border-color: rgba(140, 197, 255, 0.32);
    }
  }

  @keyframes placeholder-sheen {
    0% {
      background-position: 200% 0, 0 0;
    }

    100% {
      background-position: -20% 0, 0 0;
    }
  }

  @media (max-width: 960px) {
    .swatch-placeholder__grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
</style>
