<script lang="ts">
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport, type ApiError } from '$lib/transport';
  import { slugify } from '$lib/slugify';
  import type { Outline, CreateFirmResult } from '$lib/types';

  interface Props {
    outline: Outline;
  }

  let { outline }: Props = $props();

  let firmName = $state('');
  let submitting = $state(false);
  let errorMessage = $state<string | null>(null);

  let trimmed = $derived(firmName.trim());
  let slugPreview = $derived(trimmed ? slugify(trimmed) : '');
  let canSubmit = $derived(trimmed.length > 0 && slugPreview.length > 0 && !submitting);

  function close() {
    flow.close();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }

  async function submit(e: Event) {
    e.preventDefault();
    if (!canSubmit || !settings.repoPath) return;

    submitting = true;
    errorMessage = null;

    try {
      const result = await getTransport().request<CreateFirmResult>(
        'POST',
        '/actions/create-firm',
        {
          repoPath: settings.repoPath,
          conventionalName: trimmed,
        }
      );

      await settings.setActiveFirm(result.slug);
      flow.proceedToDeal(outline);
    } catch (e) {
      const err = e as ApiError;
      errorMessage = err.message ?? 'Failed to create firm';
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- The backdrop is decorative: it exists to dim the page and to catch a
     click-outside. The dialog is the .modal panel below, which is where the
     dialog role, aria-modal and the label now live. Marking this
     presentational is what makes the click-without-keydown correct rather
     than suppressed — Escape closes via the window handler above. -->
<div class="backdrop" onclick={handleBackdropClick} role="presentation">
  <!-- The dialog role belongs on a generic container, not on <form> (a form
       is not an interactive element and cannot carry it). `display: contents`
       means this wrapper generates no box, so the .modal flex layout is
       untouched. -->
  <div class="dialog-shell" role="dialog" aria-modal="true" aria-labelledby="firm-modal-title" tabindex="-1">
  <form class="modal" onsubmit={submit}>
    <header class="modal-head">
      <h2 id="firm-modal-title">Set up your firm</h2>
      <button type="button" class="close" onclick={close} aria-label="Close">
        ✕
      </button>
    </header>

    <div class="body">
      <p class="lede">
        We'll create a private space for your work. Everything you generate
        stays in <code>io/&#123;your-firm&#125;/</code> and is automatically
        marked private — no risk of committing client data to a public repo.
      </p>

      <label class="field">
        <span class="label">What's your firm called?</span>
        <!-- svelte-ignore a11y_autofocus -->
        <!-- The rule targets autofocus on page load, which yanks a screen
        reader away from the document. In a modal it is the opposite:
        the WAI dialog pattern expects focus to move into the dialog on
        open, and this is the first field. Escape returns the user. -->
        <input
          type="text"
          bind:value={firmName}
          placeholder="e.g., Hypernova"
          autofocus
          disabled={submitting}
        />
      </label>

      <p class="tip">
        <strong>Tip:</strong> The conventional name, often in short form. Often
        not the legal name or even the longer name. e.g., <em>"Hypernova"</em>
        instead of <em>"Hypernova Capital"</em>.
      </p>

      {#if slugPreview}
        <div class="preview">
          <span class="preview-label">Will create:</span>
          <code>io/{slugPreview}/</code>
        </div>
      {/if}

      {#if errorMessage}
        <p class="error">{errorMessage}</p>
      {/if}
    </div>

    <footer class="modal-foot">
      <button type="button" class="ghost" onclick={close} disabled={submitting}>
        Cancel
      </button>
      <button type="submit" class="cta" disabled={!canSubmit}>
        {submitting ? 'Creating…' : 'Continue →'}
      </button>
    </footer>
  </form>
  </div>
</div>

<style>
  /* Generates no box — purely a semantic container for the dialog role. */
  .dialog-shell {
    display: contents;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 15, 15, 0.4);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    z-index: 110;
  }

  .modal {
    background: white;
    border-radius: 14px;
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 50px rgba(15, 15, 15, 0.25);
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem 0.5rem;
  }

  h2 {
    font-size: 1.25rem;
    margin: 0;
  }

  .close {
    background: transparent;
    border: none;
    color: #6b7280;
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  .close:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .body {
    padding: 0.75rem 1.5rem 1rem;
  }

  .lede {
    color: #4b5563;
    line-height: 1.5;
    margin: 0 0 1.25rem;
    font-size: 0.95rem;
  }

  .field {
    display: block;
    margin-bottom: 0.5rem;
  }

  .label {
    display: block;
    font-weight: 500;
    margin-bottom: 0.4rem;
    font-size: 0.95rem;
  }

  input[type='text'] {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    font: inherit;
    font-size: 1rem;
    background: white;
    color: #0f0f0f;
  }

  input[type='text']:focus {
    outline: 2px solid #c4b5fd;
    outline-offset: 0;
    border-color: #5b21b6;
  }

  .tip {
    font-size: 0.85rem;
    color: #6b7280;
    margin: 0.5rem 0 1rem;
    line-height: 1.45;
  }

  .preview {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 0.8rem;
    background: #f5f3ff;
    border-radius: 8px;
    border: 1px solid #ddd6fe;
    margin-bottom: 1rem;
  }

  .preview-label {
    font-size: 0.85rem;
    color: #5b21b6;
    font-weight: 500;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: white;
    border: 1px solid #ddd6fe;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.9em;
  }

  .lede code {
    background: #f3f4f6;
    border: none;
  }

  .error {
    color: #c0392b;
    font-size: 0.9rem;
    margin: 0;
    padding: 0.6rem 0.8rem;
    background: #fef2f2;
    border-radius: 6px;
    border: 1px solid #fca5a5;
  }

  .modal-foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 1rem 1.5rem 1.25rem;
    border-top: 1px solid #f3f4f6;
  }

  button.ghost {
    background: transparent;
    border: 1px solid #d1d5db;
    color: #4b5563;
    padding: 0.55rem 1rem;
    border-radius: 8px;
    font: inherit;
    cursor: pointer;
  }

  button.ghost:hover:not(:disabled) {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  button.cta {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.55rem 1.1rem;
    border-radius: 8px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  button.cta:hover:not(:disabled) {
    background: #4c1d95;
  }

  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  @media (prefers-color-scheme: dark) {
    .modal {
      background: #2a2a2c;
    }

    .lede {
      color: #d1d5db;
    }

    .lede code {
      background: #1c1c1e;
    }

    input[type='text'] {
      background: #1c1c1e;
      color: #f6f6f6;
      border-color: #3a3a3c;
    }

    .tip {
      color: #9ca3af;
    }

    .preview {
      background: #2a1f3d;
      border-color: #5b21b6;
    }

    .preview-label {
      color: #c4b5fd;
    }

    code {
      background: #1c1c1e;
      border-color: #5b21b6;
      color: #f6f6f6;
    }

    .error {
      background: #2a1c1c;
      border-color: #7f1d1d;
    }

    .close {
      color: #9ca3af;
    }

    .close:hover {
      background: #1c1c1e;
      color: #f6f6f6;
    }

    .modal-foot {
      border-top-color: #3a3a3c;
    }

    button.ghost {
      border-color: #3a3a3c;
      color: #d1d5db;
    }

    button.ghost:hover:not(:disabled) {
      background: #1c1c1e;
      color: #f6f6f6;
    }
  }
</style>
