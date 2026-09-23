# id-didi-sh · splash

GitHub Pages presence for [`lossless-group/id-didi-sh`](https://github.com/lossless-group/id-didi-sh) —
the didi.sh identity service. A small Astro site that renders the repo's
`changelog/` and `context-v/` alongside the platform pitch: **one login to
fast-track DD-ready materials**, with the three services (memos, decks,
augment-it) as near-copies of their ai-labs/splash marketing cards.

Live URL: **https://lossless-group.github.io/id-didi-sh/**

## What this is

- **Astro** (no React, no JSX) per the Astro Knots conventions.
- **Single-project variant** — the splash reads `../changelog` and
  `../context-v` as plain file IO from the parent repo's working tree. No
  rollup, no submodules, no `.env`.
- **Pagefind search** — indexed at build time over the changelog and
  context-v detail pages. `kind:` and `tag:` facets.
- **Three-mode theme** — dark ("the vault", default), light ("security
  paper"), vibrant ("UV lamp"). Two-tier tokens per the `theme-system`
  convention.

## Visual posture — "credential"

This splash dresses like what the service is: an identity document.
Guilloche line-work (banknote/passport engraving) as the background
ornament, a SPECIMEN ID card as the hero object, stamp chrome for statuses,
IBM Plex + Space Grotesk type, terse datasheet voice. Deliberately distinct
from the memopop / content-farm / lfm / ai-labs splashes per the
`maintain-splash-pages` divergence discipline.

## Local dev

```sh
cd splash
pnpm install --ignore-workspace   # splash installs independently
pnpm dev                           # http://localhost:4321/id-didi-sh/
```

Search is index-at-build-time only — run `pnpm build && pnpm preview` to
exercise it locally.

## Deploy

Push to `main` → `.github/workflows/pages.yml` builds `splash/` and deploys
via `actions/deploy-pages@v4`. The workflow bootstraps Pages on first run
(`configure-pages` with `enablement: true`); the repo's Pages source should
read **"GitHub Actions"**.

## Where content lives

| Surface | Source |
|---|---|
| Hero + credential datasheet copy | `src/pages/index.astro` + `src/lib/seo.ts` |
| The three service cards | `src/content/service-highlights/*.md` (near-copied from `ai-labs/splash`) |
| Changelog | `../changelog/*.md` (the repo's real ship log) |
| Context | `../context-v/**/*.md` |
| OG banner | `public/og-banner.png` (1200×630) |

The CTA points at `https://id.didi.sh/` — live once the identity service
deploys (spec increment 5). Until then the splash says so: invite-only
while in build.
