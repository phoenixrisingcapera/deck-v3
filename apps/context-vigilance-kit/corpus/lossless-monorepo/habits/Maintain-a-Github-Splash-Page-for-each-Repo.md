---
title: Maintain a Github Splash Page for each Repo
lede: Every Lossless Group repo ships a small Astro site under splash/ that turns
  the repo into a free GitHub Pages landing page — hero, curated gallery, changelog
  and context-v rendering — without committing to a real marketing surface too early.
date_created: 2025-11-14
date_modified: 2026-05-05
semantic_version: 0.1.0.0
augmented_with: Claude Code on Opus 4.7
status: Active
applies_to: every Lossless Group repository (single-project or pseudomonorepo)
tags:
- Habit
- Astro-Knots
- Github-Pages
- Splash-Page
- Pseudomonorepos
site_uuid: b5161e1b-55bc-4a02-947a-2bc8be2cd60a
hex_code: qur9rm
date_authored_initial_draft: 2025-11-14
date_authored_current_draft: 2025-11-14
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: habits/Maintain-a-Github-Splash-Page-for-each-Repo.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/habits/Maintain-a-Github-Splash-Page-for-each-Repo.md"
---

# Maintain a Github Splash Page for each Repo

> Repo-level habit. Generic to every repo we own.
> **Reference implementation:** [`content-farm/splash/`](../../content-farm/splash/) — read its `README.md` end-to-end before scaffolding a new one.
> **First instance (predates the habit):** `ai-labs/memopop-ai/apps/memopop-site/` (lives at `apps/<name>` for historical reasons; new splashes use `splash/`).

## Why this exists

GitHub Pages is free. Every repo has a story — the why, the what, the where-it's-going — and a README pull-quote isn't enough. Readers want a hero, links, a sense of the artifact. We have a unified marketing surface at https://lossless.group but it's busy and indivdual projects get buried. The primary org website also has its own style and aesthetic, and splash pages can serve as experimentation for radically different design, layout, and UX/UI innovations. And, rather than wait the full-org collaboration and page development process, we ship a small splash page (possibly with supporting pages and docs) per repo off GitHub Pages, named `splash/` precisely to leave linguistic room for the eventual marketing site without renaming this one.

This is **a starting point, not the destination.** When a project deserves a custom-domain, or featuring on the lossless-group site, we build that separately; the splash stays put as the source repo's own Pages presence hosted on github.

> [!IMPORANT] Update the splash in addition to readme and docs
>
> This does mean we have `one more thing` to maintain, but given the speed of agent-human cooperation and the contextual information all being created already, it's worth the tradeoff.

## What "having one" means

Every repo should ship:

1. **A landing page** — hero, value proposition, curated content gallery, philosophy/principles, recent-activity teaser, CTA.
2. **A changelog renderer** — list (`/changelog/`) + per-entry detail (`/changelog/[...slug]`).
3. **A context-v renderer** — list grouped by subdirectory (`/context-v/`) + per-entry detail (`/context-v/[...slug]`).
4. **A deploy pipeline** — push to `main` builds and deploys. No manual deploy.
5. **A README at `splash/README.md`** — local dev, deploy, where content lives, how to update.
6. **`/llms.txt` (and `/llms-full.txt` when content is markdown-first)** — machine-readable corpus for LLM crawlers and agentic tools, per the [`Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md`](Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md) habit. Endpoints at `src/pages/llms.txt.ts` + `src/pages/llms-full.txt.ts`; prose templates at `src/llms/{llms.md, llms-full.md}`.
7. **`/sitemap-index.xml` + `/sitemap-0.xml` + `/robots.txt`** — search-engine discoverability, auto-generated via `@astrojs/sitemap`, per the [`Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md`](Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md) habit. Filter excludes `/llms.txt`, `/llms-full.txt`, and `/404` so the sitemap stays HTML-only.

> [!NOTE] Iteration towards consistent and usable frontmatter
> 
> Because the splash page concept is much newer than changelog and content-v, historical projects may not have consistency to enable the rendering of all content in the `changelog` and `context-v` dirs.  This is not a critical problem, but over time agent-human teams should revise/update historical frontmatter to enable better rendering.

For pseudomonorepos (children as submodules), the splash also aggregates each child's `changelog/` and `context-v/` into the parent's feeds via the **roll-up pattern** (see below).

## Locked conventions

These are deliberate. Don't drift without a reason.

### Tech & structure
- **Astro.** No React, no JSX. (See the `astro-knots` skill.)
- **Directory name:** `splash/` at repo root. *Not* `site/`. *Not* `apps/<name>`. The name preserves linguistic space for a future custom-domain marketing site.
- **Package name:** `<repo>-splash`. `private: true`. Astro is the only required dep at minimum.
- **TypeScript path aliases** in `tsconfig.json`: `@components/*`, `@layouts/*`, `@loaders/*`, `@content/*`, `@pages/*`, `@/*` — so loader code never needs `../../../` guesswork.

### Build & host
- **Host:** GitHub Pages, project-page form. Live URL pattern: `https://lossless-group.github.io/<repo>/`.
- **`astro.config.mjs`:** `site: 'https://lossless-group.github.io'`, `base: '/<repo>/'`, `trailingSlash: 'ignore'`, `build.format: 'directory'`. If a custom domain is ever added, set `site` to it and `base` to `'/'`.
- **Build trigger:** push to `main`. Aligns with the `development` → `main` → `master` tier model — things land on `main` when they're noteworthy enough to publish.
- **Deploy action:** `actions/deploy-pages@v4` with `actions/configure-pages@v5` using `enablement: true` so the workflow bootstraps Pages on first run.
- **No submodule fetching in CI for pseudomonorepos** — rolled-up content is pre-synced and committed; CI does pure file IO.

### Local dev
- `pnpm install --ignore-workspace` — required because the parent monorepo's `pnpm-workspace.yaml` does not include splash sites; the splash installs its deps independently.
- `pnpm dev` respects the configured `base`; visit `http://localhost:4321/<repo>/`.

### How the splash stays isolated from its parent repo

The splash sits inside a repo that may itself be built, rendered, or deployed. Several different mechanisms keep them from stepping on each other — they're often confused, so to be explicit:

| Concern | What enforces it |
|---|---|
| Don't publish the splash to the npm registry | `private: true` in `splash/package.json` |
| Parent install/build skips the splash | parent's `pnpm-workspace.yaml` (omit `splash/` from `packages:`) — and inside `splash/`, use `pnpm install --ignore-workspace` to opt out of the parent workspace |
| Parent Astro site doesn't render splash content | parent's `content.config.ts` globs don't reach into `splash/` |
| Splash content commits with the repo | nothing — git tracks it by default, which is what we want |

`private: true` is *only* about the npm registry. Workspace boundaries are what keep the parent's tooling from touching the splash.

### Content rendering
- Use **Lossless Flavored Markdown (LFM)** for body rendering once wired in. Until then, Astro's built-in `render(entry).Content` against a `.prose` styling target is acceptable.
- **Lenient frontmatter schemas:** every field in `content.config.ts` uses `z.preprocess` to coerce empty strings, nulls, and unexpected types gracefully. Schemas **never throw** on legacy entries — they `safeParse` and store raw frontmatter as a fallback.
- **`publish: false`** in any frontmatter excludes that entry from listings everywhere. Honor it.
- **Curated highlights collection** drives any landing-page gallery. One markdown file per item under `src/content/<thing>-highlights/`. Frontmatter: `title`, `lede`, `order` (integer; lower sorts first; alphabetical tiebreak by filename — never throws), `status`, `repo`, `icon`, `featured`, `tags`. The body renders as the long-form description.

### Editorial
- **Hand-curated** gallery. No algorithmic manifest pulling. A coding agent edits the curated list when the set changes.
- **Provenance visible** on rolled-up entries — readers can see which child repo each entry came from.
- **Hero copy** lives in `src/lib/seo.ts` and the `index.astro` frontmatter. Short, opinionated, written for someone who's never heard of the repo.
- **Stats / philosophy / contributor bands** are optional but encouraged. They make the repo feel intentional and they're cheap.

## Reference file layout

```
<repo>/
├── splash/
│   ├── astro.config.mjs              # base: '/<repo>/', trailingSlash: 'ignore'
│   ├── package.json                  # private; "<repo>-splash"; astro
│   ├── tsconfig.json                 # path aliases
│   ├── .env.example                  # GITHUB_API_TOKEN= (pseudomonorepos only)
│   ├── README.md                     # local dev, deploy, curation, where things live
│   ├── public/                       # favicon.svg, og image, brand marks
│   ├── scripts/
│   │   └── rollup-sync.ts            # pseudomonorepos only
│   └── src/
│       ├── content.config.ts         # lenient schemas + (pseudomono) unionLoader
│       ├── content/<thing>-highlights/   # curated gallery cards (one .md per item)
│       ├── rollup/                   # pseudomono only — synced submodule content; committed; do not hand-edit
│       ├── loaders/                  # frontmatter, githubContentApi, parseGitmodules, rollupFetch
│       ├── lib/seo.ts                # static SEO copy
│       ├── layouts/BaseLayout.astro  # tokens, fonts, head, body shell
│       ├── components/               # PluginCard / ProjectCard, MetaTags, etc.
│       └── pages/
│           ├── index.astro
│           ├── changelog/index.astro
│           ├── changelog/[...slug].astro
│           ├── context-v/index.astro
│           └── context-v/[...slug].astro
└── .github/workflows/pages.yml       # deploy splash/ on push to main
```

## The roll-up pattern (pseudomonorepos only)

A splash inside a pseudomonorepo aggregates each child's `changelog/` and `context-v/` into the parent's feeds. Use **sync-on-demand**, never sync-on-build.

| | Sync-on-build | Sync-on-demand (required) |
|---|---|---|
| Build time | 30s+ (API calls) | ~1s (file IO) |
| CI auth | needs `GITHUB_TOKEN` | none |
| Rate limits | every build counts against 5000/hr | sync runs at human cadence |
| Diff visibility | invisible — content materializes only at render | `git diff` shows what rolled up |
| Determinism | depends on remote state at build time | what you commit is what deploys |

Implementation rules:

- `pnpm rollup:sync` writes to `splash/src/rollup/`. **Commit those files.**
- Each synced file gets injected provenance frontmatter: `from` (child slug), `from_path` (path within source repo), optional `legacy: true`.
- A one-line marker at the top of each synced file: `<!-- Rolled up from <slug>/<path>. Edit at the source, not here. Re-run \`pnpm rollup:sync\` to refresh. -->`.
- `src/content.config.ts` uses a `unionLoader` to merge parent's local `changelog/` and `context-v/` with the `src/rollup/` tree.
- Auth: `GITHUB_TOKEN` or `GITHUB_API_TOKEN` from shell or `splash/.env`. Anonymous (60 req/hr) is acceptable for occasional manual syncs; one full sync uses ~60–70 calls.
- The sync script writes a marker `src/rollup/README.md` so anyone exploring the tree sees the directory is generated and gets the refresh recipe.

When to run `rollup:sync`:

- A child shipped a noteworthy `changelog/` entry you want surfaced.
- You bumped a submodule pointer.
- Periodically (e.g. weekly) to catch upstream drift.

## Acceptance — "this repo has a splash"

Verify before declaring the habit met:

- [ ] `splash/` directory exists at repo root
- [ ] `splash/astro.config.mjs` has correct `site` and `base: '/<repo>/'`
- [ ] `splash/README.md` documents local dev, deploy, and where content lives
- [ ] `pnpm install --ignore-workspace && pnpm build` succeeds from a clean clone
- [ ] `splash/dist/` includes routes for `/`, `/changelog/`, `/context-v/`, plus per-entry detail routes when entries exist
- [ ] `.github/workflows/pages.yml` exists, builds `splash/`, and deploys via `actions/deploy-pages@v4`
- [ ] GitHub Pages source is set to **"GitHub Actions"** in repo settings
- [ ] First deploy reaches `https://lossless-group.github.io/<repo>/` and loads cleanly
- [ ] (Pseudomonorepos only) `pnpm rollup:sync` runs locally; `splash/src/rollup/` is committed; rolled-up content appears on the live site with provenance
- [ ] `/llms.txt` (and `/llms-full.txt` when content is markdown-first) deploys at the splash root, per the [`Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md`](Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md) habit's acceptance checklist
- [ ] `/sitemap-index.xml`, `/sitemap-0.xml`, and `/robots.txt` all deploy correctly with the absolute Sitemap URL, per the [`Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md`](Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md) habit's acceptance checklist

## Maintenance cadence

- **On every shipped change** — author a `changelog/` entry in the repo's own root; it surfaces on the splash on next deploy. (See the `changelog-conventions` skill.)
- **(Pseudomonorepos) when a child ships** — run `pnpm rollup:sync`, commit `src/rollup/`, push.
- **When the curated gallery drifts** — edit `src/content/<thing>-highlights/`. New item? Add a file. Retired? Delete its file.
- **Periodically (e.g. weekly)** — sync rollup to catch upstream drift even without a triggering event.

## Variants

- **Single-project repo (no submodules):** skip the rollup machinery. `content.config.ts` reads only the local repo's `changelog/` and `context-v/`. No `src/rollup/`, no `scripts/rollup-sync.ts`, no `splash/.env`.
- **Pseudomonorepo (children as submodules):** full pattern including roll-up.
- **Repo with a separate marketing site already:** the splash still belongs at `splash/` — it's the source repo's GitHub Pages presence, distinct from the marketing surface. Cross-link from the splash to the marketing site and back.

## What this habit deliberately is not

- **Not** the eventual marketing site. When that exists it'll live elsewhere with its own custom domain.
- **Not** a CMS. Editing happens in the source repo's markdown files; the splash renders.
- **Not** dynamic. Pure static output. Any freshness comes from a deliberate `rollup:sync` + commit + push, never from runtime fetching.

## See also

- **Reference implementation:** `content-farm/splash/` and its `README.md`.
- **Reference spec:** `content-farm/context-v/specs/Github-Splash-Page-for-Content-Farm.md` — the spec the reference implements.
- **First instance:** `ai-labs/memopop-ai/apps/memopop-site/`.
- **Sibling habits:**
  - `Maintain-a-Current-README-and-other-Docs.md` — the splash is one of "those Docs."
  - `Maintain-an-Astro-Knots-site-for-Major-Projects.md` — major projects also get a custom-domain Astro Knots site beyond the splash.
  - `Maintain-Projects-Collections-on-Lossless-Site.md` — splash + main-site gallery cross-link.
  - [`Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md`](Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages.md) — every splash with a substantive content collection also serves `/llms.txt` and `/llms-full.txt` for LLM ingest. The splash is the primary surface this habit applies to.
  - [`Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md`](Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages.md) — every splash also ships `@astrojs/sitemap` + `robots.txt` for search-engine discoverability. The companion to the llms.txt habit, optimizing for the other class of crawler.
- **Skills the agent should consult when scaffolding a new splash:**
  - `astro-knots` — framework rules and prohibitions.
  - `pseudomonorepos` — parent-repo patterns, search-first behavior, roll-up convention.
  - `context-vigilance` — context-v directory roles, frontmatter, and versioning.
  - `theme-system` — two-tier tokens, three-mode contract.
  - `changelog-conventions` — changelog frontmatter and ship-note structure.
