<script lang="ts">
  import { onMount } from 'svelte';
  import {
    archiveDeckMedia,
    listDeckMedia,
    retryDeckMedia,
    uploadDeckMedia,
    type DeckMediaAsset,
    type DeckMediaRole
  } from '$lib/api/deckMedia';

  interface Props { deckId: string; }
  let { deckId }: Props = $props();
  let items = $state<DeckMediaAsset[]>([]);
  let loadState = $state<'loading' | 'ready' | 'uploading' | 'error'>('loading');
  let message = $state('');
  let role = $state<DeckMediaRole>('logo');
  let fileInput: HTMLInputElement | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  async function refresh() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
    try {
      const payload = await listDeckMedia(deckId);
      items = payload.items;
      loadState = 'ready';
      const pending = items.some((item) => item.status === 'queued' || item.status === 'processing');
      if (pending) {
        pollTimer = setTimeout(() => void refresh(), 3000);
      }
    } catch (error) {
      loadState = 'error';
      message = error instanceof Error ? error.message : 'Media library could not be loaded.';
    }
  }

  onMount(() => {
    void refresh();
    return () => { if (pollTimer) clearTimeout(pollTimer); };
  });

  async function upload(file: File) {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      message = 'Choose a PNG, JPEG, or WebP image.';
      loadState = 'error';
      return;
    }
    loadState = 'uploading';
    message = '';
    try {
      await uploadDeckMedia(deckId, file, role);
      if (fileInput) fileInput.value = '';
      await refresh();
    } catch (error) {
      loadState = 'error';
      message = error instanceof Error ? error.message : 'Media upload failed.';
    }
  }

  async function retry(item: DeckMediaAsset) {
    try { await retryDeckMedia(deckId, item.id); await refresh(); }
    catch (error) { message = error instanceof Error ? error.message : 'Media processing could not be retried.'; loadState = 'error'; }
  }

  async function archive(item: DeckMediaAsset) {
    try { await archiveDeckMedia(deckId, item.id); items = items.filter((candidate) => candidate.id !== item.id); }
    catch (error) { message = error instanceof Error ? error.message : 'Media could not be archived.'; loadState = 'error'; }
  }
</script>

<section class="tool-panel">
  <header><span>Deck media</span><h2>Media library</h2><p>Upload logos, board pictures, and deck visuals for reviewable generation and editing.</p></header>
  <label class="role-label" for="smart-deck-media-role"><span>Media type</span><select id="smart-deck-media-role" name="mediaRole" bind:value={role}><option value="logo">Logo</option><option value="board_picture">Board picture</option><option value="deck_picture">Deck picture</option></select></label>
  <label class="upload-drop" for="smart-deck-media-upload"><strong>{loadState === 'uploading' ? 'Uploading...' : 'Add media'}</strong><small>PNG, JPEG, or WebP up to 10 MB</small><input id="smart-deck-media-upload" name="mediaFile" bind:this={fileInput} type="file" accept="image/png,image/jpeg,image/webp" disabled={loadState === 'uploading'} onchange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
  {#if loadState === 'loading'}<p role="status">Loading media library...</p>{/if}
  {#if message}<p class="error" role="status">{message}</p>{/if}
  {#if loadState !== 'loading' && items.length === 0}<p class="empty">No media added yet.</p>{/if}
  <div class="media-list">
    {#each items as item (item.id)}
      <article class="media-card">
        {#if item.thumbnailUrl}<img src={item.thumbnailUrl} alt={item.altText || item.label || item.originalFilename} />{:else}<div class="media-placeholder">{item.role === 'logo' ? 'Logo' : 'Image'}</div>{/if}
        <div><strong>{item.label || item.originalFilename}</strong><small>{item.role.replace('_', ' ')} · {item.status.replace('_', ' ')}</small>{#if item.errorMessage}<small class="error">{item.errorMessage}</small>{/if}</div>
        <div class="media-actions">{#if item.status === 'failed_retryable' || item.status === 'failed_final'}<button type="button" onclick={() => void retry(item)}>Retry</button>{/if}<button type="button" class="quiet" onclick={() => void archive(item)}>Archive</button></div>
      </article>
    {/each}
  </div>
</section>

<style>
  .tool-panel, header, .role-label, .media-list, .media-card { display: grid; gap: .7rem; }
  header > span { color: #38bdf8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p { margin: 0; } header p, small, .empty { color: #94a3b8; line-height: 1.45; }
  .role-label span { color: #cbd5e1; font-size: .78rem; font-weight: 700; }
  select { width: 100%; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; background: rgba(15,23,42,.9); color: #f8fafc; padding: .7rem; font: inherit; }
  .upload-drop { display: grid; gap: .25rem; border: 1px dashed rgba(56,189,248,.55); border-radius: 12px; padding: .85rem; cursor: pointer; background: rgba(15,23,42,.72); }
  .upload-drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
  .media-card { grid-template-columns: 52px minmax(0,1fr); border: 1px solid rgba(255,255,255,.08); border-radius: 12px; padding: .6rem; background: rgba(15,23,42,.72); }
  .media-card img, .media-placeholder { width: 52px; height: 42px; border-radius: 7px; object-fit: cover; background: rgba(255,255,255,.08); color: #cbd5e1; display: grid; place-items: center; font-size: .68rem; }
  .media-card > div:nth-child(2) { min-width: 0; display: grid; gap: .18rem; } .media-card strong { color: #f8fafc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .media-card small { font-size: .72rem; }
  .media-actions { grid-column: 1 / -1; display: flex; gap: .45rem; } button { border: 0; border-radius: 8px; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; padding: .42rem .6rem; font: inherit; font-size: .74rem; font-weight: 700; cursor: pointer; } button.quiet { background: rgba(255,255,255,.08); } .error { color: #fca5a5; }
</style>
