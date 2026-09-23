---
date_created: 2026-08-17
date_modified: 2026-08-17
site_uuid: c65f23ae-a438-4f0c-bcf4-935c191869aa
hex_code: 1wcaa4
publish: true
title: Maintain Eyebrow, Heading and Subheading Blocks
lede: Cards have had a three-part heading for years — eyebrow, heading, subheading
  — and long articles need it more than cards do. Three adjacent lines, one semantic
  unit, one `<hgroup>`, and only the middle one ever reaches the table of contents.
slug: maintain-eyebrow-heading-subheading-blocks
at_semantic_version: 0.0.1.0
status: Proposed
authors:
- Michael Staton
augmented_with: Claude Code on Opus 5
tags:
- Extended-Markdown
- Render-Pipeline
- Remark
- Headings
- Information-Design
- Skimmability
- Table-Of-Contents
image_prompt: Three stacked brass nameplates of decreasing size mounted on a single
  wooden backing board, the middle one largest and polished brightest.
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: Maintain-Eyebrow-Heading-Subheading-Blocks.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/Maintain-Eyebrow-Heading-Subheading-Blocks.md"
---

# Maintain Eyebrow, Heading and Subheading Blocks

## Why Care?

Every card component in the house already renders a three-part heading: a small label above, the headline, and a line of supporting text below. It's the standard editorial shape — an **eyebrow** (the older newsprint term is *kicker*), the head, and the deck.

Markdown gives you one of the three. `##` and nothing else.

**Long articles need this more than cards do.** A card is four lines total; nobody skims a card. A recipe with five job sections and a dozen sub-headings is skimmed by almost everyone who opens it, and `##` alone gives a skimmer a bare noun phrase with no indication of what kind of thing it is or what it will tell them. An eyebrow does that in two words.

## The syntax

Three adjacent lines, in fixed order, forming **one semantic unit**:

```markdown
$$ Portfolio Operations
## Every email from a portco, filed as PDFs
&& Two passes, inventory before export — so you can verify coverage
```

| Marker | Property | Rendered as | Required |
|---|---|---|---|
| `$$ ` | `eyebrowTxt` | `.eyebrow` | No |
| `## ` | `headingTxt` | `<h2>` (any level) | **Yes** |
| `&& ` | `subHeadingTxt` | `.subheading` | No |

### Why `eyebrowTxt` and not `contextSetterTxt`

The house convention is that a text prop carries the `Txt` suffix and names the content's *role*, while the rendered element keeps its own name — so that when the visual treatment changes (eyebrow becomes a chip, a badge, a number), the prop still describes what the text *is*. That convention is right, and it is preserved here. `Txt` suffix, unchanged.

What changes is which word names the role, and the reason is that **`eyebrow` is not a presentational term.** It's editorial vocabulary, like *lede*, *byline*, or *headline* — it names what a piece of copy does, not how it looks. `contextSetter` names the same role in a word only this codebase knows. Between two names for one role, the shared one wins.

That matters more here than anywhere else, because **LFM is a published package.** Prop names on a public API are read by people with no access to our conventions. A private coinage that costs nothing internally costs real comprehension on JSR.

**`contextSetterTxt` stays accepted as an alias.** This codebase already resolves exactly this shape twice — `img-carousel` / `image-carousel`, and `semantic_version` / `at_semantic_version`: both names accepted, one canonical, and never rewrite an existing file just to change which one it uses. Same posture. Write `eyebrowTxt` in new work; leave `contextSetterTxt` where it already is and migrate opportunistically.

### Position is the semantics

**The markers mean nothing on their own. They are bound by adjacency to a heading, and that binding is the entire rule:**

- `$$` on the line **immediately above** a heading → that text becomes `eyebrowTxt`, rendered as the eyebrow.
- `&&` on the line **immediately below** a heading → that text becomes `subHeadingTxt`, rendered as the subheading.
- Anywhere else, both are ordinary text and pass through untouched.

Everything else follows from that:

1. **Contiguous lines, no blank line between them.** A blank line breaks the binding and the marker reverts to literal text.
2. **Order is fixed** — eyebrow above, subheading below. There is no reordering because there is no marker-intrinsic meaning to reorder.
3. **The heading is mandatory.** There is no such thing as a floating eyebrow; without a heading to attach to there is nothing for it to set context *for*.
4. **Either optional line may be omitted.** Eyebrow + heading, heading + subheading, and all three are all valid.
5. **Works at any heading level**, though it earns its keep at `##` and `###`.

This is why the feature is safe to enable by default: a parser that finds `$$` asks one question — *is the next line a heading?* — and if the answer is no, it does nothing at all.

## Output: one `<hgroup>`, and only one heading inside it

```html
<hgroup>
  <p class="eyebrow">Portfolio Operations</p>
  <h2 id="every-email-from-a-portco-filed-as-pdfs">Every email from a portco, filed as PDFs</h2>
  <p class="subheading">Two passes, inventory before export — so you can verify coverage</p>
</hgroup>
```

`<hgroup>` is in the HTML Living Standard for exactly this: a heading grouped with secondary content, each piece of secondary content as a `<p>`.

**The eyebrow and subheading must be `<p>`, never headings.** This is not stylistic. It is the accessibility guidance for `hgroup` — secondary content stays paragraph-level so it never enters the document outline — and it is also what keeps this feature from colliding with the table of contents. A subheading rendered as `<h3>` would appear in `tree.data.headings` as a phantom section. As a `<p>` it cannot.

Note the caveat honestly: `hgroup` currently maps to a generic role and is largely ignored in the accessibility tree, and no browser implements the HTML outline algorithm. It is the semantically correct container and it buys less than it looks like it does. `aria-roledescription` on the group and on the subtitle paragraph is worth considering; that belongs to the render layer, not the package.

## Table of contents interaction

Only the `##` reaches the outline. That falls out of the `<p>` decision above and needs no special casing.

But there is an **opportunity** here, and it is the reason this feature and the ToC work should be considered together. The eyebrow is *precisely* the grouping label a table of contents wants:

```
PORTFOLIO OPERATIONS
  Every email from a portco, filed as PDFs
```

Proposed: when a heading is part of an eyebrow block, carry it on the outline entry.

```ts
export interface LfmHeading {
  // …
  /** Eyebrow text when this heading is part of an eyebrow block. Lets a ToC
   *  render a grouping label without re-walking the tree. */
  eyebrow?: string;
}
```

Additive, optional, ignorable. A consumer that doesn't care sees no change. See [[Maintain-Table-of-Contents-from-the-Heading-Outline]] and [[Heading-Outline-Cannot-Distinguish-Container-Headings]] — if `inContainer` and `nestHeadings` land in one minor bump, this rides along naturally.

**This is the actual payoff for long documents.** The stated motivation is skimming, and a ToC that shows the eyebrow beside each heading is skimming at the document level rather than the section level.

## The `$$` problem

**`$$` is the display-math delimiter in every LaTeX-flavored markdown on earth**, and math sits on the LFM wish list. Worth confronting before committing.

**The positional rule largely defuses it.** An eyebrow is only an eyebrow when the very next line is a heading. Display math is `$$` wrapping a block that closes with another `$$` — its next line is a formula, never an `##`. The two shapes barely overlap, and where they don't overlap the parser does nothing. That's a much narrower exposure than "we took the math delimiter."

What remains is a genuine but small residue: a document that opens a display-math block on the line directly above a heading. Malformed already, and it would now fail differently.

A separate reason `$$` beats `$`: a single leading `$` is *extremely* common in the prose these sites publish — "$2M ARR", "$4.40 per million" — and would misfire constantly. The doubled marker is worth its extra keystroke.

Options, none free:

| Marker | Collides with | Verdict |
|---|---|---|
| `$$` | LaTeX display math | Overlap is narrow once the positional rule applies. Recommended |
| `$` | Currency in ordinary prose | Rejected — "$2M ARR" would misfire constantly |
| `%%` | Obsidian comments (`%%…%%`) | Worse — silently swallows content in the vault |
| `^^` | Nothing in common use | Cheap, and reads as "above" |
| `--` | Setext `h2` underline, frontmatter fence | Rejected outright |
| `::eyebrow[…]` | Nothing — it's our own directive syntax | Safe, verbose, and defeats the point |

**Recommendation: ship `$$` as specified, and register `^^` as an accepted alias from day one.** Aliasing costs nothing — the polyglot rule already means multiple syntaxes normalize to one node — and it means that if math ever lands, `$$` can be deprecated for eyebrows without a content migration. Documents authored with `^^` are already safe.

`&&` has no meaningful collision and needs no alias.

## Shipping posture

The ask was "autoship, or at least be known by default." Concretely:

- **Registered in the trigger set by default**, so the syntax is discoverable and documented rather than a per-site secret.
- **Parsed by default** — the block normalizes to a node whether or not a site styles it.
- **Rendered by the consumer**, like every other LFM node. A site with no `.eyebrow` styles gets an unstyled paragraph, not a broken page.

Degradation matters here more than usual, because this syntax will end up in files that get read outside our renderer — Obsidian, GitHub, a plain markdown preview. In all of those, `$$ Portfolio Operations` renders as literal text on its own line above the heading. Ugly, not broken, and still readable. That is the correct failure mode and it is worth protecting: **never choose a marker that makes the raw file unreadable.**

## Open questions

- **Should the eyebrow be linkable to a section index?** If eyebrows repeat across a document (`PORTFOLIO OPERATIONS` on three headings), they imply a grouping. Worth nothing at first; worth a lot if a ToC groups by them.
- **Does the subheading belong in `data.headingText`?** No — that field feeds button labels and anchors and should stay the heading alone. Recording it here so nobody re-litigates.
- **Casing and styling of the eyebrow.** Uppercase is conventional but belongs to CSS, not to the parsed value. Preserve authored casing; let the render layer decide.
- **Multiple subheading lines?** Consecutive `&&` lines could join into one paragraph or become several. Lean: allow several, each its own `<p>`, since `hgroup` permits it.

## See also

- [[Maintain-Table-of-Contents-from-the-Heading-Outline]] — the outline contract this proposes to extend with `eyebrow`
- [[Heading-Outline-Cannot-Distinguish-Container-Headings]] — the open package-side change this should ride along with
- [[Maintain-Heading-Anchors-and-Share-Links]] — why the `##` keeps sole ownership of the anchor
- [[Maintain-Directives-in-Extended-Markdown-Render-Pipeline]] — the alternative directive-shaped syntax considered and set aside
