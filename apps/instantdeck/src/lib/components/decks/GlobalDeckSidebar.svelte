<!-- GLOBAL DECK SIDEBAR: shared column-one rail for canonical deck workspaces. -->
<script lang="ts">
  import AppLogo from '$lib/components/AppLogo.svelte';

  export interface GlobalDeckSidebarItem {
    key: string;
    icon: string;
    label: string;
    href?: string;
    controls?: string;
    emphasis?: 'core' | 'preserved' | 'default';
  }

  interface Props {
    items: readonly GlobalDeckSidebarItem[];
    activeKey?: string | null;
    ariaLabel?: string;
    onItemChange?: (key: string) => void;
  }

  let {
    items,
    activeKey = null,
    ariaLabel = 'Deck workspace tools',
    onItemChange
  }: Props = $props();

  function emphasis(item: GlobalDeckSidebarItem) {
    if (item.emphasis) return item.emphasis;
    if (['slides', 'deck_map', 'design', 'ai_tools', 'brand', 'data', 'canvas', 'ai'].includes(item.key)) return 'core';
    if (['elements', 'text', 'media'].includes(item.key)) return 'preserved';
    return 'default';
  }
</script>

<aside class="global-deck-sidebar" data-deck-region="sidebar" aria-label={ariaLabel}>
  <div class="global-deck-sidebar__logo" aria-label="Deck AI Stack">
    <AppLogo size="sm" />
  </div>

  <nav class="global-deck-sidebar__nav" aria-label={ariaLabel}>
    {#each items as item}
      {@const itemEmphasis = emphasis(item)}
      {#if item.href}
        <a
          class:active={item.key === activeKey}
          class:is-core={itemEmphasis === 'core'}
          class:is-preserved={itemEmphasis === 'preserved'}
          href={item.href}
          title={item.label}
          aria-current={item.key === activeKey ? 'page' : undefined}
          aria-controls={item.controls}
        >
          <span class="icon" aria-hidden="true">{item.icon}</span>
          <span class="label">{item.label}</span>
        </a>
      {:else}
        <button
          type="button"
          class:active={item.key === activeKey}
          class:is-core={itemEmphasis === 'core'}
          class:is-preserved={itemEmphasis === 'preserved'}
          title={item.label}
          aria-pressed={item.key === activeKey}
          aria-controls={item.controls}
          onclick={() => onItemChange?.(item.key)}
        >
          <span class="icon" aria-hidden="true">{item.icon}</span>
          <span class="label">{item.label}</span>
        </button>
      {/if}
    {/each}
  </nav>
</aside>

<style>
  .global-deck-sidebar {
    grid-column: 1;
    grid-row: 1 / -1;
    min-width: 0;
    min-height: 0;
    background: rgba(7, 11, 22, 0.94);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1rem 0.5rem;
    gap: 1rem;
    overflow: auto hidden;
  }

  .global-deck-sidebar__logo {
    width: 46px;
    height: 46px;
    flex: 0 0 auto;
    border-radius: 14px;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    display: grid;
    place-items: center;
    box-shadow: 0 16px 30px rgba(124, 58, 237, 0.35);
    overflow: hidden;
  }

  .global-deck-sidebar__nav {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    width: 100%;
    align-items: center;
  }

  .global-deck-sidebar__nav :is(a, button) {
    width: 100%;
    display: grid;
    justify-items: center;
    gap: 0.25rem;
    padding: 0.65rem 0.2rem;
    border-radius: 14px;
    border: 1px solid transparent;
    background: transparent;
    color: #94a3b8;
    font: inherit;
    font-size: 0.68rem;
    line-height: 1.1;
    text-decoration: none;
    cursor: pointer;
  }

  .global-deck-sidebar__nav :is(a, button).active {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.9), rgba(14, 165, 233, 0.85));
    color: #fff;
    box-shadow: 0 14px 28px rgba(76, 29, 149, 0.35);
  }

  .global-deck-sidebar__nav :is(a, button).is-core:not(.active) {
    border-color: rgba(124, 58, 237, 0.22);
    background: rgba(124, 58, 237, 0.08);
  }

  .global-deck-sidebar__nav :is(a, button).is-preserved:not(.active) {
    opacity: 0.78;
  }

  .icon {
    font-size: 0.95rem;
    font-weight: 700;
  }

  @media (max-width: 720px) {
    .global-deck-sidebar {
      grid-column: 1;
      grid-row: 2;
      flex-direction: row;
      align-items: center;
      padding: 0.65rem 0.85rem;
      border-right: 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      overflow: auto hidden;
    }

    .global-deck-sidebar__logo {
      width: 38px;
      height: 38px;
    }

    .global-deck-sidebar__nav {
      width: auto;
      min-width: max-content;
      flex-direction: row;
    }

    .global-deck-sidebar__nav :is(a, button) {
      width: auto;
      min-width: 72px;
      padding: 0.55rem 0.5rem;
    }
  }
</style>
