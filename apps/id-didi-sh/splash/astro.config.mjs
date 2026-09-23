// @ts-check
import { defineConfig } from 'astro/config';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

// Splash for id-didi-sh.
// Hosted on GitHub Pages from lossless-group/id-didi-sh.
// Live URL: https://lossless-group.github.io/id-didi-sh/
//
// If a custom domain is added later, set `site` to that domain and `base` to '/'.
export default defineConfig({
  site: 'https://lossless-group.github.io',
  base: '/id-didi-sh/',
  trailingSlash: 'ignore',

  integrations: [
    pagefind(),
    sitemap({
      filter: (page) =>
        !page.includes('/llms.txt') &&
        !page.includes('/llms-full.txt') &&
        !page.endsWith('/404/') &&
        !page.endsWith('/404'),
    }),
  ],

  build: {
    format: 'directory',
  },
});
