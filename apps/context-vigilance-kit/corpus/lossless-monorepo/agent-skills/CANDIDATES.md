---
name: skill-candidates
description: Running backlog of potential future skills for the Lossless Group. Reference
  only - not a loadable skill.
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/CANDIDATES.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/CANDIDATES.md"
---

# Skill Candidates — Running List

A backlog of potential skills, captured as they surface. Not commitments. Not roadmap. Just **so good ideas don't fall on the floor.**

When a candidate ships, move it to the README's Skills table and add a status update here pointing to it.

> **How this list is maintained:** Update freely as ideas come up. Each entry should be brief enough to fit in one head (one head with ADHD), specific enough that a future-you remembers the trigger, and honest about whether it's a real skill or just a tag for a thing.

## What counts as a candidate

Skills come from two directions, and both are welcome here:

- **Third-party / established** — a package, spec, or tool with its own docs (e.g. an LFM plugin, an Astro integration, an Obsidian convention). The skill wraps it: when to reach for it, how we use it, the gotchas we've hit.
- **Homegrown** — patterns we coined while working together (`pseudomonorepos`, `context-vigilance`, the 5-phase loop). These start as a name we keep saying out loud, get jotted here, and only earn a `SKILL.md` once the pattern has stabilized.

Developing them all at once would be a nightmare and would freeze conventions that are still moving. The motion we respect is **experimenting → codifying → standardizing**: live with a pattern long enough to know its shape, write it down once it stops shifting, promote it to a skill once it's worth loading into every session. CANDIDATES.md is the holding pen for everything in the first two stages — so good ideas don't fall on the floor while they're still maturing.

---

## Promoted to skills (✅ shipped)

| Skill | Where | Shipped |
|---|---|---|
| `context-vigilance` | [`./context-vigilance/`](./context-vigilance/) | 2026-05-04 |
| `astro-knots` | [`./astro-knots/`](./astro-knots/) | 2026-05-04 |
| `pseudomonorepos` | [`./pseudomonorepos/`](./pseudomonorepos/) | 2026-05-04 |
| `changelog-conventions` | [`./changelog-conventions/`](./changelog-conventions/) | 2026-05-04 |
| `theme-system` | [`./theme-system/`](./theme-system/) | 2026-05-04 (scaffold) |
| `git-conventions` | [`./git-conventions/`](./git-conventions/) | 2026-05-04 (scaffold) |

---

## Active candidates

### 🚧 `lfm` — Lossless Flavored Markdown

- **Trigger:** working with `.md` content for any Astro Knots site, or considering MDX
- **Source:** [`@lossless-group/lfm`](https://jsr.io/@lossless-group/lfm) — first true Lossless package, polyglot extended-markdown → component pipeline
- **Why now:** package is in production; pattern of "any syntax can trigger a component" needs to be loadable by agents working on content
- **Effort:** medium-high. Needs a survey of the package's actual capabilities + reference patterns from existing sites
- **Currently stubbed in:** `astro-knots/SKILL.md`, `astro-knots/references/ecosystem.md`

### 🚧 `lossless-loop` — the 5-phase lifecycle

- **Trigger:** any meaningful unit of work in an active project
- **Source:** the Start → Progress → Reflect → Publish → Market diagram already in `pseudomonorepos/references/lifecycle-workflow.md`
- **Why now:** the spine that connects context-vigilance + pseudomonorepos + astro-knots
- **Effort:** medium. Needs templates for changelog entries, "publish" doc patterns, and "market" routing rules per Astro Knots site
- **Currently stubbed in:** `pseudomonorepos/references/lifecycle-workflow.md`

### `fill-enrich-components-w-data`
- the follow-up to `crawl-fetch-ingest` 
- needs to have context on how to enrich components with data from the crawled and fetched sites

### 🚧 `maintain-design-systems` — the design-system + component-library *view* per project

- **Trigger:** starting any new Astro Knots site (or shell, or splash), authoring a new visual primitive (icon family, chip variants, button states, badge styles), refactoring scattered component-decisions into a coherent system, or onboarding a new collaborator (developer / agent / end client) who needs to know "what already exists and what are the options for X"
- **Source:** the discipline we already half-practice across the Astro Knots sites — sites with brand-recognizable visual identity (`calmstorm-decks`, `chroma-decks`, `lfm/splash`, `memopop-site`) all benefit from this even where it's not yet codified. The `/dev/icons` design-review workbench pattern in `dididecks-ai/apps/deck-shell/` (2026-05-17) is the first deliberately-permanent surface of this kind in the tree
- **What it would cover:**
  - The **two-surface contract**: `DESIGN.md` documents the *chosen* tokens (covered by the existing `maintain-design-md` skill); a `/dev/*` workbench renders *candidates and current state* side-by-side at multiple sizes / on multiple backgrounds / inside the real composed UI context they live in
  - The **component-library view** — every project's `context-v/sitemap/components/` mini-specs with `composes:` / `composed_by:` cross-references so an agent or human can answer "what components exist, what does each look like, what's available for accomplishing X" without grepping the source
  - The **alternates-as-design-history convention** — unchosen candidates preserved in `alternates/` directories, importable but not used in production, so the decision context stays legible to anyone reading the codebase cold
  - The **update rigor** — what triggers a sweep (new visual primitive, new component family, refactor that changes a token's resolved value, a `theme-system` mode addition), and the discipline of keeping the DESIGN.md + sitemap + `/dev/*` workbench in sync as the project evolves
  - The **multi-audience legibility** — developers reading the source, agents grounding decisions in actual current state, end clients seeing "what they're paying for" in a single surface
- **Why now:** sibling to `maintain-splash-pages` in spirit — every important project benefits from the same discipline applied differently. The pattern is now concrete enough to name (the `/dev/icons` route + the alternates archive + the sitemap mini-specs together model the practice). The DESIGN.md skill alone is the documented-contract slice; this candidate is the broader living-system + library-view discipline that DESIGN.md is one ingredient of
- **Effort:** medium. Needs a survey of what the existing Astro Knots sites actually do today (where DESIGN.md exists, where component libraries are browsable, where they aren't), then codification of the pattern as it converges
- **Relationship to existing skills:**
  - `maintain-design-md` — sub-skill for the DESIGN.md file format. Stays canonical for *that* file; this candidate is the broader practice that DESIGN.md is one artifact of
  - `theme-system` — orthogonal but related; the token system this skill documents how to maintain
  - `maintain-splash-pages` — sibling in shape: same "every project benefits from the discipline" framing
  - `astro-knots` / `astro-component-patterns` (candidate above) — overlaps with the component-library-view dimension; this candidate may absorb or be absorbed by `astro-component-patterns` once both converge
- **Open question:** is this one skill, or two? "Maintain DESIGN.md" + "maintain a `/dev/*` workbench + alternates archive + sitemap mini-specs" could split, but the audiences are the same (developer + agent + client) and the rigor reinforces itself when practiced together. Lean toward one skill with multiple references
- **Currently stubbed in:** `ai-labs/dididecks-ai/context-v/sitemap/routes/dev-icons.md` carries the project-local version of the discipline; promotion to a cross-project skill is deferred until a second project validates the pattern
- **Confirmed:** 2026-05-17

---

## Candidates from earlier conversations

### 💭 `lossless-house-style` — voice & formatting

- **Trigger:** writing prose anywhere — doc, README, essay, exploration
- **Source:** raised when discussing skill ideas tailored to the workspace
- **Why someday:** consistent voice across `lossless.group`, READMEs, and `context-v/` documents matters once the team scales beyond one writer
- **Effort:** medium. Needs explicit articulation of voice (the user's existing writing is the corpus)

### 💭 `monorepo-nav` — quick orientation

- **Trigger:** starting a session in `lossless-monorepo` from cold
- **Source:** raised after walking the tree the first time
- **Why someday:** every agent session starts from zero; a fast orientation map saves minutes
- **Effort:** low-medium. Mostly captured by `pseudomonorepos/references/the-tree.md` already, but a more agent-focused "what is this repo" surface could exist
- **Note:** may not deserve its own skill — could fold into `pseudomonorepos`

### 💭 `obsidian-integration` — the substrate layer

- **Trigger:** working in a `context-v/` that's symlinked into an Obsidian vault, or setting one up
- **Source:** mentioned in `context-vigilance/references/philosophy.md` and `frontmatter-spec.md`
- **Why someday:** tag conventions, backlinks, frontmatter aliases, vault symlinks, plugin choices all have battle-earned answers
- **Effort:** medium. Lots of accumulated knowledge across `content-farm/`

### 💭 `submodule-hygiene` — wrangling the inevitable pain

- **Trigger:** any time a submodule is detached, missing, or mis-pinned in the tree
- **Source:** mentioned in `pseudomonorepos/references/anatomy.md` ("foot-gun")
- **Why someday:** existing scripts (`reattach-all-submodule-remotes.sh`, etc.) embody the workflow; agents could invoke them with the right context
- **Effort:** low. Mostly wrapping existing scripts in a skill that knows when to reach for them
- **Confirmed:** 2026-05-03

### 💭 `astro-component-patterns` — the conventions that compound across sites

- **Trigger:** building, refactoring, or scaffolding Astro components in any Astro Knots site
- **Source:** ~10+ Astro Knots sites with accumulated shared patterns (layouts, content collection rendering, image handling, view transitions, partial hydration choices)
- **Why someday:** each new site ships faster than the last because patterns compound — making those patterns explicit means an agent can apply them on day one of a new site instead of having to re-derive
- **Effort:** medium-high. Requires surveying current sites for what's converged vs. still divergent
- **Note:** could be its own skill *or* a sub-tree of `astro-knots/references/`. Probably its own skill once `astro-knots` proves out.
- **Confirmed:** 2026-05-03

### ~~💭 `changelog-conventions`~~ — ~~the Progress + Publish format~~

**Shipped 2026-05-04** — lives at [`./changelog-conventions/`](./changelog-conventions/). First entry is `changelog/2026-05-04_01.md`.

---

## New candidates from the studies (2026-05-03)

### 💭 `study-pattern` — learning-via-pseudomonorepo

- **Trigger:** user wants to deeply understand an external project, standard, or system
- **Source:** the `ai-labs/studies/` pseudomonorepos (`open-specs-and-standards/`, `memory-layers-for-agents/`)
- **Why someday:** the *form* of these studies is itself a reusable pattern — pseudomonorepo + submodules of subjects + `profiles/` + `inquiry/` + comparative blueprints
- **The behavioral core would be:** "create a study, add subjects as submodules, profile each, surface comparative insight, eventually graduate findings to blueprints in a real project"
- **Effort:** low-medium once the user's studies converge on the working pattern
- **Open question:** does this deserve its own skill, or is it a chapter of `pseudomonorepos`?

### 💭 `profiles-doctype` — "what is this thing and how does it work?"

- **Trigger:** answering "what is X and how does it work on the inside?" for an external repo, library, or system
- **Source:** `studies/open-specs-and-standards/context-v/profiles/Profile__OpenSpec.md` (and siblings)
- **Why someday:** profiles are a recurring need across studies and across projects (any time a dependency's internals matter, a profile is useful)
- **Note:** this is more a **doc-type extension** to `context-vigilance` than a free-standing skill — could be a new optional folder convention (`profiles/`) or a sub-genre of `blueprints/`
- **Open question:** promote `profiles/` to the canonical folder set, or document it as a project-specific pattern?

### 💭 `inquiry-vs-explorations` — quick reminder

- **Trigger:** user calls a folder `inquiry/` instead of `explorations/`
- **Source:** observation that the studies use `inquiry/` for the same cognitive mode as `explorations/`
- **Why someday:** worth a one-paragraph reminder noting they're sister conventions
- **Note:** this is probably a **reminder file** in `context-vigilance/`, not a skill
- **Action item:** consider adding to `context-vigilance/references/doc-type-guide.md` once the user decides whether to canonicalize one or accept both

---

## Patterns observed but not yet promoted

Things that *might* deserve to be skills — or might just be one-line reminders. Watching:

- **Refactor debt logging** — the pattern of "ship without searching, leave a marker" generalizes beyond pseudomonorepos. Could be a meta-skill or just a paragraph reused across skills.
- **TBD markers in skills** — `// TBD` notation as a working memory format for incomplete docs. Worth formalizing?
- **Studies with `.gitmodules` of subjects** — repeats the pseudomonorepo pattern at the study level. The recursion may have a name.
- **Comparative blueprint pattern** — "X compared to Y compared to Z, here's where each shines" — emerging from the open-specs study. Doc-type? Skill? Reminder?

---

## Maintenance

When something here gets shipped:

1. Move it to the **Promoted** table at top
2. Update the README skills table
3. Update `astro-knots/references/ecosystem.md`'s skills roadmap
4. Add a brief retro note here (`shipped DATE — file lives at PATH`)

When a candidate is abandoned: strike it through with a `~~` and a one-line reason. Don't delete — the dead-end record is itself useful.
