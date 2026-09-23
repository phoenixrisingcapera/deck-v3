// @ts-check
import { defineConfig } from 'astro/config';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

// Splash for context-vigilance-kit — catalog of context-v files across
// the Lossless Group tree.
//
// Live URL: https://lossless-group.github.io/context-vigilance-kit/
// Custom domain (post-DNS): contextvigilance.com — set `site` to the domain
// and `base` to '/' when DNS lands.
export default defineConfig({
  site: 'https://lossless-group.github.io',
  base: '/context-vigilance-kit/',
  trailingSlash: 'ignore',

  integrations: [
    // astro-pagefind runs Pagefind against `dist/` after `astro build` and
    // copies pagefind/* into the published output. Search runs entirely
    // client-side from the static index — no backend, no cost.
    pagefind(),

    // @astrojs/sitemap auto-generates sitemap-index.xml + sitemap-0.xml from
    // every page Astro emits. Filter excludes the llms.txt endpoints (those
    // serve LLMs, not search engines) and the 404 page.
    sitemap({
      filter: (page) =>
        !page.includes('/llms.txt') &&
        !page.includes('/llms-full.txt') &&
        !page.endsWith('/404/') &&
        !page.endsWith('/404'),
    }),
  ],

  build: {
    // Pagefind needs a stable per-page URL — directory output ensures each
    // corpus entry's data-pagefind-body lives at /corpus/<slug>/index.html.
    format: 'directory',
  },
});
