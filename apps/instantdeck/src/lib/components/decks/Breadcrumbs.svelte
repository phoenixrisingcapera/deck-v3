<script lang="ts">
  export type BreadcrumbItem = {
    label: string;
    href: string;
  };

  let { items = [] }: { items?: BreadcrumbItem[] } = $props();
</script>

<nav class="breadcrumbs" aria-label="Breadcrumb">
  <ol>
    {#each items as item, index}
      <li>
        {#if index < items.length - 1}
          <a href={item.href}>{item.label}</a>
        {:else}
          <span aria-current="page">{item.label}</span>
        {/if}
      </li>
    {/each}
  </ol>
</nav>

<style>
  .breadcrumbs {
    width: min(100% - 2rem, 1200px);
    margin: 0 auto 0.75rem;
    font-size: 0.875rem;
    color: var(--muted);
  }

  .breadcrumbs ol {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .breadcrumbs li::after {
    content: '/';
    margin-left: 0.4rem;
    color: var(--muted);
  }

  .breadcrumbs li:last-child::after {
    content: '';
  }

  .breadcrumbs a {
    color: inherit;
    text-decoration: none;
  }

  .breadcrumbs a:hover {
    text-decoration: underline;
  }
</style>
