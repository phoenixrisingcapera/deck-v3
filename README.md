# Deck V3 — AI Deck Platform

> Unified platform: **api/** (Python/FastAPI backend, the auth provider) + **apps/instantdeck/** (SvelteKit frontend)

---

## Architecture

```
deck-v3/
├── api/                    # Unified Python backend (FastAPI + PostgreSQL + LangGraph)
│   ├── app/                # All Python services: auth, decks, AI, workers
│   ├── alembic/            # Core DB migrations
│   ├── alembic_ai/         # AI/Vector DB migrations
│   └── railway.toml        # Railway deploy config (Docker)
└── apps/
    ├── instantdeck/        # SvelteKit 2 + Svelte 5 frontend
    └── ...                 # Future: augment-it, memopop-web, flave-web, etc.
```

**Auth model:** `api/` is the auth provider. All apps authenticate through it via JWT tokens and session cookies.

---

## Quick Start

### Prerequisites
- Python 3.11+ (with `uv`)
- Node 20+ (with `pnpm`)
- PostgreSQL 15+
- Docker (for containerized services)

### 1. Start PostgreSQL
```bash
# Ensure PostgreSQL is running
pg_isready
```

### 2. Set up the API (backend)
```bash
cd api

# Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and OPENAI_API_KEY at minimum

# Run database migrations
python -m alembic upgrade heads
python -m alembic -c alembic_ai.ini upgrade heads

# Start the API
python scripts/start_railway.py
# API runs on http://localhost:8080
```

### 3. Set up Instant Deck (frontend)
```bash
cd apps/instantdeck

# Install dependencies
pnpm install

# Configure environment (already points to localhost:8080)
cp .env.example .env.local

# Start the dev server
pnpm dev
# Frontend runs on http://localhost:5173
```

### 4. Verify
- Frontend: http://localhost:5173
- API health: http://localhost:8080/health
- Frontend health (checks backend): http://localhost:5173/api/health

---

## Railway Deployment

Both services deploy to the same Railway project via `railway.json` at the root.

### Quick Deploy

1. Push to `main` on your GitHub repo
2. In Railway, click **Deploy from GitHub** and select this repo
3. Railway reads `railway.json` and creates two services automatically:
   - **Deck V3 API** (from `api/`)
   - **Deck V3 Frontend** (from `apps/instantdeck/`)
4. Add a **PostgreSQL** database in Railway (same project)
5. Set environment variables (see below)
6. Deploy!

### API Service Environment Variables
Set these on the "Deck V3 API" service in Railway:
```
DATABASE_URL=<Railway auto-set from PostgreSQL>
AI_DATABASE_URL=<leave empty for same DB, or set separate AI DB>
AUTH_SECRET_KEY=<random 32+ byte string>
OPENAI_API_KEY=<your OpenAI API key>
ALLOWED_ORIGINS=https://your-frontend-domain.com
CORS_ORIGIN=https://your-frontend-domain.com
PUBLIC_SIGNUP_ENABLED=true
```

### Instant Deck Service Environment Variables
Set these on the "Deck V3 Frontend" service in Railway:
```
DECK_AISTACK_BACKEND_URL={{ services.api.url }}
PUBLIC_INSTANT_HTML_ENABLED=false
```
Railway's `{{ services.api.url }}` variable resolves to the API service's internal URL automatically.

### Railway Project Structure
```
Your Railway Project
├── PostgreSQL Database (auto-provisioned)
├── Deck V3 API (api/ → Docker)
│   ├── Port: 8080
│   ├── Health: /api/health/product-ready
│   └── Pre-deploy: alembic migrations
└── Deck V3 Frontend (apps/instantdeck/ → Docker)
    ├── Port: 3000
    ├── Health: /
    └── Depends on: API service
```

---

## Database

### Core database (`DATABASE_URL`)
Users, workspaces, decks, slides, billing, auth sessions, workflow jobs, exports.

### AI database (`AI_DATABASE_URL`)
Vector embeddings (pgvector), AI runs, telemetry, agent learning memories. Can be the same as core database.

### Migrations
```bash
cd api

# Core migrations
python -m alembic upgrade heads

# AI/Vector migrations
python -m alembic -c alembic_ai.ini upgrade heads

# Create new migration
python -m alembic revision --autogenerate -m "description"
python -m alembic -c alembic_ai.ini revision --autogenerate -m "description"
```

---

## API Routes

| Prefix | Purpose |
|--------|---------|
| `/api/auth/*` | Authentication (sign-in, sign-up, reset-password, logout) |
| `/api/health` | Health checks |
| `/api/decks/*` | Deck CRUD operations |
| `/api/instant-deck/*` | Instant deck generation |
| `/api/smart-deck/*` | Smart deck AI features |
| `/api/slides/*` | Slide operations |
| `/api/products/*` | Product-specific routes |
| `/api/workspace/*` | Workspace management |

---

## LLM Providers

| Provider | Status | Default Model |
|----------|--------|---------------|
| OpenAI | **Active (default)** | gpt-5-2025-08-07 |
| Qwen/DashScope | Available (explicit) | qwen3.7-plus |
| Anthropic | Disabled | claude-sonnet-4-5 |
| OpenRouter | Disabled | openai/gpt-4o |

---

## Roadmap

### Phase 1 ✅ — Instant Deck + API (this branch)
- Unified backend (`api/`) as the auth provider
- SvelteKit frontend (`apps/instantdeck/`)
- Railway deployment for both services

### Phase 2 — Identity Migration (id-didi.sh → api/)
- Rewrite Elixir/Phoenix identity service in Python
- Move to `api/app/identity/`
- SQLite3 → PostgreSQL migration
- JWT signing, JWKS, credential management

### Phase 3 — Augment-it Migration
- 12 NATS microservices → Python/FastAPI in `api/`
- SurrealDB → PostgreSQL
- JSON file stores → PostgreSQL tables
- Svelte 5 MF apps → SvelteKit routes

### Phase 4 — Desktop Apps → Web
- memopop-ai → SvelteKit web routes + LangGraph orchestrator in api/
- flave → SvelteKit web routes (CodeMirror 6 editor)

### Phase 5 — Remaining Integrations
- Context Vigilance Kit → Python service module in api/
- DidiDecks client sites → tenant-scoped SvelteKit layouts

---

## See Also

- [lossless-group/lossless-ai-labs](https://github.com/lossless-group/lossless-ai-labs) — the original pseudomonorepo
- [Deck V2 (archived)](https://github.com/acpcareconnectdev-ui/deck-v2) — previous iteration (archive branch: `archive/pre-pivot`)
