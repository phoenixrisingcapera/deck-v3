import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { resolveInstantHtmlRendererOrigin } from './src/lib/config/instantHtmlRendererOrigin.js';

const instantHtmlRendererOrigin = resolveInstantHtmlRendererOrigin(process.env);

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      out: 'build',
      precompress: true
    }),
    // SvelteKit generates nonces for page scripts/styles so the HTML CSP does
    // not need unsafe-inline allowances.
    csp: {
      mode: 'nonce',
      directives: {
        'default-src': ['self'],
        'base-uri': ['self'],
        'object-src': ['none'],
        'frame-ancestors': ['none'],
        'form-action': ['self'],
        // Temporary test mode: Svelte's runtime and legacy visual widgets use
        // inline bootstrap/style attributes. Keep the policy in one place so
        // the generated production header matches the mounted product tree.
        'script-src': ['self', 'unsafe-inline'],
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'https:', 'data:', 'blob:'],
        'connect-src': ['self', 'https:'],
        'font-src': ['self', 'data:'],
        'worker-src': ['self', 'blob:'],
        'frame-src': instantHtmlRendererOrigin ? [instantHtmlRendererOrigin] : ['none']
      }
    },
    alias: {
      '@deck-aistack-codes/shared': 'src/lib/contracts/index.ts',
      $components: 'src/lib/components',
      $server: 'src/lib/server',
      $types: 'src/lib/types'
    }
  }
};

export default config;
