---
title: 'Explore: GitHub API for Live KPIs — Credibility Without Stars'
lede: 60+ commits/day per person, 4,400+ content files, no 50K stars. What GitHub
  can give us for a credibility-by-shipping story.
date_authored_initial_draft: '2026-05-06'
date_authored_current_draft: '2026-05-06'
date_created: '2026-05-06'
date_modified: '2026-05-06'
at_semantic_version: 0.0.0.3
semantic_version: 0.0.0.3
status: Draft
augmented_with: Claude Code (Opus 4.7)
category: Explorations
tags:
- Landing-Pages
- GitHub-API
- Live-KPIs
- Development-Momentum
- Context-Vigilance
- Pseudomonorepo
authors:
- Michael Staton
- AI Labs Team
site_uuid: c86b3772-a8e0-459f-a69a-93490f309169
hex_code: 43l0mc
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: explorations/Explore-GitHub-API-for-Live-KPIs.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/explorations/Explore-GitHub-API-for-Live-KPIs.md"
---

## The reframe — credibility, not popularity

Stars are a popularity signal. We can't compete on that and probably shouldn't. The stars game has its own attractor (single high-leverage repos, viral moments, follow-the-trend topics) and we're playing a different one — many repos, sustained cadence, content + code + methodology together, AI as a documented co-developer. Our story is **shipping**, not **viral**.

Six story arcs we can actually tell from data we already have:

1. **We ship a lot** (velocity)
2. **We ship every day** (consistency / cadence)
3. **We ship across many surfaces at once** (breadth — pseudomonorepo signature)
4. **We work alongside AI, in public, with audit trail** (Co-Authored-By footprint — distinctive)
5. **We are growing a corpus, not a feature set** (content + vocabulary scale)
6. **We document our methodology** (context-v/ files as a meta-story)

A live KPI dashboard's job is to land at least three of those instantly. Stars-as-numerator pages give one number; ours should give a small set that combine into "these people are the real deal."

## What's actually shippable from GitHub data

Below: each story arc, what metric expresses it, and where the data lives. Two data sources matter — **GitHub** (commits, repos, PRs) and the **local content vault** (`content-md/lossless/`, the four-thousand-file knowledge base). Both can be aggregated nightly.

### Arc 1 — Velocity: "We ship a lot"

| Metric | Where it comes from |
|---|---|
| Total commits last 7 / 30 / 90 / 365 days, summed across all org repos | `search/commits` REST or GraphQL `repository.defaultBranchRef.target.history` |
| LOC delta (added + removed) per period | `/repos/{owner}/{repo}/stats/code_frequency` weekly buckets, summed |
| PRs merged per period | GraphQL `pullRequests(states: MERGED, ...)` |
| Releases cut per quarter | `/repos/{owner}/{repo}/releases` |

### Arc 2 — Consistency: "We ship every day"

| Metric | Where it comes from |
|---|---|
| Calendar heatmap (365-day grid, days-with-activity) | GraphQL `user.contributionsCollection.contributionCalendar` |
| Workday-active rate (% of weekdays in period with ≥1 commit) | derived from heatmap |
| Longest active streak | derived from heatmap |
| 7-day / 30-day rolling active ratio | derived |

The heatmap is the single highest-information-density artifact we can show. One image communicates "this is a working studio, not a side project."

### Arc 3 — Breadth: "We ship across many surfaces"

This is the **pseudomonorepo signature** — and it's what makes us distinctive vs. teams optimizing one repo for stars.

| Metric | Where it comes from |
|---|---|
| Distinct repos active in last 7 / 30 days | `search/commits` aggregated by repo |
| Submodule advancement count (parent bumps to new child SHA) | `git log --diff-filter=M -- <submodule-path>` per parent repo |
| Languages touched | `/repos/{owner}/{repo}/languages` per repo, unioned |
| Cross-repo "session" count (commits within N hours across ≥2 repos) | derived from commit timestamps |

### Arc 4 — AI-augmented work in public

This is **our story**. spec-kit, OpenSpec, agentskills.io don't track this. Lossless commits routinely include `Co-Authored-By: Claude Opus / Sonnet / Haiku ...` and `Co-Authored-By: Pi on Claude ...`. That's auditable AI-cooperation data, sitting in commit messages, free.

| Metric | Where it comes from |
|---|---|
| % of commits with `Co-Authored-By: Claude\|Pi\|...` | parse commit messages from `search/commits` |
| Distinct AI co-authors used (Claude Opus, Sonnet, Haiku, Pi, etc.) | parse commit message trailers |
| AI-augmented commit % over time | bucket by week |
| Top AI co-author by commit count | trailer parse |

### Arc 5 — Corpus growth: "We're building a knowledge base"

The content vault is the moat. We map ~1,600 tools, define ~477 vocabulary entries, and write ~280 lost-in-public posts. Most "developer momentum" pages don't have anything like this to point to.

| Metric | Where it comes from |
|---|---|
| Total .md files across content repos | `find` over `content-md/lossless/`, or content repos cloned in CI |
| Tools mapped (`Tooling/`) | count of files in subtree (currently 1,582) |
| Vocabulary entries (`Vocabulary/`) | currently 477 |
| New content files per month | git log of content repo |
| Cross-link density (wikilinks per file) | grep `[[...]]` over content corpus |
| Top tags | parse YAML frontmatter `tags:` arrays |

### Arc 6 — Methodology in public: "Context Vigilance is real"

This is the **meta-story** — the thing that makes packaging Context Vigilance as an open spec credible. Most frameworks ship as a doc. We ship a 397-file lived corpus.

| Metric | Where it comes from |
|---|---|
| Total `context-v/*.md` files | `find` over the lossless-monorepo tree (currently 397) |
| `context-v/` directories (projects with the practice) | currently 30 |
| Doc-type breakdown (specs / prompts / blueprints / reminders / explorations / issues) | counts per subfolder |
| Doc:code ratio (lines-of-doc vs lines-of-code) | git stats per repo |
| New context-v files per month | git log filter `-- '**/context-v/**'` |

## Concrete data we already have (snapshot 2026-05-06)

Numbers I just measured locally to ground this draft. These would be the **baseline** the dashboard launches with:

- **Content vault:** ~4,400 .md files
- **Tools mapped:** 1,582
- **Vocabulary entries:** 477
- **`context-v/` files:** 397
- **`context-v/` directories:** 30 (across 5 pseudomonorepo levels)
- **Git repos under the monorepo:** 9 (parent + immediate children) plus 15 submodule pointers
- **30-day commits at parent repos alone:** 60 (astro-knots 45, content-farm 12, ai-labs 2, monorepo 1) — submodule commits are *additional* and where most volume lives

The "60+ commits/day per person" claim becomes verifiable once we walk submodules — that should be one of the first numbers the dashboard hardens.

## Implementation sketch

Phased, so we can ship something before perfecting it.

### Phase 0 — Local "count shit" script, inject into marketing surfaces

The lowest-effort starting point — and probably the highest-ROI per hour spent. **Most of our impressive numbers are local, not in GitHub** (4,400 files, 1,582 tools, 477 vocabulary entries, 397 context-v files, 30 context-v dirs). A simple script can collect all of them in seconds and drop the result somewhere our marketing already lives.

What the script does:

- Walks `~/content-md/lossless/` and counts `.md` files per top-level subtree (Tooling, Vocabulary, concepts, projects, lost-in-public, Sources, etc.).
- Walks the monorepo tree (5+ levels deep) and counts files in every `context-v/` directory, grouped by doc-type (`specs/`, `prompts/`, `blueprints/`, `reminders/`, `explorations/`, `issues/`).
- For each child repo / submodule, runs `git log --since='30 days ago' --pretty=oneline | wc -l` and sums for a cross-repo 30-day commit total.
- Optional flags: word count totals, distinct frontmatter tags, distinct AI co-authors parsed from commit message trailers.
- Writes one snapshot artifact: `data/marketing-stats.json` (and/or `marketing-stats.md` partial).

Where it gets injected:

- **Astro sites that already exist** (`lossless.group`, the splash pages) — import the JSON at build time and render numbers inline. The splash site's existing rollup pattern (per-plugin changelog/context-v aggregation) is exactly the ergonomic precedent.
- **Marked regions of README / landing-page Markdown** — pattern like `<!-- stats:tools -->1582<!-- /stats:tools -->` with a `pnpm stats:inject` step that pattern-replaces. Lets us drop live numbers into static prose without templating gymnastics.
- **OG / share snippets** — a small "by the numbers" block baked into open-graph image generation so social shares carry the credibility numbers automatically.
- **Plugin splash pages** — each plugin's splash already shows its own context-v rollup; a global `marketing-stats.json` lets each one show "and here's the broader Lossless studio it lives in."

Implementation choices:

- Start as `scripts/count-stats.sh` (Bash, ~50 lines). Promote to `scripts/count-stats.ts` (Node) when we want frontmatter parsing or AI-co-author trailer extraction.
- Run by hand during marketing pushes; later add to a pre-deploy hook or a nightly cron. No API auth, no rate limits, no CI complexity.
- Snapshot is deterministic and reproducible — same script, same numbers, no GitHub-availability dependency.

Why this beats waiting for the GitHub API approach:

- 80% of the credibility numbers are local; no API needed for those.
- One afternoon to a working v0 instead of two weeks for the API + Action + visualization stack.
- Marketing surfaces start consuming a stable JSON shape *now*, so when Phase 1 lands the same JSON can be produced from API data and consumers don't change.

Limitations to be honest about:

- No 365-day heatmap (that needs walking commit history across every submodule — doable but more work; lives in Phase 2).
- No streak / consistency metrics yet.
- No "live" updates — runs when run. Fine for most marketing surfaces; not fine if we want a public dashboard that visibly ticks.

### Phase 1 — Headline JSON, hand-rolled, public

- **Nightly GitHub Action** that runs at 03:00 UTC: hits the GitHub GraphQL API for org `lossless-group`, walks all repos (including submodules' upstream repos), computes the Arc 1–4 numbers, writes a single `metrics.json` to a public repo (e.g. `lossless-group/momentum-data`).
- **Astro page** at `lossless.group/momentum` (or `live.lossless.group`) reads `metrics.json` at build time and renders a small grid of headline cards: total commits last 30d, active repos, AI-augmented %, longest streak.
- Build the Astro page reads from the JSON via `fetch()` at SSR time so a daily GitHub Pages / Vercel rebuild keeps it fresh; or trigger an Astro rebuild on the data repo's push event.

### Phase 2 — Calendar heatmap + AI-co-authoring chart

- Calendar heatmap of all-org daily activity, last 365 days. SVG, no chart library required (or use `cal-heatmap`).
- Stacked bar over time: human-only commits vs. AI-augmented commits, by week.
- "Top AI co-authors" mini-leaderboard (e.g. Claude Opus 4.7 — 412 commits, Pi on Sonnet 4.6 — 203, etc.).

### Phase 3 — Pseudomonorepo lattice + content metrics

- Cross-repo lattice: a grid of all repos × last 90 days, each cell shaded by commit count. Visually expresses "we ship across surfaces simultaneously."
- Substrate health card: "9 of 9 child repos active in last 7 days."
- Content vault metrics: tools mapped, vocabulary entries, link density. Pulls from a clone of the content repo in the CI step.

### Phase 4 — Methodology metrics

- Context-v file count over time (line chart).
- Doc-type breakdown (donut: specs / prompts / blueprints / reminders / explorations / issues).
- Doc:code ratio per repo (small table).

## Hosting / visualization options

- **Astro (preferred)** — already the house framework. SSR pages reading `metrics.json` from the data repo. Pages live under `lossless.group/momentum` or `live.lossless.group`.
- **GitHub Pages from `momentum-data`** — even simpler if we want it on `momentum.lossless-group.dev`. Removes the Astro rebuild dependency.
- **Charts** — start with hand-rolled SVG (calendar heatmap is ~50 lines). Upgrade to ECharts only if we need interactivity.
- **No JS runtime** — the entire dashboard can be static. Nightly job → JSON → static rebuild → CDN. No live API calls from the visitor's browser.

## Tradeoffs and open questions

- **Public vs. private repos.** Most of our work lives in private repos today. The PAT / GitHub App used by the metrics job will see them, but we have to decide what gets aggregated into the public number. Cleanest: aggregate everything (private repos contribute to totals), but only *list* / *link* the public ones.
- **AI-co-author parsing brittleness.** If commit messages have inconsistent `Co-Authored-By:` formats (e.g. "Claude Opus 4.6 (1M context)" vs "Claude Opus 4.7"), we need normalization rules. Worth defining a regex spec early.
- **Vanity-metric risk.** Easy to drift toward inflated headline numbers ("4,400 files!"). The KPI page works as credibility only if it's *honest* — including the periods of low activity, not just the highs. A 365-day heatmap shows both, which is part of why it's the strongest single artifact.
- **Rate limits.** GraphQL = 5,000 points/hour. Walking ~50 repos × commit history will fit comfortably, but content-corpus walks should run in CI against a clone, not against the API.
- **Refresh cadence.** Nightly is fine for the public face. Per-hour adds nothing the visitor will notice.
- **Where does this URL live?** `lossless.group/momentum` (subpath, easy) vs. `live.lossless.group` (subdomain, distinctive). Vote: subdomain. The page deserves a memorable address.

## Comparable projects (so we know what we're not duplicating)

- **GitHub Skyline** — per-user 3D contribution heatmap. Decorative, not org-aggregated.
- **WakaTime** — time-spent dashboards, individual-developer-focused, requires editor plugin.
- **anuraghazra/github-readme-stats** — README-card images, single-repo or single-user. We need org/cross-repo aggregation.
- **gitfluence / git-of-theseus** — history visualization. Single-repo, post-hoc.
- **`actions/contributors`** action — list contributors. Doesn't tell a momentum story.

Closest gap to what we want: **none of these aggregate cross-repo for an org and surface AI-co-authoring.** Our shape is novel enough that the dashboard itself is part of the Context Vigilance pitch — "this is what AI-augmented studios look like when they show their work."

## Open questions to answer before building

1. Public-vs-private aggregation policy: include private repo totals in headline numbers, or restrict to public?
2. AI co-author normalization: do we lock the format in `git-conventions` skill so future commits are uniformly parseable?
3. URL: `lossless.group/momentum` or `live.lossless.group`?
4. Are we comfortable showing a 365-day heatmap that includes our quiet stretches? (Vote: yes — honesty is part of the differentiator.)
5. Phase-1 scope: which 4–6 headline cards land on day one?
6. Does this page link to the **Context Vigilance** spec and the (future) **Pseudomonorepos.dev** site? It probably should — they form a triad: pattern (pseudomonorepo) + practice (context vigilance) + evidence (live KPIs).
7. Do we publicly commit `momentum-data/metrics.json` daily, or keep it private and only emit derived charts? (Vote: public — "show your work" is the brand.)
8. **Phase-0 script destinations:** which marketing surfaces consume `marketing-stats.json` first? Best initial candidates: lossless.group's Context Vigilance gallery page, each plugin splash page, the monorepo READMEs, OG share images. Pick 1–2 to land before the rest.
9. **Phase-0 script home:** lives in `~/code/lossless-monorepo/scripts/count-stats.sh` (parent monorepo, walks everything below it) or in each pseudomonorepo separately? Vote: parent — one script, walks down, single source of truth.

## Adjacent ideas worth flagging

- **Per-doc citation tracker** — once cite-wide's canonical-source format lands (see [[Citation-Resolution-and-Canonical-Sources]]), we could surface "X external citations of our content," which is a different breed of credibility metric.
- **Tool-coverage map** — we map 1,600+ tools; the dashboard could show coverage % vs. some external taxonomy (e.g. CNCF landscape, PWAs, etc.).
- **Methodology adoption graph** — once Context Vigilance is packaged as an open spec with `npx context-vigilance init`, count installations / forks / Github Action runs as adoption signal.
