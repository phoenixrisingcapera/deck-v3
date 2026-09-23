---
site_uuid: 7e1240c5-5f87-4039-9ce5-673090978bf8
hex_code: 3f985a
date_created: 2025-09-20
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
date_authored_final_draft: null
publish: false
title: Maintain Embeddable Images with Style Props
lede: An unrecognised prop on an image directive does nothing at all — no error, no
  warning, no render difference. The discipline that ends that.
summary: 'Defines the prop-management discipline for LFM''s image directives: an explicit
  registry of known props per directive, a passthrough-plus-warning policy for unknown
  ones, and coercion rules for the fact that every directive attribute arrives as
  a string. Written because the current plugins read a fixed set of attribute names
  off `node.attributes` and silently drop everything else, so a typo and an unsupported
  feature are indistinguishable to an author.'
slug: maintain-embeddable-images-with-style-props
at_semantic_version: 0.0.1.0
usageCount: '0'
status: Draft
authors:
- Michael Staton
augmented_with:
- Trae AI
- Claude Code on Claude Opus 5 (1M context)
tags:
- Images
- Directives
- LFM
- Props
- Render-Pipeline
image_prompt: On the left, a computer monitor with a magazine style article, with
  images of different sizes with wrapped text and captions.  On the right, two robots
  are laying bricks masonry style and they are creating a masonry layout with bright
  and captivating images.
banner_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/2025-sept/Maintain-Embeddable-Images-with-Style-Props_banner_image_1758374365983_ahBWh35VX.webp
portrait_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/2025-sept/Maintain-Embeddable-Images-with-Style-Props_portrait_image_1758374375095_5bfFKKJl7.webp
square_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/2025-sept/Maintain-Embeddable-Images-with-Style-Props_square_image_1758374377020_0Ucrjgpq2.webp
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: Maintain-Embeddable-Images-with-Style-Props.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/Maintain-Embeddable-Images-with-Style-Props.md"
---

# Maintain Embeddable Images with Style Props

> **Status: discipline, not a finished component spec.** This defines how props
> are *managed*. The individual props a magazine-style layout needs — float,
> wrap, span, masonry placement — are still to be designed.

## The problem this exists to prevent

Every LFM directive plugin reads a **fixed list of attribute names** off
`node.attributes` and ignores everything else. From `lfm-image-carousel.ts`:

```ts
const attrs = child.attributes || {};
const data: CarouselData = {
  variant:   resolveVariant(attrs.variant),
  sort:      resolveSort(attrs.sort, variant),
  title:     attrs.title || undefined,
  numbered:  attrs.numbered !== 'false',
  maxHeight: attrs['max-height'] || undefined,
  slides,
};
```

Anything not on that list is dropped on the floor. **There is no error, no
warning, and no visible difference in the output.** Which means these three cases
are indistinguishable to an author:

1. a prop that was misspelled (`captoin="…"`)
2. a prop that is real but unsupported by *this* directive (`caption` on a
   carousel container rather than on a slide)
3. a prop that hasn't been built yet (`float="left"`)

All three render as "nothing happened." That is the actual cost, and it gets
worse as the prop surface grows — which is exactly what magazine-style image
layout will do to it.

## The discipline

### 1. A known-prop registry per directive, in one place

Each image directive declares its props as data, not as scattered reads inside a
builder function: name, type, default, and a one-line meaning. The builder reads
from the registry. **The registry is the documentation** — a prop table that lives
next to the code cannot drift from it.

Currently known:

| Directive | Prop | Notes |
|---|---|---|
| `::image{}` (leaf) | `src` | required |
| | `alt` | required in practice — defaults to `''`, which is an accessibility hole, not a feature |
| | `label` | short caption for carousel chrome |
| | `caption` | full caption |
| `:::image-carousel` (container) | `variant` | resolved through `resolveVariant` |
| | `sort` | resolved through `resolveSort`, default depends on `variant` |
| | `title` | |
| | `numbered` | **string-compared** — `attrs.numbered !== 'false'` |
| | `max-height` | kebab-case, unlike its siblings |

Alias `:::img-carousel` collapses to `image-carousel` at parse time so renderers
match one name. Plain `![alt](src)` is also accepted, mapping markdown `title`
→ `caption`.

### 2. Unknown props pass through — and say so

**Do not silently drop.** Two rules, and they are a pair:

- **Carry unknown attributes through** onto the node's data so a downstream
  renderer or a consuming site can act on them. A prop LFM doesn't understand may
  be perfectly meaningful to the site rendering it.
- **Warn once per unknown prop, in dev only**, naming the directive, the prop, and
  the source position: `[lfm-image] unknown prop "captoin" on ::image (file.md:42).
  Passed through unrendered.`

That combination is what separates a typo from an extension: both still pass
through, but only one produces a message the author will recognise as a mistake.
Never fail the build over a prop — same posture as
[[Rule-to-Assure-Collection-Schema-is-Flexible]] in astro-knots, for the same
reason: the content is hand-authored and must not be able to break a site.

### 3. Attributes are always strings — coerce explicitly

`remark-directive` hands every attribute over as a string. There is no boolean, no
number. `numbered !== 'false'` in the carousel is the existing acknowledgement of
this, and it is worth noting what that idiom actually does: **it defaults to
`true` and requires the literal string `"false"` to disable.** `numbered="0"`,
`numbered="no"`, and `numbered=""` all read as `true`.

So the registry declares a type per prop and coercion happens in one shared place:

- **boolean** — present-and-not-`"false"` is `true`; document the default
- **number** — parse, and fall back to the default on `NaN` rather than propagating it
- **enum** — resolve through a `resolveX()` helper that returns the default on an
  unrecognised value, as `resolveVariant` and `resolveSort` already do
- **dimension** — accept a bare number as `px`, pass any CSS unit through verbatim

### 4. Naming — pick one case and hold it

`max-height` is kebab-case while `variant`, `sort`, `title`, and `numbered` are
single words, so the inconsistency is currently invisible. It will not stay
invisible once there are two-word props like `object-fit` or `aspect-ratio`.

**Kebab-case for multi-word props**, matching CSS and HTML attribute convention.
Accept camelCase as a silent alias when adding any new multi-word prop, so authors
coming from JSX aren't punished.

## Remaining work

- Design the actual style props for magazine-style layout — float/wrap, column
  span, masonry placement, aspect ratio. This document deliberately does not.
- Decide whether style props emit inline styles, utility classes, or CSS custom
  properties. Custom properties compose best with the two-tier token system and
  keep theming in the consuming site's hands.
- Build the registry + warning helper once, shared across image directives rather
  than per-plugin.
- `alt` defaulting to `''` deserves its own decision: warn on a missing `alt`,
  since a silent empty alt is a real accessibility failure rather than a styling one.

## Related

- [[Maintain-Embeddable-Slides]] — the sibling embed blueprint, same directive family
- [[Maintain-Directives-in-Extended-Markdown-Render-Pipeline]] — how directives are
  parsed and dispatched
- [[Maintain-Conditional-Components-on-Render]]
- `src/plugins/lfm-image-carousel.ts` — the current prop handling described above
