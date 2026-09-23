---
title: Pseudomonorepo Settings — Fence Each Project from Parent pnpm Workspaces
purpose: Pseudomonorepos are intentionally NOT pnpm workspaces. Without an explicit
  local `pnpm-workspace.yaml` fence, pnpm walks up the directory tree, finds the parent
  monorepo's `pnpm-workspace.yaml`, and tries to install/manage the entire workspace
  from a child project. This reminder records the only fence that actually works in
  pnpm 10 and the no-op trap to avoid.
status: Authoritative
last_verified: 2026-05-06
applies_to: every project, plugin, site, and child repo under `~/code/lossless-monorepo/`
  (and any other Lossless pseudomonorepo)
authors:
- Michael Staton
augmented_with: Claude Code on Claude Opus 4.7 (1M context)
site_uuid: 98953eed-25e0-4563-bb2b-30119577ffcc
hex_code: 8di7ct
date_created: 2026-05-08
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: reminders/Pseudomonorepo-Settings.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/reminders/Pseudomonorepo-Settings.md"
---

## Why this exists

A pseudomonorepo (see the `pseudomonorepos` skill) is **not** a true monorepo. Its
children — Obsidian plugins, Astro sites, scripts, etc. — must each install,
build, and deploy independently. Sharing a `node_modules/` or a workspace
lockfile across them is exactly what we are trying to avoid.

But the lossless-monorepo root contains a `pnpm-workspace.yaml`:

```yaml
# /Users/mpstaton/code/lossless-monorepo/pnpm-workspace.yaml
packages:
  - 'site'
  - 'content'
  - '!perplexed'
```

When you run `pnpm install` from anywhere inside the tree without a local
fence, pnpm walks up looking for a workspace root, finds this file, and
adopts the entire monorepo as the install scope. The user-visible symptom:

```
$ pnpm install
Scope: all 3 workspace projects
✔ The modules directory at "/Users/mpstaton/code/lossless-monorepo/node_modules"
   will be removed and reinstalled from scratch. Proceed? (Y/n) ·
```

That is pnpm offering to wipe the parent monorepo's `node_modules` because
it thinks you are operating on the workspace, not on the child project you
`cd`'d into. **Do not say yes.** Add a fence instead.

## The rule

Every child project in a pseudomonorepo MUST have a local `pnpm-workspace.yaml`:

```yaml
# <project-root>/pnpm-workspace.yaml
packages:
  - '.'
```

This declares the project as a single-package workspace whose only member is
itself. When pnpm walks up from inside the project, it finds **this** file
first and stops; the parent monorepo's workspace is never seen.

The same fence belongs at the **pseudomonorepo level** itself
(`content-farm/pnpm-workspace.yaml`, etc.) so that child projects without
their own fence still cannot escape upward to the lossless-monorepo root.

## What does NOT work — `ignore-workspace=true` in `.npmrc`

Several `.npmrc` files in this tree contain:

```ini
ignore-workspace=true
```

**This is silently ignored by pnpm 10.** It is not a real pnpm setting (only
the `--ignore-workspace` CLI flag exists). Verified by running
`pnpm install --lockfile-only` in `content-farm/` with `ignore-workspace=true`
present: pnpm still reported `Scope: all 3 workspace projects`. After adding
`pnpm-workspace.yaml: packages: ['.']` to `content-farm/`, the same command
ran cleanly with no scope message.

If you see `ignore-workspace=true` in a child's `.npmrc`, treat it as
documentation of intent only — the fence is the workspace yaml.

## How to verify a fence works

```bash
cd <child-project>
pnpm install --lockfile-only
```

- **Working fence:** output is just `Done in NNNms using pnpm v10.x.x`.
- **No fence (broken):** output starts with `Scope: all N workspace projects`
  and references `lossless-monorepo/node_modules`.

## Current state in `content-farm/` (snapshot 2026-05-06)

| Path | Has `pnpm-workspace.yaml` fence | Notes |
|---|---|---|
| `content-farm/` | yes — added 2026-05-05 | Stops walk-up to lossless-monorepo for any child without its own fence |
| `plugin-modules/cite-wide/` | yes — added 2026-05-05 | |
| `plugin-modules/perplexed/` | yes (pre-existing) | |
| `plugin-modules/image-gin/` | yes (pre-existing, `packages: []`) | |
| `plugin-modules/grab-reference/` | yes (pre-existing, custom packages list) | |
| `plugin-modules/file-transporter/` | no | Protected only by content-farm's fence |
| `plugin-modules/filestarter/` | no | Same |
| `plugin-modules/lmstud-yo/` | no | Same |
| `plugin-modules/metafetch/` | yes — added 2026-05-06 | |
| `plugin-modules/obsidian-git/` | no | Same |
| `plugin-modules/plunk-it/` | no | Same |
| `splash/` | no | Outside content-farm's `packages: ['.']` glob — pnpm treats it as standalone |

**Aspiration:** every child project gets its own `pnpm-workspace.yaml`. The
content-farm-level fence is the safety net, not the canonical answer.

## When scaffolding a new child project

The first file to create — before `package.json`, before `tsconfig.json`,
before anything else — is:

```yaml
# pnpm-workspace.yaml
packages:
  - '.'
```

This belongs in the project's git repo. It should be the first commit on the
default branch.

## Cross-references

- The `pseudomonorepos` skill at `~/.claude/skills/lossless-skills/pseudomonorepos/SKILL.md`
  defines the pseudomonorepo pattern but (as of 2026-05-05) does not yet
  encode this workspace-fence rule. This reminder is the canonical source
  until that skill grows a `references/workspace-fences.md`.
- The `pnpm-workspace.yaml` for each lossless-monorepo child must remain
  consistent with this convention; do not add `'plugin-modules/*'` or
  similar globs to `content-farm/pnpm-workspace.yaml` — that re-creates
  the very coupling the fence prevents.
