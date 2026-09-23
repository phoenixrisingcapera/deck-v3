import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// See src/node-builtin-stub.ts — lfm's barrel imports node builtins, so a
// browser build cannot resolve them without this aliasing.
const stub = fileURLToPath(new URL('./src/node-builtin-stub.ts', import.meta.url));

export default defineConfig({
  plugins: [svelte()],
  server: { port: 5273 },
  resolve: {
    alias: [
      { find: /^node:crypto$/, replacement: stub },
      { find: /^node:fs$/, replacement: stub },
      { find: /^node:path$/, replacement: stub },
    ],
  },
});
