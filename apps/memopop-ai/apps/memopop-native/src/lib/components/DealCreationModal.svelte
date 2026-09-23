<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport, type ApiError } from '$lib/transport';
  import { dealSlug } from '$lib/slugify';
  import type { Outline, MemoMode } from '$lib/types';

  interface Props {
    outline: Outline;
  }

  let { outline }: Props = $props();

  let isReady = $derived(flow.stage.kind === 'ready_to_run');

  let companyUrl = $state('');
  let companyName = $state('');
  let deckPath = $state<string | null>(null);
  let mode = $state<MemoMode>('consider');

  let submitting = $state(false);
  let errorMessage = $state<string | null>(null);

  let canSubmit = $derived(
    (companyUrl.trim().length > 0 || companyName.trim().length > 0)
  );

  function close() {
    flow.close();
  }

  function editInputs() {
    flow.editDeal();
    errorMessage = null;
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !isReady && !submitting) close();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !isReady && !submitting) close();
  }

  async function pickDeck() {
    const selected = await open({
      multiple: false,
      directory: false,
      title: 'Choose a pitch deck PDF',
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (typeof selected === 'string') {
      deckPath = selected;
    }
  }

  function clearDeck() {
    deckPath = null;
  }

  function deckFilename(path: string): string {
    return path.split('/').pop() ?? path;
  }

  // The directory name on disk has to be path-safe — no spaces, no fs-hostile
  // chars. dealSlug enforces "Mercury Bank" → "Mercury-Bank" while preserving
  // case (ChromaDB stays ChromaDB). Every place this name is used downstream
  // (output_dir, deal_dir, file watcher path) sees the same slugified form.
  function submit(e: Event) {
    e.preventDefault();
    if (!canSubmit) return;
    flow.markReady(outline, {
      companyUrl: companyUrl.trim(),
      companyName: dealSlug(companyName),
      deckPath,
      mode,
    });
  }

  // Live slug preview for the summary panel and the "ready to generate"
  // confirmation. Empty until the user has typed something to slugify.
  let slugPreview = $derived(dealSlug(companyName));

  function reviewSources() {
    if (flow.stage.kind !== 'ready_to_run') return;
    flow.startApprovingSources(flow.stage.outline, flow.stage.payload);
  }

  async function generate() {
    if (flow.stage.kind !== 'ready_to_run') return;
    if (!settings.repoPath) {
      errorMessage = 'Orchestrator path not set. Open Settings to anchor the repo.';
      return;
    }
    const payload = flow.stage.payload;
    const investmentType = outline.outline_type === 'fund_commitment' ? 'fund' : 'direct';
    const company = payload.companyName || payload.companyUrl;

    submitting = true;
    errorMessage = null;
    try {
      const result = await getTransport().request<{ job_id: string; status: string }>(
        'POST',
        '/memos',
        {
          repoPath: settings.repoPath,
          company_name: company,
          company_url: payload.companyUrl || undefined,
          investment_type: investmentType,
          memo_mode: payload.mode,
          firm: settings.activeFirm ?? undefined,
          deck_path: payload.deckPath ?? undefined,
          outline_name: outline.id,
        }
      );
      flow.markRunning(outline, payload, result.job_id);
    } catch (e) {
      const err = e as ApiError;
      errorMessage = err?.message ?? 'Failed to start memo generation';
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- The backdrop is decorative: it dims the page and catches a click-outside.
     The dialog is whichever .modal panel is showing, so the role, aria-modal
     and label live there. Escape closes via the window handler above. -->
<div class="backdrop" onclick={handleBackdropClick} role="presentation">
  {#if !isReady}
    <!-- display: contents — a <form> cannot carry role="dialog", and this
         wrapper generates no box so the flex layout is unchanged. -->
    <div class="dialog-shell" role="dialog" aria-modal="true" aria-labelledby="deal-modal-title" tabindex="-1">
    <form class="modal" onsubmit={submit}>
      <header class="modal-head">
        <div class="head-meta">
          <span class="badge {outline.outline_type === 'fund_commitment' ? 'fund' : 'direct'}">
            {outline.type_label}
          </span>
          <span class="firm-tag">{settings.activeFirm}</span>
        </div>
        <button type="button" class="close" onclick={close} aria-label="Close">
          ✕
        </button>
      </header>

      <h2 id="deal-modal-title">What are you analyzing?</h2>
      <p class="lede">
        Using the <strong>{outline.title}</strong> outline. We'll fill in
        defaults from the outline; you can override anything.
      </p>

      <div class="body">
        <div class="field mode-field">
          <span class="label">Memo mode</span>
          <div class="segmented">
            <button
              type="button"
              class={mode === 'consider' ? 'seg-btn seg-btn-active' : 'seg-btn'}
              onclick={() => (mode = 'consider')}
            >
              Evaluate
            </button>
            <button
              type="button"
              class={mode === 'justify' ? 'seg-btn seg-btn-active' : 'seg-btn'}
              onclick={() => (mode = 'justify')}
            >
              Justify
            </button>
          </div>
          <p class="mode-help">
            {#if mode === 'consider'}
              <strong>Evaluate mode</strong> directs research, writing, and editing
              agents to help you and your firm think through the decision of being
              lean-forward or proceeding with clarified caution.
            {:else}
              <strong>Justify mode</strong> directs research, writing, and editing
              agents to bolster the case for a decision you and your firm have
              (likely) made in good judgement, but are now in need of a memo to
              preserve the case.
            {/if}
          </p>
        </div>

        <label class="field">
          <span class="label">Company URL <span class="hint">(preferred)</span></span>
          <!-- svelte-ignore a11y_autofocus -->
          <!-- The rule targets autofocus on page load, which yanks a screen
          reader away from the document. In a modal it is the opposite:
          the WAI dialog pattern expects focus to move into the dialog on
          open, and this is the first field. Escape returns the user. -->
          <input
            type="url"
            bind:value={companyUrl}
            placeholder="https://example.com"
            autofocus
          />
        </label>

        <label class="field">
          <span class="label">Company name <span class="hint">(optional, helps disambiguate)</span></span>
          <input
            type="text"
            bind:value={companyName}
            placeholder="e.g., Stripe"
          />
          {#if slugPreview && slugPreview !== companyName.trim()}
            <span class="slug-preview">
              Saved as: <code>{slugPreview}/</code>
              <span class="slug-note">
                — spaces become hyphens for the deal directory.
              </span>
            </span>
          {/if}
        </label>

        <div class="field">
          <span class="label">Pitch deck <span class="hint">(optional)</span></span>
          {#if deckPath}
            <div class="deck-row">
              <code class="deck-path">{deckFilename(deckPath)}</code>
              <button type="button" class="link" onclick={clearDeck}>Remove</button>
            </div>
          {:else}
            <button type="button" class="ghost" onclick={pickDeck}>
              Choose a PDF…
            </button>
          {/if}
        </div>
      </div>

      <footer class="modal-foot">
        <button type="button" class="ghost" onclick={close}>Cancel</button>
        <button type="submit" class="cta" disabled={!canSubmit}>
          Review →
        </button>
      </footer>
    </form>
    </div>
  {:else}
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="deal-modal-title" tabindex="-1">
      <header class="modal-head">
        <h2 id="deal-modal-title">Ready to generate</h2>
        <button type="button" class="close" onclick={close} aria-label="Close">
          ✕
        </button>
      </header>

      <div class="body">
        <p class="lede">
          Confirm and we'll spin up the orchestrator. Generation typically takes
          10–15 minutes; you'll see live log output once the run starts.
        </p>

        <div class="summary">
          <h3>Captured</h3>
          <dl>
            <dt>Outline</dt>
            <dd>{outline.title}</dd>
            <dt>Firm</dt>
            <dd>{settings.activeFirm}</dd>
            {#if companyUrl.trim()}
              <dt>Company URL</dt>
              <dd><code>{companyUrl}</code></dd>
            {/if}
            {#if companyName.trim()}
              <dt>Company name</dt>
              <dd>
                {companyName}
                {#if slugPreview !== companyName.trim()}
                  <span class="slug-inline">
                    → saved as <code>{slugPreview}/</code>
                  </span>
                {/if}
              </dd>
            {/if}
            {#if deckPath}
              <dt>Pitch deck</dt>
              <dd><code>{deckFilename(deckPath)}</code></dd>
            {/if}
            <dt>Mode</dt>
            <dd>{mode === 'consider' ? 'Evaluate' : 'Justify'}</dd>
          </dl>
        </div>

        {#if errorMessage}
          <p class="error">{errorMessage}</p>
        {/if}
      </div>

      <footer class="modal-foot">
        <button type="button" class="ghost" onclick={editInputs} disabled={submitting}>
          ← Edit inputs
        </button>
        <!-- Curation is offered before the run, not after: a memo written
             against an unconstrained corpus can't be fixed by approving
             sources afterwards. Generating directly stays available for a
             first pass where there's nothing to curate yet. -->
        <button type="button" class="ghost" onclick={reviewSources} disabled={submitting}>
          Review sources first
        </button>
        <button type="button" class="cta" onclick={generate} disabled={submitting}>
          {submitting ? 'Starting…' : 'Generate memo →'}
        </button>
      </footer>
    </div>
  {/if}
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
    max-width: 560px;
    max-height: calc(100vh - 4rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(15, 15, 15, 0.25);
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem 0.5rem;
  }

  .head-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
  }

  .badge.direct {
    background: #ecfdf5;
    color: #065f46;
  }

  .badge.fund {
    background: #eff6ff;
    color: #1e40af;
  }

  .firm-tag {
    font-size: 0.75rem;
    color: #5b21b6;
    background: #f3e8ff;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-weight: 500;
  }

  h2 {
    font-size: 1.35rem;
    margin: 0 1.5rem 0.4rem;
  }

  .lede {
    color: #4b5563;
    margin: 0 1.5rem 1rem;
    line-height: 1.5;
    font-size: 0.95rem;
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
    overflow-y: auto;
    flex: 1;
    /* Without min-height: 0, a flex item refuses to shrink below its
       intrinsic content height — the body would push the footer below
       the modal's max-height and overflow:hidden would clip it. */
    min-height: 0;
  }

  .field {
    display: block;
    margin-bottom: 1.1rem;
    border: none;
    padding: 0;
  }

  .field.mode-field {
    margin-top: 0.75rem;
  }

  .label {
    display: block;
    font-weight: 500;
    margin-bottom: 0.4rem;
    font-size: 0.92rem;
    padding: 0;
  }

  .hint {
    color: #9ca3af;
    font-weight: 400;
    font-size: 0.85em;
  }

  .slug-preview {
    display: block;
    margin-top: 0.4rem;
    font-size: 0.78rem;
    color: #6b7280;
  }

  .slug-preview code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #f5f3ff;
    color: #5b21b6;
    padding: 0.05rem 0.35rem;
    border-radius: 3px;
    font-size: 0.95em;
  }

  .slug-note {
    font-style: italic;
    color: #9ca3af;
  }

  .slug-inline {
    display: inline;
    margin-left: 0.35rem;
    font-size: 0.85em;
    color: #6b7280;
  }

  .slug-inline code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #f5f3ff;
    color: #5b21b6;
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
  }

  input[type='text'],
  input[type='url'] {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    font: inherit;
    font-size: 1rem;
    background: white;
    color: #0f0f0f;
  }

  input[type='text']:focus,
  input[type='url']:focus {
    outline: 2px solid #c4b5fd;
    outline-offset: 0;
    border-color: #5b21b6;
  }

  .deck-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    background: #f9fafb;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
  }

  .error {
    color: #c0392b;
    font-size: 0.9rem;
    margin: 0.5rem 0 0;
    padding: 0.6rem 0.8rem;
    background: #fef2f2;
    border-radius: 6px;
    border: 1px solid #fca5a5;
  }

  .deck-path {
    flex: 1;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .segmented {
    display: flex;
    margin-top: 0.4rem;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    overflow: hidden;
    background: white;
  }

  .seg-btn {
    flex: 1;
    background: white;
    color: #4b5563;
    border: none;
    padding: 0.65rem 1rem;
    font: inherit;
    font-weight: 500;
    font-size: 0.95rem;
    cursor: pointer;
    transition: background 180ms ease, color 180ms ease;
    border-right: 1px solid #d1d5db;
  }

  .seg-btn:last-child {
    border-right: none;
  }

  .seg-btn:hover:not(.seg-btn-active) {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .seg-btn-active {
    background: #5b21b6;
    color: white;
  }

  .mode-help {
    margin: 0.6rem 0 0;
    padding: 0.6rem 0.85rem;
    font-size: 0.85rem;
    color: #4b5563;
    line-height: 1.5;
    background: #faf7ff;
    border-left: 3px solid #5b21b6;
    border-radius: 4px;
  }

  .mode-help strong {
    color: #5b21b6;
  }

  .summary {
    background: #f9fafb;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.5rem;
  }

  .summary h3 {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    margin: 0 0 0.75rem;
  }

  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content 1fr;
    column-gap: 1rem;
    row-gap: 0.5rem;
  }

  dt {
    color: #6b7280;
    font-size: 0.9rem;
  }

  dd {
    margin: 0;
    font-size: 0.95rem;
    word-break: break-word;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    background: white;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    border: 1px solid #e5e5e5;
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

  button.cta:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  button.link {
    background: transparent;
    border: none;
    padding: 0;
    color: #6b7280;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  button.link:hover {
    color: #5b21b6;
  }

  @media (prefers-color-scheme: dark) {
    .modal {
      background: #2a2a2c;
    }

    .lede {
      color: #d1d5db;
    }

    .badge.direct {
      background: #064e3b;
      color: #a7f3d0;
    }

    .badge.fund {
      background: #1e3a8a;
      color: #bfdbfe;
    }

    .firm-tag {
      background: #2a1f3d;
      color: #c4b5fd;
    }

    input[type='text'],
    input[type='url'] {
      background: #1c1c1e;
      color: #f6f6f6;
      border-color: #3a3a3c;
    }

    .deck-row {
      background: #1c1c1e;
      border-color: #3a3a3c;
    }

    .segmented {
      background: #1c1c1e;
      border-color: #3a3a3c;
    }

    .seg-btn {
      background: #1c1c1e;
      color: #d1d5db;
      border-right-color: #3a3a3c;
    }

    .seg-btn:hover:not(.seg-btn-active) {
      background: #2a2a2c;
      color: #f6f6f6;
    }

    .seg-btn-active {
      background: #a855f7;
      color: white;
    }

    .mode-help {
      background: #2a1f3d;
      color: #d1d5db;
      border-left-color: #a855f7;
    }

    .mode-help strong {
      color: #c4b5fd;
    }

    .summary {
      background: #1c1c1e;
    }

    .summary h3 {
      color: #9ca3af;
    }

    dt {
      color: #9ca3af;
    }

    code {
      background: #1c1c1e;
      border-color: #3a3a3c;
      color: #f6f6f6;
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

    button.link {
      color: #9ca3af;
    }

    button.link:hover {
      color: #c4b5fd;
    }
  }
</style>
