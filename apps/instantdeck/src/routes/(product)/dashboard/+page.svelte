<script lang="ts">
  import AppShell from '$components/AppShell.svelte';
  import DashboardGreeting from '$components/dashboard/DashboardGreeting.svelte';
  import DashboardStatCard from '$components/dashboard/DashboardStatCard.svelte';
  import DashboardTasksCard from '$components/dashboard/DashboardTasksCard.svelte';
  import DashboardTopbar from '$components/dashboard/DashboardTopbar.svelte';
  import QuickActionsCard from '$components/dashboard/QuickActionsCard.svelte';
  import RecentActivityCard from '$components/dashboard/RecentActivityCard.svelte';
  import RecentDecksCard from '$components/dashboard/RecentDecksCard.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const statCards = $derived([
    { label: 'Total Decks', value: data.dashboard.summaryCards.totalDecks, trend: `${Math.max(data.dashboard.summaryCards.totalDecks, 0)} tracked`, tone: 'violet' as const, icon: '▣' },
    { label: 'In Progress', value: data.dashboard.summaryCards.inProgressDecks, trend: `${data.workspace.processingDeckCount} processing`, tone: 'blue' as const, icon: '◫' },
    { label: 'Ready for Review', value: data.dashboard.summaryCards.readyForReviewDecks, trend: `${data.workspace.readyDeckCount} ready`, tone: 'amber' as const, icon: '◉' },
    { label: 'Published', value: data.dashboard.summaryCards.publishedDecks, trend: `${data.workspace.exportCount} exports`, tone: 'green' as const, icon: '➤' }
  ]);
</script>

<AppShell
  title="Dashboard"
  subtitle=""
  activeNav="dashboard"
  deckLabel="Deck"
  currentDeckId={data.dashboard.latestDeck?.id ?? data.workspace.activeDeckId}
  latestBatches={data.latestBatches}
  showTopBar={false}
>
  <section class="dashboard-page">
    <header class="dashboard-page__header">
      <DashboardGreeting greeting={data.dashboard.greeting} />
      <DashboardTopbar
        initialNotifications={data.dashboard.notifications.items}
        unreadCount={data.dashboard.notifications.unreadCount}
        userName={data.dashboard.greeting.userName}
      />
    </header>

    <section class="dashboard-page__stats">
      {#each statCards as card}
        <DashboardStatCard {...card} />
      {/each}
    </section>

    <section class="dashboard-page__grid dashboard-page__grid--top">
      <RecentDecksCard decks={data.dashboard.recentDecks} />
      <RecentActivityCard items={data.dashboard.recentActivity} />
    </section>

    <section class="dashboard-page__grid dashboard-page__grid--bottom">
      <DashboardTasksCard tasks={data.dashboard.tasks} />
      <QuickActionsCard currentDeckId={data.dashboard.latestDeck?.id ?? null} />
    </section>
  </section>
</AppShell>
