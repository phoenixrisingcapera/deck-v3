<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchApiJsonOrThrow } from '$lib/api/apiError';
  import type { BrandProfile } from '$lib/types/deckService-brand';
  import { hasBrandSignals } from '$lib/types/deckService-brand';
  import BrandPreviewCard from '$lib/components/deckService/brand/BrandPreviewCard.svelte';
  import BrandSelectorEditor from '$lib/components/deckService/brand/BrandSelectorEditor.svelte';

  interface Props {
    deckId: string;
    onApplyBrand?: (prompt: string, profile: BrandProfile) => void | Promise<void>;
  }

  let { deckId, onApplyBrand }: Props = $props();
  let profile = $state<BrandProfile | null>(null);
  let status = $state<'loading' | 'ready' | 'saving' | 'generating' | 'error'>('loading');
  let message = $state('');
  let editing = $state(false);
  const active = $derived(Boolean(profile && hasBrandSignals(profile)));
  const emptyProfile: BrandProfile = {
    companyName: 'Brand profile',
    primaryColor: '#3B82F6',
    secondaryColor: '#0F172A',
    accentColor: '#8B5CF6',
    backgroundColor: '#081225',
    textColor: '#E6EEF8',
    fontCandidates: ['Inter', 'Arial'],
    visualStyle: 'Modern, technical, confident',
    sourceMode: 'manual'
  };

  onMount(() => {
    void fetchApiJsonOrThrow<{ brandProfile?: BrandProfile | null }>(
      `/api/products/deck-aistack-codes/decks/${deckId}/brand-profile`,
      undefined,
      'Brand profile could not be loaded.'
    ).then((payload) => {
      profile = payload.brandProfile ?? null;
      status = 'ready';
    }).catch((error) => {
      status = 'error';
      message = error instanceof Error ? error.message : 'Brand profile could not be loaded.';
    });
  });

  async function saveProfile(input: {
    primaryColor: string;
    secondaryColor: string;
    accentColor: string;
    backgroundColor: string;
    textColor: string;
    visualStyle: string;
    fontCandidates: string[];
  }) {
    status = 'saving';
    message = '';
    try {
      const payload = await fetchApiJsonOrThrow<{ brandProfile: BrandProfile }>(
        `/api/products/deck-aistack-codes/decks/${deckId}/brand-profile`,
        {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ ...input, visualDirection: profile?.visualDirection ?? 'Apply the approved brand palette and typography with a clean executive hierarchy.' })
        },
        'Brand profile could not be saved.'
      );
      profile = payload.brandProfile;
      status = 'ready';
      editing = false;
      message = 'Brand profile saved and active for the next generated version.';
    } catch (error) {
      status = 'error';
      message = error instanceof Error ? error.message : 'Brand profile could not be saved.';
    }
  }

  async function applyBrand() {
    if (!profile || !active || !onApplyBrand) return;
    const fonts = profile.fontCandidates?.filter(Boolean).join(' and ');
    status = 'generating';
    message = 'Generating a reviewable version with the active brand…';
    try {
      await onApplyBrand(
        `Apply the active persisted deck brand to this slide. Use primary ${profile.primaryColor ?? 'the approved primary colour'}, accent ${profile.accentColor ?? 'the approved accent colour'}${fonts ? `, and typography based on ${fonts}` : ''}. Preserve content accuracy while improving executive hierarchy.`,
        profile
      );
      status = 'ready';
      message = 'Branded version ready for review.';
    } catch (error) {
      status = 'error';
      message = error instanceof Error ? error.message : 'The branded version could not be generated.';
    }
  }
</script>

<section class="brand-panel">
  <header>
    <span>Active deck brand</span>
    <h2>{profile?.companyName || 'Brand profile'}</h2>
    <p>The persisted deck profile is the active brand used by Smart Deck generation.</p>
  </header>

  {#if status === 'loading'}
    <p class="signal">Loading brand profile…</p>
  {:else}
    {#if profile}
      <div class="active-state" class:is-active={active}><span aria-hidden="true"></span>{active ? 'Active brand' : 'Brand needs approved signals'}</div>
      <BrandPreviewCard brandProfile={profile} approved={active} />
    {/if}
    {#if editing}
      <BrandSelectorEditor
        brandProfile={profile ?? emptyProfile}
        saving={status === 'saving'}
        saveError={status === 'error' ? message : ''}
        onSave={(input) => void saveProfile(input)}
        onCancel={() => { editing = false; message = ''; }}
      />
    {:else if profile}
      <div class="actions">
        <button type="button" class="secondary" onclick={() => { editing = true; message = ''; }}>Review and edit</button>
        <button type="button" class="generate" disabled={!active || status === 'generating'} onclick={() => void applyBrand()}>{status === 'generating' ? 'Generating…' : 'Use brand on slide'}</button>
      </div>
    {:else}
      <div class="empty-state">
        <strong>No persisted brand profile yet</strong>
        <p>Create the deck's first profile with the existing brand editor. It will be saved to this deck and reused by generation.</p>
        <button type="button" class="generate" onclick={() => { editing = true; message = ''; }}>Create brand profile</button>
      </div>
    {/if}
  {/if}
  {#if message}<p class="message" class:is-error={status === 'error'} role="status">{message}</p>{/if}
</section>

<style>
  .brand-panel, header { display: grid; gap: .7rem; }
  header > span { color: #38bdf8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p { margin: 0; }
  header p, .signal, .message { color: #94a3b8; line-height: 1.45; }
  .active-state { display: flex; align-items: center; gap: .45rem; color: #fbbf24; font-size: .78rem; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
  .active-state span { width: .55rem; height: .55rem; border-radius: 999px; background: currentColor; }
  .active-state.is-active { color: #86efac; }
  .actions { display: grid; grid-template-columns: 1fr 1.2fr; gap: .6rem; }
  .empty-state { display: grid; gap: .7rem; padding: 1rem; border: 1px dashed rgba(255,255,255,.16); border-radius: 12px; background: rgba(15,23,42,.6); }
  .empty-state strong { color: #f8fafc; }
  .empty-state p { color: #94a3b8; line-height: 1.45; }
  button { min-height: 42px; border: 0; border-radius: 10px; background: rgba(30,41,59,.95); color: white; font-weight: 800; cursor: pointer; }
  button.secondary { border: 1px solid rgba(255,255,255,.12); }
  button.generate { background: linear-gradient(135deg,#7c3aed,#0ea5e9); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .is-error { color: #fca5a5; }
  @media (max-width: 960px) { .actions { grid-template-columns: 1fr; } }
</style>
