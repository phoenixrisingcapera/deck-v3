// @ts-check
import { defineConfig } from 'astro/config';
import pagefind from 'astro-pagefind';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
//
// Dual deploy target:
//   • GitHub Pages → project page under /memopop-ai/ (lossless-group.github.io/memopop-ai/)
//   • Vercel       → served at the domain root (/)
// Vercel sets process.env.VERCEL at build time. Key `base` + `site` off it so
// asset URLs resolve on both hosts — otherwise the /memopop-ai/ base prefix
// 404s every CSS/JS asset on the Vercel domain and the page renders unstyled.
//
// Custom domain later? Point `site` at it and force base '/' (drop the branch).
const isVercel = !!process.env.VERCEL;

export default defineConfig({
  site: isVercel ? 'https://splashmemopop-ai.vercel.app' : 'https://lossless-group.github.io',
  base: isVercel ? '/' : '/memopop-ai/',
  trailingSlash: 'ignore',

  integrations: [
    // astro-pagefind runs Pagefind against `dist/` after `astro build` and copies
    // pagefind/* into the published output. Search runs entirely client-side from
    // the static index — no backend, no cost, mode-pivot-aware via theme tokens.
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
    // Pagefind needs a stable per-page URL — use directory output so each
    // entry's `data-pagefind-body` lands at /changelog/<from>/<slug>/index.html.
    format: 'directory',
  },
});
