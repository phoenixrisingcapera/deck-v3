<script lang="ts">
  import type { WorkspaceDashboardResponse } from '$lib/types/workspace-dashboard';

  interface Props {
    dashboard: WorkspaceDashboardResponse;
  }

  let { dashboard }: Props = $props();

  function readableStatus(status: string) {
    return status.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
</script>

<section class="returning-dashboard">
  {#if dashboard.latestDeck}
    <a class="panel latest-deck" href={`/decks/${dashboard.latestDeck.id}/smart-deck`}>
      <div class="eyebrow">Continue</div>
      <h3>{dashboard.latestDeck.title}</h3>
      <p class="muted">{readableStatus(dashboard.latestDeck.status)}</p>
    </a>
  {/if}

  {#if dashboard.decks?.length}
    <div class="panel decks-panel">
      <div class="eyebrow">All decks</div>
      <div class="decks-list">
        {#each dashboard.decks as deck}
          <a class="deck-row" href={`/decks/${deck.id}/smart-deck`}>
            <strong>{deck.title}</strong>
            <small>{readableStatus(deck.status)}</small>
          </a>
        {/each}
      </div>
    </div>
  {/if}
</section>

<style>
  .returning-dashboard { display: grid; gap: 12px; width: 100%; }

  .latest-deck { padding: 24px; display: grid; gap: 6px; }
  .latest-deck h3 { font-size: 16px; }

  .decks-panel { padding: 16px; display: grid; gap: 10px; }
  .decks-list { display: grid; gap: 2px; }

  .deck-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 10px; border-radius: var(--radius);
    transition: background 0.1s;
  }
  .deck-row:hover { background: var(--surface-hover); }
  .deck-row strong { font-size: 13px; }
  .deck-row small { font-size: 11px; color: var(--text-muted); text-transform: capitalize; }
</style>
