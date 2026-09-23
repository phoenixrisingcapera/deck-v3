---
date_created: 2026-08-08
date_modified: 2026-08-08
site_uuid: 85f12e07-97cf-45d9-b7ef-62cb30357cc7
publish: true
title: Maintain Heading Anchors And Share Links
lede: A fragment URL is a public contract, and we currently ship two incompatible
  definitions of it. This moves anchor identity into LFM as data, leaves the share
  affordance in the render layer, and fixes collisions nobody is handling.
slug: maintain-heading-anchors-and-share-links
at_semantic_version: 0.0.0.1
authors:
- Michael Staton
augmented_with: Claude Code on Opus 5
tags:
- Extended-Markdown
- Render-Pipeline
- Remark
- Heading-Anchors
- Share-Links
- Table-Of-Contents
image_prompt: A librarian robot pressing numbered brass tags into the spines of books
  flying past on a conveyor; each tag is unique and glows where a hand would grip
  it.
hex_code: sta43c
date_authored_initial_draft: 2026-08-08
date_authored_current_draft: 2026-08-08
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: Maintain-Heading-Anchors-and-Share-Links.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/Maintain-Heading-Anchors-and-Share-Links.md"
---

# Maintain Heading Anchors and Share Links

## The problem is not the missing button

`lossless-monorepo/site` renders a share button beside every heading that copies a deep link to that exact point. No other site in the fleet has it, and we want it everywhere — splash pages included.

But building the button first would cement a bug we already have. **There are two different heading-slug algorithms running across the fleet**, and they disagree.

`lossless-monorepo/site` uses `src/utils/slugify.ts`:

```ts
input.toLowerCase()
  .replace(/\.[a-z0-9]+$/, '')      // strip trailing file extension
  .replace(/[^a-z0-9\s\-_]/g, '')   // keeps underscores
  .replace(/\s+/g, '-')
  .replace(/-{3,}/g, '--')          // collapse 3+ dashes to two
  .replace(/^-+|-+$/g, '');         // trim leading/trailing dashes
```

Every astro-knots site inlines a *different* one directly in `AstroMarkdown.astro` — including `packages/lfm-astro/components/AstroMarkdown.astro`, the canonical copy-from source, so every new site inherits the divergence:

```ts
text.toLowerCase()
  .replace(/[^a-z0-9\s-]/g, "")     // drops underscores
  .trim()
  .replace(/\s+/g, "-");            // no dash collapsing, no dash trimming
```

Measured against sample headings:

| heading | `lossless/site` | astro-knots | |
|---|---|---|---|
| `Set_Up the Repo` | `set_up-the-repo` | `setup-the-repo` | differs |
| `-- Notes --` | `notes` | `---notes---` | differs |
| `Deploy to prod.md` | `deploy-to-prod` | `deploy-to-prodmd` | differs |
| `Why Care?` | `why-care` | `why-care` | same |
| `Step 1 — Install` | `step-1-install` | `step-1-install` | same |

Same heading text, different URL, depending on which site rendered it.

**Neither implementation dedupes collisions.** Two headings with the same text produce two elements with the same `id`; the browser scrolls to the first and the second is unreachable. One live instance today (`docker-intro.md` has two `#view-logs`). Rare now, monotonically increasing with content volume.

A third quiet cost: the ToC in `lossless-monorepo/site` rebuilds the outline at runtime by scraping the DOM — `querySelectorAll('h1[id], h2[id], …')` — because nothing upstream hands it one.

## Decision: LFM owns the anchor, the render layer owns the button

Split along the data/presentation seam LFM already uses everywhere else.

**Into LFM** — anchor *identity*. It is data, it must be byte-identical across every surface that renders the same document, and it is a public contract the moment someone shares a link.

**Not into LFM** — the button. LFM is a remark preset producing MDAST. It has no DOM, no framework, no opinion about Astro vs Svelte vs a splash page's bespoke renderer. Putting markup and clipboard JS in it would force a framework choice into a parser.

This is the rule already written down in `astro-knots/CLAUDE.md`: publish the processing logic, copy the presentation. Citations set the precedent exactly — `remarkCitations` computes `data.citationIndex` and removes `footnoteDefinition` nodes; each site's `Sources.astro` decides what a citation *looks* like.

### Why not `rehype-slug`

It is the standard answer and it would work — on HAST. This pipeline never converts to HAST; it renders MDAST directly through Astro components. `rehype-slug` would silently never run.

This is the identical failure mode to Astro's built-in Shiki not highlighting LFM content (see `fullstack-vc/changelog/2026-08-08_02.md`). Worth naming as a category: **anything that operates on HAST or on Astro's own markdown pipeline is inert in LFM sites.** If a capability must apply to our content, it belongs in remark, in LFM, or in the renderer — never in rehype.

## The plugin: `remarkHeadingIds`

New plugin in `src/plugins/remark-heading-ids.ts`, exported from `src/index.ts`, added to `remarkLfm` in `src/preset.ts` (enabled by default — an id on a heading breaks nothing).

For every `heading` node:

1. Extract text via `mdast-util-to-string` (handles nested emphasis, inlineCode, links).
2. Slugify (algorithm below).
3. Dedupe within the document — second occurrence gets `-2`, third `-3`.
4. Stamp `node.data.id`, `node.data.hProperties.id` (so anything that *does* reach rehype behaves), and `node.data.headingText` for use as a button label.

Then attach a document outline at `tree.data.headings`:

```ts
interface LfmHeading {
  id: string;        // final, deduped
  text: string;      // plain text, no markup
  depth: 1|2|3|4|5|6;
  duplicateOf?: string;  // set when dedupe fired — diagnostics
}
```

This is the piece that pays for itself twice. Every site gets a build-time ToC for free, and `lossless-monorepo/site`'s DOM-scraping ToC becomes a render from data.

**No new dependencies.** The obvious tools are `mdast-util-to-string` and `unist-util-visit`, but LFM deliberately avoids the latter — both `og-fetcher.ts` and `remark-lossless-wikilinks.ts` say so in comments and hand-roll their walkers to keep the dependency surface minimal. This plugin follows suit: ~15 lines of recursive walk and ~10 of text extraction, versus two packages on the install graph of every consuming site.

### Slug algorithm — bug-for-bug, plus dedupe

Ship `lossless-monorepo/site`'s algorithm **verbatim** as the default, adding only collision dedupe.

Rationale: that is the only site with share buttons in the wild, so it is the only site with a meaningful population of already-shared fragment URLs. Matching it exactly means zero breakage where breakage would actually be felt. astro-knots sites change, but they have no share UI yet, so their fragment links are near-exclusively internal ToC jumps that regenerate on build.

Dedupe is strictly additive: it cannot move an anchor that wasn't already colliding, and where it does fire the current behavior is *broken* — the second heading is unreachable either way.

Expose the algorithm as an option so a site can opt out:

```ts
remarkLfm({ headingIds: { slugify: myFn, dedupe: true } })
```

### What breaks, measured

Audit run 2026-08-08 across both content trees, comparing the two algorithms heading by heading:

| | `lossless/site` | astro-knots sites |
|---|---|---|
| headings | 323 | 11,809 |
| **anchors that move** | **0** | 646 (5%) |
| docs with colliding anchors today | 1 | 30 |
| headings slugifying to empty string | 0 | 7 |

This settles it. Adopting `lossless/site`'s algorithm moves **zero** anchors on the only site that has ever published a share link. The 646 that move are all in astro-knots, which has no share UI — those fragments are near-exclusively internal ToC jumps that regenerate at build.

What moves, by shape: underscores preserved rather than stripped (`kauffman_year` → `kauffman_year`, not `kauffmanyear`), runs of 3+ dashes collapsed to two (`changelog---2026-04-27-01` → `changelog--2026-04-27-01`), and trailing file extensions dropped (`tsconfigjson` → `tsconfig`).

Against that, the change **fixes** 31 documents whose anchors currently collide and 7 headings that currently render `id=""` — invalid HTML, and all seven collide with each other.

No legacy-alias mechanism needed. If a specific high-traffic astro-knots page turns out to matter, the plugin can expose `data.legacyId` and the renderer can emit a `<span id>` beside the heading; cheap to add later, unjustified now.

## The affordance: `HeadingAnchor.astro`

Lands in `astro-knots/packages/lfm-astro/components/` beside `AstroMarkdown.astro`, `Sources.astro`, `Callout.astro`, `CodeBlock.astro`. Copy-and-adapt, not a runtime dependency.

Adapted from `lossless-monorepo/site`'s `CopyLinkButton.astro`, with these changes:

- **Theme tokens, not hardcoded color.** The current one hardcodes `#999` and `rgb(0, 233, 233)` and reaches for `--clr-lossless-accent--brightest`, a token that only exists on that one site. Fleet version reads semantic tokens per the two-tier convention.
- **One delegated listener per page**, not per button — the current implementation attaches a document-level listener inside every button's `<script is:inline>`, so a page with 40 headings registers 40 identical listeners. Same fix already applied to `CodeBlock.astro`.
- **No `alert()` on failure.** Fall back to selecting the URL text, matching the copy-button behavior in `CodeBlock.astro`.
- **Focus-visible, not hover-only.** The button is currently unreachable by keyboard in any meaningful way.
- Consumes `node.data.id` and `node.data.headingText` — never recomputes the slug. That's the whole point.

`AstroMarkdown.astro`'s heading branch drops its inline slugify and reads `node.data.id`.

## Rollout

Ordered, because the middle steps depend on a published version.

1. **`lossless-monorepo/lfm`** — plugin, types, preset wiring, tests over the divergence table above. Bump minor, publish to GitHub Packages and JSR.
2. **`astro-knots/packages/lfm-astro`** — `HeadingAnchor.astro`; update `AstroMarkdown.astro` to read `data.id`. This is the canonical source, so it lands before any site copies from it.
3. **Per-site adoption** — bump `@lossless-group/lfm`, re-copy the two components, delete the local slugify. Start with `fullstack-vc` (actively worked, has `docs-prose`, no share UI to regress), then `mpstaton-site`, `twf_site`.
4. **`lossless-monorepo/site` last** — highest link-breakage exposure, and the only one whose ToC needs rewiring from DOM-scraping to `tree.data.headings`. Do it once the pattern is proven elsewhere.
5. **Splash pages** — they render markdown through LFM already; they inherit anchors for free and opt into the button where it makes sense.

## Open questions

- **Does `lossless-monorepo/site`'s `slugify` need to stay one function?** It currently serves heading anchors, file slugs (`getReferenceSlug`), and tag normalization (`normalizeTag`). Those are three different contracts sharing one implementation; a change for one silently moves the others. Splitting them is out of scope here but should not stay unexamined.
- **Should the outline include headings inside callouts and directives?** A `> [!info]` body can contain an `###`. Probably yes for anchors, probably no for the ToC. Needs a `data.inContainer` flag or the ToC filters by depth of nesting.
- **Does the share button belong on `h1`?** The page title is already addressable by its bare URL; an anchor there is noise.
- **Headings that slugify to nothing.** Both algorithms strip everything outside `[a-z0-9]`, so a heading made only of symbols — or written in Japanese, Arabic, Cyrillic — becomes the empty string. **7 already exist in the astro-knots tree**, all rendering `id=""` and all colliding with each other. Dedupe alone makes them unique but unreadable (`-2`, `-3`). Needs a real answer before we serve non-English content: either transliterate, or fall back to a positional id like `heading-4`. The latter is ugly but valid, stable, and two lines.

## See also

- `Maintain-Lossless-Markdown-and-Extended-Markdown-Render-Pipeline.md` — the pipeline this plugs into
- `Maintain-Directives-in-Extended-Markdown-Render-Pipeline.md` — the `data.*` stamping precedent
- `astro-knots/context-v/specs/Codifying-a-Comprehensive-Extended-Markdown-Flavor-and-Shared-Package.md` — the package contract
- `astro-knots/sites/fullstack-vc/changelog/2026-08-08_02.md` — the HAST-inert failure mode, first instance
