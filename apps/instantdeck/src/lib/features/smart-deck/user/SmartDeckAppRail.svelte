<script lang="ts">
  import AppLogo from '$lib/components/AppLogo.svelte';
  import type { DeckShellToolId } from '$lib/contracts';

  interface Item {
    key: DeckShellToolId;
    icon: string;
    label: string;
  }

  interface Props {
    items: readonly Item[];
    activeKey?: DeckShellToolId;
    onToolChange: (key: DeckShellToolId) => void;
  }

  let { items, activeKey = 'slides', onToolChange }: Props = $props();
</script>

<aside class="smart-deck-app-rail" data-deck-region="tools" aria-label="Smart Deck tools">
  <div class="smart-deck-app-rail__logo" aria-label="Deck AI Stack">
    <AppLogo size="sm" />
  </div>

  <nav class="smart-deck-app-rail__nav">
    {#each items as item}
      <button
        type="button"
        class:is-core={['slides', 'deck_map', 'design', 'ai_tools', 'brand', 'data'].includes(item.key)}
        class:is-preserved={['elements', 'text', 'media'].includes(item.key)}
        class:active={item.key === activeKey}
        title={item.label}
        aria-pressed={item.key === activeKey}
        aria-controls={item.key === 'brand' ? 'smart-deck-brand-panel' : item.key === 'ai_tools' || item.key === 'design' ? 'smart-deck-inspector' : undefined}
        onclick={() => onToolChange(item.key)}
      >
        <span class="icon">{item.icon}</span>
        <span class="label">{item.label}</span>
      </button>
    {/each}
  </nav>
</aside>

<style>
  .smart-deck-app-rail {
    grid-column: 1;
    grid-row: 1 / 4;
    background: rgba(7, 11, 22, 0.94);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1rem 0.5rem;
    gap: 1rem;
  }

  .smart-deck-app-rail__logo {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    display: grid;
    place-items: center;
    box-shadow: 0 16px 30px rgba(124, 58, 237, 0.35);
    overflow: hidden;
  }

  .smart-deck-app-rail__nav {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    width: 100%;
    align-items: center;
  }

  .smart-deck-app-rail__nav button {
    width: 100%;
    display: grid;
    justify-items: center;
    gap: 0.25rem;
    padding: 0.65rem 0.2rem;
    border-radius: 14px;
    border: 1px solid transparent;
    background: transparent;
    color: #94a3b8;
    font-size: 0.68rem;
    cursor: pointer;
  }

  .smart-deck-app-rail__nav button.active {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.9), rgba(14, 165, 233, 0.85));
    color: white;
    box-shadow: 0 14px 28px rgba(76, 29, 149, 0.35);
  }

  .smart-deck-app-rail__nav button.is-core:not(.active) {
    border-color: rgba(124, 58, 237, 0.18);
    background: rgba(124, 58, 237, 0.06);
  }

  .smart-deck-app-rail__nav button[aria-controls="smart-deck-inspector"]:not(.active) {
    border-color: rgba(124, 58, 237, 0.3);
    background: rgba(124, 58, 237, 0.1);
  }

  .smart-deck-app-rail__nav button.is-preserved:not(.active) {
    opacity: 0.78;
  }

  .icon {
    font-size: 0.95rem;
    font-weight: 700;
  }

  .label {
    line-height: 1.1;
  }

  @media (max-width: 960px) {
    .smart-deck-app-rail {
      grid-column: 1;
      grid-row: 1 / 4;
    }
  }

  @media (max-width: 720px) {
    .smart-deck-app-rail {
      grid-column: 1;
      grid-row: 2;
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
      padding: 0.65rem 0.85rem;
      border-right: none;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      gap: 0.75rem;
      overflow: auto hidden;
    }

    .smart-deck-app-rail__logo {
      width: 38px;
      height: 38px;
      flex: 0 0 auto;
    }

    .smart-deck-app-rail__nav {
      flex-direction: row;
      width: auto;
      align-items: center;
      justify-content: flex-start;
      min-width: max-content;
    }

    .smart-deck-app-rail__nav button {
      width: auto;
      min-width: 72px;
      padding: 0.55rem 0.5rem;
    }
  }
</style>
