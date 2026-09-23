# MemoPop AI

AI-powered investment memo generation for venture capital firms.

This is the workspace for MemoPop's **client surface** — the desktop app, the marketing site, and (eventually) a hosted web app. The agent engine that does the actual memo generation lives in a sibling repo: [`investment-memo-orchestrator`](../investment-memo-orchestrator/). Together they make a complete product, but they're versioned independently.

## Monorepo Structure

```
memopop-ai/
├── apps/
│   ├── memopop-native/      # Tauri 2 desktop app — the substantive client
│   ├── memopop-site/        # Astro marketing site
│   └── memopop-web-app/     # SvelteKit web app (placeholder; hosted-mode home)
│
├── packages/
│   └── shared-styles/       # Tailwind config & design tokens shared across apps
│
├── changelog/               # Monorepo-level changelog (integration narrative)
├── context-v/               # Specs, explorations, plans, reminders
└── README.md
```

## The Other Half: `investment-memo-orchestrator`

The orchestrator is a Python multi-agent system (LangGraph + 30+ specialized agents) that generates the actual memos. It exposes a FastAPI HTTP sidecar that `memopop-native` drives over `localhost:8765`.

It lives in a separate repo for two reasons:

1. **The orchestrator predates the UI.** It's real Python software with its own venv, dependencies, CLI lineage, and contributors. memopop-ai's apps consume it; they don't vendor it.
2. **The HTTP surface is general-purpose.** Any non-Python client (a notebook, curl, a future iOS app) can drive `generate_memo()` over HTTP. It's not a memopop-specific feature.

The Tauri app spawns the FastAPI sidecar as a child process pointed at the user's locally-cloned orchestrator. See `context-v/explorations/Moving-an-Agent-Orchestrator-to-an-API.md` for the design rationale.

## Quick Start

### Prerequisites

- **Bun** — `curl -fsSL https://bun.sh/install | bash`
- **For the desktop app**: Rust toolchain (`rustup`), plus the orchestrator cloned and `uv pip install -e .`'d at a sibling path. See its README for orchestrator setup.

### Install workspace deps

```bash
bun install
```

### Run the desktop app (memopop-native)

```bash
bun run dev:native
```

Window opens, the outline gallery renders once you've anchored an orchestrator path. The first action that needs Python (POST /memos) auto-spawns the FastAPI sidecar; subsequent calls reuse it.

To produce a release binary (`.app` / `.dmg` / `.exe` / `.AppImage`, depending on host OS):

```bash
bun run build:native
```

### Run the marketing site

```bash
bun run dev:site
```

### Run the web app (placeholder)

```bash
bun run dev:app
```

## Tech Stack

| Layer             | Technology                                                                |
| ----------------- | ------------------------------------------------------------------------- |
| Package manager   | Bun + workspaces                                                          |
| Marketing site    | Astro                                                                     |
| Web app           | SvelteKit + Svelte 5 (runes)                                              |
| Desktop app       | Tauri 2 + SvelteKit (static adapter) + Svelte 5 (runes)                   |
| Desktop backend   | Rust — reqwest, tokio, tauri-plugin-shell, plugins (dialog, store, fs, opener) |
| Agent engine      | Python + LangGraph (lives in sibling `investment-memo-orchestrator`)      |
| Styling           | Tailwind CSS (shared config)                                              |
| Deployment        | Vercel (sites); the desktop app installs locally                          |
| Auth (future)     | SuperTokens (Railway)                                                     |
| Database (future) | Baserow (Railway)                                                         |

## Apps

### `memopop-native` — Tauri 2 desktop app

The substantive client. Drives the orchestrator's HTTP API end-to-end:

- **Onboarding journey.** Anchor an orchestrator clone via the OS folder picker → browse outline templates from `templates/outlines/` → optionally drill into outline detail → create a firm (snake_case slug + idempotent `.gitignore` handling) → capture deal details (URL, optional deck PDF, mode).
- **Job runtime.** Click Generate and the gallery is replaced by a fullscreen `JobView` with three live panes:
  - **PhaseChecklist** (left) — ten ordered phases derived from structured milestone events streaming from the orchestrator.
  - **LogStream** (center) — terminal-dark, blinking purple cursor at the tail. Capped at 1,000 rendered / 2,000 stored with rAF-throttled scroll.
  - **ArtifactBrowser** (right) — polls the orchestrator every 3s for new files, flashes them green on arrival.
- **Stop button.** Red `⏹ Stop` in the JobView header. Routes through the Rust dispatcher directly to `SidecarManager::shutdown()` — bypasses Python entirely so it works when the sidecar is wedged in a retry loop.
- **Self-healing sidecar.** The Rust `SidecarManager` lazy-spawns `{repoPath}/.venv/bin/python -m src.server`, polls `/healthz`, and on every subsequent call probes health first — dropping stale handles and respawning fresh if the sidecar is dead, hung, or crashed.

See `apps/memopop-native/changelog/` for the foundation entries (2026-04-27_01 through _03) and this monorepo's `changelog/` for the integration story.

### `memopop-site` — Astro marketing site

Marketing copy, changelog aggregation, thought-leadership, documentation. Built with Astro for SEO and zero-JS-by-default performance.

### `memopop-web-app` — SvelteKit web app (placeholder)

Reserved for the future hosted-mode home, when the FastAPI sidecar lives behind a deployed URL instead of in-process. Not yet wired into the user journey.

## Shared Packages

### `@memopop/shared-styles`

Tailwind config and design tokens shared across Astro and Svelte apps.

```js
// In your app's tailwind.config.js
import sharedConfig from '@memopop/shared-styles/tailwind';

export default {
  presets: [sharedConfig],
  content: ['./src/**/*.{astro,html,js,svelte,ts}'],
};
```

## Architecture (memopop-native specifically)

```
┌─────────────────────────────────────────────────────────────────┐
│  Webview (Svelte 5 runes UI inside a Tauri window)              │
│   • OutlineGallery · OutlineDetail · FirmCreationModal          │
│   • DealCreationModal · JourneyBreadcrumbs                      │
│   • JobView: PhaseChecklist  ·  LogStream  ·  ArtifactBrowser   │
└────┬───────────────────────────────────────────┬────────────────┘
     │ JSON via Tauri invoke (`api_dispatch`)    │ EventSource (SSE)
     ▼                                           │
┌─────────────────────────────────────────┐      │
│  Rust dispatcher (this repo)            │      │
│   • SidecarManager: spawn / heal / kill │      │
│   • forward /memos* via reqwest         │      │
│   • POST /actions/stop-sidecar (direct) │      │
└────┬────────────────────────────────────┘      │
     │ HTTP localhost:8765                       │
     ▼                                           │
┌─────────────────────────────────────────┐      │
│  FastAPI sidecar                        │◄─────┘
│  (in sibling investment-memo-orchestrator)
│   • generate_memo() in a worker thread  │
│   • JobEventBus → SSE                   │
│   • MilestoneExtractor (~30 patterns)   │
│   • Persisted logs on every run end     │
└─────────────────────────────────────────┘
```

The Transport seam has exactly two methods — `request()` for JSON request/response, `subscribeEvents()` for SSE streaming. SSE goes **direct** from the webview to the FastAPI sidecar (the FastAPI CORS allowlist already covers Tauri origins), bypassing Rust because the dispatcher would only be reimplementing chunked HTTP forwarding.

## Development

### Changelogs

- `changelog/` (this repo, monorepo-level) — integration narrative across apps and the orchestrator boundary.
- `apps/memopop-native/changelog/` — Tauri shell foundation entries plus per-feature work.
- The marketing site aggregates entries via the GitHub raw API.

Convention: `YYYY-MM-DD_NN.md`, YAML frontmatter (`title`, `lede`, dates, `at_semantic_version`, `status`, `category`, `tags`, `image_prompt`), and a fenced commit-message block at the top ready to copy into `git commit`.

### Specs, explorations, plans

`context-v/` is the home for designs and decision records:

```
context-v/
├── specs/          # Detailed UX/UI specs (e.g., An-Onboarding-User-Journey-for-Memopop-Native.md)
├── explorations/   # Architecture explorations (e.g., Moving-an-Agent-Orchestrator-to-an-API.md)
├── plans/          # Multi-phase implementation plans
└── reminders/      # Conventions and gotchas
```

### Quality gates

```bash
# Workspace-wide
bun run lint        # Lint all workspaces
bun run typecheck   # Type-check all workspaces

# Desktop app specifically
bun --filter memopop-native check     # Svelte/TS type-check
cargo check --manifest-path apps/memopop-native/src-tauri/Cargo.toml
```

## Similar Services

MemoPop is open source. If you'd rather not run a Python library and the command line, several commercial vendors operate in this space — including:

- [DataroomHQ](https://www.dataroomhq.ai/) — AI-powered virtual data room for fundraising that generates investor-grade materials (data decks, financial analysis, investment memos) and tracks investor engagement.

The orchestrator README keeps a fuller, categorized list of comparable platforms: see [Similar Services](apps/memopop-orchestrator/README.md#similar-services).

## License

MIT
