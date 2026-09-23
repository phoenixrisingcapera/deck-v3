---
title: Deduplicate the augment-it changelog between the splash and the Laerdal collection
date_created: 2026-05-12
date_modified: 2026-05-12
status: Open
priority: Low
tags:
- Tech-Debt
- Changelog
- Augment-It
- Laerdal
- Single-Source-Of-Truth
related_issue: ai-labs/augment-it/context-v/issues/Changelog-Duplicated-Across-Splash-And-Laerdal-Collection.md
site_uuid: 495b7038-9a25-4085-a2fa-4bd3312e912b
hex_code: 460jul
date_authored_initial_draft: 2026-05-12
date_authored_current_draft: 2026-05-12
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: plans/Deduplicate-Augment-It-Changelog-Across-Splash-And-Laerdal.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/plans/Deduplicate-Augment-It-Changelog-Across-Splash-And-Laerdal.md"
---

## TL;DR

Eleven augment-it changelog entries live in two places. Pick one as the
source of truth and have the other surface read from it. Recommended:
keep `ai-labs/augment-it/changelog/` as source; have the consulting site's
Laerdal collection glob it.

## Current State

On 2026-05-12, eleven backfilled augment-it changelog entries were copied
(not moved) so the consulting site's "Laerdal Changelog" toggle would
surface them:

| Source of truth (splash reads this) | Copy (consulting site reads this) |
|---|---|
| `ai-labs/augment-it/changelog/2025-01-18_01.md` | `content/changelog--laerdal/2025-01-18_01.md` |
| `ai-labs/augment-it/changelog/2025-01-27.md` | `content/changelog--laerdal/2025-01-27.md` |
| `ai-labs/augment-it/changelog/2025-03-03_01.md` | `content/changelog--laerdal/2025-03-03_01.md` |
| `ai-labs/augment-it/changelog/2025-07-25_01.md` | `content/changelog--laerdal/2025-07-25_01.md` |
| `ai-labs/augment-it/changelog/2025-07-25_02.md` | `content/changelog--laerdal/2025-07-25_02.md` |
| `ai-labs/augment-it/changelog/2025-07-25_03.md` | `content/changelog--laerdal/2025-07-25_03.md` |
| `ai-labs/augment-it/changelog/2025-07-26_01.md` | `content/changelog--laerdal/2025-07-26_01.md` |
| `ai-labs/augment-it/changelog/2025-08-01_01.md` | `content/changelog--laerdal/2025-08-01_01.md` |
| `ai-labs/augment-it/changelog/2025-08-06_01.md` | `content/changelog--laerdal/2025-08-06_01.md` |
| `ai-labs/augment-it/changelog/2025-08-10_01.md` | `content/changelog--laerdal/2025-08-10_01.md` |
| `ai-labs/augment-it/changelog/2025-08-11_01.md` | `content/changelog--laerdal/2025-08-11_01.md` |

The copies in `content/changelog--laerdal/` have two extra frontmatter
fields prepended — `project: "Augment-It"` and `category: ...` — to fit
the visual style of the five pre-existing Laerdal entries. Body content
is byte-identical.

Five other entries in `content/changelog--laerdal/` (the 2025-02-02_01
version note + four Tanuj entries from 2025-07-23 / 2025-07-24) are
**not duplicated** — they describe pre-restart Phase-1 / 2.0.0 / prompt-
manager work that lives only in the Laerdal collection. Those stay put.

## Why It Matters

- **Edit drift.** A correction to any of the eleven backfilled entries
  has to be applied in two places, or the splash and the consulting site
  start telling slightly different stories.
- **Future client projects.** Any new repo that ships its own splash
  *and* needs to appear under a client's changelog tab on the consulting
  site will hit the same problem. Solving it once for augment-it
  establishes the pattern.

## Recommended Path — Option 2 (Laerdal loader reads from augment-it)

The cleaner option: augment-it owns its changelog; the consulting site
aggregates.

### Steps

1. **Extend the Laerdal collection's loader** in
   `site/src/content.config.ts`. The current definition globs a single
   base path:

   ```ts
   const changelogLaerdalCollection = defineCollection({
     loader: glob({ pattern: "**/*.md", base: resolveContentPath("changelog--laerdal") }),
     schema: z.object({}).passthrough()
   });
   ```

   Replace with a custom loader (or two coordinated `glob()` calls
   merged in a custom loader) that reads from **both**:
   - `<contentBasePath>/changelog--laerdal/` (the five client-history
     entries that stay)
   - `<repo-root>/ai-labs/augment-it/changelog/` (the augment-it
     entries, source of truth)

   Astro's `glob()` loader takes a single `base`, so this likely needs
   a custom loader that calls `fs.glob()` twice and merges. Pattern
   already exists in `ai-labs/augment-it/splash/src/content.config.ts`
   (the `localLoader` function) — lift it.

2. **Filter on `project: "Augment-It"` if needed.** The augment-it
   originals don't have this field; the Laerdal copies do. Decide
   whether to:
   - Inject `project: "Augment-It"` at load-time in the custom loader
     (cleaner), OR
   - Leave the field missing and rely on path-based provenance
     (`from: "augment-it"` style tag like the splash already does).

3. **Verify both surfaces still render**:

   ```bash
   # Splash unchanged
   cd ai-labs/augment-it/splash && pnpm build
   # Confirm changelog list shows 12 entries

   # Consulting site picks up augment-it entries via merged loader
   cd site && pnpm build
   # Confirm /workflow/laerdal still shows 16 entries
   # Confirm /log/laerdal-<slug> routes work for all 16
   ```

4. **Delete the eleven copies** in `content/changelog--laerdal/`:

   ```bash
   cd content/changelog--laerdal
   rm 2025-01-18_01.md 2025-01-27.md 2025-03-03_01.md \
      2025-07-25_01.md 2025-07-25_02.md 2025-07-25_03.md \
      2025-07-26_01.md 2025-08-01_01.md 2025-08-06_01.md \
      2025-08-10_01.md 2025-08-11_01.md
   # Should leave only:
   #   2025-02-02_01.md
   #   2025-07-23_01.md, _02.md, _03.md
   #   2025-07-24_01.md
   ```

5. **Verify again**:

   ```bash
   cd site && pnpm build
   # /workflow/laerdal still shows 16 entries — the 11 from
   # ai-labs/augment-it/changelog/ + the 5 still in
   # content/changelog--laerdal/
   ```

6. **Close the related issue** at
   `ai-labs/augment-it/context-v/issues/Changelog-Duplicated-Across-Splash-And-Laerdal-Collection.md`
   (set `status: Resolved`, add a `date_resolved` field, mention this
   plan in the body).

7. **Author a changelog entry** in `content/changelog--code/` for the
   tooling change (single source of truth for client changelogs across
   splash + consulting site).

## Alternative — Option 1 (Splash reads from content collection)

Less aligned but also valid: have augment-it's splash read its changelog
from `content/changelog--laerdal/` directly, filtering on
`project: "Augment-It"`.

Tradeoff: splash now depends on the `content` submodule being checked
out alongside `ai-labs/augment-it/` — works today, but couples augment-it's
self-presentation to a client-content repo it doesn't otherwise need.
Reject unless a future constraint forces it.

## How To Recognize It's Done

- [ ] `ls content/changelog--laerdal/` shows only 5 files
  (`2025-02-02_01.md`, `2025-07-23_01.md`, `2025-07-23_02.md`,
  `2025-07-23_03.md`, `2025-07-24_01.md`).
- [ ] `pnpm build` succeeds in both `site/` and
  `ai-labs/augment-it/splash/`.
- [ ] `/workflow/laerdal` on the consulting site still renders 16
  entries (5 client-history + 11 from augment-it).
- [ ] `/log/laerdal-*` detail routes work for all 16 entries.
- [ ] The augment-it splash's `/changelog/` page still renders 12
  entries (11 backfilled + 1 splash-creation entry).
- [ ] The issue at
  `ai-labs/augment-it/context-v/issues/Changelog-Duplicated-Across-Splash-And-Laerdal-Collection.md`
  is marked `status: Resolved`.

## Risk

Low. Both surfaces are static-built; if the loader merge goes wrong,
the build fails loudly and you revert. No production data is at stake.
The eleven duplicate copies will sit harmlessly in
`content/changelog--laerdal/` until the cleanup ships.
