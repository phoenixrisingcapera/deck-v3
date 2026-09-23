<script lang="ts">
  import { onMount } from 'svelte';
  import type { DeckShellProperties, UpdateDeckShellPropertiesRequest } from '$lib/contracts';
  import { fetchApiJsonOrThrow } from '$lib/api/apiError';
  import type { BrandProfile } from '$lib/types/deckService-brand';
  import { buildBrandPalette, getBrandPaletteSourceLabel, hasBrandSignals } from '$lib/types/deckService-brand';

  interface Props {
    deckId: string;
    initialProperties?: DeckShellProperties | null;
  }

  let { deckId, initialProperties = null }: Props = $props();
  // DISABLED: Direct prop captures emitted Svelte 5 initial-value warnings.
  // let companyName = $state(initialProperties?.companyName ?? '');
  // let companyWebsiteUrl = $state(initialProperties?.companyWebsiteUrl ?? '');
  // let founderName = $state(initialProperties?.founderName ?? '');
  // let teamSummary = $state(initialProperties?.teamSummary ?? '');
  // let brandSummary = $state(initialProperties?.brandSummary ?? '');
  // let visualDirection = $state(initialProperties?.visualDirection ?? '');
  function initialForm() {
    return {
      companyName: initialProperties?.companyName ?? '',
      companyWebsiteUrl: initialProperties?.companyWebsiteUrl ?? '',
      founderName: initialProperties?.founderName ?? '',
      teamSummary: initialProperties?.teamSummary ?? '',
      brandSummary: initialProperties?.brandSummary ?? '',
      visualDirection: initialProperties?.visualDirection ?? ''
    };
  }
  const initial = initialForm();
  let companyName = $state(initial.companyName);
  let companyWebsiteUrl = $state(initial.companyWebsiteUrl);
  let founderName = $state(initial.founderName);
  let teamSummary = $state(initial.teamSummary);
  let brandSummary = $state(initial.brandSummary);
  let visualDirection = $state(initial.visualDirection);
  let status = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
  let message = $state('');
  let brandProfile = $state<BrandProfile | null>(null);
  let brandStatus = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');

  onMount(() => {
    brandStatus = 'loading';
    void fetchApiJsonOrThrow<{ brandProfile?: BrandProfile | null }>(
      `/api/products/deck-aistack-codes/decks/${deckId}/brand-profile`,
      undefined,
      'Brand profile could not be loaded.'
    )
      .then((payload) => {
        brandProfile = payload.brandProfile ?? null;
        brandStatus = 'ready';
      })
      .catch(() => {
        brandProfile = null;
        brandStatus = 'error';
      });
  });

  async function save() {
    status = 'saving';
    message = '';
    const input: UpdateDeckShellPropertiesRequest = {
      companyName: companyName.trim() || null,
      companyWebsiteUrl: companyWebsiteUrl.trim() || null,
      founderName: founderName.trim() || null,
      teamSummary: teamSummary.trim() || null,
      brandSummary: brandSummary.trim() || null,
      visualDirection: visualDirection.trim() || null
    };
    try {
      await fetchApiJsonOrThrow(`/api/decks/${deckId}/properties`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(input)
      }, 'Company data could not be saved.');
      status = 'saved';
      message = 'Company data saved for future slide generation.';
    } catch (error) {
      status = 'error';
      message = error instanceof Error ? error.message : 'Company data could not be saved.';
    }
  }
</script>

<section class="tool-panel">
  <header><span>Smart data</span><h2>Company context</h2><p>Saved context is reused by brand extraction, generation, and retrieval.</p></header>
  <section class="brand-status-card">
    <div>
      <strong>Brand profile</strong>
      <span>{brandStatus === 'loading' ? 'Loading brand signals…' : brandProfile && hasBrandSignals(brandProfile) ? 'Brand signals available' : 'Brand profile is sparse'}</span>
    </div>
    {#if brandProfile?.logoUrl}
      <img src={brandProfile.logoUrl} alt="Company logo" />
    {/if}
    {#if brandProfile}
      <small>Palette source: {getBrandPaletteSourceLabel(brandProfile)}</small>
      {#if buildBrandPalette(brandProfile).length > 0}
        <div class="palette-row">
          {#each buildBrandPalette(brandProfile).slice(0, 5) as swatch}
            <span title={swatch.label} style={`background:${swatch.value}`}></span>
          {/each}
        </div>
      {/if}
    {/if}
  </section>
  <form onsubmit={(event) => { event.preventDefault(); void save(); }}>
    <label><span>Company name</span><input id="smart-deck-company-name" name="companyName" bind:value={companyName} autocomplete="organization" /></label>
    <label><span>Company website</span><input id="smart-deck-company-website" name="companyWebsiteUrl" bind:value={companyWebsiteUrl} type="url" placeholder="https://company.com" autocomplete="url" /></label>
    <label><span>Founder or CEO</span><input id="smart-deck-founder-name" name="founderName" bind:value={founderName} autocomplete="name" /></label>
    <label><span>Team and board</span><textarea id="smart-deck-team-summary" name="teamSummary" bind:value={teamSummary} rows="4" placeholder="Key leaders, board members, roles, and relevant experience"></textarea></label>
    <label><span>Brand summary</span><textarea id="smart-deck-brand-summary" name="brandSummary" bind:value={brandSummary} rows="3" placeholder="Positioning, voice, and brand constraints"></textarea></label>
    <label><span>Visual direction</span><textarea id="smart-deck-visual-direction" name="visualDirection" bind:value={visualDirection} rows="3" placeholder="Preferred slide style, hierarchy, and visual cues"></textarea></label>
    <button type="submit" disabled={status === 'saving'}>{status === 'saving' ? 'Saving...' : 'Save company data'}</button>
    {#if message}<p class:error={status === 'error'} role="status">{message}</p>{/if}
  </form>
  <small>LinkedIn URLs are not fetched or scraped. Add verified people details manually in the team and board field.</small>
</section>

<style>
  .tool-panel, form, label { display: grid; gap: 0.7rem; }
  .brand-status-card { display: grid; gap: 0.55rem; border: 1px solid rgba(255,255,255,.08); border-radius: 12px; padding: .8rem; background: rgba(15,23,42,.72); }
  .brand-status-card > div { display: grid; gap: .15rem; }
  .brand-status-card strong { color: #f8fafc; }
  .brand-status-card img { max-width: 124px; max-height: 48px; object-fit: contain; background: white; border-radius: 8px; padding: .35rem; }
  .palette-row { display: flex; gap: .45rem; flex-wrap: wrap; }
  .palette-row span { width: 24px; height: 24px; border-radius: 999px; border: 1px solid rgba(255,255,255,.12); }
  header { display: grid; gap: 0.35rem; }
  header > span { color: #38bdf8; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
  h2, p { margin: 0; }
  header p, small, form p { color: #94a3b8; line-height: 1.45; }
  label span { color: #cbd5e1; font-size: 0.78rem; font-weight: 700; }
  input, textarea { width: 100%; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; background: rgba(15,23,42,.9); color: #f8fafc; padding: .7rem; font: inherit; }
  textarea { resize: vertical; }
  button { min-height: 42px; border: 0; border-radius: 10px; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 800; cursor: pointer; }
  button:disabled { opacity: .6; }
  form p.error { color: #fca5a5; }
</style>
