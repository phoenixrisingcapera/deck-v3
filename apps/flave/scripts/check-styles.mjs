#!/usr/bin/env node
/**
 * check-styles — two gates for bug classes that shipped invisibly on 2026-08-20
 * and were caught only when a human opened the app.
 *
 * GATE 1 — `:global(...)` in a plain .css file.
 *   `:global()` is a Svelte compiler construct. In a plain stylesheet it is an
 *   invalid selector, so the browser discards the ENTIRE rule. Every callout,
 *   table and code-block style in apps/editor shipped this way: present in the
 *   bundle, dead in the browser. Nothing in a server-rendered test suite can
 *   see this, because SSR asserts markup and never evaluates CSS.
 *
 * GATE 2 — `var(--token)` referencing a token theme.css does not define.
 *   Seven of eleven tokens the editor referenced did not exist. Because each
 *   had a hardcoded fallback, the result looked plausible in dark mode and
 *   silently ignored the theme contract entirely. A fallback hides the bug;
 *   this gate does not.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, extname } from 'node:path';

const THEME = 'apps/editor/src/styles/theme.css';
const SCAN_ROOTS = ['apps', 'packages'];
const SKIP_DIRS = new Set(['node_modules', 'dist', '.vite', '.svelte-kit']);

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) yield* walk(full);
    else yield full;
  }
}


/**
 * Blank out /* … *\/ comment bodies while preserving newlines, so line numbers
 * stay accurate and a comment DESCRIBING the rule does not trip the rule.
 */
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

const problems = [];

// Every token theme.css defines.
const themeSrc = readFileSync(THEME, 'utf8');
const RUNTIME_INJECTED = new Set(['--lv']); // set inline via style="--lv: …"
const defined = new Set([...themeSrc.matchAll(/^\s*(--[A-Za-z0-9_-]+)\s*:/gm)].map((m) => m[1]));

let cssFiles = 0;
let refs = 0;

for (const root of SCAN_ROOTS) {
  let files;
  try { files = [...walk(root)]; } catch { continue; }
  for (const file of files) {
    const ext = extname(file);
    if (ext !== '.css' && ext !== '.svelte') continue;
    const src = readFileSync(file, 'utf8');
    const rel = relative('.', file);

    // GATE 1 — plain CSS only. Inside .svelte, :global() is legitimate.
    if (ext === '.css') {
      cssFiles++;
      const lines = stripComments(src).split('\n');
      lines.forEach((line, i) => {
        if (line.includes(':global(')) {
          problems.push(`${rel}:${i + 1} — ":global()" in a plain .css file. Invalid CSS; the browser drops this rule. Move the style into a .svelte component, or drop the wrapper.`);
        }
      });
    }

    // GATE 2 — token references must resolve.
    for (const m of stripComments(src).matchAll(/var\(\s*(--[A-Za-z0-9_-]+)/g)) {
      const token = m[1];
      refs++;
      // Locally-declared tokens (component-scoped) are fine.
      if (new RegExp(`${token}\\s*:`).test(src)) continue;
      if (!defined.has(token) && !RUNTIME_INJECTED.has(token)) {
        problems.push(`${rel} — var(${token}) is not defined in ${THEME}. A hardcoded fallback would hide this.`);
      }
    }
  }
}

if (problems.length) {
  const unique = [...new Set(problems)];
  console.error(`✗ styles: ${unique.length} problem(s)`);
  for (const p of unique) console.error(`   • ${p}`);
  process.exit(1);
}
console.log(`✓ styles: ${cssFiles} css file(s) clean, ${refs} token reference(s) all resolve`);
