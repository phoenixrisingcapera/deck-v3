<script lang="ts">
  import AppLogo from '$components/AppLogo.svelte';

  let { currentPath = '/' }: { currentPath?: string } = $props();

  const nav = [
    { href: '/', label: 'Product' },
    { href: '/vcs', label: 'For VCs' },
    { href: '/pricing', label: 'Pricing' },
    { href: '/about', label: 'About' },
    { href: '/contact', label: 'Contact' }
  ];

  function isActive(href: string) {
    return currentPath === href;
  }
</script>

<header class="header">
  <a class="brand" href="/">
    <AppLogo class="header-logo" alt="Deck logo" />
    <div>
      <strong>Deck</strong>
      <p>AI-powered deck intelligence</p>
    </div>
  </a>

  <nav class="links">
    {#each nav as item}
      <a href={item.href} class:active={isActive(item.href)}>{item.label}</a>
    {/each}
  </nav>

  <div class="actions">
    <a class="ghost" href="/auth/sign-in">Sign in</a>
    <a class="button" href="/auth/sign-up">Get started</a>
  </div>
</header>

<style>
  .header {
    width: min(100% - 2rem, 1200px);
    margin: 0 auto;
    padding: 1rem 1.15rem;
    border: 1px solid rgba(115, 136, 194, 0.22);
    border-radius: 26px;
    display: flex;
    justify-content: space-between;
    gap: 1.1rem;
    align-items: center;
    background:
      linear-gradient(180deg, rgba(12, 21, 48, 0.9), rgba(8, 16, 36, 0.96));
    backdrop-filter: blur(18px);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.04),
      0 18px 44px rgba(0, 0, 0, 0.22);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.8rem;
  }
  .brand p {
    margin: 0.18rem 0 0;
    font-size: 0.84rem;
    color: rgba(221, 231, 247, 0.62);
  }

  .brand strong {
    color: #f8fbff;
  }

  :global(.header-logo) {
    width: 46px;
    height: 46px;
    border-radius: 15px;
  }

  .links,
  .actions {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .links a {
    color: rgba(223, 232, 248, 0.74);
    padding: 0.7rem 0.9rem;
    border-radius: 999px;
    transition:
      color 160ms ease,
      background 160ms ease,
      border-color 160ms ease;
    border: 1px solid transparent;
  }

  .links a.active {
    color: #f8fbff;
    border-color: rgba(103, 134, 255, 0.22);
    background: linear-gradient(135deg, rgba(73, 110, 235, 0.22), rgba(120, 82, 255, 0.18));
  }

  .links a:hover {
    color: #f8fbff;
    background: rgba(255, 255, 255, 0.04);
  }

  .ghost {
    padding: 0.8rem 1rem;
    border-radius: 999px;
    border: 1px solid rgba(115, 136, 194, 0.25);
    color: rgba(236, 243, 255, 0.86);
    background: rgba(255, 255, 255, 0.04);
  }

  @media (max-width: 1100px) {
    .header {
      border-radius: 24px;
      flex-direction: column;
      align-items: start;
    }
  }
</style>
