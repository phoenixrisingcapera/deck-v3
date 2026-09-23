---
title: Understanding codebases with graphify — scope the corpus, take the free tier
  first
lede: Point graphify at a repo and it will happily graph everything, which is how
  you get a 4.2M-word hairball that buries the architecture under client PDFs. Scope
  the corpus first, build code-only for zero tokens, and layer the docs in later.
date_created: 2026-08-06
date_modified: 2026-08-06
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 5
semantic_version: 0.0.0.1
tags:
- Blueprint
- Knowledge-Graph
- Graphify
- Codebase-Comprehension
- AST-Extraction
- Corpus-Scoping
- Refactoring
status: Draft
site_uuid: 88037115-28d9-459e-93e1-42a260212265
hex_code: ofgei1
date_authored_initial_draft: 2026-08-06
date_authored_current_draft: 2026-08-06
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: blueprints/Understanding-Codebases-with-Graphify.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/blueprints/Understanding-Codebases-with-Graphify.md"
---

# Understanding codebases with graphify

## Why care?

Every repo in this tree eventually reaches the point where the person who wrote it can no longer hold it in their head. The honest signal is a sentence like *"we will soon need to refactor as the whole thing is getting very complex"* — which is not a request for a rewrite, it's a request for a **map**.

`graphify` builds that map: a persistent knowledge graph with community detection, god nodes, import cycles, and an audit trail that marks every edge `EXTRACTED` / `INFERRED` / `AMBIGUOUS`. The trap is that its default invocation (`/graphify .`) grabs everything it can read, and in a Lossless pseudomonorepo "everything" usually means a client content corpus that outweighs the source ten to one. The graph builds fine. It just answers the wrong question.

This blueprint codifies the two decisions that make the difference — **what goes in the corpus**, and **which extraction tier you pay for** — using the `ai-labs/augment-it` run of 2026-08-06 as the worked example.

## The two tiers of extraction

The single most under-appreciated fact about graphify: **code costs nothing.**

| Tier | Applies to | Mechanism | Cost |
|---|---|---|---|
| **Structural** | code (`.ts`, `.svelte`, `.mjs`, `.astro`, `.py`, …) | AST parse, deterministic, parallel | **zero tokens, no API key, no subagents** |
| **Semantic** | docs, papers, images (`.md`, `.pdf`, `.png`) | LLM — Gemini if `GEMINI_API_KEY` is set, otherwise dispatched subagents | tokens, proportional to corpus |

A code-only build needs no API key and no agent fan-out at all. On augment-it, 490 code files produced **4,330 nodes and 6,011 directed edges for 0 input / 0 output tokens**, at 99% `EXTRACTED` (74 `INFERRED` edges, avg confidence 0.67). Almost nothing in a structural build is model-guessed — which is exactly the property you want in a map you're about to refactor against.

**Take the free tier first.** It is fast, deterministic, reproducible, and answers the structural questions ("what imports what", "what's cyclic", "what's duplicated") that dominate early refactor work. Add the semantic layer when you specifically want design *intent* linked to structure.

## Scope the corpus before you build it

graphify warns above 500 files or 2M words. Treat those as the floor, not the target.

Run detection first — it is read-only and cheap:

```python
from graphify.detect import detect
from pathlib import Path
detect(Path('.'))   # -> total_files, total_words, per-category file lists
```

On augment-it, unscoped detection returned **2,910 files / 4.2M words**. The breakdown is the whole argument:

| Slice | Files | Share |
|---|---|---|
| `clients/` (reach-edu + humain-vc: transcripts, research md, 316 PDFs) | 2,106 | **72%** |
| code (`apps`, `services`, `scripts`, `packages`, `shell`, `splash`, `tools`) | 490 | 17% |
| `context-v/` + `changelog/` | 262 | 9% |

Scoped to code + docs, the same repo is **804 files / 923k words** — under both thresholds, no warning, and the architecture is legible instead of drowned.

### The rule

> **Content corpora and architecture corpora are different graphs. Never merge them.**

Client research, voice-note transcripts, and PDF libraries are genuinely worth graphing — as *their own corpus*, answering their own questions. Mixed into a source graph they dominate community detection, because there are simply more of them, and every interesting code community gets crowded off the report.

### How to scope: `.graphifyignore`

graphify honors `.graphifyignore` (gitignore syntax, per-directory, merged after `.gitignore`, and **subtractive only** — it can exclude more, never re-include). This is preferable to the multi-path merge flow because the scope decision becomes a committed, reviewable artifact:

```gitignore
# graphify corpus scope for the <repo> architecture graph.
# clients/ is 2,106 of 2,910 detected files (~72%): client content, not architecture.
# Left in, it dominates community detection and buries the code structure.
clients/
```

`node_modules`, `dist`, `build`, `.git`, and `graphify-out` itself are already in graphify's built-in `_SKIP_DIRS` — do not restate them.

## Build directed

Pass `directed=True` (CLI: `--directed`). Import and call edges have a direction, and for refactor work "who depends on whom" is the entire question. Community detection is unaffected — `cluster()` converts a `DiGraph` to undirected internally, since Louvain/Leiden require it.

## What to read first

The interactive `graph.html` is the wrong entry point at 4,000+ nodes — it's a hairball. Read `GRAPH_REPORT.md` in this order:

1. **Import Cycles** — the shortest, most actionable section. Anything listed is a refactor target with no judgment call attached.
2. **God Nodes** — highest-degree symbols; your real core abstractions, whether or not you intended them to be.
3. **Cohesion scores per community** — low cohesion on a *large* community means "this module is a bag, not a thing."
4. **Community Hubs** — the navigation index; the closest thing to a table of contents for the system.
5. **Surprising Connections** — cross-community edges you didn't know existed.

Then stop reading and start asking. The point of a built graph is traversal, not prose:

```bash
graphify query "How does a record get from the collector into SurrealDB?"
graphify path "AugmentItWorkspace" "RecordSet"
graphify explain "CurationState"
```

For learning a system, `graphify --wiki` (index plus one article per community, still free) is usually more legible than the force-directed view.

### Reading the duplication signal

The highest-value pattern in the augment-it run was not in any named section — it fell out of the community sizes. **Fourteen communities had identical size (30) and identical cohesion (0.067)**, one per app, each a `package.json`. The `tsconfig.json` files repeated the shape. Identical size *and* identical cohesion across N communities means N copies of the same structure — exactly the duplication a monorepo refactor exists to collapse.

Watch for it. Sort communities by size and look for repeated `(size, cohesion)` pairs.

## Label the communities honestly

Step 5 of the skill asks for plain-language community names. At 285 communities, hand-writing each is not realistic — but emitting `Community 0 … Community 284` makes the report useless.

The middle path: **derive labels from the longest common node-ID prefix** (graphify's AST node IDs are path-derived, so the prefix *is* the module), humanize with an acronym map, then disambiguate collisions with the modal distinguishing token. That produced 278 unique labels from 285 communities with no LLM call. The labels are honest because they're computed from real paths, not invented.

## Honesty: what the health check will tell you

Step 4.5's diagnostic is read-only and never aborts. On a code-only build, expect and **report** these rather than suppressing them:

- **Dangling-endpoint edges** (417 / 6.3% on augment-it) — overwhelmingly imports of external npm packages that were never extracted as nodes. Expected. It does mean the graph is not a complete picture of every edge.
- **Collapsed directed edges** (144) — node pairs carrying two relations at once (`imports_from` *and* `re_exports`), which a `DiGraph` flattens to one.
- **Weakly-connected nodes** (1,985 of 4,330) — a real structural finding, not a defect: the codebase is more archipelago than continent.
- **Repeated god-node names** — three distinct `registerHandlers()` functions in different services all landed in the top 5. That is a finding about naming, not a glitch in the tool.

Per the tree's Honesty Rules: surface these in the summary. A clean-looking report that hid a 6% dangling-edge rate would be lying by omission.

## Housekeeping

- **`graphify-out/` → `.gitignore`.** ~7MB of regenerable output (`graph.html` 3.5MB, `graph.json` 3.7MB, plus AST cache and manifest).
- **`.graphifyignore` → commit it.** It is not generated; it is the record of corpus scope and the reasoning behind it. The next person rebuilding must get the same graph.
- **Leave docs unstamped for later.** A code-only run leaves semantic files unstamped in `manifest.json` (314 on augment-it), so `graphify --update` adds the doc layer later without re-running AST. The AST cache makes the second build nearly free too.

## Anti-patterns

- **`/graphify .` on a pseudomonorepo without detecting first.** You will graph the client corpus and learn nothing about the code.
- **Dispatching semantic subagents before asking.** Agent fan-out costs real tokens; in this tree it also runs against the standing "no agents unless requested" rule. The structural build needs none — offer it first.
- **Prompting for an API key.** graphify reads `GEMINI_API_KEY` / `GOOGLE_API_KEY` only. It never reads `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, and a code-only corpus needs no key at all. Blocking on one is a misread of the skill.
- **Emitting placeholder community labels.** `Community 0..N` renders the report unnavigable — derive from paths instead.
- **Rebuilding from scratch to add docs.** That's what `--update` and the AST cache are for.
- **Merging a content corpus into an architecture graph** because it was easier than writing three lines of `.graphifyignore`.

## Related

- [[Browser-Drive-Verification-For-Agent-Sessions]] — the sibling pattern for the *runtime* half: graphify maps the code, browser-drive proves the surface.
- `context-v/agent-skills/pseudomonorepos/SKILL.md` — why a repo in this tree has 2,000 files of client content sitting next to its source in the first place.
- `context-v/agent-skills/context-vigilance/SKILL.md` — the `context-v/` corpus that the semantic layer graphs, once you add it.
- The `graphify` skill itself (`~/.claude/skills/graphify/SKILL.md`) — the full pipeline; this blueprint is the scoping judgment on top of it.
