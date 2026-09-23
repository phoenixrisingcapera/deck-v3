---
name: lossless-skills-readme
description: Overview of the Lossless Skills collection - installation instructions,
  skill status, and contributing guidelines. Reference only.
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/README.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/README.md"
---

# Lossless Skills

The Lossless Group's agent skills collection — across projects and people.

A shared library of [Agent Skills](https://agentskills.io/specification) used by Lossless team members and AI coding agents on Lossless projects. Skills here are tool-agnostic: they work with [pi-coding-agent](https://github.com/badlogic/pi-mono), Claude Code, OpenAI Codex, and anything else that follows the Agent Skills standard.

## Built in public

This repo is part of [The Lossless Group's](https://www.lossless.group) **Lost in Public** practice: developing methods, tooling, and institutional knowledge openly so others can adopt, adapt, critique, and contribute. Expect frequent commits, occasional churn, and skills that evolve as the team's real workflows reveal what works.

If a skill here helps you, take it. If you find a sharper way to express it, open a PR. If you disagree with a convention, open an issue — we'd rather argue in public than silently diverge.

## Skills

| Skill | Directory | What it covers — and why we care |
|---|---|---|
| **Context Vigilance** | [`context-vigilance/`](./context-vigilance/) | Framework for managing `context-v/` directories — directory roles (specs / prompts / blueprints / reminders / explorations / issues), four-part `epoch.major.minor.patch` versioning, YAML frontmatter, wikilinks. AI co-development drowns in unstructured context; this is the team's working contribution to making thinking durable, retrievable, and version-aware across humans and agents. See <https://www.lossless.group/projects/gallery/context-vigilance>. |
| **Pseudomonorepos** | [`pseudomonorepos/`](./pseudomonorepos/) | Coined Lossless pattern: parent repos that aggregate child repos (often submodules) primarily to host a parent-level `context-v/`. Encodes a *search-before-create* discipline and a tree-walking routine — without it, the same idea gets started in three places and the team loses to itself. |
| **Study Repos First** | [`study-repos-first/`](./study-repos-first/) | Discipline of pinning a curated collection of upstream repos (a *study*) around a domain question *before* designing or coding in that domain. Encodes "read upstream code, don't paraphrase from training data" — agents reach for plausible-but-stale conventions when real prior art is one `cd` away. This enforces the search-first habit for conventions, schemas, and protocols, and the setup mechanics for a study (named question, pinned submodules, promote-when-grows). |
| **Astro Knots** | [`astro-knots/`](./astro-knots/) | Tech hierarchy (HTML / CSS first, then vanilla JS, then a small package, then a framework), approved frameworks (Astro, Svelte, GSAP, Reveal), and hard prohibitions (React, JSX, Angular) for the family of ~10+ Astro sites. Without it, agents reach for `npm install` reflexively and the sites drift toward generic React-shaped JAMstack. See <https://www.lossless.group/projects/gallery/astro-knots>. |
| **Changelog Conventions** | [`changelog-conventions/`](./changelog-conventions/) | How to write `changelog/` entries — frontmatter (`publish: true`, `lede`, ISO dates), `YYYY-MM-DD_NN.md` filenames, `releases/` subfolder for product-style projects, show-don't-enforce ethos. "Changelog First Development" is the team's working theory: a fast-moving public changelog signals momentum to clients, contributors, and your future self. |
| **Git Conventions** | [`git-conventions/`](./git-conventions/) | Commit message conventions — structured headers with action verbs and effort groupings, paragraph-spaced bodies that explain impact before implementation, "Also included" riders for minor changes. Conventional Commits is too narrow; this captures both the change and the reason in a way that reads sensibly a year later. The same four-audience cascade `changelog-conventions` codifies for README / changelog / release narratives applies here: commit messages surface publicly via the GitHub commits view and the parent pseudomonorepo's rolled-up feed, so the header lands for the general audience and the body tail carries SHAs and Co-Authored-By for the internal team. |
| **gh CLI · Projects & Tasks Conventions** | [`gh-cli-projects-tasks-conventions/`](./gh-cli-projects-tasks-conventions/) | How the team uses `gh project` (GitHub Projects v2) to manage tasks across the pseudomonorepo tree. Premature on purpose — only two conventions exist today, codified now so they don't drift while the rest emerge: (1) compose with `pseudomonorepos` to resolve the repo a context-v file actually lives in (a path in the parent monorepo's working tree may belong to a submodule on GitHub, and a parent-monorepo URL 404s); (2) task bodies that reference `context-v/` files are *primarily the clickable GitHub URL* to the file in its own repo on the right branch tier, not a paraphrased summary. Ships a shell recipe for building the URL correctly plus `item-create` / `item-edit` / bulk-from-spec / field-edit examples. Open seams (status discipline, priority discipline, project layout, custom fields) are listed for fill-in as use cases write them. |
| **Theme System** | [`theme-system/`](./theme-system/) | Theme and mode architecture for Astro Knots sites: two-tier token system, three-mode contract (light / dark / vibrant), `theme.css` organization, design-system conventions. Without a shared system every site re-invents tokens, and mode toggles break in ways that are hard to debug after the fact. |
| **Maintain DESIGN.md** | [`maintain-design-md/`](./maintain-design-md/) | How to author and maintain a `DESIGN.md` file at the project root following [Google Stitch's open spec](https://github.com/google-labs-code/design.md) — frontmatter token groups (colors, typography, rounded, spacing, components) plus the eight canonical prose sections, the maintenance triggers (what code changes should bounce back into the doc), the runtime-CSS-is-source-of-truth discipline, and the precedent for off-spec extensions like the `imagery:` block. The agent-readable contract for a project's visual identity. Composes with `theme-system` (architecture) and `generate-consistent-og-images` (which reads the `imagery:` extension). |
| **Deck Iteration Workflow** | [`deck-iteration-workflow/`](./deck-iteration-workflow/) | Workflow for slides-only Astro sites (fundraise decks, conference talks): variant management, structured iteration cycle, alignment with the `calmstorm-decks` project patterns. Decks rot fast and agents over-engineer them; this keeps generation cheap and revision discipline tight when timelines are real. |
| **Crawl, Fetch, Ingest** | [`crawl-fetch-ingest/`](./crawl-fetch-ingest/) | The team's workflow for filling in team and portfolio metadata for VC firms and the operating companies they back: crawl a firm's site, fetch structured data + brand assets for people and companies referenced in a deck/PDF, ingest as canonical `.md` files with YAML frontmatter. Supports two starting anchors — **firm-anchored** (one VC → its team → its portfolio → portco CEOs) and **company-anchored** (one operating company → its backer firms → each backer's team + portfolio, stopping there) via the [`investor-credibility-ingest`](./crawl-fetch-ingest/routines/investor-credibility-ingest.md) routine, for fundraise-deck credibility cards. Encodes the four-checkpoint cascade, the cross-tool fallback pattern (Firecrawl → Tavily → OpenGraph.io), the global-cache-per-firm convention so the same firm's data is reused across multiple decks/memos. |
| **OpenGraph, Share, SEO & GEO** | [`open-graph-share-seo-geo/`](./open-graph-share-seo-geo/) | Rules for reliable share-preview unfurls in iMessage, WhatsApp, Slack, Discord, LinkedIn, X — plus traditional SEO and Generative Engine Optimization (GEO). Encodes the JPEG-over-WebP rule, the CDN-not-`/public` rule, and the ImageKit content-negotiation gotcha (`og:image:type` must match the bytes the unfurler actually receives, not the URL extension) that cost us a debugging cycle. |
| **Generate Consistent OG Images** | [`generate-consistent-og-images/`](./generate-consistent-og-images/) | How to generate share-imagery (banners, portraits, squares, tall WhatsApp/iMessage cards) for any Lossless site so the resulting images form a coherent visual family — via two coexisting techniques, picked per project or per format. **Ideogram illustration** locks every parameter on the v3 request except `prompt` and `aspect_ratio`, with the rest (style reference, color palette weights, negative prompt, seed, rendering speed) living in the project's `DESIGN.md` `imagery:` block; encodes the empty-space-as-first-class-subject prompt structure that defeats the "subject grows up into the SVG overlay zone" failure mode, at the cost of stochastic quality across runs. **Hero rasterization** turns the project's own hero/specimen component into the OG image directly via macOS's `qlmanage`+`sips` (or a Playwright screenshot) — deterministic, and a better fit when the hero already carries real data/copy that illustration would throw away. WhatsApp / iMessage chat-preview is the primary target either way. |
| **Lossless Flavored Markdown** | [`lossless-flavored-markdown/`](./lossless-flavored-markdown/) | Polyglot extended-markdown spec — user-configured *syntax-triggers* drive a render pipeline in a frontend framework, giving plain `.md` files MDX-class power without MDX's JSX-shaped lock-in. Implemented as `@lossless-group/lfm` on [JSR](https://jsr.io); source lives in `astro-knots/`. Use when authoring or rendering content, building components routed from markdown, or co-developing the package itself. |
| **Maintain Splash Pages** *(Draft)* | [`maintain-splash-pages/`](./maintain-splash-pages/) | The repo-level splash pattern: small Astro sites at `<repo>/splash/` that ship to GitHub Pages on push to `main`, render the repo's `changelog/` + `context-v/` alongside curated marketing copy, and stay isolated from any package the repo also publishes. Codifies the proven shape across three reference implementations (`memopop-site`, `content-farm/splash`, `lfm/splash`) and the package-isolation discipline that keeps splashes safe to add to repos that also publish to JSR / npm. |
| **Maintain Filemap** *(loop)* | [`maintain-filemap/`](./maintain-filemap/) | Loop discipline for keeping a `FILEMAP.md` at the root of each Lossless repo current with the actual on-disk tree. Each FILEMAP has two parts: a hand-authored **curator preface** (what each top-level directory IS — purpose, ownership, conventions; edited rarely) and a **generated `tree -L 3` block** spliced between `<!-- TREE-START -->` / `<!-- TREE-END -->` sentinels (regenerated by the loop's script every time the discipline fires). Fires on three triggers: directory-shape changes as-it-happens (new top-level dir, submodule mount/unmount, major subsystem rename), weekly cadence, and pre-release. Why both halves: a raw `tree` dump doesn't tell a newcomer *what they're looking at* — the curator preface is what makes the file legible, the generated tree is what makes it accurate. Composes with `pseudomonorepos` (parent FILEMAP stops at submodule mounts at depth 3; each submodule carries its own). |
| **Chroma Agent Skills** *(submodule)* | [`chroma-agent-skills/`](./chroma-agent-skills/) | Official skills from the [Chroma](https://www.trychroma.com) team for integrating Chroma local and Chroma Cloud (CloudClient, schema, hybrid search, cloud CLI). Pinned as a git submodule from [`chroma-core/agent-skills`](https://github.com/chroma-core/agent-skills); we vendor it here so any agent loading the Lossless skills tree gets battle-tested vector-store guidance from upstream rather than paraphrased-from-training-data Chroma usage. |
| **Market Capture Analysis** | [`market-capture-analysis/`](./market-capture-analysis/) | Answers the first of the two foundational VC questions — *how big can it get?* — by walking revenue and EBITDA across an 8-step penetration grid (`1%, 3%, 5%, 10%, 25%, 35%, 50%, 60%`) for SAM / SOM / TAM at the company's existing pricing and business model. A static if-then picture: the size of the prize at each penetration step with every assumption named so the reader can react to it. Encodes the failure modes (silently picking the optimistic cell, training-data margin assumptions, conflating "unit of sale" with "customer") and the synthesis discipline (3–5 cells in the memo, one named base case, market definition anchored explicitly). Pairs with the sibling skill [`timeline-scenario-analysis`](./timeline-scenario-analysis/), which answers *how fast?* — running this skill alone produces a destination with no route. |
| **Timeline Scenario Analysis** | [`timeline-scenario-analysis/`](./timeline-scenario-analysis/) | Answers the second of the two foundational VC questions — *how fast can it get that big?* — by stress-testing the company's current MoM/YoY growth at its actual unit of sale across four scenarios (`sustain` / `improve` / `plateau` / `reduce`). Operates on the penetration grid produced by [`market-capture-analysis`](./market-capture-analysis/); sensitivity tables show what it takes to reach each cell and how time-to-base-case shifts with small growth-rate changes. Encodes the failure modes (compounding a recent spike forever, hiding recent deceleration behind YoY, omitting the plateau scenario, skipping the base-case time-to-reach number — that last one is the single most useful sentence the skill produces). Pairs with [`market-capture-analysis`](./market-capture-analysis/); running this alone produces a growth curve aimed at nothing in particular. |
| **Competitive Analysis** | [`competitive-analysis/`](./competitive-analysis/) | Reference taxonomy for classifying competitors in an investment-memo competitive landscape section. Two orthogonal axes — **stage ring** (concentric circles outward from the target's own stage: `early stage` / `early scaleup` / `scaleup` / `mezzanine` / `incumbents`) and **competitor type** (`direct` / `adjacent` / `indirect` / `noisewashing`). Every competitor tagged on both. Encodes the noisewashing-vs-genuine-threat test (coverage doesn't discriminate, but paying users + multi-year capex + earnings-call segment reporting does), the discipline of preferring the looser classification on boundaries (most "direct" candidates are really `adjacent`), and the exhaustive-vs-synthesized two-artifact pattern shared with the two memo skills above — long classified research file + scannable memo section with a table, grouped list, or ring diagram. |
| **Search Lossless Corpus** | [`search-lossless-corpus/`](./search-lossless-corpus/) | The discipline of querying The Lossless Group's local Chroma database — populated by [`context-vigilance-kit`](https://github.com/lossless-group/lossless-ai-labs/tree/main/context-vigilance-kit) with four collections (`context-vigilance-corpus`, `lossless-changelog`, `claude-code-sessions`, `claude-code-tool-traces`) — before answering questions prior work might already have answered. Encodes the four-step agentic-search loop (decompose → execute → evaluate → synthesize), the five canonical question shapes that trigger retrieval ("what did we decide / when did we ship / why did we choose / has this failed / where did we put"), the metadata-filter patterns that keep queries precise, and the citation discipline (every claim cites `source_path` + timestamp + `source_repo_slug`). Lossless layer on top of the upstream `chroma-local` / `chroma-cloud` skills — without it the corpus sits there full of high-signal records nobody queries; with it, every "what did we decide about X" becomes grounded recall the user can verify in seconds. |
| **Lossless CRM Interface Guidelines** | [`lossless-crm-interface-guidelines/`](./lossless-crm-interface-guidelines/) | Operating manual for reading and writing the operator's Twenty CRM estate over MCP: routing across three workspaces that do *not* share data, the custom object model (Investment, Deal Source, Deal Prospect, Thesis, Thesis Fit, Events), a forced-choice 0–5 scoring standard with no neutral midpoint, the two-tier profile-links architecture (dedicated fields for sources present on nearly every record, one `Profiles` LINKS field for the long tail), and the MCP pitfalls worth knowing before the first write. Encodes the provenance discipline that makes a CRM trustable — dedupe before every create, fetch before writing a description, and *offer* model knowledge rather than smuggling it in, because an empty field is data and a wrong field is damage. First skill built to the **public skill / private config** pattern below: every operator-specific particular lives in a gitignored `config/private.json`, and the skill asks rather than guesses when it's missing. |

| **Expense Report Generation** | [`expense-report-generation/`](./expense-report-generation/) | How to turn raw card and bank statement downloads into a claim a client's finance team can approve without asking a question. Statement data is not an expense report — the gap is identification, categorisation, and disclosure, and each is where a claim gets rejected. Encodes the **parent-company descriptor trap** (Loom bills as `ATLASSIAN`, Trae as `BYTEDANCE`) and the timeline-continuity proof that resolves it, the never-invent-a-product-name rule, the statement-close gap that silently truncates a trip spanning two billing periods, cheap text extraction from bank PDFs (never read the images), cross-card reconciliation, and the BASE/EXTENDED two-section structure that lets a reviewer decline one half without unpicking the other. Financial source data stays in a gitignored `private-data/`; account-to-card mappings and letterhead details are instance facts, not skill content. |

**Planned / not yet shipped:** `lossless-loop/` — the 5-phase Start → Progress → Reflect → Publish → Market lifecycle for any meaningful unit of work. Diagram and spec live at `pseudomonorepos/references/lifecycle-workflow.md` until the skill graduates.

A running backlog of additional candidates lives in [**`CANDIDATES.md`**](./CANDIDATES.md).

## Engineer-influencer collections we watch

External skills repos from engineer-influencers in the broader community. We track them for inspiration and to see where conventions converge. These are not pinned references — just repos whose evolution we follow.

| Engineer | Repo | Known for |
|---|---|---|
| **Matt Pocock** | [mattpocock/skills](https://github.com/mattpocock/skills) | TypeScript educator and engineer (Total TypeScript, `ts-reset`). |

## Install

### Pi (recommended for Lossless contributors)

```bash
pi install git:github.com/lossless-group/lossless-skills
```

Or clone directly into the global skills directory:

```bash
git clone https://github.com/lossless-group/lossless-skills.git ~/.pi/agent/skills
```

In an active pi session, run `/reload` to pick up changes without restarting.

### Claude Code

Clone into Claude's skills directory:

```bash
git clone https://github.com/lossless-group/lossless-skills.git ~/.claude/skills
```

### OpenAI Codex / other harnesses

Clone anywhere and point your tool's skills configuration at the directory.

### Cross-tool sharing on one machine

Use the `~/.agents/skills/` location (read by pi and other Agent-Skills-compatible tools), or symlink:

```bash
ln -s ~/.pi/agent/skills ~/.agents/skills
```

## Layout

Each skill is a directory with a `SKILL.md` file:

```
<skill-name>/
├── SKILL.md              # Required: frontmatter (name, description) + instructions
├── references/           # Deep-dive docs the agent loads on demand
├── templates/            # Scaffolds for new files
└── scripts/              # Helper scripts (when needed)
```

The `description` in `SKILL.md` frontmatter determines when an agent will auto-load the skill. Be specific.

## Contributing

Skills here represent shared Lossless conventions. Before adding or changing a skill:

1. **Discuss first** if it changes how the team works (open an issue or a draft PR with rationale).
2. **Match existing conventions:**
   - Skill directory and `name:` field: lowercase with hyphens (e.g., `context-vigilance`)
   - Filenames inside skills: `Train-Case.md`
   - Frontmatter follows the Agent Skills spec
3. **Test the skill** in a real session before committing — verify the agent loads it when you'd expect.
4. **Commit message convention:**
   ```
   skill(<skill-name>): short description
   ```

### Adding a new skill

1. `mkdir <skill-name>` (lowercase, hyphens, must match `name:` in frontmatter)
2. Create `SKILL.md`:
   ```yaml
   ---
   name: <skill-name>
   description: When the agent should load this skill. Be specific about triggers.
   ---
   ```
3. Add `references/`, `templates/`, `scripts/` as needed
4. Update the **Skills** table in this README
5. Open a PR

# Public skills, private config

A pattern for keeping agent-skills publishable while the operator-specific data they
depend on stays out of the repo.

## The problem

Useful agent-skills accumulate two kinds of content:

1. **Method** — how to model a CRM, how to score, how to handle provenance, which MCP
   calls have sharp edges. Generalizable, worth sharing.
2. **Particulars** — which firms, which workspace URLs, which people, which
   relationships. Useless to anyone else and often confidential.

Inline the particulars and the skill can't be published. Strip them and the skill stops
working. Neither is acceptable if the discipline is "everything lives in one repo and
the repo is public."

## The shape

```
<skill-name>/
├── SKILL.md                     # public — method only, references config keys
├── config/
│   ├── private.example.json     # public — documents the expected shape
│   └── private.json             # gitignored — real values
└── .gitignore
```

`SKILL.md` opens with a §0 that says: read `config/private.json`, here are the keys it
provides, and **if it's missing, say so and ask — do not guess.**

## Why instructional resolution, not templating

Two ways to get values into a skill:

- **Template substitution** — `{{affiliations.venturePartner}}` placeholders,
  interpolated by a preprocessor before the agent reads the file.
- **Instructional resolution** — the skill tells the agent to read the config file and
  use what it finds.

Instructional resolution wins for now. It needs no build step, no preprocessor, and no
new failure mode. Any agent with filesystem access — Claude Code, a local harness,
anything that can `cat` a file — can do it today. And the agent can reason about a
missing or partial config, where a templater would silently emit an empty string.

Templating becomes worth it when several skills share config and drift starts to hurt.
Not before.

## Rules that keep it honest

1. **Never inline a config value back into SKILL.md.** The moment a firm name or an
   instance URL appears in the public file, the skill has stopped being publishable.
   Adding operator-specific content means adding a config key and referencing it.
2. **Keep `private.example.json` in sync.** It is the contract. If a skill starts
   reading a new key, the example documents it in the same commit.
3. **Config holds facts, not instructions.** `noDeadlines: true` is a fact about the
   operator. *How* to respond to it belongs in SKILL.md. Otherwise behaviour scatters
   across two files and neither is readable alone.
4. **Only put things in `keyRelationships` that change agent behaviour** — a routing
   path, a gatekeeper, a warm intro. It is not a contact list; the CRM is the contact
   list.
5. **Audit before publishing.** Grep the public file for names, domains, and firms:

   ```sh
   grep -niE "$(python3 -c "
   import json;c=json.load(open('config/private.json'))
   names=[c['operator']['name'],c['operator']['shortName']]
   names+=[f for v in c['affiliations'].values() if isinstance(v,list) for f in v]
   names+=list(c.get('keyRelationships',{}))
   print('|'.join(n for n in names if n))
   ")" SKILL.md
   ```

   Empty output means it's safe to push.

## Upgrade path

The gitignored JSON works today with no infrastructure. Two better versions later:

- **A real secrets manager** (SecretSpec and similar) if any of this becomes an actual
  credential rather than a preference. Config today holds no secrets — firm names and
  relationship tiers are private, not sensitive — so this is premature.
- **An MCP server serving config at runtime.** Same architecture as serving skills over
  MCP: the agent asks for `operator.affiliations` and gets it, with no file on disk and
  no per-machine setup. This is the right end state if skills are ever run somewhere
  other than the operator's own machine.

## Applying it to a new skill

1. Write the skill with the particulars inline — it's faster and you find out what's
   actually operator-specific.
2. Move each one into `config/private.json` under a sensible key.
3. Replace with a config reference in SKILL.md.
4. Update `private.example.json`.
5. Run the audit grep. Push.

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [pi skills documentation](https://github.com/badlogic/pi-mono/blob/main/packages/pi-coding-agent/docs/skills.md)
- [Context Vigilance project](https://www.lossless.group/projects/gallery/context-vigilance)
- [The Lossless Group](https://www.lossless.group)

## License

[MIT](./LICENSE) © The Lossless Group
