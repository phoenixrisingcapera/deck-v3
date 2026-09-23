# flave/splash

The source repo's own GitHub Pages presence. **Not** the eventual marketing site — if flave gets one it lives elsewhere with its own domain, and the directory is named `splash/` precisely to keep that space open.

**Live:** <https://lossless-group.github.io/flave/>

## Variant

**Single-project.** No submodules, so no `src/rollup/`, no `scripts/rollup-sync.ts`, no `.env`. `content.config.ts` reads `../changelog` and `../context-v` as plain file IO.

flave publishes no packages yet, so the package-isolation discipline does not apply. **When `@flave/format`, `@flave/render`, and friends start publishing, it will** — verify all four boundaries at that point (npm `files`, JSR `publish.include`, build entry list, parent workspace exclusion) per the `maintain-splash-pages` skill. `package.json` already carries `"private": true` as the suspenders.

## Local dev

```bash
pnpm install --ignore-workspace   # required — the parent workspace excludes splash sites
pnpm dev                          # → http://localhost:4321/flave/
```

Search is indexed at build time only. `pnpm dev` mounts the search box with a missing-index message; run `pnpm build && pnpm preview` to exercise it.

## Design

The visual contract is [`DESIGN.md`](./DESIGN.md); `src/styles/theme.css` implements it. **Runtime CSS is source of truth, DESIGN.md is the contract** — when a token's value changes in CSS, update the document.

The identity is **Press Room**: graphite ground, bone type, vermilion ink, Space Grotesk over Instrument Sans, zero-radius ledger rows, registration-mark ornament, and a deliberate misregistration on display headings.

The load-bearing idea, and the one rule worth enforcing in review:

> **The clearance ramp is semantic, not decorative.** `--color-clearance-private | -team | -lp | -public` may only ever mean *"the visibility level of this content."* Never reach for amber because a card needs warmth. If a surface uses a clearance color, that surface is making a claim about who can see something.

Dark is the default mode, per DESIGN.md §3. Light and vibrant are both complete.

## Where content comes from

| Surface | Source |
|---|---|
| `/changelog/` | `../changelog/*.md` — entries with `publish: true` |
| `/context-v/` | `../context-v/**/*.md` — same filter |
| Home feature cells | `src/content/feature-highlights/*.md` — curated, one file per cell |
| Home build-order rows | Hard-coded in `src/pages/index.astro` (`STAGES`) — it tracks the spec's §1.1 and changes rarely |

To add a feature cell, drop a new `.md` in `feature-highlights/` with `title`, `lede`, and `order`. To retire one, delete the file.

## The hero is a working demo

`src/components/StrataHero.astro` renders the *same paragraph* from a real investor update at four clearance levels and lets the reader switch between them. It is a demonstration of the product's thesis, not an illustration of it — which is why the specimen text is candid rather than lorem. If the specimen ever stops being honest, replace it; a dishonest example on a splash about honest documents would be self-defeating.

## Deploy

`.github/workflows/pages.yml` builds `splash/` and deploys on push to `main`. GitHub Pages source must be set to **GitHub Actions** in repo settings; `actions/configure-pages@v5` with `enablement: true` bootstraps it on first run.

No submodule fetching in CI — the splash reads sibling directories from the same checkout.

## Known gaps

- **No OG image.** `src/lib/seo.ts` exports an empty `OG_IMAGES`, and `MetaTags.astro` omits every image tag when none is set — an absent `og:image` unfurls as a clean text card, a broken one unfurls as a grey box. The generation recipe is in `DESIGN.md` §8.
- **No `llms.txt`.** Worth adding once there is more prose than one spec.
