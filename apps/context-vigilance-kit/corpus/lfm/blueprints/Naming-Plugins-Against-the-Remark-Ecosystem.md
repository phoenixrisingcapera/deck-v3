---
site_uuid: 72b35418-b72f-4637-b4ff-e93dcfca499d
hex_code: kkxtmo
title: Naming Plugins Against the Remark Ecosystem
lede: Three questions pick the prefix — `remark-`, `remark-lfm-`, or `lfm-` — and
  the prefix tells a stranger on JSR how much of remark they know.
publish: true
date_created: 2026-08-17
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
authors:
- Michael Staton
augmented_with:
- Claude Code on Opus 5 (1M context)
at_semantic_version: 0.0.1.0
status: Signed-Off
date_first_published: 2026-08-17
summary: The naming rule for every plugin file and exported plugin const in @lossless-group/lfm.
  Load before adding a plugin to src/plugins/, before renaming one, or when an agent
  asks whether something is 'standard remark'. Encodes the three-tier test (remark-*
  / remark-lfm-* / lfm-*), the requirement to check the actual remarkjs plugin list
  rather than reason from memory, the alias-forever rule for renamed exports, and
  the two tests that were tried and discarded before this one.
tags:
- Naming-Conventions
- Plugins
- Remark
- Consumer-Contract
- Public-API
image_prompt: Three brass library stamps of increasing width lined up on a workbench,
  each inked a different shade, the widest one straddling the seam between two open
  books.
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: blueprints/Naming-Plugins-Against-the-Remark-Ecosystem.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/blueprints/Naming-Plugins-Against-the-Remark-Ecosystem.md"
---

# Naming Plugins Against the Remark Ecosystem

## Why Care?

LFM is published to JSR and GitHub Packages, which means its plugin names are read by people who have never seen this repo. Those names carry a claim, and the claim should be true.

`remark-heading-ids` tells a stranger: *this is the ecosystem's thing, and you already know how it works.* `lfm-image-carousel` tells them: *this is ours, you'll need to read something.* Getting that backwards costs a reader real time — they either go looking for upstream docs that don't exist, or they skip our docs for a plugin they don't actually understand.

Internally, the cost is different and worse: without a rule, every new plugin restarts the argument. This document is the rule, so it stops.

## The three tiers

Ask the questions in order. The first one that answers *yes* picks the prefix.

| # | Question | Prefix | Means |
|---|---|---|---|
| 1 | Is this handled by a plugin **published by remark, or listed as a formal plugin**? | `remark-{name}` | The ecosystem owns this namespace |
| 2 | Do we **substantially change how that plugin works** and add our own flavor? | `remark-lfm-{name}` | Their capability, our behavior |
| 3 | Is this **of our own making** — a unique syntax trigger, handled our way? | `lfm-{name}` | Ours end to end |

Tier 2 is the interesting one, and it is where most of this package lives. It says the *capability* is a known remark concern but the *behavior* is ours — so the name carries both halves, in that order, because the ecosystem word is the one a reader recognizes first.

**Externally-authored libraries always keep the names their authors gave them.** `remark-gfm`, `remark-directive` and `remark-parse` are dependencies; nothing in this document applies to them.

## Check the list. Do not reason from memory

Tier 1 turns entirely on a question of fact — *does a formal plugin exist?* — and it is the step most likely to be answered wrong from training data.

**The authoritative source is `remarkjs/remark/doc/plugins.md`.** It carries both the ~34 plugins the remarkjs org maintains and the much longer formally-listed community set. Read it before assigning a tier.

Two failure modes this prevents, both observed:

- **Assuming the ecosystem has nothing.** It has `remark-wiki-link`, `remark-cite`, `remark-heading-id`, `remark-github-admonitions-to-directives`, and several fence-manipulation plugins. Every one of those moved a plugin here from tier 3 to tier 2.
- **Assuming the ecosystem has something.** It has no plugin for Open Graph metadata fetching, image carousels, or `hgroup`-style heading blocks. Three of ours are tier 3 precisely because the list is empty there.

A near-miss counts as a hit for tier 1. `remark-heading-id` implements `{#custom-id}` while ours auto-slugs, dedupes and builds an outline — different behavior, same capability, so heading ids are tier 2 rather than tier 3.

## The current assignment

Recorded so a future agent can pattern-match rather than re-derive. Correct as of 0.5.0.

| Plugin | Formal prior art | Tier | Export |
|---|---|---|---|
| `remark-lfm-callouts` | `remark-github-admonitions-to-directives`, `remark-github-blockquote-alert` | 2 | `remarkLfmCallouts` |
| `remark-lfm-citations` | `remark-cite`, `remark-numbered-footnote-labels` | 2 | `remarkLfmCitations` |
| `remark-lfm-code-fences` | `remark-code-import`, `remark-flexible-code-titles` | 2 | `remarkLfmCodeFences` |
| `remark-lfm-heading-ids` | `remark-heading-id`, `remark-custom-header-id` | 2 | `remarkLfmHeadingIds` |
| `remark-lfm-wikilinks` | `remark-wiki-link` | 2 | `remarkLfmWikilinks` |
| `lfm-link-preview` | oEmbed plugins exist, but `:::link-preview` is our trigger | 3 | `lfmLinkPreview` |
| `lfm-og-fetcher` | none | 3 | `lfmOgFetcher` |
| `lfm-image-carousel` | none | 3 | `lfmImageCarousel` |
| `lfm-heading-blocks` | none | 3 | `lfmHeadingBlocks` |

Nothing sits at tier 1 today. That is expected rather than suspicious: if a formal plugin already did the job to our satisfaction we would depend on it, not write one.

**`remarkLfm` — the preset — is a deliberate exception.** It names itself after the flavor exactly as `remarkGfm` does, it is the most-imported symbol in the package, and it is not a plugin in the sense this document governs.

## Renaming is free. Renaming exports is not

Check before assuming either way. In this package as of 0.5.0:

- **Filenames are not public API.** `package.json` exposes only `.`, `./types`, `./formats` and `./formats/*`. No plugin file is reachable by a deep import, so moving one costs nothing beyond updating `tsup.config.ts` — which names entries explicitly and *will* fail the build if you forget it.
- **Exported const names are public API.** Roughly twenty files across four sites import them.

So: **every renamed export keeps its old name as an alias, forever, until a major.**

```ts
export const remarkLfmCallouts: Plugin<[], Root> = function () { … };

/**
 * @deprecated Renamed to `remarkLfmCallouts` in 0.5.0. Permanent alias.
 */
export const remarkCallouts = remarkLfmCallouts;
```

Alias to the *shipped* name only. An intermediate name from a rename that never published is not owed an alias — carrying one advertises a version that never existed. Assert the identity (`remarkCallouts === remarkLfmCallouts`) in the verification pass so a future refactor can't silently break it.

This is the same posture the package already takes for `img-carousel` / `image-carousel`, `$$` / `^^`, and `contextSetterTxt` / `eyebrowTxt`: **both names accepted, one canonical, and never rewrite an existing file just to change which one it uses.**

## Two tests we tried first, and why they failed

Kept so nobody re-proposes them.

**"Does it contribute to remark's standard library?"** Sounds decisive. Isn't. Checking the remarkjs org's actual 34-plugin list showed it contains nothing for callouts, citations, wikilinks, code-fence routing, OG fetching, link previews *or* heading ids — so the test caught every plugin in the package and distinguished between none of them. A test that returns the same answer for all inputs is not a test.

**"Did we write it?"** A genuine improvement — provenance is a fact, not a judgment — and it correctly protects external dependencies. But applied to our own `src/plugins/`, everything is ours, so it collapsed to the same all-or-nothing result and pushed `remark-lfm-heading-ids` and `remark-lfm-code-fences` to names that overclaimed our originality.

The three-tier test survives because **it asks about the capability and the behavior separately**, and tier 2 exists to hold the answer when those two diverge. Most of a flavored-markdown package lives in exactly that gap.

## Applying it to a new plugin

1. Name the capability in ecosystem terms — *wikilinks*, *callouts*, *heading ids* — not in ours.
2. Search `remarkjs/remark/doc/plugins.md` for it. Actually search it.
3. Nothing there → tier 3, `lfm-{name}`.
4. Something there, and we behave differently → tier 2, `remark-lfm-{name}`.
5. Something there and we'd behave the same → don't write the plugin. Depend on theirs.
6. Register the entry in `tsup.config.ts` if the file needs its own chunk, and state the tier in the module doc header so the next reader doesn't re-derive it.

## See also

- `changelog/2026-08-17_02.md` — the release that established this rule and renamed nine plugins under it
- `changelog/2026-08-17_01.md` — the first, weaker statement of the rule, with the correction note
- [[Maintain-Eyebrow-Heading-Subheading-Blocks]] — the alias-both-accept-one-canonical posture applied to syntax rather than symbols
- [[Workspace-vs-JSR-for-LFM-Consumers]] — why the published-package reading matters more here than in a private repo
