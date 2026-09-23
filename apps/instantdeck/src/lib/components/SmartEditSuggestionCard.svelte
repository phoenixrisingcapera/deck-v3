<script lang="ts">
  import RiskBadge from '$components/RiskBadge.svelte';
  import StatusBadge from '$components/StatusBadge.svelte';
  import type { SmartEditSuggestion } from '$types/domain';

  interface Props {
    deckId: string;
    suggestion: SmartEditSuggestion;
  }

  let { deckId, suggestion }: Props = $props();
</script>

<article class="panel smart-card">
  <div class="topline">
    <StatusBadge status={suggestion.status} />
    <RiskBadge level={suggestion.riskLevel} />
  </div>
  <p class="muted">{suggestion.reason}</p>
  <div class="text-pair">
    <div>
      <strong>Original</strong>
      <p>{suggestion.originalText}</p>
    </div>
    <div>
      <strong>Suggestion</strong>
      <p>{suggestion.suggestedText}</p>
    </div>
  </div>
  <div class="actions">
    <form method="POST" action={`/api/decks/${deckId}/smart-edit/suggestions/${suggestion.id}?status=accepted`}>
      <button class="button" type="submit">Accept</button>
    </form>
    <form method="POST" action={`/api/decks/${deckId}/smart-edit/suggestions/${suggestion.id}?status=rejected`}>
      <button class="button secondary" type="submit">Reject</button>
    </form>
  </div>
</article>

<style>
  .smart-card {
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
  }

  .topline,
  .actions {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .text-pair {
    display: grid;
    gap: 0.75rem;
  }

  .text-pair > div {
    padding: 0.85rem;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.04);
  }

  p {
    margin: 0.35rem 0 0;
  }
</style>
