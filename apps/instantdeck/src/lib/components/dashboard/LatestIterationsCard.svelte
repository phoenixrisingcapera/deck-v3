<script lang="ts">
  import { safeDashboardImageUrl } from '$lib/dashboard/imagePolicy';
  import { dashboardIterationStatusLabel } from '$lib/dashboard/status';
  import type { DashboardDeckSummary, DashboardIterationSummary } from '$lib/types/workspace-dashboard';

  interface Props {
    latestDeck: DashboardDeckSummary | null;
    iterations: DashboardIterationSummary[];
  }

  let { latestDeck, iterations }: Props = $props();

  function updatedTime(value: string) {
    const date = new Date(value);
    // Invalid dates should not break server-side rendering; show a safe fallback instead.
    if (Number.isNaN(date.getTime())) return 'Recently updated';
    // Locale-aware display keeps the card readable without shipping a date formatting dependency.
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
  }

  function statusLabel(status: DashboardIterationSummary['status']) {
    // Convert backend workflow states into user-facing labels for the compact dashboard card.
    return dashboardIterationStatusLabel(status);
  }

  function thumbnailUrlFor(iteration: DashboardIterationSummary) {
    return safeDashboardImageUrl(iteration.thumbnailUrl);
  }
</script>

<article class="panel iterations-card">
  <div class="card-heading">
    <div class="eyebrow">Latest iterations</div>
    {#if latestDeck}
      <a class="link" href={`/decks/${latestDeck.id}/versions`}>View all</a>
    {/if}
  </div>

  <!-- Limit the right-rail card to three rows so it stays scannable beside the main dashboard content. -->
  <div class="iteration-list">
    {#each iterations.slice(0, 3) as iteration}
      {@const thumbnailUrl = thumbnailUrlFor(iteration)}
      <a class="iteration-row" href={`/decks/${iteration.deckId}/versions/${iteration.id}`}>
        <div class="iteration-thumb">
          {#if thumbnailUrl}
            <img src={thumbnailUrl} alt={iteration.title} />
          {:else}
            <span>{iteration.iterationNumber}</span>
          {/if}
        </div>
        <div>
          <strong>Iteration {iteration.iterationNumber}</strong>
          <span>{iteration.title}</span>
          <small>{updatedTime(iteration.updatedAt)} · {statusLabel(iteration.status)}</small>
        </div>
      </a>
    {:else}
      <p class="empty">No iterations generated yet.</p>
    {/each}
  </div>
</article>

<style>
  .iterations-card {
    padding: 1rem;
  }

  .card-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .iteration-list {
    display: grid;
    gap: 0.7rem;
    margin-top: 0.85rem;
  }

  .iteration-row {
    display: grid;
    grid-template-columns: 4rem minmax(0, 1fr);
    gap: 0.75rem;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.7rem;
  }

  .iteration-thumb {
    height: 3.5rem;
    display: grid;
    place-items: center;
    overflow: hidden;
    border-radius: 6px;
    background:
      linear-gradient(135deg, rgba(14, 165, 233, 0.22), transparent),
      rgba(15, 23, 42, 0.68);
    font-weight: 800;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .iteration-row div:last-child {
    min-width: 0;
    display: grid;
    gap: 0.18rem;
  }

  span,
  small,
  .empty,
  .link {
    color: var(--muted);
  }

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
