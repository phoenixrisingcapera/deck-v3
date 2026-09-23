<script lang="ts">
  import { page } from '$app/state';

  interface Props {
    deckId?: string | null;
    instantOnly?: boolean;
  }

  let { deckId = null, instantOnly = false }: Props = $props();

  const encodedDeckId = $derived(deckId ? encodeURIComponent(deckId) : null);
  const allItems = $derived([
    { label: 'Smart Deck', href: encodedDeckId ? `/decks/${encodedDeckId}/smart-deck` : '/decks' },
    { label: 'Instant Deck', href: encodedDeckId ? `/decks/${encodedDeckId}/instant-deck` : '/decks' },
    { label: 'Smart Edit', href: encodedDeckId ? `/decks/${encodedDeckId}/smart-edit` : '/decks' },
    { label: 'Due Diligence', href: encodedDeckId ? `/decks/${encodedDeckId}/due-diligence` : '/decks' },
    { label: 'Versions', href: encodedDeckId ? `/decks/${encodedDeckId}/versions` : '/decks' },
    { label: 'Export', href: encodedDeckId ? `/decks/${encodedDeckId}/export` : '/decks' }
  ]);
  const items = $derived(instantOnly ? allItems.filter((item) => item.label === 'Instant Deck') : allItems);

  function isActive(href: string) {
    const target = new URL(href, page.url.origin);
    if (target.pathname.endsWith('/versions') && page.url.pathname.startsWith(`${target.pathname}/`)) return true;
    const targetInstant = target.searchParams.get('instant') === '1';
    const currentInstant = page.url.pathname.endsWith('/instant-deck') || page.url.searchParams.get('instant') === '1';
    if (targetInstant) return currentInstant;
    if (target.pathname.endsWith('/smart-deck')) {
      return target.pathname === page.url.pathname && !currentInstant;
    }
    if (target.pathname !== page.url.pathname) return false;
    return true;
  }
</script>

<nav class="product-surface-nav" aria-label="Product surfaces">
  {#each items as item}
    <!-- Each product surface owns a substantial server load and workspace
         registration. A document navigation prevents the previous surface's
         controller state from surviving a cross-surface tab change. -->
    <a
      class:active={isActive(item.href)}
      href={item.href}
      aria-current={isActive(item.href) ? 'page' : undefined}
      data-sveltekit-reload
    >
      {item.label}
    </a>
  {/each}
</nav>

<style>
  .product-surface-nav {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .product-surface-nav a {
    display: inline-flex;
    align-items: center;
    min-height: 38px;
    padding: 0 0.95rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.68);
    color: #cbd5e1;
    text-decoration: none;
    font-size: 0.82rem;
  }

  .product-surface-nav a.active {
    border-color: rgba(96, 165, 250, 0.5);
    background: rgba(59, 130, 246, 0.14);
    color: #f8fafc;
  }
</style>
