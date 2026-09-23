# Agent instructions for `id-didi-sh`

**This repo is the polyglot exception in the Lossless tree: Elixir/Phoenix,
not TypeScript.** That is a deliberate, argued decision — see the canonical
spec before proposing a stack change:
`../context-v/specs/Id-Didi-Sh-Identity-Service.md` (in the `ai-labs`
parent). This repo's own `context-v/` holds implementation-local docs only;
the spec of record stays at the parent level.

## Load-bearing invariants (do not weaken casually)

1. **The contract is three artifacts** — the `didi_session` cookie
   (EdDSA-signed, `Domain=.didi.sh`), the JSON API under `/api`, and the
   JWKS endpoint. Consumers depend on nothing else. Changing any of these is
   a cross-service breaking change; flag it, don't slip it in.
2. **Invite-only, no passwords.** The ONLY account-creation path is invite
   redemption. Never add a self-serve signup endpoint or a password column —
   both are explicitly out of scope per the spec.
3. **Only this service mints sessions.** Consumers verify with the public
   key; the signing key never leaves this service. Symmetric algorithms
   (HS256) are forbidden for session tokens — any verifier could mint.
4. **Headless-first.** Consumer apps own the signup/login pixels and call
   the API. Do not grow hosted login pages beyond the minimal `/access`
   fallback and the OAuth callback hop.
5. **No shared packages with consumers.** Verify snippets are documentation
   that consumers copy in. Do not publish a client library — the
   no-shared-code property is what makes the Elixir choice safe.
6. **Store is a libSQL file** (`exqlite` compiled against libSQL), backed up
   via Litestream→R2. Turso-remote is a named future upgrade, not a
   dependency to introduce now.

## Working here

- **Language conventions:** idiomatic Elixir; `mix format` before commit;
  Ecto migrations are append-only once pushed.
- **Secrets** come from the environment only (signing keypair, R2 creds,
  email API key, OAuth client secrets). Never commit a secret; never write
  one to `context-v/` or `changelog/`.
- **Branch:** `main` is the working branch of this repo (mounted as a
  submodule of `ai-labs`, which is also on `main`).
- **Universal directories:** keep `context-v/` and `changelog/` current per
  the tree-wide conventions (`changelog-conventions`, `context-vigilance`
  skills). Ship notes go in `changelog/` with the titled filename pattern.

## See also

- `../CLAUDE.md` — ai-labs parent instructions (Chroma corpus, skills sync)
- `../context-v/specs/Id-Didi-Sh-Identity-Service.md` — the spec of record
- `../context-v/explorations/Didi-sh-One-Login-One-Agent-Three-Services.md`
  — the platform frame (GTM constraint, trust boundary, deploy topology)

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
