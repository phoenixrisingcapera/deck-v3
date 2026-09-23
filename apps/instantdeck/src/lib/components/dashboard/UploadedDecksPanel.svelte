<script lang="ts">
  import DeckCard from '$components/DeckCard.svelte';
  import { safeDashboardImageUrl } from '$lib/dashboard/imagePolicy';
  import { dashboardStatusToCardStatus } from '$lib/dashboard/status';
  import type { DashboardDeckSummary } from '$lib/types/workspace-dashboard';
  import type { Deck } from '$types/domain';

  interface Props {
    decks: DashboardDeckSummary[];
    workspaceId: string;
  }

  let { decks, workspaceId }: Props = $props();

  function deckForCard(deck: DashboardDeckSummary): Deck {
    // DeckCard uses the broader domain Deck shape, so this adapter maps the dashboard API contract into that UI contract.
    return {
      id: deck.id,
      // Use the workspace id supplied by the page loader instead of inventing one inside the card adapter.
      workspaceId,
      title: deck.title,
      audience: deck.audience,
      purpose: deck.purpose,
      // Normalize dashboard workflow states into the statuses supported by the shared DeckCard/StatusBadge UI.
      status: dashboardStatusToCardStatus(deck.status),
      createdAt: deck.updatedAt,
      updatedAt: deck.updatedAt,
      summary: deck.description,
      thumbnailUrl: safeDashboardImageUrl(deck.thumbnailUrl)
    };
  }
</script>

<section class="panel uploaded-decks">
  <div class="section-heading">
    <div>
      <div class="eyebrow">Library</div>
      <h2>Uploaded decks</h2>
    </div>
    <a class="link" href="/decks">View all</a>
  </div>

  {#if decks.length > 0}
    <div class="deck-grid">
      <!-- Keep the panel short; the full deck library is available from the View all link. -->
      {#each decks.slice(0, 3) as deck}
        <DeckCard deck={deckForCard(deck)} />
      {/each}
    </div>
  {:else}
    <div class="empty-state">
      <strong>No decks uploaded yet</strong>
      <a class="button" href="/decks/new">Upload your first deck</a>
    </div>
  {/if}
</section>

<style>
  .uploaded-decks {
    padding: 1.25rem;
  }

  .section-heading {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  h2 {
    margin: 0.2rem 0 0;
  }

  .deck-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.85rem;
  }

  .empty-state {
    min-height: 12rem;
    display: grid;
    place-content: center;
    gap: 1rem;
    text-align: center;
    border: 1px dashed var(--line);
    border-radius: 8px;
  }

  .link {
    color: var(--muted);
    font-weight: 700;
  }
</style>
