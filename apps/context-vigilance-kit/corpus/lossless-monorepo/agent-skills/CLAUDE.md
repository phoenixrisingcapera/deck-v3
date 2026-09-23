---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/CLAUDE.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/CLAUDE.md"
---

# Agent instructions for `lossless-agent-skills`

This repo is the shared skill library for The Lossless Group — one directory per
skill, each with a top-level `SKILL.md` following the
[Agent Skills spec](https://agentskills.io/specification). It is **public**, and it is
mounted into the anchor pseudomonorepo at `context-v/skills/`.

## Symlink sync — opening & closing habit

Claude Code only discovers a skill when it has its **own** direct-child symlink at
`~/.claude/skills/<name>`. A symlinked *parent* directory does not expose the skills
nested inside it, so an authored-but-unlinked skill is invisible to every session.

```bash
bash ./sync-skills-symlinks.sh
```

Run it at session start (picks up skills added since last session) and again after
authoring or editing any skill — newly-linked skills load in the *next* session, not
the current one. Idempotent; never clobbers a non-symlink.

Two things that break discovery and are easy to miss:

- **The directory name must match the skill's frontmatter `name:`.** A mismatch loads
  the skill without its description, so it never triggers.
- **Renaming a skill directory leaves a broken symlink behind.** The sync script adds
  the new link but does not remove the stale one. Check with
  `find ~/.claude/skills -maxdepth 1 -xtype l`.

## Public skills, private config

Skills here are published. Operator-specific particulars — firm names, workspace URLs,
key relationships — live in a gitignored `<skill>/config/private.json`, documented by a
committed `config/private.example.json`, and are read at runtime by instruction rather
than by templating. `lossless-crm-interface-guidelines/` is the reference
implementation. Full pattern, including the pre-push audit grep, is in `README.md`.

Never inline a config value back into a `SKILL.md`. The moment a firm name or an
instance URL lands in the public file, the skill has stopped being publishable.

## Vendored upstream submodules — do not overlay them

`chroma-agent-skills/` is pinned from [`chroma-core/agent-skills`](https://github.com/chroma-core/agent-skills).
We have **READ** permission only. Anything committed inside it can never be pushed, and
a local commit there would leave this repo's gitlink pointing at a SHA that exists on no
remote — the loss scenario the `pseudomonorepos` HARD STOP guards against.

So: **Lossless conventions do not get injected into vendored repos.** The tree-wide
`<!-- lossless:browser-drive:* -->` rollout reached 16 `CLAUDE.md` files including that
one; the copy inside the submodule has been reverted and lives here instead. If a future
rollout script walks the tree writing `CLAUDE.md`, exclude vendored submodules.

<!-- lossless:browser-drive:start -->
## Browser-drive verification (Playwright MCP + Claude Chrome)

Agents verify UI work by driving a real browser BEFORE asking a human to walk the surface. Two tiers:

- **Codified (default): Playwright MCP** — navigate/click/type, accessibility-tree snapshots, DOM assertions; headless-capable, runs unwatched. Wire it per repo at **project scope** (config lands in the committed `.mcp.json`):

  ```bash
  claude mcp add -s project playwright -- npx @playwright/mcp@latest
  ```

- **Interactive: `claude --chrome`** (or `/chrome` → enable by default) — Claude drives the operator's real Chrome while they watch; screenshots/GIFs + console and network logs.

Rules that make it safe and cheap:

1. Newly added MCP servers load in the **next** session, not the current one (same rule as skills symlinks).
2. Prefer **accessibility snapshots over screenshots** — raster is token-expensive; use it only for visual questions (layout, theme).
3. Browser-driven **reads are unrestricted; writes only against the repo's designated safe target** — never mint test entities in shared/canonical data.
4. The drive's click-path is **named in the phase plan before implementation**; a drive that lives only in a session transcript is not codified.
5. A browser drive proves the buttons **work**; the human walk-through still judges whether the surface is **usable**. It augments the human rung, never replaces it.

Full pattern: `context-v/blueprints/Browser-Drive-Verification-For-Agent-Sessions.md` at the anchor monorepo root (kit rollout draft: `ai-labs/context-vigilance-kit/context-v/blueprints/`). Loop integration proven in `ai-labs/augment-it/context-v/loops/`.
<!-- lossless:browser-drive:end -->

## See also

- `README.md` — the Skills table, install instructions, and the public/private config pattern
- `CANDIDATES.md` — backlog of skills not yet written
- `git-conventions/SKILL.md` — commit shape for changes in this repo
- `changelog-conventions/SKILL.md` — when a change here earns a `changelog/` entry
