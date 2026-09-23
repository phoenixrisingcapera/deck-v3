---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/AUTHORING.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/AUTHORING.md"
---

# Authoring Lossless Skills

> **All skills authored by The Lossless Group live in *this* repo (`lossless-skills`). Edit nowhere else.** Copies in projects, vendored snippets, scratch versions in `~/.claude/skills/` directly — they all drift, they all rot, and they all break sync. There is one source of truth and this is it.

## Where to author

| Action | Where |
|---|---|
| Add a new skill | New top-level dir in `lossless-skills/` containing `SKILL.md` + any `references/`, `templates/`, `scripts/` |
| Update an existing skill | Edit the file directly inside `lossless-skills/<skill-name>/` |
| Add a *collection* of skills published upstream (e.g. `chroma-core/agent-skills`) | Add as a git submodule of `lossless-skills/`, then add an entry to `NESTED_SKILLS` in `sync-skills.sh` |

Editing a copy elsewhere — in a project's `context-v/skills/`, in `~/.claude/skills/<skill>/SKILL.md` directly without symlinking, in a downloaded clone — produces silent divergence. `sync-skills.sh` won't surface it; future sessions will load the wrong copy. Don't.

## After any change, run sync-skills.sh

```bash
bash sync-skills.sh           # apply
bash sync-skills.sh --dry-run # preview only
```

Both Claude Code and Pi require **per-skill top-level entries** in their respective skill directories (`~/.claude/skills/<name>/SKILL.md`, `~/.pi/skills/<name>/SKILL.md`) — neither tool recurses into umbrella directories. The sync script handles that bookkeeping. Re-running is idempotent; existing correct symlinks are recognized and skipped. Orphans (symlinks pointing into this repo for skills that no longer exist) are surfaced as warnings.

## Why this matters

Three skills (`maintain-splash-pages`, `open-graph-share-seo-geo`, `lossless-flavored-markdown`) were silently invisible to Claude Code in this user's environment for ~two days because their per-skill symlinks were missing — the skills existed in this repo but weren't surfaced. The umbrella `~/.claude/skills/lossless-skills` symlink does *not* fix this; Claude Code only walks the top level of `~/.claude/skills/`. Source: [official Claude Code skills docs](https://code.claude.com/docs/en/skills.md).

## Adding a new regular skill

1. `mkdir <skill-name>` in this repo
2. Author `<skill-name>/SKILL.md` per the skill spec (frontmatter with `name`, `description`)
3. Add any supporting `references/`, `templates/`, `scripts/`
4. `bash sync-skills.sh` to surface it in `~/.claude/skills/` and (if installed) `~/.pi/skills/`
5. Commit inside this submodule; do not auto-bump the parent gitlink (per project convention)

## Adding a nested-skill collection (like `chroma-agent-skills`)

When upstream publishes a *collection* of skills inside a single repo (`<repo>/skills/<name>/SKILL.md` layout):

1. Add the upstream as a git submodule: `git submodule add <url> <repo-name>`
2. Open `sync-skills.sh`
3. Add an entry to `NESTED_SKILLS`: `"<repo-name>/skills/<skill>:<skill>"` per skill you want to surface
4. `bash sync-skills.sh` to materialize the per-skill symlinks
5. Commit `.gitmodules`, the gitlink, and the script change together

## Doc layout per skill

```
<skill-name>/
├── SKILL.md              ← required — frontmatter + body per agent-skills spec
├── references/           ← optional — supporting docs the skill cites
├── templates/            ← optional — boilerplate the skill produces from
└── scripts/              ← optional — helper executables the skill can run
```

The skills manifest in [context-vigilance-kit](https://github.com/lossless-group/context-vigilance-kit) (`skills-manifest.md`) tracks completeness across this repo's skills automatically — re-run its build script after authoring to refresh the inventory.

## Don't

- Don't author skills directly in `~/.claude/skills/<skill>/SKILL.md` — that file should always be a symlink into this repo, not a real file.
- Don't vendor a copy into a project's `context-v/skills/`. Projects don't author skills; they consume them via the symlinks the sync script creates.
- Don't auto-bump the parent monorepo's submodule pointer when committing here — that's the user's deliberate-tidy step, not an automation step.
