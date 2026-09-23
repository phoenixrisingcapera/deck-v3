# Deck V3 — AI Deck Platform + Product Suite

> The parent monorepo for the Deck AI platform and all companion products.
> **deck-v2** is the core (auth provider + deck engine); every other app routes through it.

---

## Architecture

```
deck-v3/                              # this repo
├── core/                             # the deck-v2 engine (auth provider)
│   ├── backend/                      # FastAPI + LangGraph + PostgreSQL
│   └── frontend/                     # SvelteKit 2 + Svelte 5
├── apps/                             # companion products
│   ├── augment-it/                   # multi-tenant AI data augmentation
│   ├── memopop-ai/                   # AI investment memo platform
│   ├── id-didi-sh/                   # didi.sh identity service (Elixir/Phoenix)
│   ├── flave/                        # agent-native document editor
│   ├── dididecks-ai/                 # slide-deck OS with client sites
│   └── context-vigilance-kit/        # corpus tooling + ChromaDB MCP
├── shared/                           # cross-cutting configs & specs
└── docs/                             # architecture docs
```

## Auth Model

**deck-v2 backend is the auth provider.** All apps authenticate through it:

1. User logs in via `core/backend/` (FastAPI auth endpoints)
2. Backend issues JWT tokens / session cookies
3. All companion apps validate tokens against the backend
4. Shared secrets live in Railway environment variables — one source of truth

The `id-didi-sh` identity service provides the cross-app SSO layer when apps need a unified `.didi.sh` session cookie. But the authority is always the deck-v2 backend.

## Services & Deployment (Railway)

All services deploy to the same Railway project:
https://railway.com/project/af0ad057-2bac-4a20-84d4-92999008271c

### Core (deck-v2)
| Service | Dir | Stack | Railway Config |
|---------|-----|-------|----------------|
| Backend | `core/backend/` | FastAPI + LangGraph + PostgreSQL + pgvector | `railway.toml` |
| Frontend | `core/frontend/` | SvelteKit 2 + Svelte 5 + Node adapter | `railway.toml` |
| Worker | `core/backend/` | Celery / background worker | `railway.worker.toml` |
| Renderer | `core/backend/` | PDF/PPTX rendering service | `railway.renderer.toml` |

### Companion Apps
| Service | Dir | Stack | Deploy Target |
|---------|-----|-------|---------------|
| **augment-it** | `apps/augment-it/` | 18 Svelte 5 MFs + 12 microservices + NATS + SurrealDB | Railway (multi-service) |
| **memopop-ai** | `apps/memopop-ai/` | Tauri 2 desktop + LangGraph backend + Astro site | Desktop + Vercel |
| **id-didi-sh** | `apps/id-didi-sh/` | Elixir/Phoenix + SQLite3 | Fly.io |
| **flave** | `apps/flave/` | Tauri 2 + Svelte 5 + Rust | Desktop |
| **dididecks-ai** | `apps/dididecks-ai/` | SvelteKit + Astro + 7 client sites | Railway |
| **context-vigilance-kit** | `apps/context-vigilance-kit/` | Python + ChromaDB + MCP | Local / Railway |

## Quick Start

### Prerequisites
- Python 3.11+ (with `uv`)
- Node 20+ (with `pnpm`)
- PostgreSQL 15+
- Docker (for containerized services)

### Core: deck-v2 Backend
```bash
cd core/backend
python -m venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
# Configure .env from Railway environment
cp .env.example .env
alembic upgrade heads && alembic -c alembic_ai.ini upgrade heads
python scripts/start_railway.py
```

### Core: deck-v2 Frontend
```bash
cd core/frontend
pnpm install
pnpm dev
```

### augment-it
```bash
cd apps/augment-it
pnpm install
docker compose up -d  # NATS + SurrealDB
pnpm dev
```

### memopop-ai
```bash
cd apps/memopop-ai
bun install
# Desktop app
cd apps/memopop-native && bun run tauri dev
# Orchestrator (LangGraph backend)
cd apps/memopop-orchestrator && python -m pip install -r requirements.txt
```

### id-didi-sh
```bash
cd apps/id-didi-sh
mix deps.get
mix ecto.setup
mix phx.server
```

### flave
```bash
cd apps/flave
pnpm install
pnpm dev
```

## LLM Providers

deck-v2 backend supports multiple providers (configured via `.env`):
- OpenAI (primary)
- Anthropic Claude
- Qwen / DashScope
- OpenRouter

## API Keys

All keys are managed through Railway environment variables. Locally, drop them in `.env` files (gitignored).

| Service | Used for |
|---------|----------|
| OpenAI | Text + image generation |
| Anthropic | Agent generation (Claude) |
| Qwen/DashScope | Alternative LLM |
| OpenRouter | Multi-model routing |

## Context Vigilance

Every project follows the context-v discipline:
- `context-v/specs/` — durable design contracts
- `context-v/explorations/` — experimental thinking
- `context-v/plans/` — implementation plans
- `context-v/reminders/` — stack preferences and conventions

Each project carries its own `context-v/` and `changelog/`.

## Branch Strategy

- `main` — production-ready
- `development` — current work
- Feature branches — `feat/...`, `fix/...`, `recovery/...`

## See Also

- [lossless-group/lossless-ai-labs](https://github.com/lossless-group/lossless-ai-labs) — the original pseudomonorepo where these projects started
- [Deck V2 (archived)](https://github.com/acpcareconnectdev-ui/deck-v2) — previous iteration with full archive branch
