---
title: Syncing Directories Across a Pseudomonorepo
lede: Three annoyances that look like one problem. Symlinks break git, submodules
  cost too much, and rclone has no watcher.
date_created: 2026-08-22
date_modified: 2026-08-22
date_authored_initial_draft: 2026-08-22
date_authored_current_draft: 2026-08-22
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 5 (1M context)
at_semantic_version: 0.0.0.1
status: Open
site_uuid: b554fe1b-fa3f-4b4d-80a4-fa9771c5e726
hex_code: veg3lu
summary: 'Exploration of how the same directory can exist, versioned, in more than
  one repo of the tree without symlinks, submodules, or hand-run scripts. Separates
  three annoyances that present as one — stale rollups, the Obsidian vault''s symlink
  farm, and agent-skill replication into child repos — and finds they need two different
  answers, not one. Converges on a manifest-driven one-way fan-out using rclone for
  the copy and watchexec for the trigger, and names the residue that no cross-platform
  tool covers: keeping a watcher alive at login is launchd on macOS, systemd on Linux,
  Task Scheduler on Windows.'
tags:
- Exploration
- Pseudomonorepos
- Sync
- Agent-Skills
- Rclone
- Tooling
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: explorations/Sync-Dirs-in-Pseudomonorepo-Architecture.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/explorations/Sync-Dirs-in-Pseudomonorepo-Architecture.md"
---

# Syncing Directories Across a Pseudomonorepo

## Why Care?

A tree of 27 repos keeps wanting the same directory to exist in more than one
place. Skills authored once should be present in the child repos whose agents
need them. A child's `changelog/` should surface on the parent's splash. The
Obsidian vault should show content that lives in a code repo.

Every attempt so far lands on one of two workarounds, and **both of them are
worse than they look**:

- **Symlink it.** Works for the filesystem, fails for git — the receiving repo
  stores a ~60-byte path blob, not the content, so the content is never
  committed, never pushed, and never version-controlled *from that side*. Worse,
  the stored path is absolute (`/Users/mpstaton/…`), so it is meaningless on any
  other machine.
- **Copy it by hand when we remember.** Which means the copy is stale for
  however long it takes to remember.

The trigger for this exploration was the second one getting named out loud:
*"Right now we 1) rollup whenever we remember. As a result, some things we do
just have stale content."*

## Three annoyances, and they are not one problem

The first useful move was separating them. They present identically — *"the same
files should be in two places"* — and they need different answers.

### 1. Rollups go stale

`<parent>/splash/scripts/rollup-sync.ts` walks each child's `changelog/` and
`context-v/` and writes into `splash/src/rollup/`. It exists in three splashes
(`ai-labs`, `astro-knots`, `content-farm`) and it works.

**It is not a copy.** It `rm -rf`s the output, regenerates, **injects provenance
frontmatter**, and flattens `<child>/<section>/` paths. No file-sync tool can do
that, because the transform is the point.

The output is also **committed** — 778 tracked files under `ai-labs/splash/src/rollup`
alone — despite being fully derived. And `rollup:sync` is a standalone npm
script, wired to neither `build` nor `dev`.

So the gap is not the mechanism. **The gap is that nothing fires it.**

### 2. The Obsidian vault's symlink farm

The vault at `~/content-md/lossless/` contains 15 symlinks into
`lossless-monorepo/content/*` — `Tooling`, `essays`, `specs`, `concepts`,
`organizations`, and the rest.

The stated complaint was *"git only manages files authentically in its dir"* —
so the Obsidian Git plugin cannot manage the symlinked content.

**Checking it inverted the diagnosis.** `content/` is a **git submodule** →
`lossless-group/lossless-content.git`, **4836 tracked files**, real remote. The
symlinked half is the *well-managed* half.

What is unmanaged is everything the vault natively owns:

| | |
|---|---|
| `.git` anywhere under `~/content-md/` | **none** |
| Loose `.md` at the vault root | **996** |
| Real (non-symlink) directories | **17** |
| Total files with no version control | **~1156** |

The symlinks are a red herring. **The vault's own content has never been
versioned, backed up, or pushed anywhere.** That is the actual finding, and it
wants `git init` plus a `.gitignore` listing the 15 symlink names — two repos,
each managing what it authentically owns.

### 3. Agent-skill replication — the real subject

Skills live once at `context-v/agent-skills/` (itself a submodule →
`lossless-agent-skills.git`). Child repos — `augment-it`, `dididecks-ai`,
`memopop-ai` — want an identical copy so that a developer working there has
them, **and so the app's own agent surface (`didi-chat`) can load them at
runtime**.

Symlinking fails for the reason above. This is the problem the rest of this
document is about.

## What rclone actually is

Worth writing down, because the assumption under the question was that rclone
might be a live mirroring daemon. It is not.

| Mode | Behaviour |
|---|---|
| `rclone copy` | One direction, **additive** — never deletes at the destination |
| `rclone sync` | One direction, makes destination **match** source (deletes) |
| `rclone bisync` | **Genuinely bidirectional**, stable as of v1.75 |

`bisync` retains listings from the prior run, detects `New`/`Newer`/`Older`/
`Deleted` on both sides, and offers `--conflict-resolve
none|path1|path2|newer|older|larger|smaller` with a `--conflict-suffix` for the
loser. Its own help says: *"considered an **advanced command**, so use with
care… or data loss can result."*

**And in no mode does rclone watch the filesystem.** There is no `rclone watch`.
It is a batch tool that runs when invoked. Every rclone workflow needs a trigger
supplied from outside.

Verified locally against v1.75 — local→local, subset by filter, real files:

```bash
rclone sync master/ childA/ \
  --filter "+ /skill-one/**" --filter "+ /skill-two/**" --filter "- *"
```

Result: `childA/skill-one/SKILL.md` and `skill-two/SKILL.md` exist as **real
files** (`.rw-r--r--`, not symlinks), an upstream edit propagates on re-run, and
`skill-three` is correctly absent.

**That filter line is the important part.** *Which skills go where* becomes
configuration — which is the capability that made submodules unattractive,
obtained without any git plumbing.

## What was ruled out, and why

**Symlinks.** The git gap above, plus absolute paths that do not survive a
different machine. Still correct for `~/.claude/skills/` — that is tool
discovery, not repo replication, and `sync-skills.sh` already solves it.

**Git submodules.** Technically the *right* primitive — git's native "reference
another repo's content from inside mine," real files on disk, one source of
truth, a per-repo pinned SHA so children can lag deliberately. **Ruled out by the
operator on cost:** a submodule brings *all* skills, and taking a subset means
`sparse-checkout`, which is per-clone plumbing to set up and maintain. *"That's
one more overhead I want to avoid."* Accepted — the manifest above gives the same
subsetting for a line of config.

**Git subtree.** Vendors content with history and can push back upstream. Real
files, committed. Rejected for history bloat and awkward commands.

**`rclone bisync`.** Bidirectional is available and is the wrong shape here. N
children syncing back to one master is hub-and-spoke multi-writer, which is the
hardest version of the problem and buys nothing: skills have one authoritative
home by convention already.

**Python plumbing.** *"I know this is possible with some light python plumbing,
but I have avoided that too."* Standing constraint — the answer should be a
binary and a shell script.

## Converging: manifest-driven one-way fan-out

```
context-v/agent-skills/
  fanout.config.json    # { targets: [ { repo, path, skills: [...] } ] }
  fanout-skills.sh      # rclone sync per target; --dry-run; refuses to clobber divergence
```

- **One direction, master → children.** No conflict semantics to reason about
  at all.
- **Real files at the destination**, so the child repo tracks, commits, and
  pushes them normally. The symlink gap closes.
- **A manifest, not sparse-checkout.** Per-target skill lists in JSON.
- **Refuses to overwrite** a target that differs from what it last wrote, unless
  `--force` — turning silent loss into a message.

### Every-save propagation is fine — an earlier objection, withdrawn

The first draft of this recommendation warned against a file watcher on the
grounds that it would propagate half-written skills into other repos. **The
operator's counter was correct and the warning is withdrawn:**

> I don't actually mind the propagation of every save. Why does it matter if I'm
> editing an agent-skill in one place and the changes are showing up in realtime
> in a folder I'm not even working in?

Three reasons it does not matter:

1. **The destination is git-tracked.** A half-written skill landing in
   `augment-it` is an uncommitted working-tree change. The next save overwrites
   it. Nothing is committed unless someone chooses to.
2. **Editors write atomically.** VS Code, Obsidian, and vim write to a temp file
   and rename. A watcher sees the old file, then the new one — never a truncated
   one.
3. **Nothing reads that folder in that instant.** Skills load at session start.

The only residue is cosmetic: `git status` in a child shows churn nobody typed.

And there is a positive case that the first draft missed — **every-save
propagation means the copy is never stale, with zero discipline required**, which
is the entire annoyance this document exists to kill.

### Why not a `post-commit` hook

Considered seriously, and it **reintroduces the problem in miniature**. A hook
fires when you commit; edit a skill and leave it uncommitted for a day and the
children are stale for a day. That is *"roll up whenever we remember"* wearing a
different hat.

Recorded because the mechanics are still worth knowing, and because
`post-merge` remains useful:

- `.git/hooks/post-commit`, executable, no extension. Runs after a successful
  commit, from the repo root. **Exit code ignored** — unlike `pre-commit` it
  cannot block anything.
- **`.git/hooks/` is not version-controlled.** A hook lives only on the machine
  that made it. To share one: commit `.githooks/` and set
  `git config core.hooksPath .githooks`.
- **It does not fire on `pull` or `merge`** — that is `post-merge`. So a skill
  edited on another machine and pulled here would not fan out.
- **The skills repo is a submodule**, so its hooks live at
  `lossless-monorepo/.git/modules/context-v/agent-skills/hooks/`, not at
  `context-v/agent-skills/.git/hooks/`. Easy to place wrongly.

**Verdict:** watcher for continuity, plus `post-merge` so a pull on another
machine also fans out. Skip `post-commit` — the watcher already covers it.

## The cross-platform requirement

Added to the decision 2026-08-22: *"I'd rather install a library that works
across Mac/Linux/Windows filesystems if there is one."*

**There is, for the watching half.**

**[watchexec](https://github.com/watchexec/watchexec)** — Rust, a single
self-contained binary with no Node or Python runtime, running on **Linux, macOS,
and Windows**. Built for exactly this job: watch a path, run a command on change.
Debouncing and VCS-directory ignores are defaults rather than flags.

```bash
watchexec -w context-v/agent-skills -- ./fanout-skills.sh
```

Alternatives weighed: **fswatch** has native backends across macOS/BSD/Linux/
Solaris/Windows but is a lower-level event *printer* that still needs a shell
loop around it. **entr** is Unix-only. **chokidar** and **watchfiles** are
excellent and are library dependencies in ecosystems this deliberately avoids.

### The residue no tool covers

**Watching is cross-platform. Keeping the watcher alive at login is not.**

| OS | Mechanism |
|---|---|
| macOS | `launchd` LaunchAgent plist (`RunAtLoad`, or `WatchPaths` and skip watchexec entirely) |
| Linux | `systemd --user` unit |
| Windows | Task Scheduler, a Startup shortcut, or NSSM |

There is no portable "run this at login" primitive. So the setup is genuinely
three-platform whatever we choose, and **that residue is the thing that needs
documenting rather than automating.**

Worth noting the macOS special case: `launchd`'s `WatchPaths` fires a job when a
path changes, which means on macOS alone watchexec is redundant. Choosing
watchexec anyway is choosing **one instruction for three platforms** over a
smaller footprint on one.

## Where the setup instructions should live

Given the residue is per-OS and cannot be automated away, the question is where
the human-readable procedure lives. Two candidates, and they are not exclusive:

1. **A `templates/` directory in the `pseudomonorepos` skill.** The skill
   currently has `SKILL.md` and `references/` but no `templates/`, and the
   agent-skills shape explicitly allows one. A template LaunchAgent plist, a
   systemd unit, and a `fanout.config.json` stub would sit naturally there — it
   is tree-shape infrastructure, which is what that skill is about.
2. **A dedicated agent-skill**, if the setup grows past templates into a real
   procedure with failure modes worth encoding — *"the watcher silently died and
   the copies went stale"* is the failure this whole approach introduces, and it
   deserves a diagnosis path.

**Leaning toward (1) first**, promoting to (2) if it grows. The pattern is a
paragraph and three config files today; a skill for that is premature. It becomes
a skill the moment someone has to debug it.

## What this costs, stated plainly

- **N copies of the same markdown in N git repos.** One skill edit becomes N
  commits across N repos, and each child's `git log` carries changes it did not
  author. This is the price of avoiding submodules, and it is a real price.
- **A new silent failure mode.** A watcher that dies stops syncing without
  saying so. The old failure was *"we forgot"*; the new one is *"we thought it
  was automatic."* The second is worse because it does not feel like a risk.
  Some liveness check is wanted — a receipt file in each target recording source
  SHA and timestamp would make staleness visible.
- **The rollup problem is not solved by any of this.** See below.

## Rollups need a different answer

Because `rollup-sync.ts` transforms rather than copies, no sync tool applies. The
fix is one line:

```json
"build": "pnpm rollup:sync && astro build"
```

The built site then **cannot** be stale, and `src/rollup/` can stop being
committed — 778 files in `ai-labs` alone, times three splashes.

**The caveat that decides it:** GitHub Pages CI must check out *nested*
submodules for a build-time rollup to work. If it cannot, keep committing the
output and add the prebuild hook locally so the committed copy is fresh whenever
anyone builds. Worth testing before deleting anything.

## Open questions

1. **Does CI recurse nested submodules?** Decides the rollup answer outright.
   Untested.
2. **What does the app actually need at runtime?** If `didi-chat` reads skills
   from a deployed container, a repo copy is not there unless the build brings
   it. That may be a build-step copy or a fetch-at-runtime — a different problem
   from developer-in-the-repo, and possibly with a different answer.
3. **Does a skill ever get improved inside a child?** The design says no, and
   one-way sync enforces it. If it turns out people do, the honest answer is to
   move the edit upstream, not to make the sync bidirectional.
4. **The vault's 1156 unversioned files.** Named in this document, not addressed
   by it. `git init` plus a `.gitignore` of the 15 symlink names is the fix and
   it is unrelated to everything else here.

## Related

- [[../agent-skills/pseudomonorepos/SKILL.md]] — the tree shape; likely home for the setup templates
- `context-v/agent-skills/sync-skills.sh` — the *tool discovery* fan-out (`~/.claude/skills/`), a different problem correctly solved
- `ai-labs/context-v/explorations/A-Syncbox-For-Client-Document-Folders.md` — the sibling exploration on syncing client corpora; same three-layer framing
- `ai-labs/studies/sync-and-content-version-control` — six pinned sync/VCS references, incl. why every file-sync tool resolves conflicts by renaming
- `context-v/reminders/Check-The-Substrate-Before-Reasoning-On-Top-Of-It.md` — why the vault diagnosis was checked rather than assumed
