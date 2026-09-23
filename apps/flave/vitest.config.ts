import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Tests render components to an HTML string via `svelte/server`, so they run in
// a node environment with no DOM. That is deliberate: the fixture suite asserts
// on rendered markup substrings, and a DOM would add cost without adding proof.
export default defineConfig({
  plugins: [svelte()],
  test: {
    environment: 'node',
    include: ['packages/*/test/**/*.test.ts'],
  },
});
