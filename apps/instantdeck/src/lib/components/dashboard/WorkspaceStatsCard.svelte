<script lang="ts">
  import type { DashboardStats } from '$lib/types/workspace-dashboard';

  interface Props {
    stats: DashboardStats;
  }

  let { stats }: Props = $props();
</script>

<!-- Read-only snapshot of backend workspace totals shown in the dashboard right rail. -->
<article class="panel stats-card">
  <div class="eyebrow">Workspace stats</div>
  <div class="stats-grid">
    <div>
      <span>Uploaded decks</span>
      <strong>{stats.uploadedDecks}</strong>
    </div>
    <div>
      <span>Iterations this week</span>
      <strong>{stats.iterationsThisWeek}</strong>
    </div>
    <div>
      <span>Slides in library</span>
      <strong>{stats.slidesInLibrary}</strong>
    </div>
    <div>
      <span>Team members</span>
      <strong>{stats.teamMembers}</strong>
    </div>
  </div>
</article>

<style>
  .stats-card {
    padding: 1rem;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.7rem;
    margin-top: 0.85rem;
  }

  .stats-grid div {
    min-height: 5.5rem;
    display: grid;
    align-content: space-between;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.8rem;
  }

  span {
    color: var(--muted);
    font-size: 0.78rem;
  }

  strong {
    font-size: 1.55rem;
  }
</style>
