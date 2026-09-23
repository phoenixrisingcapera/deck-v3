<script lang="ts">
  import type { DesignBatchPreview } from '@deck-aistack-codes/shared';
  import AppLogo from '$components/AppLogo.svelte';
  import UtilitiesBar from '$components/UtilitiesBar.svelte';
  import { sessionState } from '$lib/stores/session';

  type SidebarUtilitiesPlacement = 'hidden' | 'sidebar';

  interface Props {
    active?: string;
    currentDeckId?: string | null;
    latestBatches?: DesignBatchPreview[];
    utilitiesPlacement?: SidebarUtilitiesPlacement;
    compact?: boolean;
  }

  let { active = '', currentDeckId = null, latestBatches = [], utilitiesPlacement = 'sidebar', compact = false }: Props = $props();

  const coreItems = [
    { href: '/dashboard', label: 'Dashboard', key: 'dashboard', icon: '⌂' },
    { href: '/decks', label: 'Decks', key: 'decks', icon: '▣' },
    { href: '/templates', label: 'Templates', key: 'templates', icon: '▤' }
  ];

  // Product-surface navigation now has one owner: ProductSurfaceNav in the shell/topbar.

  const utilityItems = [
    { href: '/settings', label: 'Settings', key: 'settings', icon: '⚙' },
    { href: '/app/billing', label: 'Billing', key: 'billing', icon: '□' },
    { href: '/contact', label: 'Support', key: 'support', icon: '?' }
  ];

  function isItemActive(itemKey: string) {
    return active === itemKey;
  }

  const userName = $derived($sessionState.user?.email?.split('@')[0] || 'Account');
</script>

<aside class:app-sidebar--compact={compact} class="app-sidebar app-sidebar--dashboard">
  <a class="app-sidebar__brand" href="/dashboard" aria-label="Open dashboard">
    <AppLogo alt="Deck" />
    <div class="app-sidebar__brand-copy">
      <strong>DidiDecks</strong>
      <p>AI Deck Infrastructure</p>
    </div>
  </a>

  <a class="app-sidebar__cta" href="/decks/new" title="New deck" aria-label="New deck">
    <span aria-hidden={compact}>＋</span>
    <span class="app-sidebar__item-label">New Deck</span>
  </a>

  <nav class="app-sidebar__nav app-sidebar__nav--primary">
    {#each coreItems as item}
      <a href={item.href} class:active={isItemActive(item.key)} aria-current={isItemActive(item.key) ? 'page' : undefined} title={compact ? item.label : undefined}>
        <span>{item.icon}</span>
        <span class="app-sidebar__item-label">{item.label}</span>
      </a>
    {/each}
  </nav>

  <section class="app-sidebar__section app-sidebar__section--current">
    <span class="app-sidebar__label">Current deck</span>
    <div class="app-sidebar__hint">
      <strong>{currentDeckId ? 'Deck selected' : 'No deck selected'}</strong>
      <p>{currentDeckId ? `${latestBatches.length} recent saved versions available.` : 'Select a deck to see its options.'}</p>
    </div>
  </section>

  <nav class="app-sidebar__nav app-sidebar__nav--utility">
    {#each utilityItems as item}
      <a href={item.href} class:active={isItemActive(item.key)} title={compact ? item.label : undefined}>
        <span>{item.icon}</span>
        <span class="app-sidebar__item-label">{item.label}</span>
      </a>
    {/each}
  </nav>

  <div class="app-sidebar__footer">
    <div class="app-sidebar__user">
      <div class="app-avatar">{userName.slice(0, 1).toUpperCase()}</div>
      <div class="app-sidebar__user-copy">
        <strong>{userName}</strong>
        <p>{$sessionState.user?.email ?? 'Signed in'}</p>
      </div>
    </div>
    {#if utilitiesPlacement === 'sidebar'}
      <UtilitiesBar placement="sidebar" />
    {/if}
  </div>
</aside>
