---
date_created: 2026-08-17
date_modified: 2026-08-17
site_uuid: 3c164f80-5564-4c6a-b011-c373f8e7f90b
hex_code: xc50lc
publish: true
title: Heading Outline Cannot Distinguish Container Headings from Document Headings
lede: '`tree.data.headings` collects a `###` inside a `> [!info]` callout as a document
  section — right for anchors, wrong for a table of contents.'
slug: heading-outline-cannot-distinguish-container-headings
at_semantic_version: 0.0.1.0
status: Resolved
category: Issue Resolution
authors:
- Michael Staton
augmented_with: Claude Code on Opus 5
tags:
- Extended-Markdown
- Render-Pipeline
- Remark
- Heading-Anchors
- Table-Of-Contents
- Consumer-Contract
- Blocker
image_prompt: A nested set of glass display cases; inside the innermost one sits a
  numbered brass tag identical to the ones mounted on the outer cases, indistinguishable
  at a glance.
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: issues/Heading-Outline-Cannot-Distinguish-Container-Headings.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/issues/Heading-Outline-Cannot-Distinguish-Container-Headings.md"
---

# Heading Outline Cannot Distinguish Container Headings from Document Headings

**Status:** Resolved in 0.5.0 — see [Resolution](#resolution)
**Affects:** `src/plugins/remark-heading-ids.ts`, `LfmHeading` in `src/types/index.ts`
**Blocks:** `astro-knots/context-v/specs/Reading-Position-Table-of-Contents-for-LFM-Articles.md`

## Symptom

A heading nested inside a container — a callout body, a `:::details` block, a carousel caption — appears in `tree.data.headings` indistinguishable from a document-level section heading.

```markdown
## The field, as of August 2026        ← a real section

> [!warning] The category churns
> ### What to do about it              ← not a section. Still lands in the outline.

## How to actually decide              ← a real section
```

A table of contents built from that outline renders three top-level-ish entries where the document has two, and offers the reader a waypoint that isn't one. The more callouts a document uses, the worse it reads — and our long-form recipes use a lot of callouts.

## This is correct behavior for anchors, and that's the trap

The collection is **deliberate and right**. From the walker itself:

```ts
/** Walk every `heading` node in document order. Hand-rolled; see module note. */
function eachHeading(node: any, fn: (h: Heading) => void): void {
  if (!node || !Array.isArray(node.children)) return;
  for (const child of node.children) {
    if (child.type === 'heading') fn(child as Heading);
    // Recurse regardless — headings nest inside blockquotes, list items and
    // container directives (a `> [!info]` body can hold an `###`).
    eachHeading(child, fn);
  }
}
```

A heading inside a callout **should** get a stable anchor. A share link pointing into a callout should work. [[Maintain-Heading-Anchors-and-Share-Links]] is explicit that a fragment URL is a public contract, and that contract shouldn't stop at a container boundary.

So the plugin is not over-collecting by mistake. **It knows the heading is nested — the walker comment says so — and then discards that fact** when it builds the entry:

```ts
const entry: LfmHeading = {
  id,
  text,
  depth: node.depth as LfmHeading['depth'],
};
if (duplicateOf) entry.duplicateOf = duplicateOf;
if (synthetic) entry.synthetic = true;
headings.push(entry);
```

Nothing records ancestry. By the time a consumer sees the outline, the information is gone.

## Why it wasn't caught

The anchors work shipped the outline as a by-product — *"this is the piece that pays for itself twice"* — and nothing consumed it. The gap is only visible from the ToC end, and no ToC has been built against it yet. The anchors doc did flag it as an open question:

> *Should the outline include headings inside callouts and directives? A `> [!info]` body can contain an `###`. Probably yes for anchors, probably no for the ToC. Needs a `data.inContainer` flag or the ToC filters by depth of nesting.*

This issue is that question, escalated: it is now blocking a written spec rather than sitting as a nice-to-know.

## Proposed fix

**Record ancestry on the outline entry. Change nothing about which headings get anchors.**

```ts
export interface LfmHeading {
  id: string;
  text: string;
  depth: 1 | 2 | 3 | 4 | 5 | 6;
  duplicateOf?: string;
  synthetic?: boolean;
  /**
   * Set when the heading sits inside a container rather than at document
   * level — the container directive's `name` (`callout`, `details`,
   * `image-carousel`, …), or `blockquote` / `listItem` for plain nesting.
   * Anchors are unaffected; ToC renderers will usually filter these out.
   */
  inContainer?: string;
}
```

**Carry the name, not a boolean.** It costs the same and is strictly more useful: a consumer may reasonably want `details` headings in the ToC (they're genuinely navigable sections) while excluding `callout` ones (they're asides). A boolean forecloses that for free.

Implementation is confined to two places:

1. **`eachHeading`** gains an ancestry parameter, passing the nearest enclosing container's name down as it recurses. Innermost wins.
2. **Entry construction** stamps `if (container) entry.inContainer = container;` alongside the existing `duplicateOf` / `synthetic` lines.

Both are additive. `data.id`, `data.hProperties`, and `data.headingText` are untouched, so nothing downstream of anchors changes.

## Companion gap: ship `nestHeadings()`

Surfaced by the same spec and worth fixing in the same release, because it lands on the same consumers.

**The outline is flat.** `depth` carries the hierarchy; there is no `children`. Every consumer that renders a ToC therefore writes the identical flat-to-tree fold as its first act. That is duplicated work with a duplicated bug surface — the fold has real edge cases (a document that opens at `h3`, a jump from `h2` straight to `h4`, a trailing `h6`), and each consumer will get them wrong independently.

```ts
/** The nested shape. Extends rather than replaces, so fields a consumer has
 *  already filtered or decorated survive the fold. */
export interface LfmHeadingNode extends LfmHeading {
  children: LfmHeadingNode[];
}

/** Fold the flat outline into a tree. Pure — no framework, no DOM. */
export function nestHeadings(headings: LfmHeading[]): LfmHeadingNode[];

/** Apply a depth band and drop `synthetic` entries (no usable label), leaving
 *  their anchors untouched. The other fold every consumer writes. */
export function filterHeadings(
  headings: LfmHeading[],
  minDepth?: number,
  maxDepth?: number
): LfmHeading[];
```

Verified against the first real consumer (`fullstack-vc`, 2026-08-17): these are
exactly the two helpers the implementation needed, and `LfmHeadingNode` was
missing from the original proposal entirely.

It sits naturally beside `slugifyHeading`, which is already exported next to the plugin for exactly this reason: consumers need the algorithm, not just the output.

**Still out of scope, permanently:** components, layout, breakpoints, scroll tracking. The seam holds — the package decides what a heading is called and where it sits; the render layer decides what the reader sees.

## Alternatives considered

**Filter in the consumer by walking the tree.** Every consumer re-derives nesting from the MDAST it already has. Works, and it is precisely the per-site divergence [[Maintain-Heading-Anchors-and-Share-Links]] existed to end. Rejected for the same reason local slugifiers were.

**Emit a second, pre-filtered `tree.data.toc`.** Removes the consumer's decision, which is the problem — it hardcodes our editorial judgment that callout headings don't belong in a ToC. `details` is the counter-example. Rejected as too opinionated for the package layer.

**Trim at source with a `maxDepth` option.** Doesn't address this at all — a callout `###` and a section `###` are the same depth. Orthogonal, and separately dubious, since it would make the outline disagree with the anchors actually present in the document.

## Blast radius

Low. Both changes are **additive**:

- `inContainer` is a new optional field. Existing consumers reading `id` / `text` / `depth` are unaffected. No anchor moves, so no published fragment URL breaks.
- `nestHeadings` is a new export. Nothing existing calls it.

Version-wise this is a **minor** bump, not a major. Worth landing together so a consumer upgrading for the ToC gets both in one step.

## Resolution

**Resolved in 0.5.0 (2026-08-17).** `inContainer` records the innermost enclosing
container's name; `nestHeadings`, `filterHeadings` and `LfmHeadingNode` ship
alongside `slugifyHeading`. All additive — no anchor moved.

One thing the proposal above did not anticipate. The `<hgroup>` emitted by
`lfmHeadingBlocks` is itself a `containerDirective`, so if it runs before
`remarkHeadingIds` every eyebrow heading gets stamped `inContainer:
"heading-block"` and a ToC filtering container headings discards the entire
document. Fixed by preset ordering — heading blocks run *after* heading ids —
with a `TRANSPARENT_CONTAINERS` guard in the anchor plugin for consumers who
wire the two by hand in the other order.

The astro-knots ToC spec is unblocked. See [[2026-08-17_02]].

## See also

- [[Maintain-Table-of-Contents-from-the-Heading-Outline]] — the consumer-facing contract this issue is a defect in
- [[Maintain-Heading-Anchors-and-Share-Links]] — the decision that produced the outline, and where this was first flagged as an open question
- `astro-knots/context-v/specs/Reading-Position-Table-of-Contents-for-LFM-Articles.md` — the blocked spec
