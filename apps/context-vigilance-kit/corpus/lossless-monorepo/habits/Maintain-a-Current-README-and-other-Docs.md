---
site_uuid: 85891599-4ac6-4977-8374-c88e14febdff
hex_code: 5czbky
title: Maintain a current README and other root docs
lede: 84 repos in this tree have a README. Nineteen have a CLAUDE.md, sixteen a DESIGN.md,
  and exactly two have an AGENTS.md.
summary: Repo-level habit covering the four root-level documents every Lossless repo
  aspires to — README.md, AGENTS.md, CLAUDE.md, DESIGN.md — what each is for, what
  counts as a substantial-enough change to trigger an update, and the create-as-you-go
  rule for the ones that don't exist yet. Operationalizes documentation upkeep as
  a trigger-based practice rather than a periodic sweep.
date_created: 2025-10-21
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
date_authored_final_draft: null
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 5 (1M context)
at_semantic_version: 0.0.1.0
status: Active
applies_to: every Lossless Group repo at every tier — anchor root, pseudomonorepo
  children, leaf projects, client-sites
publish: true
tags:
- Habit
- Documentation
- README
- Agent-Context
- Design-System
- Repo-Hygiene
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: habits/Maintain-a-Current-README-and-other-Docs.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/habits/Maintain-a-Current-README-and-other-Docs.md"
---

# Maintain a current README and other root docs

> Repo-level habit. Generic to every repo at every tier. Trigger-based rather than
> periodic — it fires on a substantial change, not on a calendar. Paired with the
> [`maintain-design-md`](../agent-skills/maintain-design-md/SKILL.md) skill, which owns
> `DESIGN.md` in full detail.

## Why this exists

A README that describes the repo as it was six months ago is worse than no README,
because it is believed. The same is true of the agent-facing documents, and more
sharply: a stale `CLAUDE.md` doesn't merely mislead a human who can notice the
mismatch — it silently steers every agent session in the repo.

The habit is not "write documentation." It is **notice, at the moment of a
substantial change, that a root document now says something untrue** — and fix it
in the same breath, while the change is still in your head.

## The four root documents

| File | Audience | What it holds |
|---|---|---|
| `README.md` | humans arriving cold | what this repo is, how to run it, where things live |
| `AGENTS.md` | any coding agent | the cross-tool agent-instruction standard, tool-agnostic |
| `CLAUDE.md` | Claude Code specifically | which skills to load, tree-specific rules, hard stops |
| `DESIGN.md` | agents and humans doing visual work | design tokens and the visual contract, per the Google Stitch open spec |

**Sites and splash pages carry a fifth**, which is published rather than committed
at the root:

| Route | Audience | What it holds |
|---|---|---|
| `/llms.txt` + `/llms-full.txt` | generative engines ingesting the site | a curated, prose-first map of the site's content for LLM consumption |

It ships as an Astro route — `src/pages/llms.txt.ts` alongside
`src/pages/llms-full.txt.ts` — not a static file, so it regenerates from content
on every build. Already live on `astro-knots/splash`, `lfm/splash`,
`content-farm/splash`, `memopop-site`, `context-vigilance-kit/splash`, and `site`.

**This one has its own habit**, [[Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages]],
and the mechanics live in the `open-graph-share-seo-geo` skill. It is listed here
only so that "and other docs" is not read as ending at the repo root — when you
substantially change what a *site* is about, its `llms.txt` is one of the things
that just became wrong. Same trigger, different artifact.

`AGENTS.md` and `CLAUDE.md` overlap but are not redundant: `AGENTS.md` is the
portable form other tools read, `CLAUDE.md` is where Claude-Code-specific
mechanics live (skill loading, MCP scope, the relocation hard stop). Where they
would say the same thing, say it in `AGENTS.md` and point at it.

## Current adoption across the tree

Counted 2026-08-17, excluding the 67 third-party pinned repos:

| File | Repos |
|---|---|
| `README.md` | 84 |
| `CLAUDE.md` | 19 |
| `DESIGN.md` | 16 |
| `AGENTS.md` | **2** |

**`AGENTS.md` is the gap.** It is the emerging cross-tool standard and this tree
has essentially skipped it, having gone straight to `CLAUDE.md`. Worth creating
whenever a repo is touched substantially — see the create-as-you-go rule below.

## What counts as substantial

Update the README when a change would make a cold reader's mental model wrong:

- a new top-level directory, or a directory that changed role
- a change to how the thing is run, built, or deployed — commands, ports, env vars
- a new dependency a contributor has to install or authenticate against
- a renamed or relocated entry point
- a capability added or removed
- the repo's purpose narrowing or widening

**Not substantial:** a bug fix, a refactor with no external surface change, content
edits, a dependency patch bump. Those belong in `changelog/`, and the split is the
point — `changelog/` is what happened, the README is what is currently true.

## Create as you go

**Do not scaffold all four into every repo.** An empty `AGENTS.md` is worse than a
missing one; it is a promise the file does not keep, and the sweep that produced
this document spent its day on exactly that failure mode.

Create one when there is something real to put in it:

- **`AGENTS.md`** — the first time you explain a repo-specific convention to an
  agent that you will have to explain again
- **`CLAUDE.md`** — the first time a repo needs Claude-Code-specific mechanics
  (skills to load, an MCP server, a hard stop)
- **`DESIGN.md`** — the first time a visual decision is made that another agent
  would otherwise re-litigate. Follow the `maintain-design-md` skill; the runtime
  CSS is the source of truth and `DESIGN.md` is the contract over it.
- **Specs** — as they come out. A convention that survives two repos is a spec,
  not a README paragraph.

## Who does this — the agent, unprompted

**This habit is addressed to the agent, not to the developer.** In practice the
developer directs a substantial change; the agent is the one that must notice the
root documents now say something untrue and fix them **in the same pass, without
being asked.**

Do not ask permission to update a root doc. Updating documentation to match code
that was just deliberately changed is part of making the change, not a separate
decision. Asking converts a two-line edit into a round trip, and the answer is
always yes.

**But always report what was changed.** Not a request — a statement, after the
fact, specific enough to catch a divergence:

> Also updated `README.md`: the "Running locally" section still said port 4321;
> changed to 4399. And `CLAUDE.md` still listed `chroma-local` as the skill to
> load for corpus queries — replaced with `search-lossless-corpus`.

The reason to report rather than ask is that **the agent can be confidently wrong
about intent.** The code change is unambiguous; what it *means* for the prose
often isn't. A one-line summary lets the developer catch a doc edit that
overstates, understates, or misreads the change — at the cost of a sentence,
instead of a stale wrong document nobody reread.

Report even when the edit seems trivial. "Updated the README's directory table for
the new `loaders/` folder" costs nothing and occasionally surfaces that the folder
was meant to be temporary.

## How to apply

- Land the substantial change, then reread the README's first screen before
  committing. That is where the false claim usually is.
- Fix the doc in the **same commit** as the change. A follow-up commit is a
  follow-up that doesn't happen.
- If the change makes an agent-facing rule wrong, `AGENTS.md` / `CLAUDE.md` are
  more urgent than the README — a wrong rule there is acted on automatically.
- If the repo has no `DESIGN.md` and you just made a visual decision, that is the
  trigger to create one.

## Related

- [[Maintain-Status-Discipline-Across-Context-V-Files]] — the periodic-sweep sibling
- [[Maintain-LLM-Txt-Standard-across-Significant-Sites-&-Splash-Pages]] — owns
  `/llms.txt` in full
- [[Maintain-Sitemap-and-Robots-across-Significant-Sites-&-Splash-Pages]] — the
  other published-artifact sibling
- [[Maintain-a-Github-Splash-Page-for-each-Repo]]
- `context-v/agent-skills/maintain-design-md/SKILL.md` — owns `DESIGN.md` in full
- `context-v/agent-skills/open-graph-share-seo-geo/SKILL.md` — the `llms.txt` mechanics
- `changelog/` — where "what changed" goes; the README is "what is true now"
