/**
 * peerDiscovery — walks the monorepo to find every place that has a
 * `changelog/` or `context-v/` directory, returning each as a "peer source"
 * the unionLoader can pull from.
 *
 * Why this exists: memopop-site is nested at `apps/memopop-site/`, so the
 * astro-knots `process.cwd()/..` shortcut (which assumes the splash sits at
 * the repo root) doesn't apply. We look one level up from the site to the
 * monorepo root, then enumerate `apps/*` and `packages/*` plus the parent
 * itself.
 *
 * The resulting `slug` per peer is taken from its `package.json#name` if
 * present, falling back to the directory name. This guarantees uniqueness
 * across the workspace and gives the URL routes stable, human-readable
 * provenance segments like `/changelog/memopop-orchestrator/...`.
 */

import { readFile, readdir, stat } from 'node:fs/promises';
import { resolve, basename } from 'node:path';

export type PeerKind = 'parent' | 'app' | 'package';

export interface PeerSource {
  slug: string;
  kind: PeerKind;
  absDir: string;
  hasChangelog: boolean;
  hasContextV: boolean;
}

interface DiscoverOptions {
  /** Absolute path to apps/memopop-site/ (typically `process.cwd()` at build time). */
  siteDir: string;
}

export async function discoverPeers(opts: DiscoverOptions): Promise<PeerSource[]> {
  const monorepoRoot = resolve(opts.siteDir, '..', '..');

  const peers: PeerSource[] = [];

  const parent = await maybePeer(monorepoRoot, 'parent');
  if (parent) peers.push(parent);

  // Include every app directory — including this site itself, so its own
  // changelog/ surfaces in the archive under its own provenance slug.
  for (const dir of await listSubdirs(resolve(monorepoRoot, 'apps'))) {
    const peer = await maybePeer(dir, 'app');
    if (peer) peers.push(peer);
  }

  for (const dir of await listSubdirs(resolve(monorepoRoot, 'packages'))) {
    const peer = await maybePeer(dir, 'package');
    if (peer) peers.push(peer);
  }

  const seen = new Map<string, PeerSource>();
  for (const p of peers) {
    if (seen.has(p.slug)) {
      console.warn(`[peerDiscovery] duplicate slug "${p.slug}" — kept first (${seen.get(p.slug)!.absDir}), skipping ${p.absDir}`);
      continue;
    }
    seen.set(p.slug, p);
  }

  return [...seen.values()].sort((a, b) => {
    const order: Record<PeerKind, number> = { parent: 0, app: 1, package: 2 };
    if (order[a.kind] !== order[b.kind]) return order[a.kind] - order[b.kind];
    return a.slug.localeCompare(b.slug);
  });
}

async function maybePeer(absDir: string, kind: PeerKind): Promise<PeerSource | null> {
  const [hasChangelog, hasContextV] = await Promise.all([
    isDir(resolve(absDir, 'changelog')),
    isDir(resolve(absDir, 'context-v')),
  ]);
  if (!hasChangelog && !hasContextV) return null;

  const slug = await readPackageName(absDir) ?? basename(absDir);

  return { slug, kind, absDir, hasChangelog, hasContextV };
}

async function readPackageName(absDir: string): Promise<string | null> {
  try {
    const text = await readFile(resolve(absDir, 'package.json'), 'utf8');
    const pkg = JSON.parse(text) as { name?: string };
    if (typeof pkg.name === 'string' && pkg.name.trim()) {
      return pkg.name.replace(/^@[^/]+\//, '');
    }
  } catch {
    /* No package.json or unreadable — fall back to dirname. */
  }
  return null;
}

async function listSubdirs(parent: string): Promise<string[]> {
  try {
    const entries = await readdir(parent, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && !e.name.startsWith('.'))
      .map((e) => resolve(parent, e.name));
  } catch {
    return [];
  }
}

async function isDir(path: string): Promise<boolean> {
  try {
    const s = await stat(path);
    return s.isDirectory();
  } catch {
    return false;
  }
}

