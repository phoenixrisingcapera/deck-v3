<script lang="ts">
  import { formatRelativeTime } from '$lib/dashboard/time';
  import type { DashboardNotificationItem } from '$lib/types/workspace-dashboard';

  interface Props {
    notifications: DashboardNotificationItem[];
  }

  let { notifications }: Props = $props();
</script>

<div class="notifications-popover panel" role="dialog" aria-label="Notifications">
  <div class="notifications-popover__head">
    <strong>Notifications</strong>
    <span>{notifications.length}</span>
  </div>

  <div class="notifications-popover__list">
    {#if notifications.length > 0}
      {#each notifications as item}
        <a class="notifications-popover__item" href={item.href}>
          <div>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </div>
          <small>{formatRelativeTime(item.createdAt)}</small>
        </a>
      {/each}
    {:else}
      <p class="notifications-popover__empty">No notifications yet.</p>
    {/if}
  </div>
</div>
