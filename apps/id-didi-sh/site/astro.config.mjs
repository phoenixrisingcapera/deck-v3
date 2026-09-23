// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Site for didi.sh — the apex marketing surface — the custom-domain marketing surface, deployed on
// Vercel at the apex. Derived from splash/ (the GitHub Pages presence,
// which stays put per the maintain-splash-pages convention).
//
// Static output; no search (the dev surfaces live on the splash).
export default defineConfig({
  site: 'https://didi.sh',
  base: '/',
  trailingSlash: 'ignore',

  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('/404/') && !page.endsWith('/404'),
    }),
  ],

  build: {
    format: 'directory',
  },
});
