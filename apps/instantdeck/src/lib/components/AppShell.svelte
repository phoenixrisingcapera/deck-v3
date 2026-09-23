<script lang="ts">
  import type { DesignBatchPreview } from '@deck-aistack-codes/shared';
  import ProductSurfaceNav from '$lib/components/navigation/ProductSurfaceNav.svelte';
  import Sidebar from '$components/Sidebar.svelte';
  import TopBar from '$components/TopBar.svelte';
  import UtilitiesBar from '$components/UtilitiesBar.svelte';

  type UtilitiesPlacement = 'hidden' | 'sidebar' | 'footer' | 'topbar';

  interface Props {
    title: string;
    subtitle?: string;
    activeNav?: string;
    status?: string;
    showTopBar?: boolean;
    /** @deprecated */
    showFooterUtilities?: boolean;
    utilitiesPlacement?: UtilitiesPlacement;
    showTopBarCopy?: boolean;
    compactTopBar?: boolean;
    compactSidebar?: boolean;
    showSidebar?: boolean;
    showTopBarSearch?: boolean;
    deckLabel?: string;
    workspaceLabel?: string;
    currentDeckId?: string | null;
    latestBatches?: DesignBatchPreview[];
    actions?: import('svelte').Snippet;
    headerExtension?: import('svelte').Snippet;
    showSurfaceNav?: boolean;
    workspaceMode?: boolean;
    children?: import('svelte').Snippet;
  }

  let {
    title, subtitle = '', activeNav = 'dashboard', status = '',
    showTopBar = true, showFooterUtilities: legacyShowFooterUtilities = false,
    utilitiesPlacement = undefined, showTopBarCopy = true, compactTopBar = false,
    compactSidebar = false, showSidebar = true, showTopBarSearch = true, deckLabel = '',
    workspaceLabel = '', currentDeckId = null, latestBatches = [], actions, headerExtension,
    showSurfaceNav = true, workspaceMode = false, children
  }: Props = $props();

  // DISABLED: Defaulting to the topbar reduced the product utilities to only
  // the compact theme toggle, which made the full utilities bar disappear.
  // const resolvedUtilitiesPlacement = $derived(
  //   utilitiesPlacement ?? (legacyShowFooterUtilities ? 'footer' : showTopBar ? 'topbar' : 'hidden')
  // );
  // DISABLED: Sidebar placement could scroll out of view and was hidden by the
  // mobile sidebar treatment, so product utilities were not always available.
  // const resolvedUtilitiesPlacement = $derived(
  //   utilitiesPlacement ?? (legacyShowFooterUtilities ? 'footer' : 'sidebar')
  // );
  // Product utilities remain available when a surface explicitly requests
  // them, but the global product footer owns the default bottom-of-page chrome.
  const resolvedUtilitiesPlacement = $derived(utilitiesPlacement ?? 'hidden');
  const sidebarUtilitiesPlacement = $derived(resolvedUtilitiesPlacement === 'sidebar' ? 'sidebar' : 'hidden');
  const showTopBarResolved = $derived(showTopBar);
  const showTopBarUtilities = $derived(resolvedUtilitiesPlacement === 'topbar');
  const showFooterUtilitiesResolved = $derived(resolvedUtilitiesPlacement === 'footer');

  let mobileNavOpen = $state(false);
  let mobileViewport = $state(false);
  let drawer = $state<HTMLElement | null>(null);
  let menuButton = $state<HTMLButtonElement | null>(null);

  function closeMobileNav() {
    mobileNavOpen = false;
    requestAnimationFrame(() => menuButton?.focus());
  }

  function trapDrawerFocus(event: KeyboardEvent) {
    if (!mobileViewport || !mobileNavOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMobileNav();
      return;
    }
    if (event.key !== 'Tab' || !drawer) return;
    const focusable = [...drawer.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  $effect(() => {
    const media = window.matchMedia('(max-width: 768px)');
    const syncViewport = () => {
      mobileViewport = media.matches;
      if (!media.matches) mobileNavOpen = false;
    };
    syncViewport();
    media.addEventListener('change', syncViewport);
    return () => media.removeEventListener('change', syncViewport);
  });

  $effect(() => {
    if (mobileViewport && mobileNavOpen) requestAnimationFrame(() => drawer?.querySelector<HTMLElement>('a[href], button:not([disabled])')?.focus());
  });
</script>

<div class="app-shell" class:app-shell--compact-sidebar={compactSidebar && showSidebar} class:app-shell--no-sidebar={!showSidebar} class:app-shell--workspace={workspaceMode}>
  {#if showSidebar}
    <button bind:this={menuButton} class="app-shell__mobile-menu" type="button" aria-controls="mobile-navigation" aria-expanded={mobileNavOpen} onclick={() => (mobileNavOpen = true)}>
      <span aria-hidden="true">☰</span> Menu
    </button>
  {/if}
  {#if showSidebar}
    {#if mobileViewport && mobileNavOpen}
      <div class="app-shell__mobile-backdrop" role="presentation" onclick={closeMobileNav}></div>
    {/if}
    <div id="mobile-navigation" bind:this={drawer} class="app-shell__sidebar-drawer" class:app-shell__sidebar-drawer--open={mobileViewport && mobileNavOpen} role={mobileViewport ? 'dialog' : undefined} aria-modal={mobileViewport && mobileNavOpen ? 'true' : undefined} aria-hidden={mobileViewport && !mobileNavOpen ? 'true' : undefined} aria-label="Application navigation" inert={mobileViewport && !mobileNavOpen ? true : undefined} tabindex={-1} onkeydown={trapDrawerFocus}>
      <button class="app-shell__mobile-close" type="button" aria-label="Close navigation" onclick={closeMobileNav}>×</button>
      <Sidebar active={activeNav} {currentDeckId} {latestBatches} utilitiesPlacement={sidebarUtilitiesPlacement} compact={compactSidebar} />
    </div>
  {/if}
  <div class="app-main" inert={mobileViewport && mobileNavOpen ? true : undefined} aria-hidden={mobileViewport && mobileNavOpen ? 'true' : undefined}>
    {#if showTopBarResolved}
      <TopBar
        {title}
        {subtitle}
        {status}
        {workspaceLabel}
        {showTopBarCopy}
        {compactTopBar}
        {showTopBarSearch}
        {deckLabel}
        showUtilities={showTopBarUtilities}
        {actions}
        {headerExtension}
        surfaceNav={showSurfaceNav && !currentDeckId ? ProductSurfaceNav : undefined}
        surfaceNavProps={{ deckId: currentDeckId }}
      />
    {/if}
    <main class="app-content">{@render children?.()}</main>
    {#if showFooterUtilitiesResolved}
      <div class="app-shell__footer-utilities">
        <UtilitiesBar placement="footer" />
      </div>
    {/if}
  </div>
</div>
