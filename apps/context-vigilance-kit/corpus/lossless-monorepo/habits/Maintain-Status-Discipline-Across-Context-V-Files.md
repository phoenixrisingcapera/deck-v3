---
title: Maintain status discipline across context-v files
lede: 'A periodic sweep promoting `status` to match reality, so an agent landing cold
  can read `status: Draft` and trust that nothing has happened.'
date_created: 2026-05-16
date_modified: 2026-05-16
semantic_version: 0.1.0.0
authors:
- Michael Staton
augmented_with: Claude Code on Claude Opus 4.7 (1M context)
status: Active
applies_to: every Lossless Group repo that maintains a context-v/ directory (root,
  pseudomonorepo children, leaf projects, client-sites)
tags:
- Habit
- Context-Vigilance
- Status-Discipline
- Periodic-Sweep
- Anti-Stale-Drafts
- Plan-Lifecycle
site_uuid: bd8e0c6b-4d19-4bf8-92bb-b81303f74013
hex_code: yi3lu8
date_authored_initial_draft: 2026-05-16
date_authored_current_draft: 2026-05-16
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: habits/Maintain-Status-Discipline-Across-Context-V-Files.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/habits/Maintain-Status-Discipline-Across-Context-V-Files.md"
---

# Maintain status discipline across context-v files

> Repo-level habit. Generic to every repo that has a `context-v/`. Closely paired with the [`context-vigilance` skill](../agent-skills/context-vigilance/SKILL.md) — specifically [`references/status-discipline.md`](../agent-skills/context-vigilance/references/status-discipline.md), which is the load-bearing reference this habit operationalizes.

## Why this exists

`context-v/` directories accumulate plans, specs, explorations, and prompts over weeks and months. Without periodic attention, every doc stays at its authored-day default (`Draft`) forever — even after the work has shipped, been deferred, or been replaced.

An agent landing cold can't tell:

- What's already shipped (and therefore historical, not live work).
- What's in flight (and therefore needs continued attention).
- What was deliberately deferred (and therefore *not* a gap).
- What's stale and should be retired.

This breaks the "loadable docs" contract — `context-v/` exists so future agents and humans can land cold and orient quickly. Stale `Draft` everywhere defeats that.

The remedy: **a periodic sweep that promotes status to match reality.** This habit codifies when to run the sweep, how to scan the directory efficiently, what to write, and how to commit.

## When to run the sweep

Trigger conditions, in rough order of how often they fire:

1. **Before authoring a new plan.** "What's already live in this directory?" is unanswerable when half the plans falsely claim `Draft`. Sweep first; author after.
2. **After a coherent chunk of work lands.** When you've just shipped a phase (Phase A, Phase A+, etc.), the relevant plan(s) and any cascade docs they touch deserve a status update in the same commit-or-close-to-it as the ship.
3. **Before a state-of-the-union assessment.** When the user asks "where are we?" — sweep first so the assessment isn't built on stale signals.
4. **When you find a single drifted doc during unrelated work.** Per the drift policy, **don't auto-fix mid-session.** Surface, note, defer until the next deliberate sweep.

## The sweep procedure

For a given `<repo>/context-v/` directory:

### Step 1 — Inventory the current declared status

```bash
cd <repo>/context-v
for f in plans/*.md explorations/*.md specs/*.md prompts/*.md; do
  [ -f "$f" ] || continue
  printf "%-78s  " "$(basename "$f" .md)"
  grep -m1 "^status:" "$f" | sed 's/^status: *//'
done
```

This gives you the snapshot: filename + declared status, one row per file.

### Step 2 — For each file whose declared status looks wrong, gather ground truth

The declared status is wrong if any of these is true:

- The plan describes work that has obviously been done (cross-reference: the changelog has entries about it; commits exist; the files it predicted now exist on disk).
- The plan describes work explicitly deferred in a sibling plan (cross-reference: another plan says "this is deferred to phase X" or "we won't do this until Y").
- The plan describes work that's been replaced by a newer plan (cross-reference: a successor plan says "supersedes this" or covers the same ground with a fresher framing).
- The plan describes work that started but didn't finish (cross-reference: some artifacts exist on disk, others don't).

**Read the plan's body.** Don't rely on title alone. The Remaining-work section (if present) and the cross-references at the bottom usually tell you ground truth in two minutes.

### Step 3 — For each file, apply the right promotion

Per the [status-discipline reference](../agent-skills/context-vigilance/references/status-discipline.md), promote according to ground truth:

| If reality is… | Set status to | And ensure |
|---|---|---|
| Everything shipped | `Shipped` | `date_first_published:` set; optional `post_ship_note:` |
| Some shipped, some didn't | `Partially-Shipped` | `date_first_published:` set; `## Remaining work (as of YYYY-MM-DD)` section appended to body |
| Explicitly held | `Deferred` | `deferral_note:` set explaining the reason |
| Replaced by newer doc | `Superseded` | `superseded_by:` set on this doc; `supersedes:` set on the successor |
| Old, no longer load-bearing | `Stale` or `Archived` | optional `archive_note:` |

In every case: **bump `date_last_updated`** (or `date_modified` for older-style frontmatter) on the same edit.

### Step 4 — Verify the resulting picture

Re-run the Step 1 inventory. The output should now distinguish live work from done work at a glance:

```
Plan-Name-A                                                                     Shipped
Plan-Name-B                                                                     Partially-Shipped
Plan-Name-C                                                                     Deferred
Plan-Name-D                                                                     Draft           ← genuinely new, hasn't started
```

If two rows still look indistinguishable when their realities differ, the status values aren't doing their job — either add a missing companion field, or sharpen the body's Remaining-work section so the difference is visible.

### Step 5 — Commit shape

One commit per repo touched. Subject:

```
status-sweep(context-v): bring N plans to status-of-record as of YYYY-MM-DD
```

Body: list the promotions one per line — `Plan-Name-A: Draft → Shipped`, `Plan-Name-B: Draft → Partially-Shipped`, etc. — and reference the originating sweep trigger (e.g. "trigger: state-of-the-union assessment requested by user", or "trigger: Phase A+ shipped, propagating to plan-of-record").

If the sweep also produced a fresh inventory exploration (e.g. `Plans-Inventory-YYYY-MM-DD.md`), include that file in the same commit.

## What the sweep should NOT do

- **Don't normalize frontmatter shape.** A plan with older-style `date_modified` / `semantic_version` frontmatter and a newer plan with `date_last_updated` / `at_semantic_version` both work; **don't** rewrite older plans to the new shape during a sweep. Surface the inconsistency separately if it matters; address as a deliberate frontmatter migration, not a side effect of a status sweep.
- **Don't rewrite body content.** A status sweep updates frontmatter and appends/maintains the Remaining-work section. It does NOT edit the plan's narrative, scope, decisions, or cross-references. Those are separate concerns.
- **Don't bump semver.** A status promotion is a state-of-the-world change, not a content change. The version stays.
- **Don't rewrite historical docs that document past thinking.** Per `context-vigilance` discipline, historical narrative (explorations from prior sessions, plans from prior phases) capture past framing. If the framing later sharpened, add a one-line correction note at the top pointing at the corrected anchor — don't rewrite the body.
- **Don't sweep someone else's plans without confirming the ship state.** Authorship matters; if you're not sure something shipped, ask before promoting it.

## Anti-patterns this habit prevents

- **`Draft` forever** across an entire directory.
- **`Shipped` claims with no anchor** (`date_first_published` missing).
- **`Partially-Shipped` with no enumeration** of what's done vs. left.
- **`Deferred` with no reason.**
- **Status drift introduced as a side effect of unrelated work** (violates the broader `context-vigilance` drift policy).

## Related

- [`context-v/agent-skills/context-vigilance/SKILL.md`](../agent-skills/context-vigilance/SKILL.md) — the broader framework this habit operates within.
- [`context-v/agent-skills/context-vigilance/references/status-discipline.md`](../agent-skills/context-vigilance/references/status-discipline.md) — the canonical values, companion-field rules, and `## Remaining work` section convention.
- [`context-v/agent-skills/context-vigilance/references/frontmatter-spec.md`](../agent-skills/context-vigilance/references/frontmatter-spec.md) — the `status:` field definition + companion-field summary.
- [`context-v/agent-skills/changelog-conventions/SKILL.md`](../agent-skills/changelog-conventions/SKILL.md) — paired discipline. Every `Shipped` promotion should map to a real changelog entry the agent or human can cite.
- [`context-v/agent-skills/pseudomonorepos/SKILL.md`](../agent-skills/pseudomonorepos/SKILL.md) — tree-walking discipline. In a pseudomonorepo, sweep at every level that carries a `context-v/`, not just the root.
