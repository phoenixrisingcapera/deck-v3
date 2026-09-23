# Deck AI Stack - Frontend Agent Guide

## Project Overview
SvelteKit 2 frontend for the Deck AI-powered pitch deck analysis platform. Minimalist, professional AI product design. Each screen has one clear primary action.

## Stack
- **Framework**: SvelteKit 2 + Svelte 5 (runes)
- **Styling**: Tailwind CSS + custom CSS tokens (`tokens.css`, `themes.css`)
- **Deployment**: Railway
- **Backend**: FastAPI (deck-backend-rescue)

## Architecture

### Core Directories
- `src/routes/` — SvelteKit file-based routing
- `src/lib/components/` — Reusable Svelte components
- `src/lib/api/` — API client layer (`deckServiceClient.ts`, `auth.ts`)
- `src/lib/stores/` — Svelte stores for app state
- `src/lib/services/` — Client-side service abstractions
- `src/lib/contracts/` — TypeScript types (mirrors backend schemas)
- `src/lib/server/` — Server-side load functions and utilities

### Key Design Decisions

1. **Dark theme default** — `#000` background, clean borders, single accent color (blue)
2. **Minimal copy** — One clear CTA per screen, no verbose explanations
3. **Provider-first** — Qwen/DashScope is the default LLM provider in all selectors
4. **No dead code** — Unused components/types are removed, not deprecated

### Page Routes

- `/` — Landing page (hero + feature cards + CTA)
- `/welcome` — Authenticated home (recent decks + upload CTA)
- `/upload` — File upload (single drag-and-drop zone)
- `/processing/{deckId}` — Processing status (phase indicators)
- `/dashboard/{deckId}` — Deck list or empty state
- `/smart-deck/{deckId}` — Smart Deck editor (LLM chat, slide viewer, due diligence)
- `/settings` — User settings (provider config, workspace)
- `/admin/provider-health` — Admin AI provider health dashboard

### AI Provider UI

Provider selector is in `WorkspaceAiProviderModal.svelte`:
- 4 tabs: Qwen — Alibaba Cloud, OpenAI, Anthropic, OpenRouter
- Qwen is the first tab and default selection
- Model options per provider:
  - **Qwen**: `qwen3.7-plus` (default), `qwen-plus`, `qwen-max`, `qwen-turbo`
  - **OpenAI**: `gpt-5`, `gpt-4.1`
  - **Anthropic**: `claude-sonnet-4-5`, `claude-opus-4-1`
  - **OpenRouter**: `openai/gpt-4o`, `anthropic/claude-sonnet-4.5`

#### Qwen Strategy (v1.0.0+)

The frontend supports the complete Qwen strategy:
- **Provider label**: "Qwen — Alibaba Cloud" (not "DashScope")
- **Default model**: `qwen3.7-plus` for generation
- **Backend routing**: The backend handles separate models for critique/repair/embedding
- **Token accounting**: Tracked server-side, not exposed to frontend
- **Health status**: Available via `/admin/llm/health` endpoint

### Smart Deck LLM Chat

`LlmChatCard.svelte` — Chat interface with:
- Model selector dropdown (all providers)
- Provider label derived from model prefix
- Default model: `qwen3.7-plus`

### API Layer

`deckServiceClient.ts` handles:
- Workspace summary fetch
- First deck upload (via bridge)
- Provider config save/load
- Public interest form submission

Auth is handled separately in `auth.ts` (session validation, sign-in, sign-up).

### CSS System

- `tokens.css` — Design tokens (colors, spacing, typography)
- `themes.css` — Light/dark theme variables
- `components.css` — Component-level styles
- `layout.css` — App shell, sidebar, topbar layout

## Running

```bash
# Install dependencies
npm install

# Dev server
npm run dev

# Build
npm run build

# Type check
npx svelte-check

# Lint
npm run lint
```

## Code Conventions

- Svelte 5 runes (`$state`, `$derived`, `$effect`) — no legacy `$:` reactive statements
- TypeScript strict mode
- Components use `class="..."` for Tailwind, not `<style>` blocks
- No emojis in UI copy
- No gradient overload — minimal, professional aesthetic
- All API calls go through `deckServiceClient.ts` or `auth.ts`

## Instant Deck investor MVP acceptance

- Use existing workflow polling for processing, draft, correction, verification
  and review-needed states. Never simulate completed stages or conflate incomplete
  review with a proven factual error in the user's source.
- Display owner-visible draft strings through Svelte escaping, never raw HTML.
  Draft text is explicitly unaccepted; only the published version with ready
  render proof enables the existing product print/PDF action.
- Verify the deployed upload, draft/review actions, refresh, direct navigation and
  export. Font candidate metadata does not prove the browser loaded those fonts.
