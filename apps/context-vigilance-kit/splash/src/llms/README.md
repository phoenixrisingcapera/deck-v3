# Source of truth: human-editable prose for the llms.txt endpoints

These markdown files are read at build time by the endpoints in
`splash/src/pages/llms.txt.ts` and `splash/src/pages/llms-full.txt.ts`. The
endpoints are deliberately dumb — they do token substitution and append the
dynamic corpus content. **All voice, framing, and structural prose lives
here, not in TypeScript.**

If you want to tweak the wording on `/llms.txt` or `/llms-full.txt`, edit
the corresponding `.md` file in this directory and rebuild. No code changes.

## Files

- `llms.md` — template for `/llms.txt` (the link index).
- `llms-full.md` — template for `/llms-full.txt` (the concatenated full content).

## Tokens (substituted at build time)

| Token | Replaced with |
|---|---|
| `{{SITE_NAME}}` | `STATIC_SEO.siteName` from `splash/src/lib/seo.ts` |
| `{{ENTRY_COUNT}}` | Number of published corpus entries |
| `{{REPO_COUNT}}` | Number of distinct `source_repo_slug` values across published entries |
| `{{SEARCH_URL}}` | Absolute URL to `/search/` on the deployed site |
| `{{LLMS_FULL_URL}}` | Absolute URL to `/llms-full.txt` |
| `{{LLMS_INDEX_URL}}` | Absolute URL to `/llms.txt` |
| `{{CORPUS_INDEX}}` | The full corpus link list, grouped by source repo (used in `llms.md`) |
| `{{CORPUS_BODIES}}` | The full corpus content, each entry preceded by a metadata header (used in `llms-full.md`) |

Tokens are simple `{{NAME}}` placeholders — no Mustache, no Handlebars, no
templating engine. If a token is missing in the markdown, the endpoint emits
the file without it. If you add a new dynamic value, register it in the
endpoint's substitution map and document it here.

## Why a separate directory and not `src/lib/` or `src/content/`?

`src/lib/` is for code (TypeScript). `src/content/` is for Astro content
collections, which expect specific schemas and Astro-managed loaders. These
files are neither — they're prose templates that the build step reads as raw
strings via Vite's `?raw` import. Giving them their own directory keeps the
purpose obvious and makes the source-of-truth boundary easy to find.
