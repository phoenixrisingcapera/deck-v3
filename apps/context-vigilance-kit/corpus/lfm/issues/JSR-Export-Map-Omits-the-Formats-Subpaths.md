---
site_uuid: 3922f762-d008-43f3-9bb1-29c3b7c71d7f
hex_code: w6a2vl
title: JSR Export Map Omits the Formats Subpaths
lede: '`deno.json` declares two exports; `package.json` declares six. The four it
  omits are the entire code-fence format registry — so the feature 0.4.1 was built
  around is unreachable for every consumer that installs from JSR, which is all nine
  of them.'
slug: jsr-export-map-omits-the-formats-subpaths
publish: true
date_created: 2026-08-17
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
at_semantic_version: 0.0.1.0
status: Resolved
category: Issue Resolution
authors:
- Michael Staton
augmented_with:
- Claude Code on Opus 5 (1M context)
summary: The deno.json exports map has never included ./formats, ./formats/yang, ./formats/json-schema
  or ./formats/plantuml, so JSR consumers cannot import the fence-format handlers
  even though the files are published. Verified by unpacking the released @jsr/lossless-group__lfm@0.4.1
  npm-compat tarball. Affects both JSR delivery paths and all nine consuming sites.
  Latent today because no site imports the subpaths yet — but the 0.4.1 release notes
  and the package's own doc comments instruct people to. Fix is four lines; the release-discipline
  fix is a parity check.
tags:
- JSR
- Publishing
- Consumer-Contract
- Code-Fences
- Packaging
image_prompt: A shipping crate with six labelled compartments, four of them sealed
  shut with no handle, the goods visible through slats.
source_root: /Users/mpstaton/code/lossless-monorepo/lfm/context-v
source_relative_path: issues/JSR-Export-Map-Omits-the-Formats-Subpaths.md
source_repo_slug: lfm
collated_at: '2026-08-24'
source_path: "lfm/context-v/issues/JSR-Export-Map-Omits-the-Formats-Subpaths.md"
---

# JSR Export Map Omits the Formats Subpaths

**Status:** Resolved in 0.5.1 — see [Resolution](#resolution)
**Affects:** `deno.json`, every consumer installing from JSR
**Present since:** 0.4.1, the release that introduced the format registry

## Symptom

`deno.json` and `package.json` disagree about what is importable, and JSR enforces its map strictly.

| Subpath | npm / GitHub Packages | JSR |
|---|---|---|
| `.` | ✅ | ✅ |
| `./types` | ✅ | ✅ |
| `./formats` | ✅ | ❌ |
| `./formats/yang` | ✅ | ❌ |
| `./formats/json-schema` | ✅ | ❌ |
| `./formats/plantuml` | ✅ | ❌ |

So the import the 0.4.1 release notes tell you to write fails for anyone on JSR:

```ts
import { yang } from '@lossless-group/lfm/formats/yang';
//       ^ resolution error — no such export
```

**The files are published.** They appear in `jsr publish --dry-run` output — `src/formats/yang.ts`, `json-schema.ts`, `plantuml.ts`, `index.ts` — because `publish.include` carries `src/**/*.ts`. They are shipped and unreachable, which is the worst of both: bytes on the wire, no way to import them.

## Verified against the published artifact, not inferred

Both JSR delivery paths are affected, which matters because eight of the nine consuming sites use the npm compatibility layer rather than a native `jsr:` specifier.

Unpacking the real thing settles it:

```bash
npm pack @jsr/lossless-group__lfm@0.4.1 --registry=https://npm.jsr.io
tar -xzf jsr-lossless-group__lfm-0.4.1.tgz
```

```json
{
  "exports": {
    ".":      { "types": "./_dist/src/index.d.ts",       "default": "./src/index.js" },
    "./types":{ "types": "./_dist/src/types/index.d.ts", "default": "./src/types/index.js" }
  }
}
```

The generated npm package's `exports` is derived from `deno.json`, not from `package.json`. `npm:@jsr/lossless-group__lfm` inherits the gap exactly.

## `plantuml` is the sharp edge

For three of the four omissions there is a workaround — pull the handler off the root barrel. For `plantuml` there is none, and it is deliberate. From `src/formats/index.ts`:

> `plantuml` is not re-exported here, because importing a node builtin into
> this barrel would make it unusable in a browser context. Import it by
> subpath: `@lossless-group/lfm/formats/plantuml`.

The only documented route to it is the subpath, and the subpath doesn't exist on JSR. **PlantUML is not merely awkward for a JSR consumer — it is unreachable.**

## Why nobody has hit it

No consuming site imports `@lossless-group/lfm/formats` yet. The only references in the tree are doc comments inside the package itself and the 0.4.1 release notes.

That is why this survived a release: the fence registry shipped, the splash's `/formats` gallery proved the parsers, and nothing exercised the *authoring* path through an installed copy. 0.4.1's own "Known gaps" section came close —

> A `yang` fence in an authored markdown file still renders as a plain code
> block. The gallery at `/formats` builds its own processor, so it proves the
> parsers, not the authoring path.

— but attributed the gap to a missing renderer. The missing export is underneath it: even a site that *wrote* the renderer couldn't import the handler to feed it.

The nine consumers, for the record. All on JSR; `fullstack-vc` is already pinned to `^0.5.0`:

```
fullstack-vc          npm:@jsr/lossless-group__lfm@^0.5.0
mpstaton-site         npm:@jsr/lossless-group__lfm@0.3.0
lossless-changelog    npm:@jsr/lossless-group__lfm@latest
twf_site              npm:@jsr/lossless-group__lfm@^0.3.0
learnstart-site       npm:@jsr/lossless-group__lfm@^0.3.0
content-farm/splash   npm:@jsr/lossless-group__lfm@^0.3.0
reach-edu-hub         npm:@jsr/lossless-group__lfm@^0.3.0
lossless-at           npm:@jsr/lossless-group__lfm@^0.3.0
calmstorm-decks       jsr:^0.2.2
```

## Fix

Four lines. Mirror `package.json`:

```jsonc
// deno.json
"exports": {
  ".":                    "./src/index.ts",
  "./types":              "./src/types/index.ts",
  "./formats":            "./src/formats/index.ts",
  "./formats/yang":       "./src/formats/yang.ts",
  "./formats/json-schema":"./src/formats/json-schema.ts",
  "./formats/plantuml":   "./src/formats/plantuml.ts"
}
```

Additive — no existing import changes, nothing breaks. Run `jsr publish --dry-run` afterwards: each new entrypoint gets its own slow-types check, and `plantuml`'s node-builtin import is the one most likely to have something to say.

**Ship it as its own patch release.** 0.5.0 is already tagged and published, and JSR versions are immutable, so editing `deno.json` quietly would leave the artifact on JSR disagreeing with the `v0.5.0` tag. A four-line fix with a real consumer-facing story is a clean 0.5.1.

## The discipline fix underneath

The one-line patch treats the symptom. Two export maps hand-maintained in two files will drift again the next time a subpath is added — that is exactly how this happened.

Options, roughly in order of effort:

1. **A test asserting parity.** Read both files, compare key sets, fail on mismatch. Cheap, runs in the existing suite, catches it at the moment of divergence rather than a release later. `deno.json` values point at `src/*.ts` and `package.json` at `dist/*.js`, so compare *keys* only.
2. **Generate one from the other** in a prepublish step. Removes the class of bug but adds a build artifact to review.
3. **Leave it and remember.** What we did last time.

(1) is the recommendation. It is a handful of lines and it belongs next to `test/naming-contract.test.mjs`, which exists for the same reason: a public-API promise that fails silently in someone else's repo rather than loudly in ours.

## Blast radius

Low, and entirely additive. No published version is retroactively affected — 0.2.x through 0.5.0 shipped without these exports and will continue to. Consumers gain the subpaths on upgrade; nobody loses anything.

## Resolution

**Resolved in 0.5.1 (2026-08-17).** `deno.json` now mirrors `package.json`; all
four `./formats*` subpaths are exported and each passes its own slow-types
check on publish, PlantUML's node builtin included.

Option (1) from above shipped alongside it: `test/export-parity.test.mjs`
compares the key sets both directions, verifies every JSR target exists and is
TypeScript source, verifies every npm target resolves into `dist/`, and checks
that the two manifests agree on name and version. The test was confirmed to
fail against the pre-fix state — removing `./formats/plantuml` from
`deno.json` reproduces the original defect with a message naming the fix —
because a parity test that cannot detect the bug it was written for is worse
than none.

No source file changed. See `changelog/releases/0.5.1.md`.

## See also

- `changelog/releases/0.4.1.md` — the release that introduced the registry, and documents the imports that don't work on JSR
- [[Workspace-vs-JSR-for-LFM-Consumers]] — the other JSR-shaped consumer concern; about *pinning*, not export maps
- `context-v/blueprints/Naming-Plugins-Against-the-Remark-Ecosystem.md` — the neighbouring "check before assuming what's public API" discipline
