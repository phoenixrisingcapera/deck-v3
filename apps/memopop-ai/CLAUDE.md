# Agent instructions for `memopop-ai` (the MemoPop pseudomonorepo)

## What this is

`memopop-ai` is a Bun-workspaces monorepo containing the **client surface** of MemoPop: the Tauri 2 desktop app, the Astro marketing site, a placeholder SvelteKit web app, and shared style packages. The agent engine that actually generates memos — `memopop-orchestrator` — lives here as a git submodule under `apps/`, but it has its own GitHub repo, its own venv, its own dependency graph, and its own release cadence. The two halves are versioned independently and talk over `localhost:8765` via a FastAPI sidecar the Tauri app spawns.

This repo is a child of `ai-labs/` (see `../CLAUDE.md`) and a grandchild of `lossless-monorepo/` (see `../../CLAUDE.md`). Load the parent CLAUDE.md files when working anywhere under this tree — they cover the pseudomonorepo discipline, the `context-v/` convention, the ChromaDB-backed RAG, and the HARD STOP rules around repo relocation that apply here too.

## Repo layout

```
memopop-ai/
├── apps/
│   ├── memopop-native/        # Tauri 2 + SvelteKit desktop app — the substantive client
│   ├── memopop-orchestrator/  # Submodule — Python/LangGraph agent engine (separate GitHub repo)
│   ├── memopop-site/          # Astro marketing site
│   └── memopop-web-app/       # SvelteKit web app — placeholder for future hosted mode
│
├── packages/
│   └── shared-styles/         # Shared Tailwind config + design tokens
│
├── changelog/                 # Integration narrative (this repo level, NOT app-level)
├── context-v/                 # Specs, explorations, plans, agent-skills
├── package.json               # Bun workspaces root
└── README.md
```

## The orchestrator submodule boundary

`apps/memopop-orchestrator/` is a **separate GitHub repo**, mounted here as a submodule. Three reasons it lives apart:

1. **It predates the UI.** It is real Python software with its own CLI lineage, contributors, and changelog.
2. **The HTTP surface is general-purpose.** Any non-Python client (a notebook, curl, a future iOS app) can drive `generate_memo()` over HTTP — it is not memopop-specific.
3. **Firm-private content lives in nested submodules under `apps/memopop-orchestrator/io/<firm>/`** — alpha-jwc, alpha-partners, avalanche, humain, hypernova, etc. Those are private repos and stay private; never promote their content out into this repo.

When work touches the pipeline (agents, prompts, outlines, templates, brand-config schema, CLI scripts, agent-skills inside the orchestrator), do it inside the submodule and let the changes land in *its* changelog and commit history. When work touches the client surface (Tauri shell, Svelte UI, Astro site, the sidecar dispatcher in Rust, the integration story across the API boundary), do it here.

Bumping the orchestrator submodule pointer in this repo is appropriate when this repo's apps need to pin a newer orchestrator sha. Do it as a small `bump(submodule): apps/memopop-orchestrator → <sha>` commit, not bundled with a narrative integration commit.

## Changelog scope (this repo)

This repo's `changelog/` documents:

- Cross-app integration work (e.g., a new sidecar contract between the Tauri Rust dispatcher and the FastAPI sidecar)
- Tauri shell features (`memopop-native`)
- Astro site work (`memopop-site`) when not significant enough to live only in its app-level changelog
- Shared package changes (`packages/shared-styles/`)
- Workspace-level decisions: build scripts, lint config, Bun upgrades, monorepo restructuring
- Discovered patterns codified as `context-v/agent-skills/` entries

This repo's `changelog/` does **NOT** document:

- Anything inside the orchestrator submodule — that has its own changelog under `apps/memopop-orchestrator/changelog/`
- Anything inside a firm-private submodule (`apps/memopop-orchestrator/io/<firm>/`) — those live in each firm's own changelog
- Per-feature work that has its own home (`apps/memopop-native/changelog/` exists for Tauri shell foundation entries; small native-app features should land there first)

A pattern surfaced while editing client content (e.g., the `thesis-bleed-cleanup` skill that came out of a Panthalassa run) can land here as an agent-skill — the *pattern* is reusable across firms. The changelog entry references the skill, not the example that surfaced it. See `apps/memopop-orchestrator/CLAUDE.md` §"Changelog scope" for the symmetric rule one level down.

## Filename + frontmatter convention

`YYYY-MM-DD_NN.md`. YAML frontmatter: `title`, `lede`, `date_authored_initial_draft`, `date_last_updated`, `at_semantic_version`, `status`, `publish`, `category: Changelog`, `tags`, `authors`, optional `image_prompt`. Body starts with a fenced commit-message block ready to copy into `git commit -m`, then a prose section explaining *why* and *what's next*. See `changelog/2026-06-09_01.md` for a recent shape, and the `changelog-conventions` skill for the full rule set.

## Tech stack

| Layer             | Technology                                                                |
| ----------------- | ------------------------------------------------------------------------- |
| Package manager   | **Bun + workspaces** (not pnpm despite the lockfile being present at root) |
| Marketing site    | Astro                                                                     |
| Web app           | SvelteKit + Svelte 5 (runes)                                              |
| Desktop app       | Tauri 2 + SvelteKit (static adapter) + Svelte 5 (runes)                   |
| Desktop backend   | Rust — reqwest, tokio, tauri-plugin-shell, dialog/store/fs/opener plugins |
| Agent engine      | Python + LangGraph (lives in `apps/memopop-orchestrator/`)                |
| Styling           | Tailwind CSS via `@memopop/shared-styles`                                 |
| Deployment        | Vercel (sites); the desktop app installs locally                          |

There's a stray `pnpm-lock.yaml` at the workspace root. **Do not regenerate it or `pnpm install` here** — the workspace runs on Bun. If touching dependency state, use `bun install` / `bun add` / `bun remove`. The orchestrator submodule is Python and uses `uv` for its own deps (see `apps/memopop-orchestrator/CLAUDE.md`); never run `pip` in there.

## Working with the desktop app

```bash
# Dev — Tauri window + Vite + Rust hot-reload
bun run dev:native

# Marketing site dev
bun run dev:site

# Placeholder web app dev
bun run dev:app

# Workspace-wide quality gates
bun run lint
bun run typecheck

# Tauri release binary (depends on host OS)
bun run build:native
```

Architecture seam, in one line: **Webview ↔ Rust dispatcher ↔ FastAPI sidecar**. The Rust `SidecarManager` lazy-spawns `{repoPath}/.venv/bin/python -m src.server` from the user's locally-anchored orchestrator clone, polls `/healthz`, drops stale handles, and respawns fresh if the sidecar is dead, hung, or crashed. SSE goes **direct** from webview to FastAPI (CORS allowlist already covers Tauri origins), bypassing Rust because the dispatcher would only be reimplementing chunked HTTP forwarding. The full architecture diagram is in the README.

When testing the desktop app, the "anchor an orchestrator path" step in the onboarding journey is required before any `/memos*` call can succeed — the sidecar manager has no path to spawn against until then. For agent-side testing, point it at `apps/memopop-orchestrator/` inside this very repo.

## `context-v/` here

Same convention as elsewhere in the Lossless tree (see the `context-vigilance` skill). Three subdirectories carry most of the load:

| Subdir              | Role |
|---------------------|------|
| `specs/`            | Detailed UX/UI specs (e.g., `An-Onboarding-User-Journey-for-Memopop-Native.md`) |
| `explorations/`     | Architecture explorations and decision records (e.g., `Moving-an-Agent-Orchestrator-to-an-API.md`, `Separating-Retrieval-from-Generation-in-Agent-Pipelines.md`) |
| `plans/`            | Multi-phase implementation plans |
| `agent-skills/`     | Skills callable from any Claude Code session under this tree |

Existing agent-skills:

- `competitive-analysis/` — taxonomy for competitor classification in memos
- `market-capture-analysis/` — sizing/capture analytical pattern
- `timeline-scenario-analysis/` — scenario modelling pattern
- `thesis-bleed-cleanup/` — post-generation editorial pass that confines an over-invoked external thesis to its structural homes (Exec Summary + the section whose job is that thesis + Closing Assessment); came out of multi-agent-writer pipelines reaching for the same powerful external source independently

Two top-level files worth knowing:

- `MemoPop-Creative-Brief.md` — the product narrative the marketing site and onboarding copy descend from
- `Links-for-Corpus.md` — corpus reference URLs

## Architectural directions in flight

The orchestrator's CLAUDE.md captures the pipeline-side direction (retrieval/generation split, cross-run source curation, outline as taxonomy contract). The client-side analogues you'll trip over here:

1. **Transport seam is intentional.** The two-method `request()` / `subscribeEvents()` contract is what lets the orchestrator move from in-process to remote without rewriting the webview. Don't add a third method casually.
2. **Tauri origins are part of the CORS contract.** Any new FastAPI route the webview hits directly via SSE needs to inherit the existing allowlist; check `apps/memopop-orchestrator/src/server/` before assuming a new route Just Works.
3. **The Webview never sees the orchestrator's filesystem directly.** Artifact polling goes through the API. The OS folder picker exists to capture the orchestrator clone path *once*; everything else flows over HTTP.

## See also

- `README.md` — the human-facing overview, with the full architecture diagram and the marketing prose
- `apps/memopop-orchestrator/CLAUDE.md` — the pipeline side; the canonical home for memo-pipeline guidance
- `apps/memopop-native/changelog/` — Tauri shell foundation entries (`2026-04-27_01` through `_03`)
- `apps/memopop-native/README.md` — desktop app specifics
- `apps/memopop-site/README.md` — Astro site specifics
- `../CLAUDE.md` — `ai-labs/` parent guidance (uv discipline, MCP scope, branch tier model)
- `../../CLAUDE.md` — `lossless-monorepo/` root (HARD STOP relocation rules, pseudomonorepo discipline)
- The `context-vigilance`, `pseudomonorepos`, `changelog-conventions`, and `astro-knots` skills auto-load when relevant

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
