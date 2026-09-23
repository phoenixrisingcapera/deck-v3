#!/usr/bin/env node
/**
 * prove-flave-render — the loop's spine.
 *
 * Written once, re-run every phase. Converts "did we break the floor?" from a
 * worry into a ten-second check. Climbs the cheap rungs of the test ladder in
 * order and stops at the first red one, because a phase built on red is the
 * failure mode the loop exists to prevent.
 *
 * Usage:  pnpm prove
 */
import { spawnSync } from 'node:child_process';

const RUNGS = [
  { rung: 0, name: 'frontmatter parses', cmd: 'node', args: ['scripts/check-frontmatter.mjs'] },
  { rung: 0, name: 'styles resolve', cmd: 'node', args: ['scripts/check-styles.mjs'] },
  { rung: 0, name: 'svelte-check + tsc', cmd: 'pnpm', args: ['exec', 'svelte-check', '--tsconfig', './tsconfig.json', '--output', 'human'] },
  { rung: 1, name: 'fixture suite', cmd: 'pnpm', args: ['exec', 'vitest', 'run'] },
  { rung: 2, name: 'editor builds', cmd: 'pnpm', args: ['--filter', '@flave/editor', 'build'] },
];

let failed = null;
for (const step of RUNGS) {
  process.stdout.write(`\n── rung ${step.rung}: ${step.name} ──\n`);
  const r = spawnSync(step.cmd, step.args, { stdio: 'inherit' });
  if (r.status !== 0) { failed = step; break; }
}

if (failed) {
  console.error(`\n✗ FLOOR IS RED at rung ${failed.rung} (${failed.name}).`);
  console.error('  Do not start the next phase. Surface it.\n');
  process.exit(1);
}

console.log('\n✓ floor is green — rungs 0..2 clean.');
console.log('  Not proven here (honest list):');
console.log('   • No browser drive — the app builds and serves, but no click-path is codified.');
console.log('   • Live preview re-render on keystroke: $derived is wired but only SSR is exercised.');
console.log('   • Source-range -> click mapping is asserted in markup, not through a real click.\n');
