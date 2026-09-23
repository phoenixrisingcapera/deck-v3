// @ts-check
import { defineConfig } from 'astro/config';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

// Splash for flave.
// Hosted on GitHub Pages from lossless-group/flave.
// Live URL: https://lossless-group.github.io/flave/
//
// If a custom domain is added later, set `site` to that domain and `base` to '/'.
// (Distinct from any future custom-domain marketing site — that would live elsewhere.)
export default defineConfig({
  site: 'https://lossless-group.github.io',
  base: '/flave/',
  trailingSlash: 'ignore',

  integrations: [
    // astro-pagefind runs Pagefind against `dist/` after `astro build` and copies
    // pagefind/* into the published output. Search runs entirely client-side from
    // the static index — no backend, no cost, mode-pivot-aware via theme tokens.
    // See astro-knots/context-v/explorations/Implementing-Full-Text-Search-by-Default.md
    // for the convention rationale.
    pagefind(),

    // @astrojs/sitemap auto-generates sitemap-index.xml + sitemap-0.xml from
    // every page Astro emits. Filter excludes the llms.txt endpoints (those
    // serve LLMs, not search engines) and the 404 page.
    sitemap({
      filter: (page) =>
        !page.endsWith('/404/') &&
        !page.endsWith('/404'),
    }),
  ],

  build: {
    // Pagefind needs a stable per-page URL — directory output ensures each
    // entry's data-pagefind-body lives at /changelog/<slug>/index.html.
    format: 'directory',
  },
});
