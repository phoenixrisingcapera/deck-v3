<script lang="ts">
  import { createInstantDeckShare, revokeInstantDeckShare } from '$lib/api/deckService/workflow.client';
  import type { DeckExportShareCreated } from '$lib/contracts/types';

  interface Props {
    deckId: string;
    designVersionId: string | null;
    generatedSlideId: string | null;
    sourceSlideId: string | null;
    artifactId: string | null;
    canEdit: boolean;
    generating?: boolean;
    onKeepAndEdit: () => void | Promise<unknown>;
    onGenerateAnother: () => void | Promise<unknown>;
  }

  let {
    deckId,
    designVersionId,
    generatedSlideId,
    sourceSlideId,
    artifactId,
    canEdit,
    generating = false,
    onKeepAndEdit,
    onGenerateAnother
  }: Props = $props();

  function versionHref(path: string) {
    const params = new URLSearchParams();
    if (designVersionId) params.set('designVersionId', designVersionId);
    if (generatedSlideId) params.set('generatedSlideId', generatedSlideId);
    if (sourceSlideId) params.set('slide', sourceSlideId);
    if (artifactId) params.set('artifactId', artifactId);
    const query = params.toString();
    return query ? `${path}?${query}` : path;
  }

  const smartDeckHref = $derived(versionHref(`/decks/${deckId}/smart-deck`));
  const diligenceHref = $derived(versionHref(`/decks/${deckId}/due-diligence`));
  const versionsHref = $derived(versionHref(`/decks/${deckId}/versions`));

  let shareState = $state<'idle' | 'creating' | 'ready' | 'revoking' | 'error'>('idle');
  let activeShare = $state<DeckExportShareCreated | null>(null);
  let shareUrl = $state('');
  let shareMessage = $state('');

  async function copyShareUrl() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      shareMessage = 'Share link copied.';
    } catch {
      shareMessage = 'The link is ready. Open it and copy it from the address bar.';
    }
  }

  async function createShare() {
    if (!designVersionId || shareState === 'creating' || shareState === 'revoking') return;
    shareState = 'creating';
    shareMessage = 'Creating a link for this exact DesignVersion…';
    try {
      const created = await createInstantDeckShare(deckId, designVersionId);
      activeShare = created;
      shareUrl = `${window.location.origin}/shared/decks/${encodeURIComponent(created.shareId)}/${encodeURIComponent(created.shareToken)}`;
      shareState = 'ready';
      await copyShareUrl();
    } catch (error) {
      activeShare = null;
      shareUrl = '';
      shareState = 'error';
      shareMessage = error instanceof Error ? error.message : 'Could not create the share link.';
    }
  }

  async function revokeShare() {
    if (!activeShare || shareState === 'revoking') return;
    shareState = 'revoking';
    shareMessage = 'Revoking share link…';
    try {
      await revokeInstantDeckShare(deckId, activeShare.exportId, activeShare.shareId);
      activeShare = null;
      shareUrl = '';
      shareState = 'idle';
      shareMessage = 'Share link revoked.';
    } catch (error) {
      shareState = 'error';
      shareMessage = error instanceof Error ? error.message : 'Could not revoke the share link.';
    }
  }
</script>

<section class="instant-result-actions" aria-label="Instant Deck result actions" data-instant-result-actions>
  <div class="instant-result-actions__intro">
    <div>
      <span class="eyebrow">Published Instant Deck</span>
      <h4>Version-backed result</h4>
    </div>
    <p>The compiled DesignVersion is saved and render-proofed before these actions become available.</p>
  </div>

  <div class="instant-result-actions__primary" aria-label="Result actions">
    <button
      type="button"
      class="primary"
      disabled={!canEdit}
      title={canEdit ? 'Keep this DesignVersion and open Smart Edit with its exact generated identity.' : 'The generated section identity is still preparing.'}
      onclick={() => void onKeepAndEdit()}
    >Keep &amp; edit</button>
    <button
      type="button"
      class="secondary"
      disabled={generating}
      title="Keep this version and start one more whole-deck redesign through the same Instant Deck pipeline."
      onclick={() => void onGenerateAnother()}
    >{generating ? 'Generating…' : 'Generate another'}</button>
    <a class="secondary" href={versionHref(`/decks/${deckId}/export`)} title="Export the exact displayed compiled DesignVersion.">Export</a>
    <button
      type="button"
      class="secondary"
      disabled={!designVersionId || generating || shareState === 'creating' || shareState === 'revoking'}
      title="Publish the exact displayed compiled DesignVersion as a revocable HTML site."
      onclick={() => void createShare()}
    >{shareState === 'creating' ? 'Creating link…' : activeShare ? 'Rotate share link' : 'Share link'}</button>
  </div>

  {#if shareUrl}
    <div class="instant-result-actions__share" data-instant-deck-share-ready>
      <input aria-label="Instant Deck share URL" readonly value={shareUrl} />
      <button type="button" onclick={() => void copyShareUrl()}>Copy</button>
      <a href={shareUrl} target="_blank" rel="noopener noreferrer">Open site</a>
      <button type="button" disabled={shareState === 'revoking'} onclick={() => void revokeShare()}>Revoke</button>
    </div>
  {/if}
  {#if shareMessage}
    <p class:error={shareState === 'error'} class="instant-result-actions__message" role={shareState === 'error' ? 'alert' : 'status'}>{shareMessage}</p>
  {/if}

  <details class="instant-result-actions__continue">
    <summary>Continue in…</summary>
    <div class="instant-result-actions__links">
      <a href={smartDeckHref}>
        <strong>Smart Deck</strong>
        <span>Make global narrative and ordering changes using this generated version.</span>
      </a>
      <a href={diligenceHref}>
        <strong>Due Diligence</strong>
        <span>Change the audience or diligence lens without replacing the investor original.</span>
      </a>
      <a href={versionsHref}>
        <strong>Versions</strong>
        <span>Compare or restore persisted versions while retaining this exact identity.</span>
      </a>
    </div>
  </details>
</section>

<style>
  .instant-result-actions { display: grid; gap: .75rem; padding: .9rem 1rem; border: 1px solid var(--line); border-radius: 14px; background: rgba(15, 23, 42, .66); }
  .instant-result-actions__intro { display: grid; gap: .2rem; }
  .instant-result-actions__intro h4 { margin: 0; font-size: .98rem; }
  .instant-result-actions__intro p { margin: 0; color: var(--muted); font-size: .8rem; }
  .eyebrow { color: var(--accent); font-size: .68rem; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
  .instant-result-actions__primary { display: flex; flex-wrap: wrap; gap: .5rem; }
  .instant-result-actions__primary button,
  .instant-result-actions__primary a { min-height: 38px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--line); border-radius: 9px; padding: .55rem .8rem; color: var(--ink); background: rgba(255, 255, 255, .05); font: inherit; font-weight: 700; text-decoration: none; }
  .instant-result-actions__primary .primary { border-color: transparent; color: #fff; background: var(--accent); }
  .instant-result-actions__primary button:disabled { cursor: not-allowed; opacity: .5; }
  .instant-result-actions__share { display: grid; grid-template-columns: minmax(0, 1fr) auto auto auto; gap: .4rem; align-items: center; }
  .instant-result-actions__share input { min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: .55rem .65rem; color: var(--ink); background: rgba(2, 6, 23, .7); }
  .instant-result-actions__share button,
  .instant-result-actions__share a { min-height: 34px; display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: 8px; padding: .4rem .6rem; color: var(--ink); background: rgba(255, 255, 255, .05); font: inherit; font-size: .78rem; font-weight: 700; text-decoration: none; }
  .instant-result-actions__message { margin: 0; color: var(--muted); font-size: .78rem; }
  .instant-result-actions__message.error { color: #fca5a5; }
  .instant-result-actions__continue { border-top: 1px solid var(--line); padding-top: .65rem; }
  .instant-result-actions__continue summary { cursor: pointer; color: var(--ink); font-weight: 700; }
  .instant-result-actions__links { display: grid; gap: .45rem; margin-top: .55rem; }
  .instant-result-actions__links a { display: grid; gap: .15rem; padding: .55rem .65rem; border: 1px solid transparent; border-radius: 9px; color: inherit; text-decoration: none; }
  .instant-result-actions__links a:hover { border-color: var(--line); background: rgba(255, 255, 255, .04); }
  .instant-result-actions__links span { color: var(--muted); font-size: .78rem; line-height: 1.35; }
  @media (max-width: 720px) { .instant-result-actions__share { grid-template-columns: 1fr 1fr; } .instant-result-actions__share input { grid-column: 1 / -1; } }
</style>
