---
title: Maintain sitemap.xml and robots.txt across significant sites & splash pages
lede: Every site that wants to be found ships an `@astrojs/sitemap` build and a `robots.txt`
  with an absolute `Sitemap:` pointer.
date_created: 2026-05-09
date_modified: 2026-05-09
semantic_version: 0.1.0.0
augmented_with: Claude Code on Claude Opus 4.7 (1M context)
status: Active
applies_to: every Lossless Group splash, marketing site, and Astro Knots client site
  that wants to be indexed by search engines
tags:
- Habit
- SEO
- Sitemap
- Robots
- Splash-Page
- Astro-Knots
site_uuid: e8b3aa49-caee-470a-9cce-fb48c035493b
hex_code: 2eudug
date_authored_initial_draft: 2026-05-09
date_authored_current_draft: 2026-05-09
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: habits/Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/habits/Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md"
---

# Maintain sitemap.xml and robots.txt across significant sites & splash pages

> Repo-level habit. Generic to every site we publish that wants discoverability.
> **Reference implementation:** [`ai-labs/context-vigilance-kit/splash/`](../../ai-labs/context-vigilance-kit/splash/) — `astro.config.mjs` + `public/robots.txt` + `src/layouts/BaseLayout.astro`. All five Lossless splashes (cvk, astro-knots, content-farm, memopop-site, lfm) ship this pattern.
> **How-to skill:** [`open-graph-share-seo-geo`](../agent-skills/open-graph-share-seo-geo/SKILL.md), specifically the `## Sitemap & robots.txt` section and [`references/sitemap-implementation.md`](../agent-skills/open-graph-share-seo-geo/references/sitemap-implementation.md).

## Why this exists

A sitemap is the cheapest, most boring SEO win available. Without one, a search engine has to walk every link from your homepage to discover what's there — slow, lossy, biased toward whatever the homepage emphasizes. Without a `robots.txt` pointer, the crawler doesn't even know your sitemap exists.

The Astro team maintains an official integration (`@astrojs/sitemap`) that walks every static route at build time and emits a valid sitemap with absolute URLs. Setup is two lines: install the package, add to integrations array. There is no excuse to skip it.

`robots.txt` is the canonical discovery path — crawlers fetch it first and follow the `Sitemap:` directive. It also tells crawlers what's off-limits if anything is. Without robots.txt you depend on the crawler stumbling onto your sitemap by URL convention, which works for Google but isn't guaranteed elsewhere.

Together they're the floor of "this site is set up correctly for search." Everything else (canonical URLs, OG tags, JSON-LD, llms.txt) builds on top.

## What "having it" means

Every site this habit applies to should ship:

1. **`@astrojs/sitemap` integration** in `astro.config.mjs`, with a filter excluding non-HTML routes (`/llms.txt`, `/llms-full.txt`, `/404`).
2. **`public/robots.txt`** containing `User-agent: *`, `Allow: /`, and an **absolute** `Sitemap:` URL pointing at the deployed sitemap-index.
3. **`<link rel="sitemap" type="application/xml" href={`${base}sitemap-index.xml`} />`** in `BaseLayout.astro`'s `<head>`.
4. **Build output** — `dist/sitemap-index.xml` + `dist/sitemap-0.xml` + `dist/robots.txt` all present and correct after every deploy.

The integration auto-discovers everything Astro emits. There is no manual URL list to maintain.

## Locked conventions

These are deliberate. Don't drift without a reason.

### The official integration, never a hand-rolled sitemap

We use `@astrojs/sitemap` (maintained by Astro Core). Don't write a custom endpoint that emits XML. Don't use a third-party fork. The official integration handles trailing slashes, the `site` + `base` composition, sitemap chunking, and the `<lastmod>` timestamps correctly out of the box.

### One filter, one shape, copied across splashes

```js
sitemap({
  filter: (page) =>
    !page.includes('/llms.txt') &&
    !page.includes('/llms-full.txt') &&
    !page.endsWith('/404/') &&
    !page.endsWith('/404'),
})
```

This filter is the same on every Lossless splash. If a splash adds new non-HTML endpoints, **extend** the filter. Don't relax the existing exclusions.

### Absolute URL in the `Sitemap:` line of robots.txt

Search engines treat `Sitemap:` as an absolute URL by spec. A relative path is invalid. For a path-deployed splash on GitHub Pages, the path must be in the URL:

```
Sitemap: https://lossless-group.github.io/<repo>/sitemap-index.xml
```

When a custom domain lands and `astro.config.mjs` flips, update `robots.txt` in the same commit. The integration regenerates the sitemap automatically from `site` + `base`; only the static `robots.txt` needs a manual edit.

### The `<link rel="sitemap">` in head is small but expected

Place it next to the favicon `<link>` tag and the llms.txt `<link rel="alternate">` tag — they're root-relative resource hints that belong together.

### `customPages` is forbidden

`@astrojs/sitemap` accepts a `customPages` option for hand-listing URLs the integration can't auto-discover. We don't use it. Every page in our sites is an Astro route the integration finds for free. If a page is missing from the sitemap, the cause is (a) the filter excludes it, (b) it isn't actually being rendered, or (c) it's an API/endpoint route that shouldn't be in the sitemap. Diagnose at the source — never paper over it with `customPages`.

## Reference file layout

```
<site>/
├── astro.config.mjs               # imports @astrojs/sitemap, registers in integrations[]
├── package.json                   # has @astrojs/sitemap as a dependency
├── public/
│   └── robots.txt                 # absolute Sitemap: line
└── src/
    └── layouts/
        └── BaseLayout.astro       # <link rel="sitemap"> in <head>
```

After build, the output:

```
dist/
├── sitemap-index.xml              # generated by integration
├── sitemap-0.xml                  # generated by integration; one URL per included page
├── robots.txt                     # copied from public/
└── ...
```

## Conformance gap on path-deployed GitHub Pages splashes

GitHub Pages serves project sites under `https://lossless-group.github.io/<repo>/`. The sitemap and robots.txt deploy at:

- `https://lossless-group.github.io/<repo>/sitemap-index.xml`
- `https://lossless-group.github.io/<repo>/robots.txt` (also at host root via Astro's `public/` copy-through)

This is **fine** for indexing — Google and Bing both follow the absolute `Sitemap:` URL in robots.txt regardless of path. When DNS for a custom domain lands and `astro.config.mjs` flips `base` to `'/'`, the URLs become root-level and look exactly like a textbook setup. No code changes needed beyond the `astro.config.mjs` flip and the `robots.txt` `Sitemap:` line update.

## Acceptance — "this site has sitemap+robots"

Verify before declaring the habit met:

- [ ] `@astrojs/sitemap` is in `package.json` dependencies.
- [ ] `astro.config.mjs` imports and registers `sitemap()` in the integrations array.
- [ ] The integration's `filter` callback excludes `/llms.txt`, `/llms-full.txt`, and `/404`.
- [ ] `public/robots.txt` exists with `User-agent: *`, `Allow: /`, and an absolute `Sitemap:` URL.
- [ ] `BaseLayout.astro` has `<link rel="sitemap" type="application/xml" href={`${base}sitemap-index.xml`} />` in `<head>`.
- [ ] `pnpm build` (or `bun run build`) produces `dist/sitemap-index.xml` and `dist/sitemap-0.xml`.
- [ ] `dist/robots.txt` is present (copied through from `public/`).
- [ ] URL count matches expectations: `grep -o '<url>' dist/sitemap-0.xml | wc -l` returns the number of HTML pages minus the filtered routes. **Note: `grep -c` returns 1 because Astro emits single-line minified XML — use `grep -o ... | wc -l`.**
- [ ] Filter verified: `grep -E '/llms\.txt</loc>|/llms-full\.txt</loc>|/404/</loc>' dist/sitemap-0.xml` returns empty.
- [ ] After deploy, `curl https://<host>/<base>/sitemap-index.xml` returns valid XML.
- [ ] After deploy, `curl https://<host>/robots.txt` shows the absolute Sitemap URL.

## Maintenance cadence

- **On every content addition.** No manual sitemap edit needed — the integration regenerates from the same routes Astro emits. Next deploy refreshes both files automatically.
- **When a new non-HTML route is added** (a new `.json`, `.txt`, `.xml` endpoint, etc.). Extend the `filter` callback in `astro.config.mjs` to exclude it. Same commit as the new route.
- **When the site moves to a custom domain.** Update `astro.config.mjs` (`site` to the domain, `base` to `'/'`) AND update `public/robots.txt` (`Sitemap:` line) in the same commit. Submit the new sitemap to Google Search Console / Bing Webmaster Tools for fast re-indexing.
- **When `@astrojs/sitemap` releases a new minor.** Bump the dep at the same cadence as other Astro deps. Breaking changes are rare; the integration is mature.
- **Periodically (quarterly).** Verify the live `/sitemap-index.xml` is fresh — `<lastmod>` should reflect the most recent deploy. If a URL pattern changed (e.g., a route was renamed), the old URL's 404 in the sitemap will surface in Search Console eventually; fix at source.

## Variants

- **Pseudomonorepo splashes with rolled-up content** (cvk, content-farm, astro-knots, lfm): full pattern. Sitemap auto-includes rolled-up content because each rolled-up entry is a real Astro route. The publish/private gate that filters rolled-up entries from rendering also keeps them out of the sitemap.
- **Astro Knots client sites** (`mpstaton.com`, `the-water-foundation.com`, `fullstack-vc.com`, etc.): full pattern. Sitemap is even more important on client sites since they have custom domains and are aiming for search visibility.
- **Lossless main site** (`lossless.group`): full pattern.
- **Slide-deck-only sites and gated decks** (`calmstorm-decks` and similar): **skip the integration**. Ship `robots.txt` with `User-agent: *` + `Disallow: /` instead. Gated content shouldn't be in any search engine's index.
- **Internal tooling and admin dashboards**: same as above — `Disallow: /`, no sitemap.

## What this habit deliberately is not

- **Not** a substitute for OpenGraph or schema.org metadata. Sitemap is *discovery*; OG and schema are *presentation*. Both are needed.
- **Not** a substitute for `llms.txt`. Sitemap is for search engines (HTML pages, ranked for human readers). llms.txt is for LLMs (markdown, ingested as a corpus). They're complementary; the sitemap filter explicitly excludes the llms endpoints.
- **Not** dynamic. The sitemap regenerates only at build time. Any freshness comes from a deliberate redeploy.
- **Not** a hand-maintained URL list. We never use `customPages`. The integration discovers routes; if it can't, the route is the problem.
- **Not** an excuse to skip robots.txt. The integration alone doesn't ship robots.txt — the static file in `public/` is its complement and is required.

## See also

- **Reference implementation:** all five Lossless splashes:
  - `ai-labs/context-vigilance-kit/splash/` (463 URLs)
  - `astro-knots/splash/` (162 URLs)
  - `content-farm/splash/` (95 URLs)
  - `ai-labs/memopop-ai/apps/memopop-site/` (128 URLs; uses bun)
  - `lfm/splash/` (17 URLs; long base path `/lossless-flavored-markdown-package/`)
- **The Astro integration:** [`@astrojs/sitemap` docs](https://docs.astro.build/en/guides/integrations-guide/sitemap/)
- **The standards:** [sitemaps.org](https://www.sitemaps.org/) protocol; [Google Search Central — Sitemap docs](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview)
- **How-to skill:** [`open-graph-share-seo-geo`](../agent-skills/open-graph-share-seo-geo/SKILL.md), specifically:
  - The [`## Sitemap & robots.txt` section](../agent-skills/open-graph-share-seo-geo/SKILL.md) of `SKILL.md`.
  - [`references/sitemap-implementation.md`](../agent-skills/open-graph-share-seo-geo/references/sitemap-implementation.md) for the full porting recipe with copy-paste-ready config.
- **Sibling habits:**
  - [`Maintain-a-Github-Splash-Page-for-each-Repo.md`](Maintain-a-Github-Splash-Page-for-each-Repo.md) — splashes are the primary surface this habit applies to.
  - [`Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md`](Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md) — the LLM-facing companion to this habit. Both ship together; the sitemap filter explicitly excludes the llms.txt endpoints so the two don't pollute each other.
  - [`Maintain-an-Astro-Knots-site-for-Major-Projects.md`](Maintain-an-Astro-Knots-site-for-Major-Projects.md) — major-project Astro Knots sites also ship sitemap+robots.
  - [`Maintain-Projects-Collections-on-Lossless-Site.md`](Maintain-Projects-Collections-on-Lossless-Site.md) — the org site itself qualifies.
- **Skills the agent should consult when scaffolding sitemap on a new site:**
  - `open-graph-share-seo-geo` — the rules and the porting recipe (above).
  - `astro-knots` — framework rules and prohibitions.
  - `pseudomonorepos` — for splashes that roll up child-repo content; the same publish gate that excludes rolled-up entries from rendering also keeps them out of the sitemap.
