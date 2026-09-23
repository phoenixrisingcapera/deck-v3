<script lang="ts">
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';

  const links = [
    { href: '/privacy', label: 'Privacy' },
    { href: '/terms', label: 'Terms' },
    { href: '/contact', label: 'Contact' },
    { href: '/auth/sign-in', label: 'Sign in' }
  ];
</script>

<div class="marketing-utility">
  <div class="marketing-utility__inner">
    <nav class="marketing-utility__links">
      {#each links as link}
        <a href={link.href}>{link.label}</a>
      {/each}
    </nav>
    <div class="marketing-utility__actions">
      <span class="marketing-trust">
        <span class="marketing-trust__dot"></span>
        Enterprise-grade security
      </span>
      <ThemeToggle />
    </div>
  </div>
</div>

<style>
  .marketing-utility {
    width: min(100% - 2rem, 1200px);
    margin: 0 auto;
    padding: 0.5rem 0;
  }

  .marketing-utility__inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .marketing-utility__links {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .marketing-utility__links a {
    color: var(--text-secondary);
    font-size: 12px;
    transition: color 160ms ease;
  }

  .marketing-utility__links a:hover {
    color: var(--text);
  }

  .marketing-utility__actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .marketing-trust {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 11px;
  }

  .marketing-trust__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success);
  }

  @media (max-width: 720px) {
    .marketing-trust { display: none; }
  }
</style>
