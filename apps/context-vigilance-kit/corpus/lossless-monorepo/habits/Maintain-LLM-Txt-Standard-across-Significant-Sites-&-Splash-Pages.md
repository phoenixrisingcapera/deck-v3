---
title: Maintain the llms.txt standard across significant sites & splash pages
lede: Every substantive site serves `/llms.txt` and `/llms-full.txt`, regenerated
  on deploy, so crawlers ingest the corpus in one fetch.
date_created: 2026-05-09
date_modified: 2026-05-09
semantic_version: 0.1.0.0
augmented_with: Claude Code on Claude Opus 4.7 (1M context)
status: Active
applies_to: every Lossless Group site or splash with a substantive content collection
  (corpus, blog, changelog, docs, case studies)
tags:
- Habit
- LLM-Discovery
- GEO
- llms-txt
- Splash-Page
- Astro-Knots
- Context-Vigilance
site_uuid: 2bacb512-bca7-4090-a653-b08148526df0
hex_code: 95nm2p
date_authored_initial_draft: 2026-05-09
date_authored_current_draft: 2026-05-09
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: habits/Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/habits/Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md"
---

# Maintain the llms.txt standard across significant sites & splash pages

> Repo-level habit. Generic to every site we publish that has content worth ingesting.
> **Reference implementation:** [`ai-labs/context-vigilance-kit/splash/`](../../ai-labs/context-vigilance-kit/splash/) — read its `src/llms/README.md` end-to-end before scaffolding a new one.
> **How-to skill:** [`open-graph-share-seo-geo`](../agent-skills/open-graph-share-seo-geo/SKILL.md), specifically [`references/llms-txt-implementation.md`](../agent-skills/open-graph-share-seo-geo/references/llms-txt-implementation.md).

## Why this exists

LLMs are crawlers now. When a model goes to learn what's on one of our sites — to cite us in a conversation, to answer a question that depends on something we wrote, to ground a recommendation in our taxonomy — its first instinct is to fetch a few pages, parse the HTML, strip the chrome, and assemble a working understanding. Across a 500-doc corpus that's slow, lossy, expensive, and rate-limit-prone. The model gives up before it gets to the proof.

The [llms.txt standard](https://llmstxt.org/) (published in 2024) is the lightweight fix: a small markdown file at `/llms.txt` that lists what's available, and an optional `/llms-full.txt` that contains the full content concatenated. One fetch. Already markdown, no parser needed. The spec is small enough that a junior dev can implement it in an evening, and the maintenance burden after that is zero — the file regenerates from the same content collection that drives the site's HTML pages.

We adopt it because Context Vigilance is, fundamentally, a thesis that **giving the agent the right context, in the right shape, before you ask it for code is the difference between "almost worked" and "shipped."** If we preach that to our readers, we should practice it for the agents reading us.

> [!IMPORTANT] One file. Two files for sites with substantive bodies.
>
> A site with 5 pages doesn't need this. A site with 50 markdown documents does. A splash that aggregates rolled-up content from a dozen child repos absolutely does. Use judgment.

## What "having it" means

Every site this habit applies to should ship:

1. **`/llms.txt`** at the site root — a markdown link index per the spec, with site framing, reference links, and a per-section listing of every published content entry.
2. **`/llms-full.txt`** at the site root (when content is markdown-first) — every published entry's raw markdown body concatenated, each preceded by a metadata header (title, source, canonical URL, last-modified date), separated by horizontal rules.
3. **A `src/llms/` directory** containing the human-editable markdown templates (`llms.md`, `llms-full.md`) and a local `README.md` documenting the site's token vocabulary.
4. **An optional `<link rel="alternate" type="text/markdown" href="/llms.txt">`** in the layout's `<head>` for explicit discoverability.
5. **Build-time generation** — the files are emitted during `pnpm build`, never at request time.

For pseudomonorepo splashes that aggregate child-repo content, the `/llms.txt` lists rolled-up entries with provenance (which child repo each came from), and `/llms-full.txt` includes the full rolled-up bodies.

## Locked conventions

These are deliberate. Don't drift without a reason.

### Source of truth: prose lives in markdown, not TypeScript

The voice, framing, opening blockquote, reference-section links, and corpus-intro paragraph all live in `src/llms/llms.md` (and `src/llms/llms-full.md`). The endpoint at `src/pages/llms.txt.ts` imports the markdown via Vite's `?raw` query, substitutes `{{TOKEN}}` placeholders, and emits.

**Why:** the people who tweak voice are not always the people who tweak code. Putting prose in TypeScript template literals forces a developer-flavored review process for what should be a copy edit. Splash maintainers will avoid the file. The text rots.

### Endpoint is a dumb assembler, not a writer

The `.ts` file does three things: load template, build token map, substitute. Token substitution is a regex `template.replace(/\{\{(\w+)\}\}/g, ...)` — no Mustache, no Handlebars, no templating engine. Missing tokens pass through unchanged so typos surface in the output instead of disappearing silently.

### Absolute URLs everywhere, computed at build time

```ts
const site = import.meta.env.SITE;
const base = import.meta.env.BASE_URL;
const root = new URL(base, site).toString().replace(/\/$/, '');
```

All links inside `/llms.txt` and `/llms-full.txt` are `${root}/...`. When the site moves to a custom domain, the URLs update automatically — no endpoint change needed.

### Same publish/private gate as the rendered HTML

If `[...slug].astro` filters with `data.publish !== false && data.private !== true`, the endpoint must use the same predicate. Anything not in the rendered HTML must not be in `/llms-full.txt` either — otherwise drafts leak.

### Build statically, never at request time

Astro static endpoints (default `output: 'static'`). Generating multi-MB `/llms-full.txt` over a 500-doc corpus on every request would blow up render budgets. The endpoints emit `dist/llms.txt` and `dist/llms-full.txt` once per deploy.

### Canonical token vocabulary

| Token | Replaced with |
|---|---|
| `{{SITE_NAME}}` | Static site name from `STATIC_SEO.siteName` (`src/lib/seo.ts`) |
| `{{ENTRY_COUNT}}` | Number of published entries in the primary collection |
| `{{REPO_COUNT}}` | Number of distinct source repos (rolled-up splashes only) |
| `{{SEARCH_URL}}` | Absolute URL to the site's search page |
| `{{LLMS_FULL_URL}}` | Absolute URL to `/llms-full.txt` |
| `{{LLMS_INDEX_URL}}` | Absolute URL to `/llms.txt` |
| `{{CORPUS_INDEX}}` | Generated link list, grouped by source — used in `llms.md` |
| `{{CORPUS_BODIES}}` | Generated concatenation of raw bodies — used in `llms-full.md` |

Add tokens as the site needs them. Document each one in the site's `src/llms/README.md` so future editors can see the vocabulary.

## Reference file layout

```
<site>/
├── src/
│   ├── llms/
│   │   ├── README.md          # token vocabulary, scoped to this site
│   │   ├── llms.md            # template for /llms.txt
│   │   └── llms-full.md       # template for /llms-full.txt (optional)
│   ├── pages/
│   │   ├── llms.txt.ts        # endpoint — assembles /llms.txt
│   │   └── llms-full.txt.ts   # endpoint — assembles /llms-full.txt
│   ├── lib/
│   │   └── seo.ts             # already present; provides STATIC_SEO.siteName
│   └── layouts/
│       └── BaseLayout.astro   # add <link rel="alternate" type="text/markdown"> for discoverability
└── astro.config.mjs           # `site` and `base` are read by the endpoints at build time
```

## Conformance gap on path-deployed GitHub Pages splashes

The spec assumes the file lives at the host root: `https://host/llms.txt`. Splashes deployed under a path on `lossless-group.github.io` (e.g., `/context-vigilance-kit/`) place the file at the path, not the host root. **Convention-based discovery — a crawler that just GETs `/llms.txt` from the host — won't catch them until DNS for the custom domain lands.**

This is **not a blocker** for shipping the habit. Tools pointed explicitly at the path-based URL still work today. Endpoints read `import.meta.env.SITE` and `BASE_URL` at build time and emit absolute URLs, so when `astro.config.mjs` flips `base` to `'/'` and `site` to the custom domain, conformance kicks in automatically with no code change.

For the meantime, the optional `<link rel="alternate" type="text/markdown">` tag in `<head>` provides explicit discoverability for any tool that examines the page first.

## Acceptance — "this site has llms.txt"

Verify before declaring the habit met:

- [ ] `src/llms/llms.md` exists with site-appropriate prose using `{{TOKEN}}` placeholders.
- [ ] `src/llms/llms-full.md` exists (skip only for non-markdown-first sites — see Variants below).
- [ ] `src/llms/README.md` documents the token vocabulary used in this site's templates.
- [ ] `src/pages/llms.txt.ts` exists, imports the template via `?raw`, substitutes tokens, and emits `text/markdown`.
- [ ] `src/pages/llms-full.txt.ts` exists with the same shape (when `/llms-full.txt` is shipped).
- [ ] `pnpm build` produces `dist/llms.txt` and `dist/llms-full.txt`.
- [ ] No `{{TOKEN}}` strings remain in the built output: `grep -oE '\{\{[A-Z_]+\}\}' dist/llms.txt` returns empty.
- [ ] All links in the index resolve: spot-check 3–5 with `curl -s -o /dev/null -w "%{http_code}\n"` after deploy.
- [ ] `Content-Type: text/markdown; charset=utf-8` on both files: `curl -sI '<host>/llms.txt'`.
- [ ] `BaseLayout.astro` includes `<link rel="alternate" type="text/markdown" href={`${base}llms.txt`}>`.
- [ ] Same publish/private gate as `[...slug].astro` for the corresponding collection.

## Maintenance cadence

- **On every content addition.** Authors don't touch llms.txt — the endpoint regenerates from the same content collection that drives the site's HTML. The next deploy refreshes both files.
- **When site voice or framing shifts.** Edit `src/llms/llms.md` or `src/llms/llms-full.md` directly. No code review needed for prose changes — same path as any other hand-authored markdown in the repo.
- **When you add a new dynamic value.** Add a new `{{TOKEN}}` to the template, register it in the endpoint's tokens map, and document it in `src/llms/README.md`. All three together, in one commit.
- **When the publish/private gate changes in `[...slug].astro`.** Re-derive the predicate from the live page template and replace it in the endpoint. The two must not drift.
- **When the site moves to a custom domain.** Flip `astro.config.mjs` `site` and `base` — endpoints automatically emit host-root URLs and become spec-conformant.
- **Periodically (quarterly).** Open the live `/llms.txt`, scan the rendered prose, sanity-check that the framing still matches how the site describes itself elsewhere. Voice drift is the failure mode that's hardest to catch in CI.

## Variants

- **Pseudomonorepo splashes with rolled-up content** (the canonical case — `content-farm/splash`, `astro-knots/splash`, `lfm/splash`, `context-vigilance-kit/splash`): full pattern. `/llms.txt` lists entries with provenance (which child repo each came from); `/llms-full.txt` concatenates rolled-up bodies. Same publish gate as the rolled-up rendering.
- **Astro Knots client sites** (`mpstaton.com`, `the-water-foundation.com`, `fullstack-vc.com`, `hypernova-site`, etc.): smaller surface area. Ship `/llms.txt` with site purpose + key page links. Skip `/llms-full.txt` unless the site has a substantive blog or case-study collection — for a portfolio with five top-level pages, `/llms.txt` alone is enough.
- **Documentation sites** (the eventual `lfm/splash` evolution, future SDK docs): both files. Documentation is exactly the use case the spec was designed for.
- **Lossless main site** (`lossless.group`): both files, with the index grouped by section (projects, plugins, writing, principles).

## What this habit deliberately is not

- **Not** an SEO replacement. Standard OpenGraph + JSON-LD + canonical URLs still apply. llms.txt is a separate concentric ring around them — see the [`open-graph-share-seo-geo`](../agent-skills/open-graph-share-seo-geo/SKILL.md) skill for how the rings fit together.
- **Not** for slide-deck-only sites or one-shot fundraise pages. Crawl-and-cite is rarely the goal there; access gates often apply.
- **Not** dynamic. The files are generated at build time, never at request time. Any freshness comes from a deliberate redeploy (which the splash habit already triggers on push to `main`).
- **Not** a content management system. The endpoint reads from existing content collections — same source of truth as the rendered HTML pages. New content lands in the collection; the next deploy refreshes both files automatically.
- **Not** an excuse to skip robots.txt. If you want to gate AI crawlers, do it at robots.txt; llms.txt does not authorize anything by itself.

## See also

- **Reference implementation:** `ai-labs/context-vigilance-kit/splash/` — `src/llms/{llms.md, llms-full.md, README.md}` plus `src/pages/{llms.txt.ts, llms-full.txt.ts}`. 460 corpus entries from 27 source repos, 132 KB index + 5.7 MB full file, built in ~30ms.
- **The spec:** [llmstxt.org](https://llmstxt.org/) — small enough to read in 10 minutes.
- **How-to skill:** [`open-graph-share-seo-geo`](../agent-skills/open-graph-share-seo-geo/SKILL.md) — the broader OG/SEO/GEO conventions this fits into. Specifically:
  - The [`## llms.txt` section](../agent-skills/open-graph-share-seo-geo/SKILL.md) of `SKILL.md` for the rules and rationale.
  - [`references/llms-txt-implementation.md`](../agent-skills/open-graph-share-seo-geo/references/llms-txt-implementation.md) for the full porting recipe with copy-paste-ready endpoint code.
- **Sibling habits:**
  - [`Maintain-a-Github-Splash-Page-for-each-Repo.md`](Maintain-a-Github-Splash-Page-for-each-Repo.md) — the splashes are the primary surface this habit applies to.
  - [`Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md`](Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md) — the search-engine companion to this habit. Both ship together; the sitemap filter explicitly excludes the llms.txt endpoints so the two don't pollute each other.
  - [`Maintain-an-Astro-Knots-site-for-Major-Projects.md`](Maintain-an-Astro-Knots-site-for-Major-Projects.md) — major-project Astro Knots sites also ship llms.txt.
  - [`Maintain-Projects-Collections-on-Lossless-Site.md`](Maintain-Projects-Collections-on-Lossless-Site.md) — the org site itself qualifies.
  - [`Maintain-a-Current-README-and-other-Docs.md`](Maintain-a-Current-README-and-other-Docs.md) — llms.txt is one of "those Docs," but for agents instead of humans.
- **Skills the agent should consult when scaffolding llms.txt on a new site:**
  - `open-graph-share-seo-geo` — the rules and the porting recipe (above).
  - `astro-knots` — framework rules and prohibitions.
  - `context-vigilance` — context-v directory roles and frontmatter discipline.
  - `pseudomonorepos` — for splashes that roll up child-repo content; the same publish gate applies to the rolled-up entries.
