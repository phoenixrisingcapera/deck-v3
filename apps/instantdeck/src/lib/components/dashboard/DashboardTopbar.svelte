<script lang="ts">
  import DashboardNotificationsPopover from '$components/dashboard/DashboardNotificationsPopover.svelte';
  import type { DashboardNotificationItem } from '$lib/types/workspace-dashboard';

  interface Props {
    initialNotifications: DashboardNotificationItem[];
    unreadCount: number;
    userName: string;
  }

  let { initialNotifications, unreadCount, userName }: Props = $props();

  function seedNotifications() {
    return initialNotifications;
  }

  function seedUnreadCount() {
    return unreadCount;
  }

  let search = $state('');
  let open = $state(false);
  let notifications = $state<DashboardNotificationItem[]>(seedNotifications());
  let count = $state(seedUnreadCount());

  $effect(() => {
    notifications = initialNotifications;
    count = unreadCount;
  });

  function toggleNotifications() {
    open = !open;
  }
</script>

<div class="dashboard-topbar">
  <label class="dashboard-topbar__search">
    <input bind:value={search} type="search" placeholder="Search decks..." aria-label="Search decks" />
    <span aria-hidden="true">⌕</span>
  </label>

  <div class="dashboard-topbar__actions">
    <div class="dashboard-topbar__notifications">
      <button type="button" class="dashboard-topbar__icon" aria-label="Open notifications" aria-expanded={open} onclick={toggleNotifications}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
          <path d="M10 21h4" />
        </svg>
        {#if count > 0}<span class="dashboard-topbar__count">{count}</span>{/if}
      </button>
      {#if open}
        <DashboardNotificationsPopover {notifications} />
      {/if}
    </div>

    <a class="dashboard-topbar__profile" href="/settings/account/settings" aria-label={`Open account settings for ${userName}`}>
      <span class="dashboard-topbar__avatar">{userName.slice(0, 1).toUpperCase()}</span>
      <span>{userName}</span>
      <span aria-hidden="true">›</span>
    </a>
  </div>
</div>
