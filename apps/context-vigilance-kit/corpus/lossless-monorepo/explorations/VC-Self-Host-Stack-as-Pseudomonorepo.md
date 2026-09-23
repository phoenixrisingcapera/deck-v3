---
title: VC Self-Host Stack as a Pseudomonorepo (and a Paired Study)
lede: Two orphan dirs, `twenty-crm/` and `twenty-deployment/`, hint at a deployable
  stack a VC firm could self-host instead of renting SaaS.
date_created: 2026-05-19
date_modified: 2026-05-19
authors:
- Michael Staton
augmented_with:
- Claude Opus 4.7
semantic_version: 0.0.0.2
tags:
- Self-Hosting-Cloud
- Self-Hosted-Alternatives
- Pseudomonorepo
- VC-Tech-Stack
- Exploration
status: In-Review
related:
- '[[A logic behind Self-Hosted VC Stacks]]'
- '[[pseudomonorepos]]'
- '[[study-repos-first]]'
site_uuid: fadf61ca-e0cc-4279-884f-b4722bd89928
hex_code: g1c06k
date_authored_initial_draft: 2026-05-19
date_authored_current_draft: 2026-05-19
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: explorations/VC-Self-Host-Stack-as-Pseudomonorepo.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/explorations/VC-Self-Host-Stack-as-Pseudomonorepo.md"
---

# VC Self-Host Stack as a Pseudomonorepo (and a Paired Study)

## The question

Two dirs sit at the root of `lossless-monorepo/` that should not be there:

- `twenty-crm/` — a fork/clone of [TwentyCRM](https://github.com/twentyhq/twenty), the open-source Affinity alternative
- `twenty-deployment/` — three thin shell + Dockerfile artifacts for shipping the above to Railway

They're clutter under our ongoing "tidy the root" sweep, but they're not *just* clutter. They're the first two pieces of a real thesis we've already articulated in [[A logic behind Self-Hosted VC Stacks]]: that a VC firm can replace **$85k–$280k/yr of SaaS spend** with a self-hosted open-source stack (TwentyCRM, Papermark, Cal.com, Mattermost, Jitsi, Metabase, NocoDB, BookStack, …) for the cost of a VPS and some DevOps attention.

So the question is two-layered:

1. **Where does this stack live in our tree?** A new child pseudomonorepo (e.g. `self-host-stack/` → eventually remote `vc-self-host-stack`)? A subdir of an existing child? Something else?
2. **How do we actually serve clients from it?** A study of pinned upstreams is research; a deploy-per-client product is a business. What's the shape of the thing that turns one into the other?

## Why we don't already know

- We've never run the "deploy an OSS stack for a client" play end-to-end. The Twenty/Railway artifacts were a half-step toward FullStackVC / Avalanche / Hypernova / Banner / Reach / Big Idea Ventures (per the `for_clients:` list in the logic doc) but **no client actually used it**. So we have a thesis and a stub, but no proof.
- We don't yet know whether the "stack" is: (a) one mega-repo with N submodules of upstream OSS, (b) a thin orchestration layer (Docker Compose / Terraform / Railway templates) that *references* upstream OSS without vendoring it, or (c) per-client repos forked from a template. Each has very different implications for maintenance, customization, and how we charge.
- The relationship between the **stack** (the thing we ship) and the **study** (the thing we learn from) is not yet drawn. Per [[study-repos-first]], we should be pinning the upstreams as a study *before* designing the stack — and `studies/content-driven-website-engines/` is the existing precedent for what that looks like (a `README.md` plus submodule subdirs of upstream repos).
- "Serve clients" is doing a lot of work. Are we (i) selling a managed deploy (we host, they pay monthly), (ii) selling a one-time setup engagement (we deploy on their infra, hand off), (iii) selling a template + advisory (they deploy, we consult), or (iv) something Lossless-flavored we haven't named? The right repo shape depends on this answer.

## What we already have

- `twenty-crm/` at root — TwentyCRM with our Railway-flavored `Dockerfile.railway`, `railway.toml`, `render.yaml`, `deploy-railway.sh`. Possibly a stale fork; possibly a clean clone with our deploy artifacts layered on. Worth confirming before we move it.
- `twenty-deployment/` at root — three files: `deploy-railway.sh`, `deploy.sh`, `Dockerfile`. Almost certainly belongs *inside* whatever wraps `twenty-crm/`, not as a sibling.
- [[A logic behind Self-Hosted VC Stacks]] in `~/content-md/lossless/` — the articulated thesis with vendor-by-vendor pricing, recommended OSS alternatives, and savings math. This is the marketing/why doc that any new pseudomonorepo should point to (and that a splash page would render).
- `studies/content-driven-website-engines/` — the existing precedent for what a "study" looks like in this tree. A `README.md`, a domain framing (`astro-big-doc`, `content-structure`, `galaxy`, `mdbook`), and presumably submodule pins.
- No prior `self-host-stack/` directory, no `studies/vc-self-host-stack/` directory. Greenfield.

## Options

### Option A — `self-host-stack/` as a new child pseudomonorepo

Create a new top-level child (peer to `ai-labs/`, `astro-knots/`, `content-farm/`, `tidyverse/`) called `self-host-stack/`. Inside, each tool gets its own subdir (`twenty/`, `papermark/`, `cal/`, `mattermost/`, …) containing **our deploy wrappers** (Dockerfile, compose file, Railway/Fly template, env example), not the upstream source itself. Upstream source lives in a paired study.

**Pros:**
- Matches the existing pseudomonorepo grain — agents already know how to navigate `<root>/<child>/<leaf>` and load `context-v/` at each level.
- Clear separation: this child is "things we deploy"; the study is "things we read."
- Eventually splits cleanly to a remote `vc-self-host-stack` when the surface stabilizes.

**Cons:**
- Premature naming risk: "self-host-stack" might be too generic; "vc-self-host-stack" is more honest about the audience but locks us out of, say, a YC-accelerator variant later.
- We don't yet know if `twenty/` etc. should be subdirs or submodules — if we hand-roll deploys we want subdirs, if we ever want to track upstream Twenty for our customizations we want submodules.

### Option B — `ai-labs/vc-self-host-stack/` as a grandchild

Nest it under `ai-labs/` since the eventual differentiator is the AI/MCP layer wrapping the OSS tools (Twenty's MCP integration is already called out in the logic doc).

**Pros:**
- Honest about where the moat is — the OSS stack alone is commoditized; the AI orchestration on top is the Lossless angle.
- Co-locates with `dididecks-ai/` and other client-facing AI work.

**Cons:**
- Two levels deep before you reach the actual deploy artifacts, which makes the `for_clients:` mapping less discoverable.
- Implies AI is required to use the stack, which isn't true.

### Option C — Thin orchestration only, no vendoring

Don't keep `twenty-crm/` at all. Replace it with a tiny `self-host-stack/twenty/` containing only the Dockerfile, compose snippet, and Railway/Fly template that *pulls the official Twenty Docker image*. Same for every other tool. The "stack" becomes a directory of recipes, not a directory of forks.

**Pros:**
- Massively less to maintain. No fork drift. No CVE patching on our side.
- The repo stays small and reviewable. A new client deployment is "pick from menu, fill env, deploy."
- Forces us to confront customization questions upfront — if a client needs a Twenty patch, that's a separate conversation with a clear cost.

**Cons:**
- We lose the ability to ship Lossless-flavored modifications quickly (the Railway-specific Dockerfile in `twenty-crm/` suggests we already wanted some).
- Some tools may not ship clean upstream images.

### Option D — Per-client repos forked from a template

The pseudomonorepo holds a **template** (`self-host-stack/template/`). Each client gets their own remote repo (`fullstackvc-stack`, `avalanche-stack`, etc.) forked from it. Customizations, secrets, infra choices live in the per-client repo.

**Pros:**
- Cleanest "serve clients" answer — each client owns their deploy, we own the template.
- Aligns with how splash pages work (per-repo splash deployed independently).
- Lets us bill setup once and advisory/maintenance ongoing without owning the runtime.

**Cons:**
- Template-and-fork patterns require real discipline to keep the upstream template alive after the first few forks diverge.
- Doesn't tell us where the template itself should live in our tree.

## The paired study question

Per [[study-repos-first]], before we design any of A–D we should pin the actual upstream repos and read them. A new entry under `studies/`:

```
studies/
  vc-self-host-stack/
    README.md                # domain framing, why these tools, what we're learning
    twenty/                  # submodule → twentyhq/twenty
    papermark/               # submodule → mfts/papermark
    cal-com/                 # submodule → calcom/cal.com
    mattermost/              # submodule → mattermost/mattermost
    jitsi-meet/              # submodule → jitsi/jitsi-meet
    metabase/                # submodule → metabase/metabase
    nocodb/                  # submodule → nocodb/nocodb
    bookstack/               # submodule → BookStackApp/BookStack
    ...
```

This is the "read the code, don't paraphrase from training data" half. The deploy-stack pseudomonorepo (whichever of A–D wins) is the "build the thing" half. They cross-reference: each tool's subdir in the deploy stack links to its pinned upstream in the study.

The logic doc (`A logic behind Self-Hosted VC Stacks`) ends up living in three places by reference: as a content-side `.md` in `content/lossless/`, as the `README.md` of the study (or the deploy stack, or both), and as the prose body of the deploy stack's splash page when we build one.

## Decision (2026-05-19)

**Option A wins, with an internal/external naming split and a `core/` + `studies/` shape inside.**

- Local directory name in this tree: **`self-host-stack/`** (peer to `ai-labs/`, `astro-knots/`, `content-farm/`, `tidyverse/`).
- Remote on GitHub under `lossless-group/`: **`vc-self-host-stack`** — for SEO and customer-facing clarity, since the audience really is VC firms.
- Two subdirs inside, both **just folders that hold submodules added from the monorepo root**:
  - **`core/`** — the tools we've chosen to actually deploy and stand behind (initial set: Twenty, Papermark, Cal.com, Mattermost, Metabase — TBD).
  - **`studies/`** — areas where we explored alternatives but didn't commit (e.g., BookStack vs. Outline vs. Wiki.js for the knowledge-base slot; Jitsi vs. BigBlueButton for the video slot).
- Submodules are added **from the monorepo root** (not from inside `self-host-stack/`) so the parent's `.gitmodules` records them and the [[pseudomonorepos]] branch-alignment / fetch / status rules apply uniformly.

This collapses the earlier "is the study a sibling of the stack or part of it?" question — the study lives **inside** the stack as the `studies/` subdir. The `core/` vs `studies/` split is the same shape as "chosen prior art" vs "considered prior art." One repo, two clear roles.

The earlier "Option C no-vendor discipline" still applies inside `core/`: each entry there should ideally be a thin deploy wrapper (Dockerfile, compose snippet, Railway/Fly template, env example) referencing the upstream image, **not** a fork of the upstream. The submodule under `core/twenty/` therefore points at our deploy-wrapper repo, not at `twentyhq/twenty` itself. Upstream `twentyhq/twenty` belongs under `studies/twenty/` (or wherever we keep the read-only pin).

## Tentative direction (superseded — see Decision above)

Leaning toward **Option A + a paired study**, with **Option C's no-vendor discipline** applied inside it:

1. **Now (this session, if approved):** Stop calling these orphan root dirs. Either delete `twenty-crm/` and `twenty-deployment/` (the Railway deploy was never used, no client was served, nothing of value is in there beyond the deploy scripts which are 30 lines total) — or move them under `self-host-stack/twenty/` as historical artifacts and gitignore them out of the active surface.
2. **Soon:** Scaffold `studies/vc-self-host-stack/` with `README.md` pointing to the logic doc, and pin the first 3–5 upstream repos as submodules (Twenty, Papermark, Cal.com, Mattermost, Metabase).
3. **Soon:** Scaffold `self-host-stack/` as a new child pseudomonorepo with its own `context-v/` and `changelog/`, holding only deploy recipes (Option C discipline). Cross-link to the study.
4. **Later, with a real client:** Try Option D — fork the deploy stack into `<client>-stack` and run a real engagement end-to-end. Only then do we know if the "serve clients" answer is managed-deploy, setup-engagement, or template+advisory.

The "how do we serve clients" question is **deliberately deferred** to step 4 because we don't have the data to answer it without a live engagement, and over-designing the repo around an unvalidated business model is exactly the trap.

## Open questions for the user

- Confirm `twenty-crm/` and `twenty-deployment/` contain nothing worth preserving (the Railway scripts can be re-derived in 20 min). If yes → straight delete is cleanest.
- Is "self-host-stack" or "vc-self-host-stack" the right name? The audience is specifically VC, but the pattern generalizes to any small professional-services firm. Naming locks the audience.
- Do we want the study and the deploy stack to be **siblings** in this tree, or should one be remote from the start? Studies have stayed local (`studies/` is gitignored or just unpushed in some tree configurations); deploy stacks probably want a remote sooner.
- The logic doc lives in `~/content-md/lossless/` — should a copy live in the new pseudomonorepo's root as `README.md`, or should it stay canonical in content-md and be referenced via wikilink only?

## Decision log

- 2026-05-19 — exploration opened.
- 2026-05-19 — **Option A chosen.** Local `self-host-stack/`, remote `lossless-group/vc-self-host-stack`. Inside: `core/` (chosen tools) + `studies/` (alternatives explored). Both are plain dirs holding submodules added from the monorepo root. Open questions about the logic doc's canonical location and the fate of `twenty-crm/` / `twenty-deployment/` still pending.
