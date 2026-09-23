---
title: 'Explore: Using PRs More — Why a Solo Dev Should Bother'
lede: 'PRs aren''t a review ritual — they''re an integration ritual: squash a granular
  trail into one shipped unit with a stable URL and a CI gate.'
date_authored_initial_draft: '2026-05-06'
date_authored_current_draft: '2026-05-06'
date_created: '2026-05-06'
date_modified: '2026-05-06'
at_semantic_version: 0.0.0.4
semantic_version: 0.0.0.4
status: Draft
augmented_with: Claude Code (Opus 4.7)
category: Explorations
tags:
- Pull-Requests
- Git-Workflow
- Solo-Development
- Squash-Merge
- AI-Augmented
- Changelog-First-Development
authors:
- Michael Staton
- AI Labs Team
site_uuid: c1538d67-7ec2-43be-8d1b-dbfa85470e52
hex_code: i3hcns
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: explorations/Using-PRs-More.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/explorations/Using-PRs-More.md"
---

## The honest reframe

The reason PRs feel pointless is the framing — *"PRs are for code review"* — and there isn't any code review when you're solo. Drop that framing. **PRs are an integration ritual, not a review ritual.** Code review is one thing they enable, but only one of several. The integration ritual has at least four other jobs that pay even when nobody else is watching.

This also resolves the tiny-commits tension you flagged. The reason tiny commits *feel* right while developing is because **they are right** — they're checkpoints, easy to revert one thing, easy to bisect. The reason they feel wrong in retrospect is that you're staring at the *main branch's history*, which is supposed to read like a narrative, not a debugging trail. Both can be true at once if the tiny commits live on a branch and main only sees the squashed result.

## What a PR actually buys you (when nobody else reviews)

### 1. The squash-merge — turn a developing trail into a shipping unit

This is the headliner. During development, you commit granularly:

```
ec922c6  init(rebrand): rename modal files
4d31a02  WIP: settings.ts
9a8e1f1  fix typo
3b5e2c7  WIP: still settings
24e5a5c  rebrand sweep done, all tests green
c80d93b  cleanup
```

Six commits, all noise on main. Squash-merging the PR collapses them into:

```
24e5a5c  refactor(rebrand): sweep Open Graph Fetcher identifiers to Metafetch
```

One commit per shipped unit. Main reads like the changelog, not a debugging tape. **The branch keeps the granular history** (in the PR's commits tab) for future bisecting if you ever need it. You get both.

This alone justifies the practice for solo devs who care about main-branch readability — which Lossless does, because main-branch readability is part of the credibility narrative we're trying to build (see [[Explore-GitHub-API-for-Live-KPIs]]).

### 2. A self-review checkpoint

Open the PR, look at the *whole diff* in one view. Read it like a stranger. Catch:

- Forgotten `console.log` / `console.error` debug lines
- Commented-out code that snuck through
- Out-of-scope edits (you went to fix X, ended up touching Y — was that intentional?)
- Files you forgot you edited
- Inverted boolean logic (the dread "if `!` got dropped during a refactor")

Hour-old you is not the same engineer as five-minutes-old you. The diff view is the cheapest cognitive fresh-eyes you can buy.

### 3. A stable URL anchor for everything downstream

Once a PR is merged, its URL is permanent. That URL is referenced by:

- **Changelog entries** ([[Changelog-Conventions]] — see "Linking to commits and PRs" once we add it).
- **Issue threads** that closed the PR.
- **Cross-repo references** in submodule bumps.
- **The (future) live KPI dashboard** ([[Explore-GitHub-API-for-Live-KPIs]]) — "PRs merged this week" is a more legible momentum number for an external reader than "raw commit count".
- **Docs** that need to point to "this is when we changed X."

Direct-pushed commits also have URLs, but commit URLs are atomic — they don't aggregate the *unit* of work, they show one of N commits. PR URLs are the unit. That's the difference between citing "page 47" and citing "Chapter 3."

### 4. CI gate by default

If we have CI configured (lint, typecheck, build), it runs on PR open. Direct pushes to main can land broken work; PR-with-CI can't. Even solo, that's a free guardrail. Lossless doesn't have heavy CI yet on most plugin repos, but the day we do, the PR habit means the CI is automatically meaningful.

### 5. AI-co-developer audit trail

This is the quietly important one. When Claude Code or Cursor or Pi opens a PR (or pushes to a branch the human then opens a PR for), the PR thread becomes:

- The decision log: "we tried X, it didn't work, we did Y"
- The provenance log: who/what touched what
- The reviewable artifact: a future you, or a future agent, can read the PR thread and reconstruct the reasoning without spelunking commit messages

This composes especially well with the `Co-Authored-By: Claude ...` trailer convention. The PR body can summarize "this PR was developed in collaboration with Claude Opus 4.7 over 3 sessions; key decisions are in commit messages and the thread below." That's exactly the AI-augmented narrative we want to surface in the live KPI dashboard.

## The tiny-commits tension, resolved

The pattern that resolves it:

| Phase | Commit style | Where it lives |
|---|---|---|
| Developing | **Tiny, frequent, WIP-friendly** — checkpoint anything that compiles | Feature branch |
| Shipping | **One coherent unit, well-titled** | Main, via squash-merge of the PR |

The branch keeps the granular history (the PR's "Commits" tab is the audit trail). Main keeps the narrative.

**You don't have to change anything about how you develop.** You just stop pushing those WIP commits directly to main. You push them to a branch, then squash-merge the PR.

## Minimum viable solo PR practice

For any unit of work bigger than a typo:

1. **Branch off main.** `git checkout -b <topic-name>` — name it for the unit, e.g. `rebrand-to-metafetch`, `settings-section-collapsibles`.
2. **Commit granularly during development.** Same instinct you have now. Don't change it.
3. **When the unit is done**, push the branch and open a PR: `gh pr create --fill` (auto-fills title/body from the latest commit message).
4. **Self-review the unified diff.** GitHub's "Files changed" view; read it like a stranger.
5. **Squash-merge.** GitHub UI → "Squash and merge". Set the squash commit message to a clean unit-level summary (this becomes the main-branch line item).
6. **Delete the branch** (GitHub auto-deletes if you turn that setting on).
7. **Reference the PR URL in the changelog entry** for the unit (per the new "Linking to commits and PRs" section in `changelog-conventions`).

Total overhead vs. direct push: roughly **30 seconds per unit** if you have `gh` aliased and auto-delete-branch enabled.

## When to skip the PR (honest list)

Don't make this a religion. Direct-push to main is fine for:

- Single-file typo fixes
- README tweaks below the fold
- Lockfile-only changes (`pnpm-lock.yaml` after a dependency add)
- Reverting something you literally just pushed
- Hotfixes when CI is broken and you need to unblock yourself
- Pure config tweaks that can't realistically break anything

The heuristic: **would a stranger want to read this as a unit?** If yes → PR. If it's just plumbing → push and move on.

## Branch-protection settings worth flipping (solo defaults)

We're solo, so don't require reviewers. But these are net-positive even for one person:

- **Require linear history** (no merge commits — squash or rebase only). Keeps `git log --oneline` actually readable.
- **Auto-delete branches on merge.** Removes one piece of cleanup overhead.
- **Block force pushes to main** (force on branches is fine). Protects against the worst kind of accident.
- **Required status checks** (when CI exists). Blocks merging on red.

Skip:

- Required reviewers (we're solo).
- Required signed commits (use it if you want, but optional).
- Restrict push to main entirely (overkill for solo — the PR habit + linear history is enough discipline).

## Tooling and friction reducers

The whole thing only works if it stays low-friction. Specifically:

- **`gh pr create --fill`** auto-fills title/body from the latest commit message. Means good commit messages on the branch generate the PR for free.
- **A repo-level alias or `pnpm` script** like `pnpm ship` that runs: `git push -u origin HEAD && gh pr create --fill --web`. One command from "my work is done" to "PR open in browser."
- **GitHub setting: "Default to PR title and description for the squash commit message"** — keeps main-branch lines consistent with what readers see in the PR.
- **A Claude Code slash command** (or skill instruction) like `/ship` that:
  1. Creates a branch named from the work
  2. Commits any pending changes
  3. Pushes
  4. Opens the PR with a generated title/body summarizing the unit
  5. Leaves the squash-merge as a manual gate (we never auto-merge our own work)

The `/ship` flow turns this from "ceremony" into "a single command at the end of work."

## How this composes with other Lossless practices

- **Changelog-First Development** — PRs make `changelog/` entries dramatically easier to write because the PR is already the unit. Title → entry title; PR body → entry body draft; PR URL → the link in the entry.
- **Linking to commits and PRs** in changelogs (proposed for `changelog-conventions`) — when work landed via PR, link the PR; otherwise the commit. PRs become the preferred citation form.
- **Live KPI dashboard** ([[Explore-GitHub-API-for-Live-KPIs]]) — "PRs merged" is the legible momentum number for the public face. "Commits" is the engine-room number.
- **AI co-developer audit** — every PR with `Co-Authored-By: Claude ...` is a public datapoint about the AI-augmented practice. The dashboard can count these.
- **Pseudomonorepo roll-up** — when a parent splash aggregates a child's changelog, PR URLs stay valid (they're absolute), commit URLs do too. No special handling needed.

## Tradeoffs to be honest about

- **Friction tax.** Even 30 seconds per unit is overhead. On days with 60+ commits, the overhead is bounded by *units* (maybe 5–10), not commits — but it's still nonzero. Worth it; not free.
- **The "self-review of self" feels weird for a few weeks.** It stops feeling weird once the diff catches a real bug.
- **Branch sprawl** if we don't enable auto-delete. One-time setting.
- **WIP commits in the PR's history are a little embarrassing** ("WIP", "fix typo", "still WIP"). They're the dev journal — only visible if someone clicks into the Commits tab. Most people won't. The squash-merge presents the clean face.
- **Public-vs-private repo asymmetry.** Public repos are obviously where PRs pay externally; private repos still get the squash-merge + self-review benefits but the audit-trail value is internal-only. Still net-positive.
- **Hotfix override.** When something is on fire, the PR step is friction that hurts. Document the carve-out (the "skip the PR" list above) so we don't beat ourselves up about it.

## Open questions

1. **Default branch name.** `main` (current default for new repos) or keep `master` for older ones? Worth normalizing as a separate small chore.
2. **Squash-merge as the *enforced* default vs. opt-in?** Vote: enforced via branch protection on new repos, manual on legacy. Linear history is easier to read whichever way.
3. **`/ship` slash command — write it for Claude Code, or just bash alias?** Probably the alias is enough; the slash command pays only when AI is doing the wrap-up.
4. **PR templates per repo?** Probably yes for the plugin repos (a 4-line template: *what shipped / why / how to test / linked changelog entry*). Probably no for the content/docs repos.
5. **Do we want to retroactively turn on these branch-protection settings across all 9+ existing repos?** Or only new ones going forward?
6. **Friction-vs-discipline tipping point.** If `pnpm ship` is one command, the practice is sustainable. If it ever becomes a 4-step ritual, it dies. We should periodically audit the friction.
7. **Changelog entry — written before the PR is opened, after it's merged, or in the PR body and lifted out post-merge?** Probably option 3: write the prose in the PR body, lift to `changelog/` after squash-merge with the merged-PR URL filled in.

## Practical next steps if we adopt this

1. Pick **one repo** to pilot on for two weeks. Recommendation: `metafetch` (it's the most active right now and the rebrand work just landed in three commits that would have been one clean PR).
2. Add the `pnpm ship` alias (or repo-level npm script) — the friction reducer is the keystone.
3. Update branch protection on that one repo (linear history, auto-delete branches, no force push to main).
4. Add the "Linking to commits and PRs" section to `changelog-conventions` skill.
5. After two weeks, retrospect: did it pay? Did it cost what we expected? If yes, roll out to the rest.
