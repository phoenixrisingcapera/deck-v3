<script lang="ts">
  import { page } from '$app/state';
  import AppLogo from '$lib/components/AppLogo.svelte';

  interface Props {
    deckId: string;
    activePanel?: 'canvas' | 'elements' | 'text' | 'design' | 'media' | 'brand' | 'data' | 'deck_map' | 'ai';
  }

  let { deckId, activePanel = 'canvas' }: Props = $props();

  const items = [
    { panel: 'canvas', icon: '▣', label: 'Canvas' },
    { panel: 'elements', icon: '◌', label: 'Elements' },
    { panel: 'text', icon: 'T', label: 'Text' },
    { panel: 'design', icon: 'D', label: 'Design' },
    { panel: 'media', icon: '▧', label: 'Media' },
    { panel: 'brand', icon: 'B', label: 'Brand' },
    { panel: 'data', icon: '◫', label: 'Data' },
    { panel: 'deck_map', icon: 'DM', label: 'Deck Map' },
    { panel: 'ai', icon: 'AI', label: 'AI Tools' }
  ] as const;

  // Preserve the origin query param so context-aware return works after edits
  const origin = $derived(page.url.searchParams.get('origin') ?? null);

  function smartEditHref(panel?: string) {
    const params = new URLSearchParams();
    if (panel && panel !== 'canvas') params.set('panel', panel);
    if (origin) params.set('origin', origin);
    const qs = params.toString();
    return `/decks/${deckId}/smart-edit${qs ? `?${qs}` : ''}`;
  }
</script>

<aside class="smart-edit-sidebar" aria-label="Smart Edit tools">
  <div class="smart-edit-sidebar__logo" aria-label="Deck AI Stack">
    <AppLogo size="sm" />
  </div>

  <nav aria-label="Smart Edit tool panels">
    {#each items as item}
      <a
        class:active={activePanel === item.panel}
        href={smartEditHref(item.panel)}
        title={item.label}
        aria-current={activePanel === item.panel ? 'page' : undefined}
        aria-controls={item.panel === 'ai' ? 'smart-edit-ai-workspace' : undefined}
      >
        <span class="icon" aria-hidden="true">{item.icon}</span>
        <span class="label">{item.label}</span>
      </a>
    {/each}
  </nav>
</aside>

<style>
  .smart-edit-sidebar {
    grid-column: 1;
    grid-row: 1;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(7, 11, 22, 0.94);
    padding: 1rem 0.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .smart-edit-sidebar__logo {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    display: grid;
    place-items: center;
    box-shadow: 0 16px 30px rgba(124, 58, 237, 0.35);
    overflow: hidden;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    width: 100%;
    align-items: center;
  }

  a {
    width: 100%;
    display: grid;
    justify-items: center;
    gap: 0.25rem;
    padding: 0.65rem 0.2rem;
    border-radius: 14px;
    border: 1px solid transparent;
    background: transparent;
    color: #94a3b8;
    text-decoration: none;
    font-size: 0.68rem;
  }

  a.active {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.9), rgba(14, 165, 233, 0.85));
    color: white;
    box-shadow: 0 14px 28px rgba(76, 29, 149, 0.35);
  }

  a[href*="panel=ai"]:not(.active) {
    border-color: rgba(124, 58, 237, 0.24);
    background: rgba(124, 58, 237, 0.08);
  }

  .icon {
    font-size: 0.95rem;
    font-weight: 700;
  }

  .label {
    line-height: 1.1;
  }
</style>
