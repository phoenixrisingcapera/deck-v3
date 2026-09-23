---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/splash/README.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/splash/README.md"
---

# lossless-agent-skills · splash

GitHub Pages splash for [lossless-group/lossless-agent-skills](https://github.com/lossless-group/lossless-agent-skills).

**Live URL:** https://lossless-group.github.io/lossless-agent-skills/

Built per the `maintain-splash-pages` skill in this repo. Operator/CLI posture (dark default, mono-forward, blueprint-grid background, brutalist hairline cards) — deliberately distinct from the sibling Lossless splashes.

## Local dev

```bash
cd splash
pnpm install --ignore-workspace
pnpm dev
```

Visit `http://localhost:4321/lossless-agent-skills/`. The `base` is respected — visiting `/` without the prefix shows nothing.

## Build + preview

```bash
pnpm build
pnpm preview
```

`pnpm build` runs Astro → Pagefind → sitemap, and writes everything to `dist/`. Use `preview` (not `dev`) to exercise search locally — Pagefind only generates its index at build time.

## What gets rendered

The splash auto-discovers content from the repo root (one level up from `splash/`):

| Where | What | Page route |
|---|---|---|
| `<repo>/*/SKILL.md` + `<repo>/*/*/SKILL.md` | Skill bodies (one card + detail page per skill) | `/skills/[slug]/` |
| `<repo>/changelog/*.md` | Changelog entries | `/changelog/[slug]/` |

No `context-v/` rendering — this repo *is* a context-v in the parent monorepo, so the skills themselves are the primary content surface.

The content config (`src/content.config.ts`) uses **lenient schemas** that never throw on legacy frontmatter — they `safeParse` and store raw frontmatter as a fallback. Every render-side date call goes through `toDate(unknown)` from `src/lib/date.ts` so a stringy date never crashes a page.

## How content is excluded

- **`publish: false`** in any frontmatter excludes that entry from both the rendered HTML and `/llms-full.txt`.
- **The skills glob** skips `splash/`, `node_modules/`, `dist/`, `.astro/`, `.git/`, `public/` by default. To skip more, extend `SKILL_EXCLUDES` in `src/content.config.ts`.

## Deploy

Push to `main`. `.github/workflows/pages.yml` runs `pnpm install --ignore-workspace && pnpm build`, uploads `splash/dist/`, and deploys via `actions/deploy-pages@v4`. First run uses `actions/configure-pages@v5` with `enablement: true` so Pages is auto-enabled.

**Pages source must be set to "GitHub Actions"** in repo settings → Pages. The `configure-pages` action handles enablement on first run, but the source toggle is a one-time manual step if Pages was previously set to "Branch."

## SEO / OG / GEO

Per the `open-graph-share-seo-geo` skill in this repo:

- **OG image** is referenced absolute (1200×630 JPEG) — placeholder in `src/lib/seo.ts` should be replaced with an ImageKit-hosted JPEG before the splash is publicly shared. JPEG (not WebP) for unfurler compatibility.
- **Sitemap** auto-generated via `@astrojs/sitemap` with a filter that excludes `/llms.txt`, `/llms-full.txt`, and `/404`.
- **robots.txt** at `public/robots.txt` declares the absolute Sitemap URL.
- **llms.txt + llms-full.txt** at the splash root — `src/llms/*.md` are the editable templates, `src/pages/llms*.txt.ts` are the dumb assemblers.
- **JSON-LD** schema (`TechArticle` for skills, `BlogPosting` for changelog) injected by `MetaTags.astro` on detail pages.

## Search

Full-text via Pagefind. `data-pagefind-body` on detail pages (`skills/[slug]`, `changelog/[slug]`); list pages opt out via `data-pagefind-ignore="all"`. Filter facets: `kind:Skill | Changelog`, plus one `tag:` per frontmatter tag. Press `/` from anywhere to open the search popover.

## Where to edit what

| To change… | Edit… |
|---|---|
| Site title / description / OG defaults | `src/lib/seo.ts` |
| Theme tokens / mode palette | `src/styles/theme.css` |
| Long-form rendering | `src/styles/prose.css` |
| Hero copy | `src/pages/index.astro` (frontmatter + body) |
| llms.txt voice / framing | `src/llms/llms.md` (not the `.ts` endpoint) |
| Skills index sort default | `src/pages/skills/index.astro` and `SortControls` props |
| Changelog index sort default | `src/pages/changelog/index.astro` |

## Visual posture

Operator/CLI — diverges from siblings:

| Axis | This splash | memopop | content-farm | lfm |
|---|---|---|---|---|
| Default mode | **dark** (operator) | dark | dark | light |
| Display + sans | **JetBrains Mono + Inter** | Fraunces + Inter | (similar) | Newsreader + Manrope |
| Hero composition | **terminal-prompt + tree panel** | centered, stacked CTAs | (similar) | asymmetric manuscript |
| Card chrome | **brutalist hairline, no glow, sharp corners** | rounded glass + glow | (similar) | printer's-mark corners |
| Background | **blueprint grid** | radial mesh + faint grid | (similar) | paper grain + margin rule |
| Brand spine | **teal + amber + magenta** | cyan + aquamarine + plum | (similar) | ink-violet + sienna + moss |
| Voice | **handbook / datasheet** | matter-of-fact | matter-of-fact | literary / manuscript |

## License

MIT, matching the parent repo.
