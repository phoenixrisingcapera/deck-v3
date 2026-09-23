import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// ─── Lenient preprocessors — never throw on author-written frontmatter ────

const lenientString = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.string().optional(),
);

const lenientStringArray = z.preprocess(
  (v) => {
    if (v === '' || v === null || v === undefined) return undefined;
    if (Array.isArray(v)) return v.map(String);
    if (typeof v === 'string') return [v];
    return v;
  },
  z.array(z.string()).optional(),
);

const lenientNumber = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.number().optional(),
);

const lenientBoolean = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.boolean().optional(),
);

// ─── The landing's single collection — the three service cards ────────────
// (The GitHub splash carries the changelog/context-v dev surfaces; the
//  landing is conversion-only and links back to the splash for the build
//  log.)

const serviceHighlights = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/service-highlights' }),
  schema: z
    .object({
      title: lenientString,
      lede: lenientString,
      order: lenientNumber,
      status: lenientString,
      service: lenientString,
      slug: lenientString,
      repo: lenientString,
      stamp_ink: lenientString,
      icon: lenientString,
      featured: lenientBoolean,
      tags: lenientStringArray,
      docs: lenientString,
    })
    .passthrough(),
});

export const collections = {
  'service-highlights': serviceHighlights,
};
