/**
 * unionLoader — Astro content collection loader factory.
 *
 * Walks every discovered peer for files under <peer.absDir>/<collectionName>/
 * (recursively), parses frontmatter, injects provenance fields if absent,
 * and writes each as a content store entry.
 *
 * The id encodes provenance: `${peer.slug}/${relPath-without-extension}`.
 * Routes split it back apart at request time.
 */

import { readFile } from 'node:fs/promises';
import { glob as fsGlob } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseFrontmatter } from './frontmatter.ts';
import { discoverPeers, type PeerSource } from './peerDiscovery.ts';

export interface UnionLoaderOptions {
  collectionName: 'changelog' | 'context-v';
  /** Absolute path to apps/memopop-site/ — defaults to process.cwd(). */
  siteDir?: string;
}

interface AstroLoaderArgs {
  store: {
    clear(): void;
    set(entry: { id: string; data: unknown; body?: string }): void;
  };
  parseData: (args: { id: string; data: unknown }) => Promise<unknown>;
  logger: { info: (msg: string) => void; warn: (msg: string) => void };
}

export function unionLoader(options: UnionLoaderOptions) {
  return {
    name: `memopop-union:${options.collectionName}`,
    load: async ({ store, parseData, logger }: AstroLoaderArgs): Promise<void> => {
      store.clear();

      const siteDir = options.siteDir ?? process.cwd();
      const peers = await discoverPeers({ siteDir });

      let totalLoaded = 0;
      let totalSkipped = 0;
      const perPeer = new Map<string, number>();

      for (const peer of peers) {
        const has = options.collectionName === 'changelog' ? peer.hasChangelog : peer.hasContextV;
        if (!has) continue;

        const collectionDir = resolve(peer.absDir, options.collectionName);
        const { loaded, skipped } = await loadFromPeer({
          peer,
          collectionDir,
          collectionName: options.collectionName,
          store,
          parseData,
          logger,
        });
        totalLoaded += loaded;
        totalSkipped += skipped;
        perPeer.set(peer.slug, loaded);
      }

      const breakdown = [...perPeer.entries()]
        .filter(([, n]) => n > 0)
        .map(([slug, n]) => `${slug}=${n}`)
        .join(' ');

      // Astro's content logger already prefixes with the loader name, so
      // we don't repeat it here.
      logger.info(
        `${totalLoaded} entries from ${perPeer.size} peers — ${breakdown || 'none'}` +
          (totalSkipped > 0 ? ` (${totalSkipped} skipped: publish:false)` : ''),
      );
    },
  };
}

interface LoadFromPeerArgs {
  peer: PeerSource;
  collectionDir: string;
  collectionName: 'changelog' | 'context-v';
  store: AstroLoaderArgs['store'];
  parseData: AstroLoaderArgs['parseData'];
  logger: AstroLoaderArgs['logger'];
}

async function loadFromPeer({
  peer,
  collectionDir,
  collectionName,
  store,
  parseData,
  logger,
}: LoadFromPeerArgs): Promise<{ loaded: number; skipped: number }> {
  let loaded = 0;
  let skipped = 0;

  let files: string[];
  try {
    files = [];
    for await (const f of fsGlob('**/*.md', { cwd: collectionDir })) {
      files.push(f);
    }
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
      logger.warn(`glob failed for ${peer.slug}: ${(err as Error).message}`);
    }
    return { loaded: 0, skipped: 0 };
  }

  for (const relPath of files) {
    if (relPath === 'README.md' || relPath.endsWith('/README.md')) continue;

    const absPath = resolve(collectionDir, relPath);
    let text: string;
    try {
      text = await readFile(absPath, 'utf8');
    } catch (err) {
      logger.warn(`read failed for ${absPath}: ${(err as Error).message}`);
      continue;
    }

    const { data, body } = parseFrontmatter(text);
    if (data.publish === false) { skipped++; continue; }

    const merged = {
      ...data,
      from: data.from ?? peer.slug,
      from_path: data.from_path ?? relPath,
      from_kind: data.from_kind ?? peer.kind,
    };

    const idBase = relPath.replace(/\.md$/, '');
    const id = `${peer.slug}/${idBase}`;

    let parsed: unknown;
    try {
      parsed = await parseData({ id, data: merged });
    } catch (err) {
      logger.warn(`schema rejected ${id} (${(err as Error).message}); storing raw frontmatter`);
      parsed = merged;
    }

    store.set({ id, data: parsed, body });
    loaded++;
  }

  return { loaded, skipped };
}
