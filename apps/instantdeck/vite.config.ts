import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@deck-aistack-codes/shared': path.resolve('src/lib/contracts/index.ts')
    }
  },
  plugins: [sveltekit()]
});
