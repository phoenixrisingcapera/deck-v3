---
site_uuid: a5b144d5-aecf-4ae4-994a-a0e9dfb63bad
hex_code: tus2jg
title: Setup Analytics across Sites
date_created: 2026-05-08
date_authored_initial_draft: 2026-05-08
date_authored_current_draft: 2026-05-18
authors:
- Michael Staton
at_semantic_version: 0.0.1.0
tags:
- Prompt
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: prompts/Setup-Analytics-Across-Sites.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/prompts/Setup-Analytics-Across-Sites.md"
---

# Note to Agents:

We have not chosen a single analytics platform, and to be honest we don't really need one but we are launching a lot of project splash pages and, for when we have a custom domain, pushing out a marketing site.  It would be good to see "traction" or "interest" once we start promoting.

## Update to May 08, 2026.  

We are going to add OpenPanel.dev to the mix.  Umami is free for three sites, and Fathom is a little more polished and allows unlimited websites (you pay based on traffic), but we can't self-host it. After poking around OpenPanel, it feels right for the job, more advanced too. And self-hosting is an option but given our traffic using the hosted version is fine, with optionality to migrate to self-hosted. 

### OpenPanel migration pass

Start with `astro-knots/sites/mpstaton-site` and migrate one site at a time. OpenPanel's hosted version is the current default for low-traffic sites because it supports multiple sites cleanly, includes richer behavior tracking than the first-pass Umami/Fathom setup, and leaves us the option to self-host later if traffic or privacy needs change.

For Astro sites, keep the same per-site `<Analytics />` component pattern and the same `import.meta.env.PROD` gate. The only value needed in rendered browser code is the OpenPanel `clientId`; secrets and MCP tokens must stay server-side and must not be emitted into HTML. Use `OPENPANEL_`-prefixed environment variables to avoid collisions with other services. The local convention for the first site is `OPENPANEL_CLIENT_ID`, mirrored into Vercel for production builds.

### OpenPanel.dev setup

```
Per site credentials will need to be added to each site and splash page .env files.

<script>
  window.op=window.op||function(){var n=[];return new Proxy(function(){arguments.length&&n.push([].slice.call(arguments))},{get:function(t,r){return"q"===r?n:function(){n.push([r].concat([].slice.call(arguments)))}} ,has:function(t,r){return"q"===r}}) }();
  window.op('init', {
    clientId: '5cb0bac1-7868-40d4-9eed-741bcb78cedc',
    trackScreenViews: true,
    trackOutgoingLinks: true,
    trackAttributes: true,
    // sessionReplay: {
    //   enabled: true,
    // },
  });
</script>
<script src="https://openpanel.dev/op1.js" defer async></script>
```

### OpenPanel Astro component pattern

```astro
---
const isProd = import.meta.env.PROD;
const openPanelClientId = import.meta.env.OPENPANEL_CLIENT_ID;
---

{isProd && openPanelClientId && (
  <>
    <script is:inline define:vars={{ openPanelClientId }}>
      window.op=window.op||function(){var n=[];return new Proxy(function(){arguments.length&&n.push([].slice.call(arguments))},{get:function(t,r){return"q"===r?n:function(){n.push([r].concat([].slice.call(arguments)))}} ,has:function(t,r){return"q"===r}}) }();
      window.op('init', {
        clientId: openPanelClientId,
        trackScreenViews: true,
        trackOutgoingLinks: true,
        trackAttributes: true,
      });
    </script>
    <script is:inline src="https://openpanel.dev/op1.js" defer async></script>
  </>
)}
```

## Rollout status (updated 2026-05-08)

### Vercel-deployed sites — confirmed live

OpenPanel script is in deployed HTML and `import.meta.env.OPENPANEL_CLIENT_ID` resolves. Verified via curl + view-source.

| Site | Component | Status | Trackers layered |
|---|---|---|---|
| `mpstaton.com` | `astro-knots/sites/mpstaton-site/src/components/Analytics.astro` | ✅ Live | Umami + Fathom + OpenPanel |
| `the-water-foundation.com` | `astro-knots/sites/twf_site/src/components/Analytics.astro` | ✅ Live | Umami + Fathom + OpenPanel |
| `fullstack-vc.com` | `astro-knots/sites/fullstack-vc/src/components/Analytics.astro` | ✅ Live | Fathom + OpenPanel (no Umami — over free-tier cap) |

### Vercel-deployed sites — code shipped, env var not yet set

| Site | Component | Status | What's left |
|---|---|---|---|
| `hypernova-site` | `astro-knots/sites/hypernova-site/src/components/Analytics.astro` | ⚠️ Inert in prod | Set `OPENPANEL_CLIENT_ID` in Vercel project Environment Variables, redeploy. The component's gate (`openPanelClientId && …`) currently emits nothing in prod HTML. |
| `lossless.group` | `site/src/components/Analytics.astro` | ⚠️ Code shipped, full deploy deferred | Legacy site — verifying / setting env var deferred to a dedicated session. |

### GitHub Pages splash sites — script in HTML, attribution unconfirmed

OpenPanel script + clientId are baked into the deployed HTML (verified via curl). Repo Variables are set; workflows inject them at build. **OpenPanel dashboards still show no events as of 2026-05-08 night.** Most likely cause: each OpenPanel project needs the deployed origin added to its allowed-domains list. Investigation deferred — see "Splash analytics — open thread" below.

**Resolved 2026-05-09:** confirmed via DevTools Network — `api.openpanel.dev/track` was returning **401 Unauthorized**. Root cause was exactly the hypothesis: each OpenPanel client's "supported domains" field was empty/missing the GitHub Pages origin. Adding `https://lossless-group.github.io/` to the `splash_astro-knots` client flipped the response to 200 in the same incognito tab. Same fix needed (and applied) for `splash_content-farm` and `splash_lossless-flavored-markdown`. No code change required — this was a dashboard-config gap.

| Splash | Component | Workflow injection |
|---|---|---|
| `lossless-group.github.io/astro-knots` | `astro-knots/splash/src/components/Analytics.astro` | `astro-knots/.github/workflows/pages.yml` — `env: OPENPANEL_CLIENT_ID: ${{ vars.OPENPANEL_CLIENT_ID }}` |
| `lossless-group.github.io/content-farm` | `content-farm/splash/src/components/Analytics.astro` | `content-farm/.github/workflows/pages.yml` (note: also needed `--ignore-workspace` on `pnpm install` to fix a build break introduced when an untracked parent `pnpm-workspace.yaml` got swept in) |
| `lossless-group.github.io/lossless-flavored-markdown-package` | `lfm/splash/src/components/Analytics.astro` | `lfm/.github/workflows/pages.yml`. OpenPanel-only — first tracker for this splash. |
| `lossless-group.github.io/context-vigilance-kit` | `ai-labs/context-vigilance-kit/splash/src/components/Analytics.astro` | `ai-labs/context-vigilance-kit/.github/workflows/pages.yml`. Wired 2026-05-09 — same exact pattern as astro-knots/splash. Pending: set `OPENPANEL_CLIENT_ID` repo Variable in `context-vigilance-kit` repo + add `https://lossless-group.github.io/` to `splash_context-vigilance` client's supported domains in OpenPanel. |
| `lossless-group.github.io/lossless-ai-labs` | `ai-labs/splash/src/components/Analytics.astro` | `ai-labs/.github/workflows/pages.yml`. Wired 2026-05-17 — same OpenPanel-only pattern as lfm/splash. Pending: create OpenPanel project (suggested name `splash_ai-labs`), set `OPENPANEL_CLIENT_ID` repo Variable in `ai-labs` repo, add `https://lossless-group.github.io/` to the project's supported domains. |

### Out of scope this round

- `lossless-group.github.io/memopop-ai` — site relocating from `apps/memopop-site/` to `memopop-ai/splash/`. Owner is handling separately; same pattern when it lands.

## Splash analytics — open thread (2026-05-08 night)

The splashes are the only surface where OpenPanel still shows zero activity despite the script deploying correctly. Things already verified:

- Script tag is in the rendered HTML on all three splash domains
- `clientId` UUID is correctly baked in (visible via `view-source:` and matches the project clientId in OpenPanel)
- `OPENPANEL_CLIENT_ID` repo Variables are set in all three repos
- Pages workflows ran successfully after the Variable was added (manual re-run on astro-knots, fresh push on lfm + content-farm)

What hasn't been confirmed yet:

- **OpenPanel project domain allowlist** — each project on openpanel.dev typically needs the deployed origin added to its allowed-domains list, otherwise events fire from the browser but get rejected server-side. Likely root cause; needs verification by checking each OpenPanel project's settings.
- **Browser blockers during testing** — uBlock, Brave Shields, Safari content blockers all default-block `openpanel.dev`. The user clicking around their own site in their normal browser may be tracking-blocked. Test in incognito with extensions off.
- **Right project / right dashboard** — confirm the OpenPanel dashboard being viewed corresponds to the clientId baked into that specific splash's HTML (not a sibling project).

**Next step on this thread:** open each OpenPanel project, add the deployed origin (`https://lossless-group.github.io`) to allowed-domains, then re-test in an incognito window. If activity appears, close the thread. If not, capture a network-tab screenshot of the OpenPanel POST request + response and compare to a known-working Vercel site.

**Closed 2026-05-09.** Confirmed via DevTools Network: `track` returned 401 before the domain was added, 200 after. The "supported domains" field on each OpenPanel client must include `https://lossless-group.github.io/` for browser events from GitHub Pages to be accepted. `clientSecret` is *not* used in browser code (only `clientId`) — any GitHub repo Secret holding `OPENPANEL_CLIENT_SECRET` for splashes is unused and can be deleted.

## Lessons captured (2026-05-08)

- **Don't pin `packageManager` in site `package.json`.** fullstack-vc had `"packageManager": "pnpm@10.15.0"` and broke Vercel builds with pnpm 10's strict postinstall-script gate (the "Ignored build scripts: esbuild, sharp" warning). The other Astro Knots sites work because they don't pin — Vercel uses its own (older) pnpm. Removing the pin is the actual fix; `pnpm.onlyBuiltDependencies` and `.npmrc only-built-dependencies[]` are defensive but don't fully cover the gate. The user phrased this as: "Vercel obeys a different version of pnpm we have been over this." Memory: `feedback_no_packagemanager_pin.md`.
- **Auth in the header doesn't gate analytics.** A hypothesis came up that fullstack-vc's auth-aware header was hiding analytics from Vercel/OpenPanel. False — `<Analytics />` is in `<head>` (BoilerPlateHTML.astro line 90), the Header is in the `<body>` and renders a logged-out default state for everyone. Anonymous traffic gets the full HTML including the analytics scripts. Proven by curl returning 200 with the OpenPanel script in the response.
- **Vercel deployment-page thumbnails can show 403 even when the site is fine.** Stale screenshots from when "Standard Protection" was enabled. The site itself returns 200 to anonymous traffic. Flip Vercel Authentication to "Disabled" if the thumbnail still matters; otherwise ignore.

## GitHub Pages env vars — operational reference

GitHub Pages itself doesn't read `.env` files — env vars must be injected at build time inside the GitHub Actions workflow. Because OpenPanel `clientId` is publicly visible in rendered HTML (it's the public side of the SDK), it lives as a **repo Variable**, not a Secret:

- Repo Settings → **Secrets and variables → Actions → Variables tab** → `New repository variable` → name `OPENPANEL_CLIENT_ID`, value = the site's clientId from OpenPanel.
- Workflow Build step exposes it via `env: OPENPANEL_CLIENT_ID: ${{ vars.OPENPANEL_CLIENT_ID }}` so Astro's `import.meta.env.OPENPANEL_CLIENT_ID` resolves at build time.
- After setting the Variable, trigger a rebuild — either `Actions → latest run → Re-run all jobs`, or push any commit to `main`/`master`.

All three splash workflows are wired this way as of 2026-05-08.

## For now in May 2026, Umami and Fathom are our starters.

> Umami will only allow three sites on their hosted platform without payment, though they have a self-host OSS option.  Fathom is a little more polished and allows unlimited websites (you pay based on traffic), but we can't self-host it.  

> Though we don't really self-host now it's an ambition of ours.

Anyway, the actual snippets are in a .gitignore folder called .analytics at monorepo root.
`/Users/mpstaton/code/lossless-monorepo/.analytics`

We have 8 sites to hook up.  Discuss.

If you read the docs for each platform, you'll see that they have different features and syntactic differences in embedding snippets.  We need to decide which one to use for each site. 

My first pass concern is just general traffic.  

Though, I would like to know what people actually click on.


---

# Convergence (2026-05-06)

We are intentionally splitting this into two passes. **This prompt is Pass 1 — get scripts live and start collecting traffic.** Pass 2 (clicks, custom events, flows, goals) is captured in a sibling prompt: [[Implement-Deeper-Analytics-Tracking]] — `/Users/mpstaton/code/lossless-monorepo/context-v/prompts/Implement-Deeper-Analytics-Tracking.md`.

## Pass 1 — Get it live (this prompt)

### Platform allocation
Already encoded in `/Users/mpstaton/code/lossless-monorepo/.analytics/Setup-Analytics-Platforms-Across-Live-Sites.md`:

- **Umami** — top 3 only (free-tier ceiling): `lossless.group`, `the-water-foundation.com`, `mpstaton.com`
- **Fathom** — all 8 sites (unlimited on traffic-based pricing)

### Implementation rules
1. **Production-only gate.** Wrap every script tag in `{import.meta.env.PROD && (...)}` so localhost and PR previews don't pollute the dashboards.
2. **One canonical `<head>` per site.** Each Astro site has multiple layouts, but only one of them should own the `<head>`. If a site renders `<head>` from several layouts, fix that first by routing through a shared `<BaseHead>` partial; analytics surfaces the duplication but is not the sole reason to fix it.
3. **Tiny `<Analytics />` component per site.** Per-site, not per-monorepo — each site is its own Astro app with its own IDs. The component just emits the two (or one) script tags, gated on `PROD`.
4. **Snippets are copied verbatim from `.analytics/Setup-Analytics-Platforms-Across-Live-Sites.md`** — do not regenerate IDs.
5. **No event instrumentation in Pass 1.** Just the passive scripts.

### Per-site placement — as shipped (2026-05-06)

Each site got an `<Analytics />` component at `src/components/Analytics.astro` containing the verbatim snippets from `.analytics/`, gated on `import.meta.env.PROD`, with `is:inline` on the script tags so Astro/Vite doesn't try to bundle the external CDN URLs.

| Site | Component | Wired into |
|---|---|---|
| `lossless.group` | `site/src/components/Analytics.astro` | `src/layouts/Layout.astro` + 3 slide-embed pages (`pages/slides/[collection]/[...slug].astro`, `pages/slides/embed/[...slug].astro`, `pages/slides/embed/astro/[...slug].astro`) |
| `the-water-foundation.com` | `astro-knots/sites/twf_site/src/components/Analytics.astro` | `BoilerPlateHTML.astro`, `OneSlideDeck.astro`, `MarkdownSlideDeck.astro` (3 layouts each emit their own `<html>` — see Pass 2 cleanup note below) |
| `mpstaton.com` | `astro-knots/sites/mpstaton-site/src/components/Analytics.astro` | `BaseLayout.astro`, `PromotionDeckLayout.astro` |
| `fullstack-vc.com` | `astro-knots/sites/fullstack-vc/src/components/Analytics.astro` | `BoilerPlateHTML.astro` (single canonical head; `OneSlideDeck` wraps `BaseThemeLayout` which wraps this) |
| `lossless-group.github.io/content-farm` | `content-farm/splash/src/components/Analytics.astro` | `src/layouts/BaseLayout.astro` |
| `lossless-group.github.io/astro-knots` | `astro-knots/splash/src/components/Analytics.astro` | `src/layouts/BaseLayout.astro` |
| `lossless-group.github.io/memopop-ai` | `ai-labs/memopop-ai/apps/memopop-site/src/components/Analytics.astro` | `apps/memopop-site/src/layouts/BaseLayout.astro` |
| `hypernova-site` | `astro-knots/sites/hypernova-site/src/components/Analytics.astro` | `src/layouts/BoilerPlateHTML.astro` |

### Skipped on lossless.group
These pages emit their own `<head>` but are debug/internal-only — no analytics added, no need:
- `src/pages/debug-mocs.astro`
- `src/pages/test-tag-mocs.astro`
- `src/pages/debug/sequential-section.astro`
- `src/pages/backlink.astro` (SSR redirect handler — no UI)

### Cleanup deferred to Pass 2 / future
- **`twf_site` head duplication**: `BoilerPlateHTML`, `OneSlideDeck`, and `MarkdownSlideDeck` all emit their own `<html>`. `MarkdownSlideDeck` even nests `<html>` inside its own `<body>` (broken). For Pass 1 we instrumented all three; the right long-term fix is to route slide layouts through `BoilerPlateHTML` so there's one canonical head. Not blocking analytics — Umami/Fathom dedupe pageviews via session, so the worst-case is double-fire on a malformed page.
- **`mpstaton-site` head duplication**: `BaseLayout` (public) and `PromotionDeckLayout` (private gated decks) each emit their own `<html>`. Both instrumented. PromotionDeck pages are noindex but still want traction tracking.
- **`lossless.group` slide-embed pages**: 3 dynamic pages emit their own complete HTML rather than going through `Layout.astro`. Could be refactored to a shared `<BaseHead>` partial. Not urgent.

### Still-open questions
- **`memopop-ai` deploy URL**: the snippet is in place, but the Fathom dashboard must list the actual live domain or events won't record. If `lossless-group.github.io/memopop-ai` is wrong (subdomain, Vercel, etc.), update the Fathom site config — no code change needed.
- **Live status**: snippets are gated on `PROD`, so any site that isn't actually deployed yet just won't fire. Safe no-op.

## Pass 2 — Deeper tracking (separate prompt)

See [[Implement-Deeper-Analytics-Tracking]]. That prompt covers:
- Fathom `trackEvent()` for CTAs, form submits, downloads
- Umami `data-umami-event` attributes and `umami.track()` calls
- Outbound link tracking (manual on both platforms)
- SPA pageview tracking (if any of the sites become SPAs)
- Goals/conversions on Fathom
- A small set of named events shared across sites for cross-site comparability

**Do not start Pass 2 work until Pass 1 is shipped and we've seen at least a week of baseline traffic.** Premature instrumentation is noise.
