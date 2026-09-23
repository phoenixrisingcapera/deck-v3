---
date_created: 2026-08-17
date_modified: 2026-08-17
site_uuid: 3e3afb82-d640-4c13-8c80-06447b8f2ab6
hex_code: md6yd4
publish: true
title: Maintain Table of Contents from the Heading Outline
lede: '`remarkHeadingIds` already attaches a ToC-ready outline. Nobody renders it:
  the outline is flat and can''t flag headings buried in a callout.'
slug: maintain-table-of-contents-from-the-heading-outline
at_semantic_version: 0.0.0.1
authors:
- Michael Staton
augmented_with: Claude Code on Opus 5
tags:
- Extended-Markdown
- Render-Pipeline
- Remark
- Table-Of-Contents
- Heading-Anchors
- Consumer-Contract
image_prompt: A brass card catalogue whose drawers float free of the cabinet and arrange
  themselves into a nested tree in mid-air; one drawer is shaded, half-hidden inside
  a glass case.
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: Maintain-Table-of-Contents-from-the-Heading-Outline.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/Maintain-Table-of-Contents-from-the-Heading-Outline.md"
---

# Maintain Table of Contents from the Heading Outline

## The outline already exists

[[Maintain-Heading-Anchors-and-Share-Links]] moved anchor identity into the package, and it shipped a second thing almost as a side effect. `remarkHeadingIds` attaches to the tree:

```
tree.data.headings    ordered outline, ready to render a table of contents
```

That comment is in the plugin's own source. The promise is real and the data is good. **What is missing is not a renderer — renderers belong to consumers. What is missing is the last mile of the contract**, and this document is about what LFM still owes a consumer that wants to build one.

## What a consumer gets today

```ts
interface LfmHeading {
  id: string;           // final, deduped anchor id; matches the heading node's data.id
  text: string;         // plain text, markup stripped
  depth: 1 | 2 | 3 | 4 | 5 | 6;
  duplicateOf?: string; // this slug collided with an earlier heading. diagnostics
  synthetic?: boolean;  // text slugified to nothing; a positional id was used
}
```

Enabled by default — `headingIds !== false` in the preset — so any consumer already calling `remarkLfm` has this whether they know it or not. It costs nothing when unused.

**Three properties worth stating plainly**, because each pushes work onto the consumer:

1. **It is flat.** `depth` carries the hierarchy; there is no `children`. Every consumer that wants a nested list writes the same fold. That is arguably fine — nesting rules differ by surface — but it means the first thing every ToC does is identical, and we should decide whether to ship it.
2. **It is document order.** Which is what a ToC wants, so this one is correct as-is.
3. **`synthetic` and `duplicateOf` are diagnostics, not display data.** A `synthetic` heading has no useful label and should probably be omitted from a ToC while keeping its anchor. A `duplicateOf` heading should render its text normally — the id already disambiguates it.

## The gap: headings inside containers

This is the open question carried over from the anchors decision, and it is **the reason a ToC cannot be built cleanly today**:

> *A `> [!info]` body can contain an `###`. Probably yes for anchors, probably no for the ToC.*

An `h3` inside a callout, a `:::details` block, or an `::image-carousel` caption is a legitimate heading — it deserves an anchor, and a share link to it should work. It is almost never something a reader wants listed as a top-level waypoint in the document's table of contents.

Today `data.headings` cannot tell the two apart. A naive ToC over-collects and shows structure that isn't structure.

**Proposed: stamp `inContainer` on the outline entry.**

```ts
interface LfmHeading {
  // …
  /** Set when the heading sits inside a container directive (callout,
   *  details, carousel, …) rather than at document level. Anchors still
   *  work; ToC renderers will usually filter these out. */
  inContainer?: string;   // the container directive's name
}
```

Carrying the container's *name* rather than a boolean costs nothing and is strictly more useful — a consumer may reasonably want `details` headings in the ToC while excluding `callout` ones.

Tracked as [[Heading-Outline-Cannot-Distinguish-Container-Headings]], which carries the reproduction, the exact code path, and the alternatives that were rejected.

This is a **package-side change**, which means it lands on LFM's release cycle, not a site's. Any consumer planning a ToC should either wait for it or filter by their own tree walk in the meantime — and the second option is exactly the per-site divergence the anchors decision existed to stop.

## What LFM should and should not ship

Same seam as [[Maintain-Heading-Anchors-and-Share-Links]]: **the package decides what a heading is called and where it sits; the render layer decides what the reader sees.**

**In scope for the package:**

- The outline itself (shipped)
- `inContainer` classification (proposed above)
- Optionally, a **pure `nestHeadings(headings)` helper** exported alongside the types — no framework, no DOM, just flat-to-tree. Every consumer writes this; shipping it removes an identical fold from each one, the way `slugifyHeading` is already exported next to the plugin.

**Out of scope, permanently:**

- Any component, in any framework
- Layout, breakpoints, collapse behavior, scroll-position tracking. All of that is viewport and product-specific — see the astro-knots spec below for how involved it gets.
- Deciding which depths appear. `h2`+`h3` is the common answer and it is still the consumer's call.

## What building one actually needed (2026-08-17)

The first real consumer shipped in `fullstack-vc` on 2026-08-17. Three things the
proposal above got wrong or left out, learned by writing the code rather than
reasoning about it.

### 1. `LfmHeadingNode` is referenced but never defined

The `nestHeadings` signature in the issue returns `LfmHeadingNode[]` — a type
nothing specifies. It needs to ship alongside, and the obvious shape is the flat
entry plus children:

```ts
export interface LfmHeadingNode extends LfmHeading {
  children: LfmHeadingNode[];
}
```

Worth stating explicitly that it **extends** rather than replaces: a consumer
that has already filtered or decorated entries (see `eyebrow` below) keeps those
fields through the fold.

### 2. `filterHeadings` is the *other* helper every consumer writes

The open question above rejected a plugin-level `maxDepth` — correctly, because
trimming at source would make the outline disagree with the anchors actually in
the document. But that reasoning doesn't apply to a **pure helper**, and the
implementation needed one immediately:

```ts
export function filterHeadings(
  headings: LfmHeading[],
  minDepth = 2,
  maxDepth = 3
): LfmHeading[];
```

It does two things every ToC does: apply a depth band (`h2`–`h3` is the useful
default) and **drop `synthetic` entries**, whose text slugified to nothing and
which therefore have no label worth showing — while leaving their anchors alone.

Same argument as `nestHeadings`: pure, framework-free, and otherwise written
identically by every consumer with the same two judgement calls made privately
each time.

### 3. The three proposed additions are one release, not three

`inContainer`, `eyebrow` (from [[Maintain-Eyebrow-Heading-Subheading-Blocks]]),
and the two helpers are all additive optional fields or new exports. Landing them
separately means three upgrade cycles for consumers who need the ToC. Landing
them together is one minor bump:

```ts
export interface LfmHeading {
  id: string;
  text: string;
  depth: 1 | 2 | 3 | 4 | 5 | 6;
  duplicateOf?: string;
  synthetic?: boolean;
  inContainer?: string;  // container directive name, when nested
  eyebrow?: string;      // when the heading is part of an eyebrow block
}

export interface LfmHeadingNode extends LfmHeading { children: LfmHeadingNode[] }
export function nestHeadings(headings: LfmHeading[]): LfmHeadingNode[];
export function filterHeadings(h: LfmHeading[], min?: number, max?: number): LfmHeading[];
```

Until that lands, the site-local copy lives at
`fullstack-vc/src/components/markdown/toc-types.ts` and is written to be deleted
rather than migrated — same names, same signatures, no extra behaviour.

### Confirmed as correctly out of scope

Building the component did not change these. The renderer owns them and the
package should stay out:

- The three viewport states, breakpoints, and collapse behaviour
- Scroll-position tracking, and the tie-break rule when several headings are in view
- **Measuring the site's pinned header** to offset the ToC — this turned out to be
  the fiddliest part of the implementation, and it is entirely a render-layer and
  per-site concern

## Guidance for consumers

For anyone wiring a ToC against this outline:

1. **Read `tree.data.headings`. Do not scrape the DOM.** The pre-LFM ToC on `lossless-monorepo/site` rebuilds its outline at runtime with `querySelectorAll('h1[id], h2[id], …')` because nothing upstream handed it one. That is no longer true, and DOM scraping cannot see `synthetic` or `duplicateOf` at all.
2. **Do not recompute slugs.** Use `heading.data.id`. A consumer that slugifies independently re-creates the exact divergence this plugin was written to end.
3. **Check your LFM version.** `remarkHeadingIds` landed in **0.4.0**. On 0.3.x, `data.id` is `undefined` and headings lose their ids entirely — upgrade the package *before* adopting a renderer that depends on it.
4. **Expect anchor churn on upgrade.** The default slugifier is bug-for-bug compatible with `lossless-monorepo/site`'s algorithm, which differs from what astro-knots sites computed locally. The anchors doc counted 646 moved anchors across astro-knots, judged acceptable there because those fragments are internal ToC jumps that regenerate at build. Re-verify for any site with published share links.

## Open questions

- ~~**Ship `nestHeadings`, or leave the fold to consumers?**~~ **Decided: ship it.** Pure, testable, framework-free, and otherwise written identically by every consumer — with real edge cases (a document opening at `h3`, an `h2` → `h4` jump, a trailing `h6`) each would get wrong independently. Folded into [[Heading-Outline-Cannot-Distinguish-Container-Headings]] so both land in one minor bump.
- **Does `inContainer` need to be recursive-aware?** A heading three containers deep is still "in a container"; carrying only the innermost name is probably enough, but a depth count may be cheap enough to include.
- **Should the plugin offer a `maxDepth` option** that trims the outline at source? Probably not — it costs consumers nothing to filter, and trimming at source would make the outline disagree with the anchors actually present in the document.

## See also

- [[Maintain-Heading-Anchors-and-Share-Links]] — the decision that produced `remarkHeadingIds`, the migration count, and the `HeadingAnchor.astro` sibling affordance
- [[Maintain-Lossless-Markdown-and-Extended-Markdown-Render-Pipeline]] — where this sits in the pipeline
- `astro-knots/context-v/specs/Reading-Position-Table-of-Contents-for-LFM-Articles.md` — the render-layer half: three viewport states, scrollspy, mobile behavior. Consumes exactly the contract described here, and is blocked on the `inContainer` question above.
