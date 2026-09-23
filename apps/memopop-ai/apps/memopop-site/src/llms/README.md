# Source of truth: human-editable prose for the llms.txt endpoints

These markdown files are read at build time by the endpoints in
`src/pages/llms.txt.ts` and `src/pages/llms-full.txt.ts`. The endpoints are
deliberately dumb — they do token substitution and append the dynamic
content rolled up from the `changelog` and `context-v` content collections.
**All voice, framing, and structural prose lives here, not in TypeScript.**

If you want to tweak the wording on `/llms.txt` or `/llms-full.txt`, edit
the corresponding `.md` file in this directory and rebuild. No code changes.

## Files

- `llms.md` — template for `/llms.txt` (the link index).
- `llms-full.md` — template for `/llms-full.txt` (the concatenated full content).

## Tokens (substituted at build time)

| Token | Replaced with |
|---|---|
| `{{SITE_NAME}}` | `SITE_DEFAULTS.name` from `src/lib/seo.ts` (e.g. `MemoPop AI`) |
| `{{CHANGELOG_COUNT}}` | Number of entries in the `changelog` collection |
| `{{CONTEXTV_COUNT}}` | Number of entries in the `context-v` collection |
| `{{REPO_COUNT}}` | Number of distinct `from` (source peer) values across both collections |
| `{{SEARCH_URL}}` | Absolute URL to `/search/` on the deployed site |
| `{{LLMS_FULL_URL}}` | Absolute URL to `/llms-full.txt` |
| `{{LLMS_INDEX_URL}}` | Absolute URL to `/llms.txt` |
| `{{CHANGELOG_INDEX}}` | Generated changelog link list, grouped by `from`, sorted by date desc within each group (used in `llms.md`) |
| `{{CONTEXTV_INDEX}}` | Generated context-v link list, grouped by `from`, sorted alphabetically by title within each group (used in `llms.md`) |
| `{{CORPUS_BODIES}}` | Concatenation of raw bodies from both collections, each entry preceded by a metadata header (used in `llms-full.md`) |

Tokens are simple `{{NAME}}` placeholders — no Mustache, no Handlebars, no
templating engine. If a token is missing in the markdown, the endpoint emits
the file without it. If you add a new dynamic value, register it in the
endpoint's substitution map and document it here.

## Per-splash adaptations vs. the canonical reference

This splash differs from the canonical `context-vigilance-kit/splash` pattern
in three ways, all driven by memopop-site's actual content shape:

1. **Two collections, not one.** `changelog` and `'context-v'` are separate
   Astro content collections (see `src/content.config.ts`). The endpoints
   read both and produce two separate sections in `/llms.txt`
   (`## Changelog` and `## Context-V`). `/llms-full.txt` concatenates from
   both, with a `kind` field in each entry header to disambiguate.
2. **Provenance via `from`, not `source_repo_slug`.** Memopop's union loader
   stamps every entry with `from`, `from_kind`, and `from_path` — these
   identify which peer in the monorepo (orchestrator, this site, workspace
   itself) the entry came from. Grouping in `/llms.txt` happens by `from`.
3. **No publish/private gate.** Unlike cvk's corpus, memopop's `[...slug]`
   pages render every entry without filtering on `data.publish` or
   `data.private`. The endpoints match that behavior — every entry that
   ships in the rendered HTML also appears in `/llms.txt` and
   `/llms-full.txt`. If a publish gate is later added to the page templates,
   re-derive the predicate here and apply it to keep the two in sync.

## Why a separate directory and not `src/lib/` or `src/content/`?

`src/lib/` is for code (TypeScript). `src/content/` is for Astro content
collections, which expect specific schemas and Astro-managed loaders. These
files are neither — they're prose templates that the build step reads as raw
strings via Vite's `?raw` import. Giving them their own directory keeps the
purpose obvious and makes the source-of-truth boundary easy to find.
