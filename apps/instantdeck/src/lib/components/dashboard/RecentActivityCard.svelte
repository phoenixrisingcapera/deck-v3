<script lang="ts">
  import { formatRelativeTime } from '$lib/dashboard/time';
  import type { DashboardActivityItem } from '$lib/types/workspace-dashboard';

  interface Props {
    items: DashboardActivityItem[];
  }

  let { items }: Props = $props();
</script>

<section class="panel dashboard-card recent-activity-card">
  <div class="dashboard-card__head">
    <h2>Recent Activity</h2>
  </div>

  <div class="recent-activity-card__list">
    {#each items as item}
      {#if item.href}
        <a class="recent-activity-card__item" href={item.href}>
          <span class={`recent-activity-card__icon recent-activity-card__icon--${item.iconTone}`} aria-hidden="true">•</span>
          <div>
            <strong>{item.title}</strong>
            <p>{item.subtitle}</p>
          </div>
          <small>{formatRelativeTime(item.createdAt)}</small>
        </a>
      {:else}
        <div class="recent-activity-card__item">
          <span class={`recent-activity-card__icon recent-activity-card__icon--${item.iconTone}`} aria-hidden="true">•</span>
          <div>
            <strong>{item.title}</strong>
            <p>{item.subtitle}</p>
          </div>
          <small>{formatRelativeTime(item.createdAt)}</small>
        </div>
      {/if}
    {/each}
  </div>
</section>
