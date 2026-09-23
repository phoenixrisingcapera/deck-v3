<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    deckId: string;
    slideId?: string | null;
    cacheKey?: string | null;
    persistedSummary?: string | null;
    title?: string;
    content?: Snippet;
  }

  type SummaryResponse = {
    summary?: string | null;
  };

  let {
    deckId,
    slideId = null,
    cacheKey = null,
    persistedSummary = null,
    title = 'Details',
    content
  }: Props = $props();

  let open = $state(false);
  let summaries = $state<Record<string, string>>({});
  let loadedKey = $state<string | null>(null);
  let loadingKeys = $state<Record<string, boolean>>({});
  let failedKey = $state<string | null>(null);
  let error = $state('');

  const visibleSummary = $derived(
    cacheKey ? persistedSummary?.trim() || summaries[cacheKey] || '' : ''
  );
  const contextChanged = $derived(Boolean(
    open && cacheKey && loadedKey !== cacheKey && !loadingKeys[cacheKey] && failedKey !== cacheKey
  ));
  const loading = $derived(Boolean(cacheKey && loadingKeys[cacheKey]));

  async function loadDetails(
    requestedKey: string,
    requestedDeckId: string,
    requestedSlideId: string,
    persisted: string | null
  ) {
    const savedSummary = persisted?.trim() ?? '';
    if (savedSummary) {
      summaries = { ...summaries, [requestedKey]: savedSummary };
      loadedKey = requestedKey;
      failedKey = null;
      error = '';
      return;
    }
    if (summaries[requestedKey]) {
      loadedKey = requestedKey;
      failedKey = null;
      error = '';
      return;
    }
    if (loadingKeys[requestedKey]) return;

    loadingKeys = { ...loadingKeys, [requestedKey]: true };
    failedKey = null;
    error = '';
    try {
      const response = await fetch(
        `/api/decks/${encodeURIComponent(requestedDeckId)}/slides/${encodeURIComponent(requestedSlideId)}/smart-edit/summary`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ force: false })
        }
      );
      const payload = (await response.json().catch(() => null)) as SummaryResponse | { message?: string; detail?: string } | null;
      if (!response.ok) {
        const message = payload && 'message' in payload
          ? payload.message
          : payload && 'detail' in payload
            ? payload.detail
            : null;
        throw new Error(message || 'Details could not be generated.');
      }
      const summary = payload && 'summary' in payload ? payload.summary?.trim() ?? '' : '';
      if (!summary) throw new Error('Details generation returned no summary.');
      summaries = { ...summaries, [requestedKey]: summary };
      if (cacheKey === requestedKey) {
        loadedKey = requestedKey;
        failedKey = null;
        error = '';
      }
    } catch (caught) {
      if (cacheKey === requestedKey) {
        failedKey = requestedKey;
        error = caught instanceof Error ? caught.message : 'Details could not be generated.';
      }
    } finally {
      const { [requestedKey]: _completed, ...remainingLoadingKeys } = loadingKeys;
      loadingKeys = remainingLoadingKeys;
    }
  }

  function toggleDetails() {
    open = !open;
  }

  function retryDetails() {
    if (!cacheKey || !slideId) return;
    failedKey = null;
    error = '';
    void loadDetails(cacheKey, deckId, slideId, null);
  }

  $effect(() => {
    const requestedKey = cacheKey;
    const requestedSlideId = slideId;
    const persisted = persistedSummary;
    if (!open || !requestedKey || !requestedSlideId) return;
    if (failedKey === requestedKey) return;
    if (loadedKey === requestedKey && (summaries[requestedKey] || persisted?.trim())) return;
    void loadDetails(requestedKey, deckId, requestedSlideId, persisted);
  });
</script>

<section class="global-deck-details" data-deck-region="details">
  <button
    class="details-toggle"
    type="button"
    aria-expanded={open}
    aria-controls="global-deck-details-content"
    onclick={toggleDetails}
  >
    <span>
      <strong>{title}</strong>
      <small>{open ? 'Hide summary and supporting tools' : 'Open summary and supporting tools'}</small>
    </span>
    <span class="toggle-mark" aria-hidden="true">{open ? '−' : '+'}</span>
  </button>

  {#if open}
    <div id="global-deck-details-content" class="details-content">
      {#if !slideId || !cacheKey}
        <p class="details-state">Select a slide to request details.</p>
      {:else if loading || contextChanged}
        <p class="details-state" role="status">Generating details for the selected slide...</p>
      {:else if error}
        <div class="details-error" role="alert">
          <p>{error}</p>
          <button type="button" onclick={retryDetails}>Try again</button>
        </div>
      {:else if visibleSummary}
        <div class="generated-summary">
          <span>AI slide summary</span>
          <p>{visibleSummary}</p>
        </div>
      {/if}

      {#if content}
        <div class="surface-details">
          {@render content()}
        </div>
      {/if}
    </div>
  {/if}
</section>

<style>
  .global-deck-details {
    width: min(100%, 1040px);
    justify-self: center;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.88);
    overflow: hidden;
  }

  .details-toggle {
    width: 100%;
    min-height: 3.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.8rem 1rem;
    border: 0;
    background: transparent;
    color: var(--ink-strong);
    text-align: left;
    cursor: pointer;
  }

  .details-toggle > span:first-child {
    display: grid;
    gap: 0.2rem;
  }

  .details-toggle small,
  .details-state,
  .generated-summary span {
    color: var(--muted);
  }

  .toggle-mark {
    width: 2rem;
    height: 2rem;
    display: grid;
    place-items: center;
    border: 1px solid var(--line);
    border-radius: 999px;
    color: var(--accent);
    font-size: 1.1rem;
  }

  .details-content {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-top: 1px solid var(--line);
  }

  .details-state,
  .details-error p,
  .generated-summary p {
    margin: 0;
  }

  .generated-summary {
    display: grid;
    gap: 0.45rem;
    padding: 0.9rem;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.035);
  }

  .generated-summary span {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .generated-summary p {
    line-height: 1.6;
  }

  .details-error {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    color: #fca5a5;
  }

  .details-error button {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--line);
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.04);
    color: var(--ink-strong);
  }

  .surface-details {
    min-width: 0;
  }
</style>
