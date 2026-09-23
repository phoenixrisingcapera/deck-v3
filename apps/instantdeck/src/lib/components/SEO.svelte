<script lang="ts">
  import { SITE, buildTitle, canonicalUrl } from '$lib/seo/seo';
  import type { SeoConfig } from '$lib/seo/seo';

  let { seo }: { seo: SeoConfig } = $props();

  const title = $derived(buildTitle(seo.title));
  const url = $derived(canonicalUrl(seo.canonicalPath));
  const image = $derived(seo.image || SITE.defaultImage);
  const robots = $derived(seo.noindex ? 'noindex, nofollow' : 'index, follow');
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={seo.description} />
  <meta name="robots" content={robots} />
  <link rel="canonical" href={url} />

  {#if seo.keywords?.length}
    <meta name="keywords" content={seo.keywords.join(', ')} />
  {/if}

  <meta property="og:site_name" content={SITE.name} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={seo.description} />
  <meta property="og:url" content={url} />
  <meta property="og:type" content={seo.type || 'website'} />
  <meta property="og:image" content={image} />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={title} />
  <meta name="twitter:description" content={seo.description} />
  <meta name="twitter:image" content={image} />

  {#if seo.type === 'article' && seo.publishedTime}
    <meta property="article:published_time" content={seo.publishedTime} />
  {/if}

  {#if seo.type === 'article' && seo.modifiedTime}
    <meta property="article:modified_time" content={seo.modifiedTime} />
  {/if}
</svelte:head>
