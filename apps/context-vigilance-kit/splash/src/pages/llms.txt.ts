/**
 * /llms.txt — index of corpus content for LLM consumers.
 *
 * Spec: https://llmstxt.org/
 *
 * The human-editable prose template for this file lives at
 * `splash/src/llms/llms.md` (with token documentation in
 * `splash/src/llms/README.md`). This file is the dumb assembler: it loads
 * the template, computes dynamic values, and substitutes tokens. To tweak
 * the voice or framing of /llms.txt, edit the markdown — not this file.
 *
 * Conformance note: the spec assumes the file lives at the host root
 * (https://host/llms.txt). Until DNS for contextvigilance.com lands, the
 * splash deploys under a path (/context-vigilance-kit/), so the file lives
 * at https://lossless-group.github.io/context-vigilance-kit/llms.txt.
 * Tools pointed explicitly at that URL still work; convention-based
 * discovery starts working once `astro.config.mjs` flips `base` to '/'.
 */

import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { STATIC_SEO } from '@lib/seo';
import template from '../llms/llms.md?raw';

export const GET: APIRoute = async () => {
  const site = import.meta.env.SITE ?? 'https://lossless-group.github.io';
  const base = import.meta.env.BASE_URL ?? '/';
  const root = new URL(base, site).toString().replace(/\/$/, '');

  const all = await getCollection('corpus');
  const published = all.filter(
    (e) => (e.data as any).publish !== false && (e.data as any).private !== true,
  );

  const byRepo = new Map<string, typeof published>();
  for (const entry of published) {
    const repo = (entry.data as any).source_repo_slug || 'unknown';
    if (!byRepo.has(repo)) byRepo.set(repo, [] as any);
    byRepo.get(repo)!.push(entry);
  }
  const repos = [...byRepo.keys()].sort();
  for (const repo of repos) {
    byRepo.get(repo)!.sort((a, b) => {
      const ta = ((a.data as any).title ?? a.id).toLowerCase();
      const tb = ((b.data as any).title ?? b.id).toLowerCase();
      return ta.localeCompare(tb);
    });
  }

  const corpusLines: string[] = [];
  for (const repo of repos) {
    corpusLines.push(`### ${repo}`);
    corpusLines.push('');
    for (const entry of byRepo.get(repo)!) {
      const data = entry.data as any;
      const title = data.title ?? entry.id;
      const url = `${root}/corpus/${entry.id}/`;
      const lede = data.lede ?? data.description ?? data.summary;
      corpusLines.push(lede ? `- [${title}](${url}): ${lede}` : `- [${title}](${url})`);
    }
    corpusLines.push('');
  }

  const tokens: Record<string, string> = {
    SITE_NAME: STATIC_SEO.siteName,
    ENTRY_COUNT: String(published.length),
    REPO_COUNT: String(repos.length),
    SEARCH_URL: `${root}/search/`,
    LLMS_FULL_URL: `${root}/llms-full.txt`,
    LLMS_INDEX_URL: `${root}/llms.txt`,
    CORPUS_INDEX: corpusLines.join('\n').trimEnd(),
  };

  const body = template.replace(/\{\{(\w+)\}\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(tokens, name) ? tokens[name] : match,
  );

  return new Response(body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};
