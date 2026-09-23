<script lang="ts">
  import type { DashboardDeckSummary, DashboardStats, DashboardUserSummary } from '$lib/types/workspace-dashboard';

  interface Props {
    user: DashboardUserSummary;
    stats: DashboardStats;
    latestDeck: DashboardDeckSummary | null;
  }

  let { user, stats, latestDeck }: Props = $props();
</script>

<!-- Top-level dashboard CTA area: all links are derived from latestDeck so empty workspaces still route safely. -->
<section class="panel dashboard-hero">
  <div class="hero-copy">
    <div class="eyebrow">Workspace</div>
    <h1>Welcome back</h1>
    <p>Your workspace is ready. Continue your latest deck, review iterations, or upload a new deck to get started.</p>
    <div class="hero-actions">
      <!-- Force a document navigation so a failed or stale client-side route load cannot leave this CTA on /dashboard. -->
      <a class="button" data-sveltekit-reload href={latestDeck ? `/decks/${latestDeck.id}/smart-deck` : '/decks'}>Continue latest deck</a>
      <a class="button secondary" href="/decks">Review iterations</a>
      <a class="button secondary" href="/decks/new">Upload new deck</a>
    </div>
  </div>

  <div class="hero-metrics" aria-label={`Dashboard metrics for ${user.handle}`}>
    <article>
      <span>Current deck</span>
      <!-- This metric intentionally shows whether there is an active/latest deck, not the total deck count. -->
      <strong>{latestDeck ? '1' : '0'}</strong>
    </article>
    <article>
      <span>Iterations this week</span>
      <strong>{stats.iterationsThisWeek}</strong>
    </article>
    <article>
      <span>Decks uploaded</span>
      <strong>{stats.uploadedDecks}</strong>
    </article>
  </div>
</section>

<style>
  .dashboard-hero {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(260px, 0.48fr);
    gap: 1rem;
    padding: 1.35rem;
    align-items: end;
  }

  .hero-copy {
    display: grid;
    gap: 1rem;
  }

  h1,
  p {
    margin: 0;
  }

  h1 {
    font-size: clamp(2rem, 4vw, 3.3rem);
  }

  p {
    max-width: 48rem;
    color: var(--muted);
    font-size: 1rem;
  }

  .hero-actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .hero-metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.65rem;
  }

  article {
    min-height: 6.25rem;
    display: grid;
    align-content: space-between;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.9rem;
  }

  span {
    color: var(--muted);
    font-size: 0.78rem;
  }

  strong {
    font-size: 1.8rem;
  }

  @media (max-width: 780px) {
    .dashboard-hero,
    .hero-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
