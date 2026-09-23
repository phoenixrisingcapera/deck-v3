<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import BackendErrorBanner from '$lib/components/decks/BackendErrorBanner.svelte';
  import ProductFooter from '$components/ProductFooter.svelte';
  import RouteProgress from '$components/RouteProgress.svelte';
  import MobileAppGate from '$lib/layouts/MobileAppGate.svelte';
  import { classifyProductLayoutMode, isFullHeightProductWorkspace } from '$lib/layouts/productLayoutMode';
  import { sessionState } from '$lib/stores/session';
  import { theme } from '$lib/stores/theme';
  import { isMobileViewport } from '$lib/stores/viewport';

  let { children }: { children: import('svelte').Snippet } = $props();

  const deckWorkspaceRoute = $derived(
    /^\/decks\/(?!(?:new|llm-report|insights)(?:\/|$))[^/]+(?:\/|$)/.test(page.url.pathname)
  );
  const uploadRoute = $derived(/^\/decks\/new(?:\/|$)/.test(page.url.pathname));
  const gateForMobile = $derived(deckWorkspaceRoute && !uploadRoute);
  const layoutMode = $derived(classifyProductLayoutMode(page.url.pathname));
  const fullHeightWorkspaceRoute = $derived(isFullHeightProductWorkspace(layoutMode));
  const dashboardRoute = $derived(page.url.pathname === '/dashboard');

  if (browser) {
    theme.prime('dark');
  }

  onMount(() => {
    sessionState.load();
  });
</script>

<svelte:head>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<BackendErrorBanner />

<div class="app-route-shell" data-sveltekit-preload-data="off" data-product-route-frame>
  <RouteProgress />
  <MobileAppGate enabled={$isMobileViewport && gateForMobile}>
    <div
      class="app-product-frame"
      class:app-product-frame--workspace={fullHeightWorkspaceRoute}
      data-layout-mode={layoutMode}
    >
      <div class="app-shell-region">
        {@render children()}
      </div>
      {#if !dashboardRoute}
        <ProductFooter compact={fullHeightWorkspaceRoute} />
      {/if}
    </div>
  </MobileAppGate>
</div>
