# id-didi-sh

**The identity plane for the didi.sh service family** — one small, owned
auth service behind `id.didi.sh`. Create an account once (from inside
whichever app invited you), and you're signed in across **memos**
(memopop-ai), **decks** (dididecks-ai), and **augment-it** via a single
`.didi.sh` session cookie.

> **Status:** live and invite-only. Magic-link auth, entities, and BYOK
> credential lending are built and tested (106 tests). The canonical spec lives
> in the parent pseudomonorepo:
> [`ai-labs/context-v/specs/Id-Didi-Sh-Identity-Service.md`](https://github.com/lossless-group/lossless-ai-labs/blob/main/context-v/specs/Id-Didi-Sh-Identity-Service.md)

## Where this runs

**Three surfaces, three hosts.** They are deliberately separate; if you are
looking for "the didi.sh repo", it is all three of these plus this Elixir app.

| Surface | Lives at | Hosted on | Source |
|---|---|---|---|
| **The service** (this app) | **id.didi.sh** | **Fly.io** — app `id-didi-sh`, region `lax`, 1× shared-cpu-1x / 512MB | `lib/` |
| **Landing page** | **didi.sh** + `www` | **Vercel** — project `id-didi-sh` under the **`colearn-labs`** team, Root Directory `site` | `site/` |
| **Build log / docs** | lossless-group.github.io/id-didi-sh | **GitHub Pages** — `.github/workflows/pages.yml`, on push to `main` | `splash/` |

| | |
|---|---|
| **Language** | **Elixir / Phoenix 1.8** — the polyglot exception in the Lossless tree |
| **Database** | **SQLite file** via `ecto_sqlite3`/`exqlite`, on a Fly Volume (`idds_data` → `/data/id_didi_sh.db`). Migrations run **at boot**, not as a `release_command` |
| **Database (decided, not yet cut over)** | **Turso** — decision 2026-08-20, *"easy because I can log into it and fix things by hand."* See `context-v/plans/Storage-and-Backups-for-id-didi-sh.md`. **Credential storage is gated on this cutover** so no lent key is written to the unreplicated volume |
| **Registrar / DNS** | **Vercel** owns `didi.sh`; `id` is a CNAME to `id-didi-sh.fly.dev` |
| **Email** | **Swoosh** — Resend in prod, the Local adapter in dev (`/dev/mailbox`) |
| **Secrets** | Fly secrets. `SECRET_KEY_BASE`, `ID_SIGNING_JWK`, `CREDENTIAL_ENCRYPTION_KEY`, the Resend key |
| **No CDN, no Redis, no queue** | One container, one file, one process. That is the whole production topology |

## What it is

The didi.sh platform converges its three independently-built,
independently-deployed services on exactly two shared planes: this identity
service, and the didi agent. This repo is the first one.

The design follows a GTM constraint that shaped everything: **nobody
searches for a platform** — they search for a deck designer or a memo
generator. So each service is its own front door, and this service is
**headless-first**: accounts are created *from inside the app the user is
working in*, through an API the app calls from its own branded signup UI.
The service owns the pixels; id.didi.sh owns the record and the session.

## The contract

A consumer (any `*.didi.sh` service) ever sees three artifacts:

1. **A cookie** — `didi_session`, `Domain=.didi.sh`, `HttpOnly`, `Secure`,
   `SameSite=Lax`. The value is a short-lived (~12h) **EdDSA-signed token**
   verified *locally* by every service: signature + `exp`, no network call
   per request. If this service is briefly down, existing traffic keeps
   flowing — only new logins and refreshes wait.
2. **A JSON API** at `id.didi.sh/api/*` — magic-link issue/redeem, invite
   redeem (the only account-creation path; invite-only, no self-serve
   signup, no passwords), OAuth start/callback, session refresh/logout,
   `GET /api/me` for org + role claims.
3. **A public key set** at `/.well-known/jwks.json`.

Behind the contract: a 30-day rolling server-side session is the refresh and
revocation authority; tenancy is the **flat entity model** below (the earlier
domain-as-id org model is superseded — an `organizations` table still exists
alongside `entities`, which is a known duplication, see
`context-v/issues/Entities-and-Organizations-Both-Exist.md`); the stable person
id is **`didi_id`** (UUIDv7), minted here and only here. Only this service mints
sessions — consumers verify, never sign.

## Entities — how collaboration is described

**The tenancy model is flat, and that is the whole design.**

An **entity** is any place work happens. It has a `kind`, and the kind is a
**display label that confers no structure and no powers**:

```
organization   workspace   project   team
```

There is no hierarchy. `entities` has **no `parent_id`** — a schema assertion
in the test suite fails if anyone adds one. An "organization" entity is not a
parent of a "project" entity, because there are no parents. Adding a new kind
is therefore free: `team` was added because it is a word people already use,
and it cost one line.

### Why flat

The obvious model is org → workspace → project, membership inherited downward.
It cannot describe how anybody actually works:

- The operator holds accounts for **palmer-ai** under a **humain.vc** address.
- One person belongs to many organizations — sometimes with their email at that
  domain, sometimes not, often as an admin.
- And the general case, which is every startup: **service providers, advisors,
  investors.**

Derive membership from an email domain and you have built a system that
**structurally cannot express an advisor.** So:

> **Membership is an explicit grant, and the granted person's address is
> irrelevant to it.**

There is no `default_domain` column and no auto-join. Both existed briefly and
were deleted; the guard is now that the field does not exist. Invite redemption
is the only account-creation path — no self-serve signup, no passwords, ever.

### Removal never cascades

Removing someone from one entity removes exactly that one membership. Nothing
else changes, because nothing contains anything else. This surprises people, so
the API says it out loud: every removal response carries `also_member_of` — the
list of places that person still reaches — and any UI presenting removal must
show it. Telling someone "removed" when they still have access is the failure
this prevents.

### Roles

`superuser` · `org_owner` · `org_admin` · `editor` · `viewer`, per membership
row. `effective_role/2` consults exactly two things: a live loan (see below)
and the membership row. Never a domain.

## Keys — bring your own, lend it, take it back

The feature the service exists to make safe. **The person holding the credit
card is frequently not on the project.**

A partner expenses the OpenAI account; the analysts burning the tokens joined
the workspace last week and rotate off next month. The usual answers are a
shared doc, an env var somebody screenshots, or adding the partner to a project
they have no business being in so the billing works.

Instead: **paste a key once, lend it to one or more entities, and the people
there can spend it without ever being able to read it.**

### The one line that governs everything

> A **borrower** — a human — never sees a credential's value. Only a
> **registered server-side app** can resolve one to plaintext.

`RequireApp` does not merely ignore a session cookie on the resolve path; it
**rejects** the request with `app_credential_required`. A test sends a valid app
token *and* a valid session cookie and asserts `403`. If a browser could reach
plaintext by carrying a cookie, the invariant would be broken by the transport
rather than by anyone's intent.

The moment a borrower can read the key, lending has become giving — and giving
is not something you can take back.

### The shape

```
person ──owns──> credential ──cascade──> loan ──> entity
                     │                              │
                     └────── usage ─────────────────┘
                          (owner-only meter)
```

One **lending act** creates one **cascade** and one **loan per entity**, so you
name an organization, a workspace and a project in a single gesture — and can
pull the key from all of them at once, or from one, leaving the rest live.

**A loan is live only if** the loan has not ended, its cascade has not ended,
the cascade has not expired, and the credential is not revoked. Four independent
ways to die, resolved in **one query**, so no caller can forget a condition it
never sees.

- **Encrypted at rest** — AES-256-GCM via `cloak_ecto`. A test reads the raw
  SQLite column with `Repo.query`, bypassing the Ecto type that would decrypt
  it, and asserts the secret is not in those bytes.
- **`render/1` is an allowlist**, built by naming safe fields rather than
  dropping unsafe ones — so a column added later is invisible until someone
  deliberately exposes it. Only `last_four` ever leaves, because a human has to
  tell two keys apart without seeing either.
- **Revocation keeps the row.** The key stops working; the usage history — the
  record of what your card paid for — stays.
- **Lending confers admin.** `effective_role/2` returns `:admin` for anyone with
  a live loan, membership row or not.
- **Caps are enforced where spend happens**, in `resolve/4`. Exceeding one
  returns `402`.
- **Usage is owner-only.** Not even an entity admin may read it; showing
  per-caller detail would tell them who used what without those people agreeing
  to it.
- **Consequences are named in the API**, not just the UI: lending returns a
  notice saying this reaches *everyone in these entities, including anyone added
  later* — so every client says it, including ones nobody has written yet.

### The human surface

**`/keys`** — a LiveView for someone who will paste one value into one labelled
field and will not open a terminal. Paste a key, name a place if you are in none
yet, tick where it goes, confirm. Each key lists where it currently reaches, and
each of those carries its own take-back. There is no reveal toggle and no masked
echo — the obvious feature request and the wrong answer.

## API

Everything a consumer touches. **No shared client package, on purpose** —
verification snippets (TS `jose`, Python `PyJWT`, ~30 lines) ship as
documentation to copy in.

| Method | Route | What |
|---|---|---|
| `GET` | `/.well-known/jwks.json` | public keys — verify locally, no network call per request |
| `POST` | `/api/magic-links` | issue. Always `202`; never reveals whether an account exists |
| `POST` | `/api/magic-links/redeem` | redeem → session cookie |
| `POST` | `/api/session/refresh` | rolling 30-day server-side session |
| `DELETE` | `/api/session` | log out |
| `GET` | `/api/me` | identity + memberships + roles |
| `GET`·`POST` | `/api/entities` | list / create |
| `GET` | `/api/entities/:id` | one entity |
| `GET`·`POST` | `/api/entities/:entity_id/members` | list / add |
| `DELETE` | `/api/entities/:entity_id/members/:didi_id` | remove — response carries `also_member_of` |
| `GET`·`POST` | `/api/credentials` | list (never the value) / store |
| `DELETE` | `/api/credentials/:id` | revoke; keeps the row and its history |
| `GET` | `/api/credentials/:credential_id/usage` | the meter — **owner only** |
| `POST` | `/api/credentials/:credential_id/cascades` | lend to one or more entities |
| `DELETE` | `/api/cascades/:id` | take it back everywhere |
| `DELETE` | `/api/cascades/:id/loans/:entity_id` | take it back from one place |
| `POST` | `/api/internal/resolve` | **the only path returning plaintext.** Registered apps only; rejects sessions |

Browser surfaces: `/` (service datasheet), `/access` (magic-link landing —
needs `?token=`, it is not a login form), `/keys` (the lender's surface).

## Stack

**Elixir / Phoenix** — deliberately the polyglot exception in the Lossless
tree, and safe here specifically: the headless contract means no consumer
imports this service's code, so the implementation language is invisible by
design.

| Piece | Choice | State |
|---|---|---|
| Framework | Phoenix 1.8.8, LiveView 1.2 | built |
| Serving | Bandit; multi-stage Dockerfile → OTP release | built |
| Store | Ecto + `ecto_sqlite3`/`exqlite`, one file on a Fly Volume | built |
| Token signing | JOSE (erlang-jose), **EdDSA / Ed25519** | built |
| Encryption at rest | **`cloak_ecto`**, AES-256-GCM behind `IdDidiSh.Vault` | built |
| Email | Swoosh — Resend in prod, Local adapter in dev | built |
| CSS | Tailwind 4 + daisyUI (both ship with `mix phx.new`), driven by `assets/css/theme.css` | built |
| Icons | heroicons, pinned to the tag | built |
| HTTP client | `req` | built |
| Store → **Turso** | `ecto_libsql`, unofficial Rust NIFs | **decided, not cut over** |
| OAuth client flows | Assent (GitHub, Google Workspace, LinkedIn) | **not built** — not in `mix.exs` yet |
| Admin console | LiveView at `/admin` | **not built** — no such route today |
| Litestream → R2 | — | **moot.** Turso subsumes it; see the storage plan |

The dependency list is short on purpose. There is no CDN, no Redis, no
background-job queue and no message bus: production is one container talking
to one file.

## Consumers

| Service | Adapter |
|---|---|
| augment-it (first) | TS verify on the workspace WS gate; replaces the flat token map. First real users: the reach-edu and humain-vc client teams |
| decks (dididecks-ai) | Astro middleware port of the calmstorm gate |
| memos web (memopop-ai) | Same TS adapter |
| memos desktop (Tauri) | System-browser flow → one-time code exchange → keychain-held bearer token, verified by the FastAPI sidecar via PyJWT + JWKS |

Verification snippets (TS `jose`, Python `PyJWT`, ~30 lines each) ship as
documentation for consumers to copy in — **no shared package, on purpose.**

## Implementation increments

- [x] **1 — Walking skeleton** *(2026-07-06)*. Schema, Ed25519 keypair + JWKS,
      magic-link issue → redeem → `didi_session` → `/api/me` → refresh →
      logout. Proven live by `scripts/prove-skeleton.sh`.
- [x] **2 — Entities and invites** *(2026-08-20)*. Flat entity model,
      memberships, HTTP endpoints, the removal disclosure, and invites that
      reach strangers by email and attach on redeem.
- [x] **3–7 — Credentials and lending** *(2026-08-21)*. Encryption at rest,
      cascades and loans, admin earned by lending, the app-only resolve path,
      cap enforcement, the owner-only meter, and `/keys` — a human can lend a
      key without a terminal.
- [x] **Design system** *(2026-08-21)*. The app wears the credential posture:
      three modes (dark / light / vibrant) driven from `assets/css/theme.css`.
- [ ] **Turso cutover.** Decided 2026-08-20. **Credential storage is gated on
      it** — the code is written and deliberately not deployed, so no lent key
      reaches the unreplicated Fly volume.
- [ ] **First consumer.** augment-it's TS verify adapter + access panel.
- [ ] **OAuth.** GitHub → Google Workspace → LinkedIn. Spec amended 2026-08-20
      to make didi.sh a full authorization server (OAuth 2.1 + OIDC).
- [ ] **Admin console.** Invites, entities, memberships, sessions, event log.
- [ ] **Consumers two and three.** decks middleware, memos web, the Tauri
      device-exchange flow.

## Development

First-time setup (macOS):

```sh
brew install elixir                # Elixir ≥ 1.18 / OTP 27 (asdf works too)
mix archive.install hex phx_new    # the Phoenix project generator
```

Then:

```sh
mix setup                                  # deps + db + migrations + assets
mix id.seed alice@example.com "Alice"      # invite stand-in until increment 3
mix phx.server                             # http://localhost:4000
./scripts/prove-skeleton.sh                # the increment-1 acceptance proof
mix test                                   # the suite
```

Local dev uses a host-only cookie on `localhost` and an auto-generated dev
keypair (`priv/keys/`, gitignored); the `.didi.sh` cookie is only meaningful
deployed. `mix id.gen.keypair` produces the production `ID_SIGNING_JWK`.
Dev-only: magic-link responses echo the raw token (`echo_login_tokens`) so
the prove script runs without reading the Swoosh mailbox at `/dev/mailbox`.

Secrets (signing keypair, R2 credentials, email API key, OAuth client
secrets) come from the environment — never committed, never in this repo.

## Testing

The suite is ExUnit (Elixir's standard test framework — no extra deps):

```sh
mix test                                                            # the whole suite
mix test test/id_didi_sh_web/controllers/identity_contract_test.exs # just the identity contract
```

Beyond the walking-skeleton flow (`auth_flow_test.exs`), the load-bearing
file is **`identity_contract_test.exs`** — it pins the exact contract that
augment-it's fake id-plane test fixture mimics: a minimal JWT (`sub`/`sid`
only, no tenancy baked in), the JWKS key that verifies a freshly-minted
token, `/api/me` memberships, and `/api/session/refresh` re-minting an
expired-but-authentic token while the session row lives (refusing once it's
dead). If this contract drifts, augment-it's transport/session tests are
testing a fiction — so this suite is what keeps the fake honest.

This is **Group A** of the cross-repo test story documented in augment-it's
[`Corpora-Builder-Harmony-Test-Registry`](../augment-it/context-v/specs/Corpora-Builder-Harmony-Test-Registry.md);
augment-it's `pnpm test:all` runs this suite too when `mix` is on the path.

## Deploy (Fly.io → id.didi.sh)

The deploy artifacts are committed: `fly.toml` (lax region, port 8080, a
Fly Volume at `/data` for the libSQL file, migrations run **at boot** —
never as a `release_command`, which runs on an ephemeral machine without
the volume) and a release `Dockerfile` generated by
`mix phx.gen.release --docker`, pinned to the repo's toolchain.

One-time setup:

```sh
brew install flyctl                # the CLI (installs the `fly` command)
fly auth login                     # browser auth

fly apps create id-didi-sh
fly volumes create idds_data --region lax --size 1 -a id-didi-sh

# Secrets — NEVER plaintext env vars, never committed:
fly secrets set -a id-didi-sh \
  SECRET_KEY_BASE="$(mix phx.gen.secret)" \
  ID_SIGNING_JWK="$(mix id.gen.keypair | sed -n 's/^{/{/p' | head -1)"
```

Deploy + wire the domain:

```sh
fly deploy                          # builds remotely from the Dockerfile
fly certs add id.didi.sh -a id-didi-sh

# DNS lives in Vercel (the didi.sh registrar):
vercel dns add didi.sh id CNAME id-didi-sh.fly.dev
```

Verify: `curl https://id.didi.sh/.well-known/jwks.json` returns the
public key, and `scripts/prove-skeleton.sh` runs against
`BASE=https://id.didi.sh` (dev-token echo is off in prod, so the
magic-link step requires a real mailbox — increment 3's invites are the
production onboarding path).

Notes: `auto_stop_machines` is off on purpose — the identity plane must not
cold-start under JWKS and refresh traffic. **Litestream→R2 is moot** — the
2026-08-20 decision to move to Turso subsumes it, and backups become a
checkbox (confirm the PITR window) rather than a project. Until the cutover,
Fly volume snapshots are the recovery story, which is precisely why credential
storage is gated on it.

## Lineage

This service supersedes the earlier plan to extract a vendored
`lossless-auth-core` package. Prior art it draws on:

- [`Shared-Auth-for-Applied-AI-Labs`](https://github.com/lossless-group/lossless-ai-labs/blob/main/context-v/explorations/Shared-Auth-for-Applied-AI-Labs.md) — the architecture source (pathways, org model, roles, scale posture)
- [`Didi-sh-One-Login-One-Agent-Three-Services`](https://github.com/lossless-group/lossless-ai-labs/blob/main/context-v/explorations/Didi-sh-One-Login-One-Agent-Three-Services.md) — the platform frame and the GTM headless requirement
- `dididecks-ai` → `Calmstorm-Auth-Inventory` — audited session/token/invite mechanics (ported as semantics, not code)
- `astro-knots/sites/fullstack-vc` — three-provider OAuth + account-linking merge chain (users imported at launch; code ported as reference)

---

Part of [The Lossless Group](https://github.com/lossless-group)'s `ai-labs`
pseudomonorepo. Every repo here keeps a `context-v/` (living documentation)
and a `changelog/` (ship log) — start there.
