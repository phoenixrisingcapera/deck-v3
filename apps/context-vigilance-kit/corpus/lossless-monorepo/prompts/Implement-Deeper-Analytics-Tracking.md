---
site_uuid: fe2030b1-1e85-4c8e-bd4f-e12f3b02b91b
hex_code: u9i8bl
title: Implement Deeper Analytics Tracking
date_created: 2026-05-08
date_authored_initial_draft: 2026-05-08
date_authored_current_draft: 2026-05-08
authors:
- Michael Staton
at_semantic_version: 0.0.1.0
tags:
- Prompt
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: prompts/Implement-Deeper-Analytics-Tracking.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/prompts/Implement-Deeper-Analytics-Tracking.md"
---

# Implement Deeper Analytics Tracking

> **This is Pass 2 of analytics work.** Pass 1 (just getting Umami/Fathom scripts live) is captured in [[Setup-Analytics-Across-Sites]]. **Do not start this prompt until Pass 1 has shipped on all 8 sites and at least a week of baseline traffic has been collected.** The whole point of waiting is to see what's worth instrumenting before we instrument anything.

## Note to Agents

The motivating question from the original prompt was: **"I would like to know what people actually click on."** Pass 1 doesn't answer that — it only counts pageviews. This prompt is the work that answers it.

Two analytics platforms are in play, with different tracking models:

- **Fathom** — entirely manual. No auto-tracked events. Everything is `fathom.trackEvent('Name')` after the script loads. Goals/conversions are configured in the Fathom dashboard against named events. Active on `lossless.group`, `the-water-foundation.com`, `mpstaton.com` plus all the splash/secondary sites.
- **Umami** — declarative-first via `data-umami-event="Name"` HTML attributes (no JS required), with `umami.track()` as the imperative escape hatch. Active only on the top 3 (free-tier ceiling).

Where both are active (`lossless.group`, `twf`, `mpstaton`), instrument *both* with parallel event names so we can sanity-check one platform against the other.

## Reference docs (re-read these before designing events)

- Fathom Events Overview — https://usefathom.com/docs/events/overview
- Fathom Link Clicks — https://usefathom.com/docs/events/link-clicks
- Fathom SPA pageview tracking — https://usefathom.com/docs/integrations/spa
- Umami Track Events — https://docs.umami.is/docs/track-events
- Umami Tracker Functions — https://docs.umami.is/docs/tracker-functions

## What we know from the docs (digest, May 2026)

### Fathom

- `fathom.trackEvent('event name')` — the only public API for events.
- `fathom.trackEvent('cart add', { _value: 100 })` — `_value` is in **cents**, used for monetary goals.
- **Nothing is auto-tracked.** Even outbound links require a click handler. Don't assume "outbound clicks just work" — they don't.
- Event names cannot be renamed in the dashboard once created. Pick the taxonomy carefully (see "Event taxonomy" below).
- Events do not fire on `localhost`. The `import.meta.env.PROD` gate from Pass 1 is fine; nothing extra is needed.
- For SPA-style sites (none today, but plausible later), call `fathom.trackPageview()` on route change.

### Umami

- Declarative form (preferred): `<button data-umami-event="signup-cta">Sign up</button>`. No JS required.
- Custom event properties: `data-umami-event-plan="pro"` becomes `{plan: "pro"}` on the event. **All values are stored as strings.**
- Imperative form: `umami.track('signup-cta')` or `umami.track('signup-cta', { plan: 'pro' })`.
- Event name max length: **50 characters.** Keep names short.
- Outbound link tracking is **not automatic** in the snippet we're using. If we want it, add `data-umami-event` to relevant `<a>` tags or wire a delegated click listener.

## Event taxonomy (proposed, finalize before instrumenting)

A shared taxonomy across sites lets us compare apples to apples and reuse Fathom goal definitions. Proposal:

| Event name | Fires on | Meaning |
|---|---|---|
| `cta-primary` | Click on a hero / above-the-fold primary CTA | The single most important conversion path on a splash |
| `cta-secondary` | Click on a secondary CTA (learn-more, demo, etc.) | Lower-intent interest |
| `outbound-click` | Any external link click | Where readers go next |
| `internal-nav` | Click on internal nav links from a splash | Did the splash drive site exploration? |
| `form-submit` | Successful form submission (newsletter, contact, etc.) | Hard conversion |
| `download` | Click on a downloadable asset | Asset-level interest signal |
| `read-complete` | Article/post fully scrolled (lossless.group only) | Content engagement |
| `tool-open` | Tool/toolkit page opened (lossless.group only) | Which tools attract eyeballs |

Custom properties (Umami `data-umami-event-*` / Fathom event name suffixes):
- `cta-primary` should always include the destination — Umami via `data-umami-event-dest="..."`, Fathom by appending the destination to the event name (`cta-primary -> demo-form`) since Fathom doesn't support custom properties.
- `outbound-click` should include the host — same pattern.

**Note the asymmetry:** Umami carries structured properties, Fathom doesn't. For Fathom, we synthesize uniqueness by encoding the most important property into the event name. Don't go overboard or we'll have hundreds of one-off Fathom events.

## Per-site instrumentation targets

### Splash pages (`content-farm/splash`, `astro-knots/splash`, `memopop-ai`, `hypernova-site`, `fullstack-vc`)
- `cta-primary` on the main CTA
- `cta-secondary` on any "learn more" / external doc link
- `outbound-click` on links out to docs, GitHub, demos
- `form-submit` if a signup/newsletter form exists

### `the-water-foundation.com`, `mpstaton.com`
- `cta-primary` and `cta-secondary` on hero CTAs
- `internal-nav` on top-nav links (gives a sense of what sections people care about)
- `outbound-click` on any external citations / partner links

### `lossless.group` (the heaviest site)
- `cta-primary` / `cta-secondary` on the marketing surfaces
- `internal-nav` on the global nav
- `tool-open` on tool article views (use Astro middleware or a layout-level event so it fires automatically per page)
- `read-complete` via an IntersectionObserver on a sentinel near the article footer
- `form-submit` on newsletter / contact
- `outbound-click` on external citations from articles

## Implementation patterns

### Where the events live
- **Declarative (Umami)** — directly on the JSX-like Astro markup of the component that renders the CTA / link. Don't centralize; co-location reads better and survives refactors.
- **Imperative (Fathom + Umami fallbacks)** — a single tiny `analytics.ts` per site exporting `trackEvent(name, props)` that fans out to both `fathom.trackEvent` and `umami.track` (where present). Consumers don't need to know which platforms are wired.

### A reasonable shape for the helper

```ts
// analytics.ts
declare global {
  interface Window {
    fathom?: { trackEvent: (name: string, opts?: { _value?: number }) => void };
    umami?: { track: (name: string, data?: Record<string, string>) => void };
  }
}

export function trackEvent(name: string, props?: Record<string, string>) {
  if (typeof window === 'undefined') return;
  const fathomName = props?.dest ? `${name} -> ${props.dest}` : name;
  window.fathom?.trackEvent(fathomName);
  window.umami?.track(name, props);
}
```

Outbound-link auto-instrumentation can be a single delegated listener attached once at layout level:

```ts
document.addEventListener('click', (e) => {
  const a = (e.target as HTMLElement).closest('a[href^="http"]');
  if (!a) return;
  const href = (a as HTMLAnchorElement).href;
  if (new URL(href).host === location.host) return;
  trackEvent('outbound-click', { dest: new URL(href).host });
});
```

(Verify this doesn't conflict with declarative `data-umami-event` attributes already on those `<a>` tags — Umami will fire both, which is double-counting.)

### Production gate
Same as Pass 1 — `{import.meta.env.PROD && (...)}` around any inline `<script>` we add. The helper itself is harmless to import in dev (the global APIs just won't exist), so no gate needed there.

## Goals to configure in Fathom (after events are firing)
- `cta-primary -> demo-form` (or whatever the highest-intent CTA is per site)
- `form-submit`
- `download` (if any site ships a downloadable asset)

Set these up in the Fathom dashboard, not in code. The whole point of Fathom goals is they're decoupled from the embed.

## Open design questions for the implementing agent

1. **Outbound vs internal:** the `outbound-click` delegated listener fires on every external link, which on `lossless.group` might be hundreds of citation links per article. Is that signal-to-noise OK, or should we limit to specific link classes? Decide before instrumenting `lossless.group`.
2. **`read-complete`:** what threshold — 80% scroll, or footer-in-view? Footer-in-view is more honest (people scroll past long footers) but less generous. Pick one and document it next to the implementation.
3. **PII:** none of the proposed events carry PII. **Verify form-submit handlers don't accidentally pass user input as event properties.** Umami stores everything as a string and Fathom shows event names verbatim in the dashboard — both are bad places for email addresses.
4. **Event-name namespacing:** do we prefix by site (`lossless.cta-primary`) or rely on the dashboard filter? Recommend no prefix — each Fathom/Umami site is already isolated.
5. **Single-page apps:** none of the 8 sites are SPAs today. If any move to client-side routing, Pass 2 needs revisiting (Fathom `trackPageview()`, Umami `umami.track()` on route change).

## Acceptance criteria for Pass 2

- Every site listed in [[Setup-Analytics-Across-Sites]] has at minimum a `cta-primary` event firing where applicable.
- The shared `analytics.ts` helper exists in each site that has a non-trivial CTA surface.
- Goals are configured in the Fathom dashboard for the primary conversions per site.
- A short note added to this prompt (or a new `context-v/specs/Analytics-Convention.md`) documenting the final event taxonomy and any deviations made during implementation.
- No PII in any event name or property.
