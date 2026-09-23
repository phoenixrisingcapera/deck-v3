---
name: llms-templates-readme
description: How the /llms.txt and /llms-full.txt endpoints assemble their output
  — token vocabulary and edit conventions.
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/splash/src/llms/README.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/splash/src/llms/README.md"
---

# llms.txt templates

The endpoints at `src/pages/llms.txt.ts` and `src/pages/llms-full.txt.ts` are
dumb assemblers. The voice and framing of `/llms.txt` and `/llms-full.txt` live
in the markdown files in this directory, with `{{TOKEN}}` placeholders for any
value computed at build time.

**To change voice / framing:** edit the markdown.
**To add a new dynamic value:** add the token here, then add the substitution
in the endpoint.

## Tokens

| Token | Replaced with |
|---|---|
| `{{SITE_NAME}}` | `STATIC_SEO.siteName` from `src/lib/seo.ts` |
| `{{SKILL_COUNT}}` | Number of skills in the `skills` collection |
| `{{CHANGELOG_COUNT}}` | Number of published changelog entries |
| `{{SEARCH_URL}}` | Absolute URL to `/search/` |
| `{{LLMS_INDEX_URL}}` | Absolute URL to `/llms.txt` |
| `{{LLMS_FULL_URL}}` | Absolute URL to `/llms-full.txt` |
| `{{SKILLS_INDEX}}` | Generated link list of skills (alpha by title) — used in `llms.md` |
| `{{CHANGELOG_INDEX}}` | Generated link list of changelog entries (date_modified desc) — used in `llms.md` |
| `{{CORPUS_BODIES}}` | Generated concatenation of raw markdown bodies — used in `llms-full.md` |

## The publish gate

Both endpoints apply `entry.data.publish !== false` — the same filter the
rendered HTML pages use. Anything excluded from the rendered site is also
excluded from the LLM-facing files.

## Why markdown, not template literals

Voice and framing are human-edited, not dev-edited. Putting prose inside a
`.ts` template literal would force a developer-flavored review process for what
should be a copy edit. Keeping the source-of-truth in markdown means future
maintainers can edit the file without touching the endpoint logic.

Spec: https://llmstxt.org/
