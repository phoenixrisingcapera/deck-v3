<script lang="ts">
  import { safeDashboardImageUrl } from '$lib/dashboard/imagePolicy';
  import { formatRelativeTime } from '$lib/dashboard/time';
  import type { DashboardRecentDeck } from '$lib/types/workspace-dashboard';

  interface Props {
    decks: DashboardRecentDeck[];
  }

  let { decks }: Props = $props();

  function statusTone(status: DashboardRecentDeck['status']) {
    if (status === 'ready_to_review') return 'amber';
    if (status === 'preparing') return 'blue';
    if (status === 'failed') return 'rose';
    return 'green';
  }
</script>

<section class="panel dashboard-card">
  <div class="dashboard-card__head">
    <h2>Recent Decks</h2>
    <a href="/decks">View all decks →</a>
  </div>

  <div class="recent-decks">
    {#each decks as deck}
      {@const preview = safeDashboardImageUrl(deck.thumbnailUrl)}
      <a class="recent-decks__row" href={deck.href}>
        <div class="recent-decks__deck">
          <div class="recent-decks__thumb">
            {#if preview}
              <img src={preview} alt={deck.title} />
            {:else}
              <span>{deck.title}</span>
            {/if}
          </div>

          <div class="recent-decks__copy">
            <strong>{deck.title}</strong>
            <span>{deck.companyName ?? 'Deck workspace'}</span>
            <small>Updated {formatRelativeTime(deck.updatedAt)}</small>
          </div>
        </div>

        <div class="recent-decks__meta">
          <span class={`recent-decks__status recent-decks__status--${statusTone(deck.status)}`}>{deck.statusLabel}</span>
          <div class="recent-decks__avatars" aria-label="Deck collaborators">
            {#each deck.collaborators.slice(0, 3) as collaborator}
              <span title={collaborator.name}>{collaborator.initials}</span>
            {/each}
            {#if deck.extraCollaboratorCount > 0}<small>+{deck.extraCollaboratorCount}</small>{/if}
          </div>
        </div>
      </a>
    {/each}
  </div>
</section>
