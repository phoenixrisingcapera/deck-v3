import { defineCollection, z } from 'astro:content';
import { unionLoader } from '@loaders/unionLoader';

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

// Accepts Dates, ISO strings, numbers; returns undefined for anything that
// isn't actually a valid date — including the workspace's `"[]"` placeholder
// for "not yet authored" and any other unparseable string. Never throws, so
// schema validation never falls back to raw frontmatter on date fields alone.
const lenientDate = z.preprocess(
  (v) => {
    if (v === undefined || v === null || v === '') return undefined;
    if (v instanceof Date) return Number.isNaN(v.getTime()) ? undefined : v;
    if (typeof v === 'number') {
      const d = new Date(v);
      return Number.isNaN(d.getTime()) ? undefined : d;
    }
    if (typeof v === 'string') {
      const t = v.trim();
      if (t === '' || t === '[]' || t === '~' || t === 'TBD' || t === 'tbd') return undefined;
      const d = new Date(t);
      return Number.isNaN(d.getTime()) ? undefined : d;
    }
    return undefined;
  },
  z.date().optional(),
);

const lenientNumber = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.number().optional(),
);

const lenientBoolean = z.preprocess(
  (v) => (v === '' || v === null ? undefined : v),
  z.boolean().optional(),
);

// ─── Provenance shared by both collections ────────────────────────────────

const provenanceFields = {
  from: lenientString,
  from_path: lenientString,
  from_kind: lenientString,
};

// ─── changelog ────────────────────────────────────────────────────────────

const changelogSchema = z
  .object({
    ...provenanceFields,

    title: lenientString,
    lede: lenientString,
    summary: lenientString,
    description: lenientString,

    date: lenientDate,
    date_authored_initial_draft: lenientDate,
    date_authored_current_draft: lenientDate,
    date_authored_final_draft: lenientDate,
    date_first_published: lenientDate,
    date_last_updated: lenientDate,
    date_created: lenientDate,
    date_modified: lenientDate,

    category: lenientString,
    status: lenientString,
    at_semantic_version: lenientString,
    semantic_version: lenientString,
    augmented_with: lenientString,
    app: lenientString,
    publish: lenientBoolean,
    usage_index: lenientNumber,

    tags: lenientStringArray,
    authors: lenientStringArray,
    files_added: lenientStringArray,
    files_modified: lenientStringArray,
    files_removed: lenientStringArray,
    files_changed: lenientStringArray,

    image: lenientString,
    image_prompt: lenientString,
    image_text: lenientString,
    banner_image: lenientString,
    portrait_image: lenientString,
    square_image: lenientString,
  })
  .passthrough();

const contextVSchema = z
  .object({
    ...provenanceFields,

    title: lenientString,
    lede: lenientString,
    summary: lenientString,
    description: lenientString,
    purpose: lenientString,

    date: lenientDate,
    date_created: lenientDate,
    date_modified: lenientDate,
    date_authored_initial_draft: lenientDate,
    date_authored_current_draft: lenientDate,
    date_authored_final_draft: lenientDate,
    date_first_published: lenientDate,
    date_last_updated: lenientDate,
    date_updated: lenientDate,
    last_verified: lenientDate,

    category: lenientString,
    status: lenientString,
    at_semantic_version: lenientString,
    semantic_version: lenientString,
    augmented_with: lenientString,
    publish: lenientBoolean,
    applies_to: lenientString,

    authors: lenientStringArray,
    tags: lenientStringArray,
    image: lenientString,
    image_prompt: lenientString,
  })
  .passthrough();

// ─── Collections ──────────────────────────────────────────────────────────

const changelog = defineCollection({
  loader: unionLoader({ collectionName: 'changelog' }),
  schema: changelogSchema,
});

const contextV = defineCollection({
  loader: unionLoader({ collectionName: 'context-v' }),
  schema: contextVSchema,
});

export const collections = {
  changelog,
  'context-v': contextV,
};
