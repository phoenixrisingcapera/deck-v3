import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// ─── Lenient preprocessors ────────────────────────────────────────────────
// The corpus aggregates context-v files from across the Lossless tree, each
// authored by hand under different conventions. The schema must tolerate
// every shape — never throw on author-written frontmatter.

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

const lenientDate = z.preprocess(
  (v) => {
    if (v === undefined || v === null || v === '') return undefined;
    if (v instanceof Date) return Number.isNaN(v.getTime()) ? undefined : v;
    if (typeof v === 'string') {
      const t = v.trim();
      if (!t || t === '[]' || t === '~' || /^tbd$/i.test(t)) return undefined;
      const d = new Date(t);
      return Number.isNaN(d.getTime()) ? undefined : d;
    }
    return undefined;
  },
  z.date().optional(),
);

const lenientBoolean = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.boolean().optional(),
);

// ─── Corpus collection ────────────────────────────────────────────────────
// Reads every collated markdown file under ../corpus/. The collator stamps
// provenance keys (source_root, source_relative_path, source_repo_slug,
// collated_at) on each copy; we surface those on the entry.

const corpusSchema = z
  .object({
    title: lenientString,
    lede: lenientString,
    description: lenientString,
    summary: lenientString,
    status: lenientString,
    semantic_version: lenientString,

    date_created: lenientDate,
    date_modified: lenientDate,

    authors: lenientStringArray,
    augmented_with: lenientStringArray,
    tags: lenientStringArray,

    // Provenance keys stamped by the collator.
    source_root: lenientString,
    source_relative_path: lenientString,
    source_repo_slug: lenientString,
    collated_at: lenientString,

    publish: lenientBoolean,
    private: lenientBoolean,
  })
  .passthrough();

const corpus = defineCollection({
  loader: glob({ pattern: '**/*.md', base: '../corpus' }),
  schema: corpusSchema,
});

export const collections = { corpus };
