<script lang="ts">
  import CurrentDeckCard from '$components/dashboard/CurrentDeckCard.svelte';
  import LatestIterationsCard from '$components/dashboard/LatestIterationsCard.svelte';
  import WorkspaceStatsCard from '$components/dashboard/WorkspaceStatsCard.svelte';
  import type { DashboardDeckSummary, DashboardIterationSummary, DashboardStats } from '$lib/types/workspace-dashboard';

  interface Props {
    latestDeck: DashboardDeckSummary | null;
    stats: DashboardStats;
    latestIterations: DashboardIterationSummary[];
  }

  let { latestDeck, stats, latestIterations }: Props = $props();
</script>

<!-- The right rail groups secondary dashboard context so the main page can keep the primary deck action focused. -->
<aside class="dashboard-rail">
  <CurrentDeckCard deck={latestDeck} />
  <WorkspaceStatsCard {stats} />
  <LatestIterationsCard {latestDeck} iterations={latestIterations} />
</aside>

<style>
  .dashboard-rail {
    display: grid;
    gap: 1rem;
    align-content: start;
  }
</style>
