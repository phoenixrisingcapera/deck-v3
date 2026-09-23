# context-vigilance-kit

> Treat context files with the same vigilance as code, and *context becomes the code* — or the parent to it. Regenerating code, fixing bugs, refactoring, even migrating across languages or tech stacks — work that used to take days, weeks, or months — compresses to minutes.
>
> Generating a fully-featured splash page — search, three viewing modes, coherent theme CSS, full markdown rendering — now takes **5 minutes**. Only with context vigilance.

Tooling for the **Context Vigilance** practice — collating, indexing, and eventually publishing the `context-v/` directories scattered across [The Lossless Group](https://github.com/lossless-group) tree (and beyond) as a single, queryable corpus. Brand site: [contextvigilance.com](https://contextvigilance.com) (forthcoming). Scope, rationale, and decision history live in the parent exploration: [[Collate-Context-Files-into-Context-Vigilance-as-Repo-&-Project]] (under `ai-labs/context-v/explorations/`).

## Corpus state — August 2026

After the 2026-08-18 context-v tier sweep (every `context-v/` document across the tree brought to frontmatter conformity, then re-collated):

| metric | count |
|---|---:|
| total files | **1,166** |
| `worked-on` (≥500 content lines) | 108 |
| `idea-started` (100–499 content lines) | 648 |
| `stub` (<100 content lines) | 410 |
| without YAML frontmatter | 59 |

| skills (tracked separately in `skills-manifest.md`) | 27 |
|---|---:|
| with `SKILL.md` | 24 |
| `complete` (per Anthropic agent-skills spec) | 14 |

The *without YAML frontmatter* row in the corpus table is **orthogonal** to the three buckets — a file lands in exactly one bucket (by `content_lines`) and is *separately* tagged as missing frontmatter (`yaml_lines == 0`). The frontmatter-less files are scattered across all three buckets; a doc can be `worked-on` and still be missing its frontmatter.

**Publishing strategy.** Ship the 107 `worked-on` docs first while building a systematic, agent-assisted process to fill out the 354 stubs and 540 idea-started entries. The corpus manifest is the gate that makes this triage tractable — re-run `python scripts/build-corpus-manifest.py` after every fill-out batch to track progress against this baseline.

> *(Earlier baselines for reference — May 2026 post-curation: 583 total / 110 worked-on / 263 idea-started / 210 stub / 59 no-frontmatter. Original pre-curation pass: 787 total / 138 worked-on / 353 idea-started / 296 stub / 100 no-frontmatter. See git history of `sources.md` for the curation diffs.)*

## The folder taxonomy (as of 2026-07-21)

The [[context-vigilance]] skill is the source of truth; summary here for orientation:

- **Canonical, eight folders, three cognitive modes** — Prep: `specs/` → `plans/` → `prompts/` (descending altitude); Reflective: `blueprints/`, `reminders/`, `agent-skills/` (executable know-how in the Anthropic SKILL.md shape); Journey: `explorations/`, `issues/`.
- **Universal utilities** — `extra/` (scratch / out-of-band; gitignored by default, always excluded from the corpus) and `sitemap/` (maps of a project's own pages/routes/slides/surfaces).
- **Experimental tier** (proposed; shape deliberately not yet enforced) — `loops/` (recurring operational loop definitions), `handoffs/` (end-of-session state capture for the next session or collaborator), `decisions/` (isolated decision artifacts, kin to ADRs), `contracts/` (constitution rules agents must always follow, or ironclad API-level data-flow contracts).

`plans/` and `agent-skills/` were promoted from the long tail to canon on 2026-07-21 after tree-wide adoption (14 and 5 repos respectively) — the assimilation path the experimental tier now formalizes.

## What's in here (v0)

```
context-vigilance-kit/
├── README.md                          ← you are here
├── sources.md                         ← curated list of source dirs (generated, then human-curated)
├── corpus-manifest.md                 ← per-file triage view (yaml & content line counts; auto-generated)
├── skills-manifest.md                 ← agent-skills inventory; tracked separately from corpus
├── requirements.txt                   ← Python dependencies (install with `uv pip install -r ...`)
├── scripts/
│   ├── assemble-context-v-sources.py       ← walks the tree, populates sources.md
│   ├── build-corpus-manifest.py            ← reads sources.md, emits per-file inventory with bucket labels
│   ├── build-skills-manifest.py            ← reads sources.md, inventories context-v/skills/* per source
│   ├── collate.py                          ← reads sources.md, copies files into corpus/ with provenance
│   ├── ingest-all.sh                       ← master orchestrator: runs every Chroma ingester in sequence
│   ├── ingest-to-chroma.py                 ← context-v rollup → `context-vigilance-corpus` collection
│   ├── ingest-changelogs-to-chroma.py      ← every <repo>/changelog/ → `lossless-changelog` collection
│   ├── ingest-claude-sessions-to-chroma.py ← transcripts → `claude-code-sessions` + `claude-code-tool-traces` (opt-in)
│   └── smoke-test-chroma.py                ← end-to-end probe of the Chroma integration; throwaway
├── context-v/                         ← this kit's own specs/plans/etc. (rolled up by ai-labs splash)
├── corpus/                            ← collated output with provenance frontmatter (committed; the splash renders it)
└── splash/                            ← Astro 5 catalog of every context-v file in the corpus
```

## Install

This kit's dependencies live in `requirements.txt` (kit-scoped; not in the ai-labs root manifest).

```bash
# Preferred — uv (faster, deterministic, project-default for this team):
uv pip install -r requirements.txt

# Or, with pip:
pip install -r requirements.txt
```

First run of any Chroma-touching script will auto-download the default embedding model (`all-MiniLM-L6-v2`, ~79 MB) into `~/.cache/chroma/`. One-time cost; cached afterwards.

To verify the Chroma integration end-to-end:

```bash
python3 scripts/smoke-test-chroma.py
```

Ingests a handful of real corpus files, runs sample queries, prints similarity-ranked hits.

## Ingest the corpus

After curating `sources.md`, build (or rebuild) the searchable corpus in Chroma. The master orchestrator runs every ingester in sequence:

```bash
# Default: context-v rollup + changelog rollup (both safe to rerun):
./scripts/ingest-all.sh

# Opt in the privacy-sensitive Claude Code transcript collections:
./scripts/ingest-all.sh --with-claude

# See ./scripts/ingest-all.sh --help for --reset, --dry-run, and --only-* flags.
```

Four collections land in the same `.chroma/` persistent client: `context-vigilance-corpus`, `lossless-changelog`, and (opt-in) `claude-code-sessions` + `claude-code-tool-traces`. Or run the context-v ingester directly:

```bash
# Full ingest into the canonical collection (idempotent on stable IDs):
python3 scripts/ingest-to-chroma.py

# Drop and recreate the collection from scratch (use after schema changes):
python3 scripts/ingest-to-chroma.py --reset

# Smoke ingest just the first N files:
python3 scripts/ingest-to-chroma.py --limit 50

# Query the live collection without re-ingesting:
python3 scripts/ingest-to-chroma.py --query "your question here"
```

Chunks markdown by `## ` headings; each chunk gets a stable ID
(`<repo-slug>::<safe-relative-path>::<chunk-index>`) so re-runs upsert
cleanly. Files with `private: true` in their frontmatter are skipped.

The collection lives at `.chroma/` (gitignored). Default name:
`context-vigilance-corpus`.

## Graphiti — the temporal knowledge graph (experimental)

Chroma answers *"what did we write that sounds like this."* It has no mechanism
for *"what changed about this, and when"* — there is no **between** in a vector
index. [Graphiti](https://github.com/getzep/graphiti) stores typed entities and
bi-temporally versioned edges, where every fact carries `valid_at` / `invalid_at`
(when it was true in the world) separately from `created_at` / `expired_at`
(when the graph learned and retired it).

This is **additive, not a migration.** Chroma stays and still covers all ~28,000
chunks. The graph currently covers one slice — the **479 changelog entries**
across the tree — because dated ship records are the data shape the bi-temporal
model was designed for, and because Graphiti runs an LLM extraction call per
episode rather than a cheap local embedding per chunk.

```bash
# 1. Dependencies (separate from requirements.txt — only needed for the graph).
uv pip install -r requirements-graphiti.txt

# 2. Local embeddings via Ollama — 384-dim, no API key, same MiniLM family Chroma uses.
ollama pull all-minilm && ollama serve

# 3. Neo4j.
docker compose -f docker-compose.graphiti.yml up -d    # browser at :7474

# 4. Anthropic key for extraction. graphiti-core needs a RAW key — it cannot
#    borrow Claude Code's session auth.
cp .env.example .env && $EDITOR .env

# 5. Ingest. Always dry-run first; --limit gives you a cheap smoke run.
python scripts/ingest-changelogs-to-graphiti.py --dry-run
python scripts/ingest-changelogs-to-graphiti.py --limit 10
python scripts/ingest-changelogs-to-graphiti.py

# 6. Query it.
python scripts/query-graphiti.py --stats
python scripts/query-graphiti.py "when did we ship the Chroma corpus"
python scripts/query-graphiti.py --mode around --center "augment-it" "decile"
```

Ingest is **resumable and idempotent** — `.graphiti-state/changelog-ingest.json`
maps each source path to a content hash and is written after every successful
episode, so a Ctrl-C or a failure costs you one entry, not the whole run.
Discovery is imported from `ingest-changelogs-to-chroma.py` rather than
reimplemented, so both indexes always cover exactly the same files.

Rationale, upstream gotchas (there is no sentence-transformers embedder in
graphiti-core despite the MCP server README advertising one), the entity
ontology, and the open questions: **`context-v/explorations/Graphiti-Over-The-Lossless-Corpus.md`**.

## Splash page — public catalog

`splash/` is a small Astro 5 site that renders `corpus/` as a public catalog: every collated context-v file gets its own page, all files are grouped by source repo on the index, and the whole thing builds to static HTML in seconds. **Live at <https://lossless-group.github.io/context-vigilance-kit/>** — deployed by `.github/workflows/pages.yml` on push to `master`, `main`, or `development`.

```bash
cd splash
pnpm install --ignore-workspace   # one-time; ai-labs's pnpm-workspace doesn't include this dir
pnpm dev                          # http://localhost:4321/context-vigilance-kit/
pnpm build                        # writes static site to splash/dist/
pnpm preview                      # serves dist/ locally
```

Build output today: **1,166 corpus files** (small handful skipped due to schema or duplicate-id edge cases). Index page groups entries by `source_repo_slug`; detail pages render the full markdown with frontmatter as a metadata block. The site ships Pagefind full-text search, a sitemap + robots.txt, `/llms.txt` + `/llms-full.txt` endpoints for LLM ingest, and an OG share card — see `changelog/` for how each landed.

## Claude Code MCP integration

The kit ships a `.mcp.json` that wires the Chroma MCP server into Claude Code at **project scope** (so the config persists across sessions and travels with the repo). The same config is mirrored at `ai-labs/.mcp.json` so a Claude Code session opened anywhere in the ai-labs tree picks it up.

```jsonc
// .mcp.json (root of kit and root of ai-labs)
{
  "mcpServers": {
    "chroma": {
      "command": "uvx",
      "args": [
        "chroma-mcp", "--client-type", "persistent",
        "--data-dir", "/abs/path/to/context-vigilance-kit/.chroma"
      ]
    }
  }
}
```

Once `.mcp.json` is in place:

1. **Restart Claude Code** in the project. `.mcp.json` is loaded on session start, not hot-reloaded.
2. Verify the server is discovered: `claude mcp list` (should show `chroma` as connected).
3. In a prompt, type `@chroma:` to see exposed resources, or call its tools directly.

Whenever the corpus changes (you re-run `ingest-to-chroma.py`), the MCP server already reads the same `.chroma/` directory — no MCP restart needed. Only the `.mcp.json` itself needing to change requires a session restart.

## Quickstart

Run from the kit directory after dependencies are installed:

```bash
# 1. Walk the tree and discover context-v/ directories.
#    First run creates sources.md; subsequent runs preserve curation and append new finds.
python scripts/assemble-context-v-sources.py

# 2. Open sources.md, flip `include: true` on entries you want, add notes,
#    add legacy/open-call directories by hand with `kind: legacy` (with `subdirs:`)
#    or `kind: open-call`.

# 3. Build the pre-collation manifest. Counts yaml-frontmatter and content lines
#    per file, buckets each into stub / idea-started / worked-on. Use it to triage
#    what needs agent fill-out BEFORE you commit to a corpus build.
python scripts/build-corpus-manifest.py

# 4. Inventory agent skills separately. Walks every context-v/skills/<skill>/ under
#    your included sources, parses each SKILL.md frontmatter, counts assets.
#    Skills are excluded from corpus-manifest so they don't pollute the to-do list,
#    but indexed downstream alongside the corpus.
python scripts/build-skills-manifest.py

# 5. Run the collator. Reads sources.md, copies files into corpus/ with provenance keys.
python scripts/collate.py
```

**Clickable paths.** Both manifests render file paths as markdown links with editor-relative paths. In VS Code, Cursor, Windsurf, and Trae's markdown preview, clicking the path opens the source file in the same editor window. Configured to relativize against the manifest's own directory; no editor-specific URI scheme required.

Optional flags on the assembler:

```bash
python scripts/assemble-context-v-sources.py --root /path/to/another/tree
python scripts/assemble-context-v-sources.py --output sources.md
```

## How sources.md works

`sources.md` is a Markdown file with YAML frontmatter. The frontmatter is the machine-consumable part (read by both scripts); the body is human curation rationale that the assembler preserves on re-run.

Each entry in the `sources:` list has:

- `path` — absolute filesystem path to a `context-v/` directory or a legacy root
- `kind` — one of:
  - `context-v` — canonical context-v structure (eight folders plus utility/experimental tiers, per the [[context-vigilance]] skill)
  - `legacy` — pre-context-v notes; pair with `subdirs:` whitelist to scope what's collated
  - `study-context-v` — lives inside a `studies/<name>/` collection
  - `open-call` — published proposals in the Hyperloop-paper spirit ("we thought of this, someone please build it"); flat directories, whole tree collated
- `include` — `true` to collate, `false` to skip
- `note` — free-form curation rationale (optional)
- `subdirs` — for `kind: legacy` only, a whitelist of subdirectories to walk

**Idempotency contract.** The assembler treats every entry already in `sources.md` as authoritative. New paths are appended with `include: false` and a dated note so the user opts them in deliberately. Removed paths (no longer on disk) are flagged as warnings to stdout but never silently dropped.

## Privacy / no-collision boundary

`corpus/` lives **outside** `context-v/` so the ai-labs splash rollup (which walks `context-v/` directories) does not pick up duplicates of files already collated from their original homes. This is the boundary by *location*, not by flag.

Per-file escape hatch: setting `private: true` in a file's frontmatter causes the collator to skip it. Reserved for edge cases the location-based boundary doesn't cover.

The kit's own `ai-labs/context-vigilance-kit/context-v/` is normal Lossless content (the kit's specs, plans, prompts, etc.) and **is** rolled up by the ai-labs splash — that's intentional.

**Path-substring exclusions.** Files whose absolute paths match any entry in `SKIP_PATH_SUBSTRINGS` (in both `build-corpus-manifest.py` and `collate.py`) are skipped:

- `/context-v/extra/` — per-directory escape hatch for scratch, out-of-band, or work-in-progress notes that should not flow into the corpus.
- `/context-v/skills/` — agent skills are tracked by `build-skills-manifest.py` as a separate concern. They're indexed downstream (ChromaDB), but excluded from the corpus to-do list so they don't dilute the fill-out work queue.
- `/context-v/changelog/` and `/context-v/changelogs/` — ship-log entries follow the [[changelog-conventions]] skill and are a different artifact class than fill-out-needing context-v docs. They land in the ChromaDB stream alongside the corpus, but stay out of the "complete a bunch of context-v files soon after splash launch" workflow. Both singular and plural forms exist in the wild; both are excluded.

## Provenance keys added by the collator

The collator does not modify originals. It writes copies into `corpus/` with these frontmatter keys appended:

- `source_root` — the source entry's `path` from `sources.md`
- `source_relative_path` — the file's path relative to that source root
- `source_repo_slug` — short identifier derived from the source path (last meaningful component)
- `collated_at` — ISO date the copy was written

## Repo status

The kit lives at **<https://github.com/lossless-group/context-vigilance-kit>** (public) and is mounted in `ai-labs/` as a git submodule — the promotion this section once described as "next step" is done. Work happens inside the submodule; ai-labs tracks the gitlink. Branch tiers follow the tree-wide model: `development` → `main` → `master`.

## Related

- [[Collate-Context-Files-into-Context-Vigilance-as-Repo-&-Project]] — the scoping exploration in `ai-labs/context-v/explorations/`
- [[context-vigilance]] skill — the practice this kit codifies into tooling
- [[pseudomonorepos]] skill — `references/content-rollup.md` informs how a future remote-fetcher fits in alongside the v0 filesystem walker
- [[open-specs-and-standards]] study — informs Track 4 (publishing context-vigilance as an open spec)
