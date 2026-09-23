#!/usr/bin/env node
/**
 * check-frontmatter — parse every context-v/ and changelog/ frontmatter block.
 *
 * The loop doc's first hard-won rule is that a list item containing ": " breaks
 * standard YAML parsers, and that it silently bit four files on the proving run.
 * A rule an agent has to remember degrades exactly when it matters; a rule the
 * proof script enforces does not. This is the cheap end of the same thesis as
 * context-v-as-a-plugin: make the convention a query, not a habit.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { parse } from 'yaml';

const ROOTS = ['context-v', 'changelog'];
const REQUIRED = ['title', 'date_created', 'date_modified'];

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (entry.endsWith('.md')) yield full;
  }
}

let checked = 0;
const problems = [];

for (const root of ROOTS) {
  let files;
  try { files = [...walk(root)]; } catch { continue; }
  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    const m = text.match(/^---\n([\s\S]*?)\n---/);
    if (!m) { problems.push(`${relative('.', file)} — no frontmatter block`); continue; }
    checked++;
    let data;
    try {
      data = parse(m[1]);
    } catch (err) {
      problems.push(`${relative('.', file)} — YAML: ${String(err.message).split('\n')[0]}`);
      continue;
    }
    const missing = REQUIRED.filter((k) => data?.[k] == null);
    if (missing.length) problems.push(`${relative('.', file)} — missing: ${missing.join(', ')}`);
  }
}

if (problems.length) {
  console.error(`✗ frontmatter: ${problems.length} problem(s) across ${checked} files`);
  for (const p of problems) console.error(`   • ${p}`);
  process.exit(1);
}
console.log(`✓ frontmatter: ${checked} files parse and carry the required keys`);
