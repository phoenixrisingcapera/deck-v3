<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { settings } from '$lib/stores/settings.svelte';
  import DealsDropdown from './DealsDropdown.svelte';

  let onSettingsPage = $derived(page.url.pathname.startsWith('/settings'));

  function goHome() {
    goto('/');
  }

  function goSettings() {
    goto('/settings');
  }
</script>

<header class="header">
  <button type="button" class="brand" onclick={goHome}>
    <span class="logo">M</span>
    <span class="name">MemoPop</span>
  </button>

  <div class="spacer"></div>

  {#if settings.loaded && settings.activeFirm}
    <DealsDropdown />
    <div class="firm-pill" title="Active firm">
      <span class="dot"></span>
      <span class="firm-name">{settings.activeFirm}</span>
    </div>
  {/if}

  <button
    type="button"
    class="settings-btn"
    class:active={onSettingsPage}
    onclick={goSettings}
    title="Settings"
    aria-label="Settings"
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="3"></circle>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>
  </button>
</header>

<style>
  .header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
    border-bottom: 1px solid #e5e5e5;
    background: #ffffff;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: transparent;
    border: none;
    padding: 0;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  .logo {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: linear-gradient(135deg, #5b21b6, #a855f7);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.95rem;
  }

  .name {
    font-weight: 600;
    font-size: 1rem;
  }

  .spacer {
    flex: 1;
  }

  .firm-pill {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem 0.3rem 0.6rem;
    background: #f3e8ff;
    border-radius: 999px;
    font-size: 0.85rem;
    color: #5b21b6;
    font-weight: 500;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #5b21b6;
  }

  .settings-btn {
    background: transparent;
    border: none;
    padding: 0.4rem;
    border-radius: 6px;
    color: #6b7280;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .settings-btn:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .settings-btn.active {
    background: #f3e8ff;
    color: #5b21b6;
  }

  @media (prefers-color-scheme: dark) {
    .header {
      background: #1c1c1e;
      border-bottom-color: #2a2a2c;
    }

    .firm-pill {
      background: #2a1f3d;
      color: #c4b5fd;
    }

    .dot {
      background: #c4b5fd;
    }

    .settings-btn {
      color: #9ca3af;
    }

    .settings-btn:hover {
      background: #2a2a2c;
      color: #f6f6f6;
    }

    .settings-btn.active {
      background: #2a1f3d;
      color: #c4b5fd;
    }
  }
</style>
