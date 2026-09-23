<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/state';
  import Breadcrumbs from '$lib/components/decks/Breadcrumbs.svelte';
  import JsonLd from '$lib/components/JsonLd.svelte';
  import SEO from '$lib/components/SEO.svelte';
  import MarketingFooter from '$lib/components/marketing/MarketingFooter.svelte';
  import MarketingHeader from '$lib/components/marketing/MarketingHeader.svelte';
  import MarketingUtilitiesBar from '$lib/components/marketing/MarketingUtilitiesBar.svelte';
  import { breadcrumbJsonLd, organizationJsonLd, softwareApplicationJsonLd } from '$lib/seo/jsonld';
  import { publicBreadcrumbs, publicSeoPages } from '$lib/seo/pages';
  import { normalizePath } from '$lib/seo/seo';
  import { theme } from '$lib/stores/theme';

  let { children }: { children: import('svelte').Snippet } = $props();

  const shelllessPaths = ['/sign_in_landing'];
  const hideShell = $derived(shelllessPaths.some((path) => page.url.pathname.startsWith(path)));
  const pathname = $derived(normalizePath(page.url.pathname));
  const seo = $derived(publicSeoPages[pathname] ?? publicSeoPages['/']);
  const breadcrumbs = $derived(publicBreadcrumbs[pathname] ?? []);
  const breadcrumbLd = $derived(
    breadcrumbs.length > 0
      ? breadcrumbJsonLd(breadcrumbs.map((item) => ({ name: item.label, item: item.href })))
      : null
  );
  const homeStructuredData = $derived(pathname === '/' ? [organizationJsonLd(), softwareApplicationJsonLd()] : []);

  if (browser) {
    // The public site should default to the same premium dark product direction unless the user already chose otherwise.
    theme.prime('dark');
  }
</script>

<SEO {seo} />

{#each homeStructuredData as data}
  <JsonLd {data} />
{/each}

{#if breadcrumbLd}
  <JsonLd data={breadcrumbLd} />
{/if}

{#if hideShell}
  {@render children()}
{:else}
  <div class="marketing-shell">
    <MarketingUtilitiesBar />
    <MarketingHeader currentPath={page.url.pathname} />

    <main class="marketing-main">
      {#if breadcrumbs.length > 0}
        <Breadcrumbs items={breadcrumbs} />
      {/if}
      {@render children()}
    </main>

    <MarketingFooter />
  </div>
{/if}
