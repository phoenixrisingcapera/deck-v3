<script lang="ts">
  import { goto } from '$app/navigation';
  import { createEventDispatcher } from 'svelte';
  import { deckServiceClient } from '$lib/api/deckServiceClient';
  import DeckLoaderOverlay from '$components/DeckLoaderOverlay.svelte';
  import type { FirstDeckUploadRouteResponse } from '@deck-aistack-codes/shared';

  const dispatch = createEventDispatcher<{
    uploaded: FirstDeckUploadRouteResponse;
  }>();

  interface Props {
    disabled?: boolean;
    disabledReason?: string;
    redirectHref?: string | null;
  }

  let {
    disabled = false,
    disabledReason = 'Upload is temporarily unavailable.',
    redirectHref = null
  }: Props = $props();

  let selectedFile = $state<File | null>(null);
  let uploading = $state(false);
  let errorMsg = $state('');

  async function openRedirectFlow() {
    if (disabled) {
      errorMsg = disabledReason;
      return;
    }

    if (!redirectHref) {
      return;
    }

    await goto(redirectHref);
  }

  async function submitUpload() {
    if (disabled) {
      errorMsg = disabledReason;
      return;
    }

    if (!selectedFile) {
      errorMsg = 'Choose a PDF or PowerPoint file to begin the deck review workflow.';
      return;
    }

    uploading = true;
    errorMsg = '';

    try {
      const result = await deckServiceClient.uploadFirstDeck(selectedFile);
      dispatch('uploaded', result);
    } catch (error) {
      errorMsg = error instanceof Error ? error.message : 'Upload failed.';
    } finally {
      uploading = false;
    }
  }

  const uploadLoaderSteps = $derived([
    { label: 'Create deck', status: uploading ? 'running' : 'pending' },
    { label: 'Upload file', status: uploading ? 'running' : 'pending' },
    { label: 'Confirm upload', status: uploading ? 'running' : 'pending' },
    { label: 'Process deck', status: uploading ? 'running' : 'pending' },
    { label: 'Open workspace', status: 'pending' }
  ] satisfies Array<{ label: string; status: 'pending' | 'running' | 'complete' | 'failed' }>);
</script>

<section class="panel upload-card" id="first-deck-upload">
  <div class="upload-card__intro">
    <div class="eyebrow">Workspace intake</div>
    <h2>No decks yet</h2>
    <p class="muted">Upload your source deck to start the first review flow. The original file stays attached while AI prepares slide previews, review notes, and editable suggestions.</p>
  </div>

  {#if redirectHref}
    <button
      type="button"
      class="upload-card__dropzone upload-card__dropzone-button"
      data-disabled={disabled}
      onclick={openRedirectFlow}
    >
      <span class="upload-card__drop-label">Drop or load your file</span>
      <span class="upload-card__drop-copy">Open the intake flow to upload your deck and optional brand context</span>
    </button>
  {:else}
    <label class="upload-card__dropzone" data-disabled={disabled}>
      <input
        type="file"
        accept=".pdf,.ppt,.pptx,application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
        disabled={disabled}
        onchange={(event) => {
          const target = event.currentTarget as HTMLInputElement;
          selectedFile = target.files?.[0] ?? null;
        }}
      />
      <span class="upload-card__drop-label">Choose a PDF or PowerPoint deck</span>
      <span class="upload-card__drop-copy">Investor update, pitch deck, IC draft, diligence deck, or board presentation</span>
    </label>
  {/if}

  <div class="upload-card__meta">
    <div class="pill">Accepted now: PDF, PPT, PPTX</div>
    <div class="pill">Private workspace upload</div>
    <div class="pill">Reviewable AI output only</div>
  </div>

  {#if disabled}
    <p class="upload-card__notice">{disabledReason}</p>
  {/if}

  {#if selectedFile}
    <div class="pill upload-card__file">{selectedFile.name}</div>
  {/if}

  {#if errorMsg}
    <p class="upload-card__error">{errorMsg}</p>
  {/if}

  <div class="upload-card__actions">
    <button
      class="button"
      type="button"
      onclick={redirectHref ? openRedirectFlow : submitUpload}
      disabled={uploading || disabled}
    >
      {#if redirectHref}
        Open intake
      {:else}
        {uploading ? 'Uploading...' : 'Upload first deck'}
      {/if}
    </button>
    <a class="button secondary" href="/decks/new">Guided intake</a>
  </div>
</section>

<DeckLoaderOverlay
  open={uploading}
  title="Preparing your deck..."
  subtitle={selectedFile ? `Saving ${selectedFile.name} before extraction starts.` : 'Saving the source deck before extraction starts.'}
  statusLabel="Saving"
  progress={28}
  steps={uploadLoaderSteps}
/>

<style>
  .upload-card {
    padding: 1.5rem;
    display: grid;
    gap: 1.1rem;
  }

  .upload-card__intro {
    max-width: 58rem;
  }

  h2 {
    margin: 0.35rem 0 0;
    font-size: clamp(1.8rem, 2.6vw, 2.5rem);
    letter-spacing: -0.04em;
  }

  .upload-card__dropzone {
    width: 100%;
    display: grid;
    gap: 0.35rem;
    padding: 1.35rem;
    border: 1px dashed var(--line-strong);
    border-radius: 24px;
    background:
      radial-gradient(circle at top left, var(--accent-soft), transparent 28%),
      var(--surface-soft);
    color: var(--ink);
    position: relative;
    overflow: hidden;
  }

  .upload-card__dropzone-button {
    text-align: left;
  }

  .upload-card__dropzone[data-disabled='true'] {
    opacity: 0.7;
  }

  .upload-card__dropzone input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .upload-card__drop-label {
    font-size: 1.05rem;
    font-weight: 600;
  }

  .upload-card__drop-copy {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .upload-card__meta {
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .upload-card__file {
    width: fit-content;
  }

  .upload-card__notice {
    margin: 0;
    color: var(--muted);
  }

  .upload-card__error {
    margin: 0;
    color: var(--danger);
  }

  .upload-card__actions {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
  }

  @media (max-width: 720px) {
    .upload-card {
      padding: 1.15rem;
    }

    .upload-card__actions .button {
      width: 100%;
    }
  }
</style>
