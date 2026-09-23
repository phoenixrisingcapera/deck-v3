/**
 * /llms-full.txt — concatenated raw markdown of every published corpus entry.
 *
 * Spec: https://llmstxt.org/
 *
 * The human-editable prose template for this file lives at
 * `splash/src/llms/llms-full.md` (with token documentation in
 * `splash/src/llms/README.md`). This file is the dumb assembler: it loads
 * the template, gathers the corpus bodies, and substitutes tokens. To tweak
 * voice or framing, edit the markdown — not this file.
 */

import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { STATIC_SEO } from '@lib/seo';
import template from '../llms/llms-full.md?raw';

export const GET: APIRoute = async () => {
  const site = import.meta.env.SITE ?? 'https://lossless-group.github.io';
  const base = import.meta.env.BASE_URL ?? '/';
  const root = new URL(base, site).toString().replace(/\/$/, '');

  const all = await getCollection('corpus');
  const published = all.filter(
    (e) => (e.data as any).publish !== false && (e.data as any).private !== true,
  );

  published.sort((a, b) => {
    const ra = ((a.data as any).source_repo_slug || 'unknown').toLowerCase();
    const rb = ((b.data as any).source_repo_slug || 'unknown').toLowerCase();
    if (ra !== rb) return ra.localeCompare(rb);
    const ta = ((a.data as any).title ?? a.id).toLowerCase();
    const tb = ((b.data as any).title ?? b.id).toLowerCase();
    return ta.localeCompare(tb);
  });

  const bodyParts: string[] = [];
  for (const entry of published) {
    const data = entry.data as any;
    const title = data.title ?? entry.id;
    const repo = data.source_repo_slug || 'unknown';
    const sourcePath = data.source_relative_path || entry.id;
    const url = `${root}/corpus/${entry.id}/`;

    bodyParts.push('---');
    bodyParts.push('');
    bodyParts.push(`## ${title}`);
    bodyParts.push('');
    bodyParts.push(`- Source repo: \`${repo}\``);
    bodyParts.push(`- Source path: \`${sourcePath}\``);
    bodyParts.push(`- Canonical URL: ${url}`);
    if (data.date_modified) {
      const dm = data.date_modified instanceof Date ? data.date_modified : new Date(data.date_modified);
      if (!Number.isNaN(dm.getTime())) bodyParts.push(`- Last modified: ${dm.toISOString().slice(0, 10)}`);
    }
    bodyParts.push('');
    bodyParts.push(entry.body ?? '');
    bodyParts.push('');
  }

  const tokens: Record<string, string> = {
    SITE_NAME: STATIC_SEO.siteName,
    ENTRY_COUNT: String(published.length),
    LLMS_INDEX_URL: `${root}/llms.txt`,
    CORPUS_BODIES: bodyParts.join('\n').trimEnd(),
  };

  const body = template.replace(/\{\{(\w+)\}\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(tokens, name) ? tokens[name] : match,
  );

  return new Response(body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};
