<script lang="ts">
  import ChangeReviewCard from '$components/smart-edit/ChangeReviewCard.svelte';
  import type { AdaptationSuggestion, DeckSlideRevision, SmartEditSuggestion } from '$types/domain';

  interface Props {
    deckId: string;
    suggestions: (AdaptationSuggestion | SmartEditSuggestion)[];
    revisions: DeckSlideRevision[];
  }

  let { deckId, suggestions, revisions }: Props = $props();
  let reviewSuggestions = $state<(AdaptationSuggestion | SmartEditSuggestion)[]>([]);
  let savingSuggestionId = $state<string | null>(null);
  let reviewError = $state('');
  let activeFilter = $state<'all' | 'pending' | 'accepted' | 'rejected' | 'high-risk'>('all');

  $effect(() => {
    reviewSuggestions = suggestions;
  });

  const filteredSuggestions = $derived(
    reviewSuggestions.filter((suggestion) => {
      if (activeFilter === 'all') return true;
      if (activeFilter === 'high-risk') return isSmartEditSuggestion(suggestion) && suggestion.riskLevel === 'high';
      return suggestion.status === activeFilter;
    })
  );
  const selectedSuggestion = $derived(filteredSuggestions[0] ?? null);
  const selectedRevision = $derived(
    selectedSuggestion ? revisions.find((revision) => revision.blockId === selectedSuggestion.blockId) ?? null : null
  );

  function isSmartEditSuggestion(suggestion: AdaptationSuggestion | SmartEditSuggestion): suggestion is SmartEditSuggestion {
    return 'originalText' in suggestion;
  }

  function readErrorMessage(payload: unknown, fallback: string) {
    if (!payload || typeof payload !== 'object') return fallback;
    const record = payload as Record<string, unknown>;
    if (typeof record.message === 'string') return record.message;
    if (typeof record.detail === 'string') return record.detail;
    if (typeof record.error === 'string') return record.error;
    return fallback;
  }

  function readStatus(payload: unknown, fallback: string) {
    if (!payload || typeof payload !== 'object') return fallback;
    const record = payload as Record<string, unknown>;
    const suggestion = record.suggestion && typeof record.suggestion === 'object' ? (record.suggestion as Record<string, unknown>) : record;
    return String(suggestion.status ?? fallback);
  }

  function editHrefFor(suggestion: AdaptationSuggestion | SmartEditSuggestion) {
    if (!suggestion.slideId || !suggestion.blockId) return null;
    const params = new URLSearchParams({
      slide: suggestion.slideId,
      block: suggestion.blockId,
      instruction: suggestion.suggestedText
    });
    return `/decks/${deckId}/smart-edit?${params.toString()}`;
  }

  async function decideSuggestion(suggestion: AdaptationSuggestion | SmartEditSuggestion, status: 'accepted' | 'rejected') {
    savingSuggestionId = suggestion.id;
    reviewError = '';
    const path = isSmartEditSuggestion(suggestion)
      ? `/api/decks/${deckId}/smart-edit/suggestions/${suggestion.id}`
      : `/api/decks/${deckId}/suggestions/${suggestion.id}`;

    try {
      const response = await fetch(path, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ status })
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(readErrorMessage(payload, 'Suggestion decision failed.'));
      }
      const nextStatus = readStatus(payload, status);
      reviewSuggestions = reviewSuggestions.map((item) =>
        item.id === suggestion.id ? { ...item, status: nextStatus as typeof item.status } : item
      );
    } catch (error) {
      reviewError = error instanceof Error ? error.message : 'Suggestion decision failed.';
    } finally {
      savingSuggestionId = null;
    }
  }
</script>

<section class="panel review-panel">
  <div class="review-grid">
    <aside class="filters">
      <div class="eyebrow">Filters</div>
      <div class="filter-list">
        <button class:active={activeFilter === 'all'} class="filter" type="button" onclick={() => (activeFilter = 'all')}>All</button>
        <button class:active={activeFilter === 'pending'} class="filter" type="button" onclick={() => (activeFilter = 'pending')}>Pending</button>
        <button class:active={activeFilter === 'accepted'} class="filter" type="button" onclick={() => (activeFilter = 'accepted')}>Accepted</button>
        <button class:active={activeFilter === 'rejected'} class="filter" type="button" onclick={() => (activeFilter = 'rejected')}>Rejected</button>
        <button class:active={activeFilter === 'high-risk'} class="filter" type="button" onclick={() => (activeFilter = 'high-risk')}>High risk</button>
      </div>
      <div class="category-list">
        <strong>By category</strong>
        <!-- Category is not present in the canonical suggestion contract. These
             labels remain informational until the backend returns that field. -->
        <span title="Category filtering is not available">Market</span>
        <span title="Category filtering is not available">Evidence</span>
        <span title="Category filtering is not available">Financials</span>
        <span title="Category filtering is not available">Narrative</span>
      </div>
    </aside>

    <div class="change-list">
      <div class="eyebrow">Change list</div>
      {#if reviewError}
        <p class="review-error">{reviewError}</p>
      {/if}
      {#each filteredSuggestions as suggestion}
        <ChangeReviewCard
          title={'title' in suggestion ? suggestion.title : 'Smart Edit Suggestion'}
          sourceType={'title' in suggestion ? 'adaptation suggestion' : 'smart edit'}
          originalText={'originalText' in suggestion ? suggestion.originalText : ''}
          suggestedText={suggestion.suggestedText}
          finalText={selectedRevision && selectedRevision.blockId === suggestion.blockId ? selectedRevision.nextText : null}
          reason={suggestion.reason}
          riskLevel={'riskLevel' in suggestion ? suggestion.riskLevel : 'medium'}
          status={suggestion.status}
          saving={savingSuggestionId === suggestion.id}
          editHref={editHrefFor(suggestion)}
          onAccept={() => decideSuggestion(suggestion, 'accepted')}
          onReject={() => decideSuggestion(suggestion, 'rejected')}
        />
      {/each}
      {#if filteredSuggestions.length === 0}
        <p class="muted">No changes match this filter.</p>
      {/if}
    </div>

    <aside class="detail-panel">
      <div class="eyebrow">Detail preview</div>
      {#if selectedSuggestion}
        <strong>{'title' in selectedSuggestion ? selectedSuggestion.title : 'Selected Smart Edit'}</strong>
        <div class="detail-card">
          <span class="detail-label">Suggested</span>
          <p>{selectedSuggestion.suggestedText}</p>
        </div>
        {#if 'originalText' in selectedSuggestion}
          <div class="detail-card">
            <span class="detail-label">Original</span>
            <p>{selectedSuggestion.originalText}</p>
          </div>
        {/if}
        {#if selectedRevision}
          <div class="detail-card">
            <span class="detail-label">Applied revision</span>
            <p>{selectedRevision.nextText}</p>
          </div>
        {/if}
        <div class="detail-card">
          <span class="detail-label">Reason</span>
          <p>{selectedSuggestion.reason}</p>
        </div>
      {:else}
        <p class="muted">No change items are available for this deck yet.</p>
      {/if}
    </aside>
  </div>
</section>

<style>
  .review-panel {
    padding: 1rem;
  }

  .review-grid {
    display: grid;
    grid-template-columns: 220px minmax(0, 1.2fr) minmax(280px, 0.8fr);
    gap: 1rem;
  }

  .filters,
  .change-list,
  .detail-panel {
    display: grid;
    align-content: start;
    gap: 0.9rem;
  }

  .filter-list,
  .category-list {
    display: grid;
    gap: 0.55rem;
  }

  .filter {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.65rem 0.9rem;
    background: transparent;
    color: var(--ink-soft);
    text-align: left;
  }

  .filter.active {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(232, 187, 108, 0.08);
  }

  .review-error {
    margin: 0;
    color: var(--danger);
    font-size: 0.9rem;
  }

  .category-list span,
  .detail-card {
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 0.85rem;
    background: rgba(255,255,255,0.03);
  }

  .detail-card p {
    margin: 0.4rem 0 0;
    line-height: 1.6;
  }

  .detail-label {
    color: var(--muted);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  @media (max-width: 1100px) {
    .review-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
