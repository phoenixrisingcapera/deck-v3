<script lang="ts">
  import { page } from '$app/state';
  import { settings } from '$lib/stores/settings.svelte';
  import Header from '$lib/components/Header.svelte';
  import JourneyBreadcrumbs from '$lib/components/JourneyBreadcrumbs.svelte';

  let { children } = $props();

  let onSettingsPage = $derived(page.url.pathname.startsWith('/settings'));
  let showBreadcrumbs = $derived(
    settings.loaded && !!settings.repoPath && !onSettingsPage
  );

  $effect(() => {
    if (!settings.loaded) {
      settings.load();
    }
  });
</script>

<div class="app">
  <Header />
  {#if showBreadcrumbs}
    <JourneyBreadcrumbs />
  {/if}
  <main class="content">
    {@render children()}
  </main>
</div>

<style>
  :global(:root) {
    font-family: Inter, Avenir, Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.5;
    color: #0f0f0f;
    background-color: #fafaf9;
    font-synthesis: none;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  :global(body) {
    margin: 0;
  }

  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }

  .app {
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .content {
    flex: 1;
    min-height: 0;
    padding: 0;
  }

  @media (prefers-color-scheme: dark) {
    :global(:root) {
      color: #f6f6f6;
      background-color: #1c1c1e;
    }
  }
</style>
