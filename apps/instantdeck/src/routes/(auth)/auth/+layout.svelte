<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/state';
  import SEO from '$lib/components/SEO.svelte';
  import { publicSeoPages } from '$lib/seo/pages';
  import { normalizePath } from '$lib/seo/seo';
  import { theme } from '$lib/stores/theme';

  let { children }: { children: import('svelte').Snippet } = $props();

  const pathname = $derived(normalizePath(page.url.pathname));
  const seo = $derived(publicSeoPages[pathname] ?? publicSeoPages['/auth/sign-in']);

  if (browser) {
    theme.prime('dark');
  }
</script>

<SEO {seo} />

{@render children()}
